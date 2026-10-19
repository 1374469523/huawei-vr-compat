#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
erofs-extract.py —— 纯 Python 的 EROFS 只读提取器（含 LZ4 解压）

为什么需要它：EMUI 10/11 的 system / hw_product 等分区是 EROFS + LZ4，
Windows 上的 7-Zip 不支持 EROFS，无法直接取出固件里的 APK。

支持：
  - 数据布局 FLAT_PLAIN(0) / FLAT_INLINE(2)
  - 数据布局 COMPRESSED_FULL(1) / COMPRESSED_COMPACT(3)，算法 LZ4
    （含 EROFS 的 "0padding" 语义：每个物理簇的数据前导零补齐要先跳过）
  - 紧凑索引的 4B / 2B 两种打包
依赖：无（LZ4 块解码自带实现，不依赖 python-lz4）

用法：
  python erofs-extract.py list    <image.img> [目录]
  python erofs-extract.py extract <image.img> <镜像内路径> <输出文件>
  python erofs-extract.py find    <image.img> <关键字>

本实现按 Linux fs/erofs 的 on-disk 结构编写，关键常量：
  erofs_super_block 128B @0x400, erofs_inode_compact 32B, erofs_inode_extended 64B,
  erofs_dirent 12B, z_erofs_map_header 8B, z_erofs_lcluster_index 8B,
  Z_EROFS_FULL_INDEX_ALIGN(end) = ALIGN(end,8) + 8 + 8
"""
import mmap
import struct
import sys
import os

# ---------------------------------------------------------------- 基础结构
FT_DIR = 2
S_IFMT = 0o170000
S_IFDIR = 0o040000

TYPE_PLAIN, TYPE_HEAD1, TYPE_NONHEAD, TYPE_HEAD2 = 0, 1, 2, 3
ADV_COMPACTED_2B = 0x0001
ADV_BIG_PCLUSTER_1 = 0x0002
ADV_BIG_PCLUSTER_2 = 0x0004
LI_D0_CBLKCNT = 1 << 11

ALG = {0: 'lz4', 1: 'lzma', 2: 'deflate'}


def lz4_decompress(src, out_size):
    """LZ4 块解码。src 可以带尾部补零；输出固定为 out_size 字节。"""
    out = bytearray()
    ip, n = 0, len(src)
    while len(out) < out_size:
        if ip >= n:
            break
        token = src[ip]; ip += 1
        lit = token >> 4
        if lit == 15:
            while True:
                b = src[ip]; ip += 1
                lit += b
                if b != 255:
                    break
        if lit:
            out += src[ip:ip + lit]; ip += lit
        if len(out) >= out_size:
            break
        if ip + 2 > n:
            break
        offset = src[ip] | (src[ip + 1] << 8); ip += 2
        if offset == 0:
            break
        mlen = token & 15
        if mlen == 15:
            while True:
                b = src[ip]; ip += 1
                mlen += b
                if b != 255:
                    break
        mlen += 4
        start = len(out) - offset
        if start < 0:
            raise ValueError('LZ4 偏移越界')
        for k in range(mlen):
            out.append(out[start + k])
    if len(out) < out_size:
        out += bytes(out_size - len(out))
    return bytes(out[:out_size])


class Erofs:
    def __init__(self, path):
        self.f = open(path, 'rb')
        self.mm = mmap.mmap(self.f.fileno(), 0, access=mmap.ACCESS_READ)
        SB = 1024
        (self.magic, _csum, self.feat_compat, self.blkszbits,
         self.sb_extslots, self.root_nid) = struct.unpack_from('<IIIBBH', self.mm, SB)
        if self.magic != 0xE0F5E1E2:
            raise ValueError('不是 EROFS 镜像（magic=0x%x）' % self.magic)
        (self.blocks, self.meta_blkaddr, self.xattr_blkaddr) = struct.unpack_from('<III', self.mm, SB + 36)
        self.feat_incompat, = struct.unpack_from('<I', self.mm, SB + 80)
        self.BLK = 1 << self.blkszbits
        self.META = self.meta_blkaddr << self.blkszbits

    def close(self):
        self.mm.close()
        self.f.close()

    def iloc(self, nid):
        return self.META + (nid << 5)

    def read_inode(self, nid):
        off = self.iloc(nid)
        fmt, xic = struct.unpack_from('<HH', self.mm, off)
        version = fmt & 1
        dl = (fmt >> 1) & 7
        if version == 0:
            mode, nlink, size, _res = struct.unpack_from('<HHII', self.mm, off + 4)
            iu, = struct.unpack_from('<I', self.mm, off + 16)
            isz = 32
        else:
            mode, _res = struct.unpack_from('<HH', self.mm, off + 4)
            size, = struct.unpack_from('<Q', self.mm, off + 8)
            iu, = struct.unpack_from('<I', self.mm, off + 16)
            isz = 64
        xsz = 0 if xic == 0 else 12 + 4 * (xic - 1)
        return dict(nid=nid, version=version, dl=dl, mode=mode, size=size,
                    iu=iu, isize=isz, xsize=xsz, iloc=off)

    def data_start(self, i):
        if i['dl'] == 0:
            return i['iu'] * self.BLK
        if i['dl'] == 2:
            return self.iloc(i['nid']) + i['isize'] + i['xsize']
        return None

    def flat_inline_head(self, i):
        """FLAT_INLINE(dl=2) 的头部整块长度与内联尾块起点。

        EROFS 的 FLAT_INLINE 并不是「整个文件都内联在 inode 后面」：
        前 `size // BLK` 个整块仍然在 i_u 指向的位置，只有不足一块的**尾部**
        内联在 inode 元数据之后。以前按「全部内联」读，`/system/framework`
        这种超过一块的目录就只读到尾巴，开头几十个文件凭空消失。
        """
        BLK = self.BLK
        head = i['size'] // BLK * BLK
        tail_off = self.iloc(i['nid']) + i['isize'] + i['xsize']
        return head, tail_off

    def inode_bytes(self, i):
        """按逻辑顺序取出 inode 的内容（只处理未压缩的两种布局）。"""
        mm = self.mm
        if i['dl'] == 0:
            return bytes(mm[i['iu'] * self.BLK: i['iu'] * self.BLK + i['size']])
        if i['dl'] == 2:
            head, tail_off = self.flat_inline_head(i)
            data = b'' if head == 0 else bytes(mm[i['iu'] * self.BLK: i['iu'] * self.BLK + head])
            return data + bytes(mm[tail_off: tail_off + i['size'] - head])
        return None

    def list_dir(self, i):
        mm, BLK = self.inode_bytes(i), self.BLK
        if mm is None:
            # 压缩目录少见；用通用的 read_file 兜底。
            try:
                mm = self.read_file(i['nid'])
            except Exception:
                return []
        ents = []
        nb = (i['size'] + BLK - 1) // BLK
        for b in range(nb):
            base = b * BLK
            if base + 12 > len(mm):
                break
            nid0, nameoff0 = struct.unpack_from('<QH', mm, base)
            if nid0 == 0 and nameoff0 == 0:
                continue
            if nameoff0 == 0 or nameoff0 % 12 or nameoff0 > BLK:
                continue
            n = nameoff0 // 12
            if n <= 0 or n * 12 > BLK:
                continue
            arr, bad = [], False
            for k in range(n):
                p = base + k * 12
                nid, nameoff = struct.unpack_from('<QH', mm, p)
                if nid == 0 or nameoff >= BLK or nameoff < n * 12:
                    bad = True
                    break
                arr.append((nid, nameoff, mm[p + 10]))
            if bad:
                continue
            for k, (nid, nameoff, ft) in enumerate(arr):
                end = arr[k + 1][1] if k + 1 < n else BLK
                nm = mm[base + nameoff: base + end].split(b'\x00')[0]
                try:
                    nms = nm.decode('utf-8')
                except Exception:
                    continue
                if not nms or any(ord(c) < 32 for c in nms):
                    continue
                ents.append((nms, nid, ft))
        return ents

    def lookup(self, path):
        nid = self.root_nid
        for part in [p for p in path.split('/') if p]:
            hit = None
            for nm, cnid, ft in self.list_dir(self.read_inode(nid)):
                if nm == part:
                    hit = cnid
                    break
            if hit is None:
                return None
            nid = hit
        return nid

    # ---------------------------------------------------------- 压缩索引
    def _decode_bits(self, pack_off, lclusterbits, lomask, bitpos):
        v = struct.unpack_from('<I', self.mm, pack_off + (bitpos // 8))[0] >> (bitpos & 7)
        return v & lomask, (v >> lclusterbits) & 3

    def _unpack_compact(self, pos, amortizedshift, advise, lclusterbits=12):
        BLK = self.BLK
        lomask = (1 << lclusterbits) - 1
        if (1 << amortizedshift) == 4 and lclusterbits <= 14:
            vcnt = 2
        elif (1 << amortizedshift) == 2 and lclusterbits == 12:
            vcnt = 16
        else:
            raise ValueError('不支持的紧凑索引打包')
        big = bool(advise & ADV_BIG_PCLUSTER_1)
        encodebits = ((vcnt << amortizedshift) - 4) * 8 // vcnt
        eofs = pos % BLK
        base = (eofs // (vcnt << amortizedshift)) * (vcnt << amortizedshift)
        pack_off = pos - (eofs - base)
        idx = (eofs - base) >> amortizedshift
        lo, t = self._decode_bits(pack_off, lclusterbits, lomask, encodebits * idx)
        rec = dict(type=t, clusterofs=0, pblk=0, compressedblks=0)
        if t == TYPE_NONHEAD:
            rec['clusterofs'] = 1 << lclusterbits
            if lo & LI_D0_CBLKCNT:
                rec['compressedblks'] = lo & ~LI_D0_CBLKCNT
                return rec
            if idx + 1 != vcnt:
                return rec
            lo2, t2 = self._decode_bits(pack_off, lclusterbits, lomask, encodebits * (idx - 1))
            if t2 != TYPE_NONHEAD:
                lo2 = 0
            elif lo2 & LI_D0_CBLKCNT:
                lo2 = 1
            rec['clusterofs'] = 1 << lclusterbits
            rec['delta0'] = lo2 + 1
            return rec
        rec['clusterofs'] = lo
        nblk, j = 0, idx
        if not big:
            nblk = 1
            while j > 0:
                j -= 1
                lo2, t2 = self._decode_bits(pack_off, lclusterbits, lomask, encodebits * j)
                if t2 == TYPE_NONHEAD:
                    j -= lo2
                if j >= 0:
                    nblk += 1
        else:
            while j > 0:
                j -= 1
                lo2, t2 = self._decode_bits(pack_off, lclusterbits, lomask, encodebits * j)
                if t2 == TYPE_NONHEAD:
                    if lo2 & LI_D0_CBLKCNT:
                        j -= 1
                        nblk += lo2 & ~LI_D0_CBLKCNT
                        continue
                    j -= lo2 - 2
                    continue
                nblk += 1
        rec['pblk'] = struct.unpack_from('<I', self.mm, pack_off + (vcnt << amortizedshift) - 4)[0] + nblk
        return rec

    def _load_compact(self, i, lcn, totalidx, ebase, advise):
        c4 = (32 - (ebase % 32)) // 4
        if c4 == 8:
            c4 = 0
        if (advise & ADV_COMPACTED_2B) and c4 < totalidx:
            c2 = ((totalidx - c4) // 16) * 16
        else:
            c2 = 0
        pos = ebase
        if lcn < c4:
            shift = 2
        else:
            pos += c4 * 4
            lcn -= c4
            if lcn < c2:
                shift = 1
            else:
                pos += c2 * 2
                lcn -= c2
                shift = 2
        pos += lcn * (1 << shift)
        return self._unpack_compact(pos, shift, advise)

    def _load_full(self, i, lcn, idx_base):
        pos = idx_base + lcn * 8
        advise, clusterofs, u = struct.unpack_from('<HHI', self.mm, pos)
        t = advise & 3
        rec = dict(type=t, clusterofs=0, pblk=0, compressedblks=0)
        if t == TYPE_NONHEAD:
            rec['clusterofs'] = 1 << 12
            d0, d1 = struct.unpack_from('<HH', self.mm, pos + 4)
            if d0 & LI_D0_CBLKCNT:
                rec['compressedblks'] = d0 & ~LI_D0_CBLKCNT
            rec['delta0'] = d0
            rec['delta1'] = d1
            return rec
        rec['clusterofs'] = clusterofs
        rec['pblk'] = u
        return rec

    # ---------------------------------------------------------------- 读文件
    def read_file(self, nid, verbose=False):
        i = self.read_inode(nid)
        mm, BLK = self.mm, self.BLK
        if i['dl'] in (0, 2):
            return self.inode_bytes(i)
        if i['dl'] not in (1, 3):
            raise ValueError('不支持的数据布局 dl=%d' % i['dl'])

        totalidx = (i['size'] + BLK - 1) // BLK
        hpos = (i['iloc'] + i['isize'] + i['xsize'] + 7) & ~7
        _fragoff, advise, algtype, clusterbits = struct.unpack_from('<IHBB', mm, hpos)
        lcb = 12 + (clusterbits & 7)
        alg1, alg2 = algtype & 15, algtype >> 4
        if alg1 not in (0, 3) and alg2 not in (0, 3):
            raise ValueError('本工具只实现 LZ4（alg=%s/%s）' % (ALG.get(alg1), ALG.get(alg2)))
        if i['dl'] == 1:
            idx_base = hpos + 8 + 8
            recs = [self._load_full(i, lcn, idx_base) for lcn in range(totalidx)]
        else:
            ebase = 8 + hpos
            recs = [self._load_compact(i, lcn, totalidx, ebase, advise) for lcn in range(totalidx)]

        out = bytearray(i['size'])
        for lcn, r in enumerate(recs):
            t = r['type']
            if t == TYPE_NONHEAD:
                continue
            la = (lcn << lcb) | r['clusterofs']
            if la >= i['size']:
                continue
            nxt = i['size']
            for l2 in range(lcn + 1, totalidx):
                if recs[l2]['type'] != TYPE_NONHEAD:
                    nl = (l2 << lcb) | recs[l2]['clusterofs']
                    if nl > la:
                        nxt = nl
                    break
            D = nxt - la
            if D <= 0:
                continue
            pblk = r['pblk']
            if t == TYPE_PLAIN:
                data = bytes(mm[pblk * BLK: pblk * BLK + D])
            else:
                blk = bytes(mm[pblk * BLK: (pblk + 1) * BLK])
                k = 0
                while k < len(blk) and blk[k] == 0:   # EROFS 0padding：跳过前导零
                    k += 1
                data = lz4_decompress(blk[k:], D)
            out[la:la + len(data)] = data
        return bytes(out)


# ---------------------------------------------------------------- CLI
def cmd_list(e, root):
    nid = e.lookup(root) if root else e.root_nid
    if nid is None:
        print('路径不存在:', root); return
    for nm, cnid, ft in e.list_dir(e.read_inode(nid)):
        if nm in ('.', '..'):
            continue
        if ft == FT_DIR:
            print('  [dir ] %s' % nm)
        else:
            info = e.read_inode(cnid)
            print('  [file] %-58s %9d  dl=%d' % (nm, info['size'], info['dl']))


def cmd_extract(e, path, out):
    nid = e.lookup(path)
    if nid is None:
        print('镜像内不存在:', path); return 1
    i = e.read_inode(nid)
    if (i['mode'] & S_IFMT) == S_IFDIR:
        print('这是一个目录:', path); return 1
    data = e.read_file(nid)
    d = os.path.dirname(os.path.abspath(out))
    if d:
        os.makedirs(d, exist_ok=True)
    open(out, 'wb').write(data)
    print('已导出 %s -> %s (%d 字节)' % (path, out, len(data)))
    return 0


def cmd_find(e, kw):
    kw = kw.lower()
    stack = [(e.root_nid, '')]
    seen = set()
    while stack:
        nid, path = stack.pop()
        if nid in seen:
            continue
        seen.add(nid)
        i = e.read_inode(nid)
        if (i['mode'] & S_IFMT) != S_IFDIR:
            continue
        for nm, cnid, ft in e.list_dir(i):
            if nm in ('.', '..'):
                continue
            p = path + '/' + nm
            if kw in p.lower():
                info = e.read_inode(cnid)
                kind = 'dir ' if ft == FT_DIR else 'file'
                print('  [%s] %-70s %9d dl=%d' % (kind, p, info['size'], info['dl']))
            if ft == FT_DIR:
                stack.append((cnid, p))


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    cmd, img = sys.argv[1], sys.argv[2]
    e = Erofs(img)
    try:
        if cmd == 'list':
            cmd_list(e, sys.argv[3] if len(sys.argv) > 3 else '')
        elif cmd == 'extract':
            return cmd_extract(e, sys.argv[3], sys.argv[4])
        elif cmd == 'find':
            cmd_find(e, sys.argv[3])
        else:
            print(__doc__)
            return 2
    finally:
        e.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
