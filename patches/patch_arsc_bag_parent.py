"""改二进制 `resources.arsc` 里某个 style bag 的 parent（只改 4 字节）。

`com.huawei.vrservice` 是用 `apktool d -r` 解的（资源表有重复项，不带 -r 解不出来），
所以它的 `res/` 里没有 `values/styles.xml` 可改，父级只在二进制资源表里。
实测 `apktool b` 会把解码树里的 `resources.arsc` 原样写进包（比对过 sha256），
所以在树上改这一张表就能进包。

只处理 style bag 的 parent 字段，其它一个字节不动：

    ResTable_type(0x0201).offsets[entry] -> ResTable_map_entry.parent(u32)

用法：

    python patches/patch_arsc_bag_parent.py [仓库根]

脚本自己会先把表里所有「父级指向 0x02xxxxxx（EMUI 的 androidhwext 包）」的
bag 打出来，改完再扫一遍确认一个不剩。
"""

import struct
import sys
from pathlib import Path

RES_TABLE = 0x0002
RES_TABLE_PACKAGE = 0x0200
RES_TABLE_TYPE = 0x0201
RES_TABLE_TYPE_SPEC = 0x0202

FLAG_COMPLEX = 0x0001
FLAG_SPARSE = 0x0001
NO_ENTRY = 0xFFFFFFFF

ANDROIDHWEXT = 0x02

# 模块 -> [(type_id, entry_id, 期望的旧父级, 新父级), ...]
#   0x7f0a000c style/Theme_NoTitle：原父级 androidhwext:style/Theme.Emui.Dark
#   换成 @android:style/Theme.Holo.NoActionBar（0x0103006c），与另外三个包一致。
FIXES = {
    "com.huawei.vrservice": [
        (0x0A, 0x0C, 0x020600CD, 0x0103006C),
    ],
}


def u16(buf, off):
    return struct.unpack_from("<H", buf, off)[0]


def u32(buf, off):
    return struct.unpack_from("<I", buf, off)[0]


def iter_chunks(buf, start, end):
    pos = start
    while pos + 8 <= end:
        ctype = u16(buf, pos)
        hsize = u16(buf, pos + 2)
        size = u32(buf, pos + 4)
        if size < 8 or pos + size > end:
            return
        yield pos, ctype, hsize, size
        pos += size


def type_chunks(buf):
    """产出 (包 id, type chunk 起点, type id, flags, entryCount, entriesStart, headerSize)。"""
    for tpos, ttype, thsize, tsize in iter_chunks(buf, 0, len(buf)):
        if ttype != RES_TABLE:
            continue
        for ppos, ptype, phsize, psize in iter_chunks(buf, tpos + thsize, tpos + tsize):
            if ptype != RES_TABLE_PACKAGE:
                continue
            package_id = u32(buf, ppos + 8)
            for cpos, ctype, chsize, csize in iter_chunks(buf, ppos + phsize, ppos + psize):
                if ctype != RES_TABLE_TYPE:
                    continue
                yield (package_id, cpos, buf[cpos + 8], buf[cpos + 9],
                       u32(buf, cpos + 12), u32(buf, cpos + 16), chsize)


def entry_offset(buf, cpos, flags, entry_count, entries_start, header_size, entry_id):
    """返回该 entry 在 type chunk 里的相对偏移，没有则 None。"""
    offs = cpos + header_size
    if flags & FLAG_SPARSE:
        for i in range(entry_count):
            idx = u16(buf, offs + i * 4)
            if idx == entry_id:
                off = u16(buf, offs + i * 4 + 2)
                return None if off == NO_ENTRY else entries_start + off
        return None
    if entry_id >= entry_count:
        return None
    off = u32(buf, offs + entry_id * 4)
    return None if off == NO_ENTRY else entries_start + off


def bags(buf):
    """产出 (包 id, type id, entry id, parent 字段的文件偏移, 当前 parent 值)。"""
    for package_id, cpos, type_id, flags, count, start, hsize in type_chunks(buf):
        if flags & FLAG_SPARSE:
            ids = [u16(buf, cpos + hsize + i * 4) for i in range(count)]
        else:
            ids = range(count)
        for entry_id in ids:
            off = entry_offset(buf, cpos, flags, count, start, hsize, entry_id)
            if off is None:
                continue
            epos = cpos + off
            eflags = u16(buf, epos + 2)
            if not eflags & FLAG_COMPLEX or eflags & 0x0008:  # 只认普通 bag
                continue
            yield package_id, type_id, entry_id, epos + 8, u32(buf, epos + 8)


def scan(buf, label):
    bad = [(p, t, e, v) for p, t, e, _o, v in bags(buf) if (v >> 24) == ANDROIDHWEXT]
    for p, t, e, v in bad:
        print("     %s 父级 0x%08x -> 0x%02x%02x%04x" % (label, v, p, t, e))
    return bad


def main(root):
    for module, fixes in FIXES.items():
        path = Path(root) / "decode" / module / "resources.arsc"
        buf = bytearray(path.read_bytes())
        print("%s：改前指向 androidhwext 的 bag" % module)
        scan(buf, "命中")
        for type_id, entry_id, old, new in fixes:
            hits = [(o, v) for p, t, e, o, v in bags(buf)
                    if t == type_id and e == entry_id]
            if not hits:
                raise SystemExit("%s: 找不到 type=0x%02x entry=0x%04x"
                                 % (module, type_id, entry_id))
            for off, value in hits:
                if value == new:
                    print("     type=0x%02x entry=0x%04x 已是 0x%08x，跳过"
                          % (type_id, entry_id, new))
                    continue
                if value != old:
                    raise SystemExit("%s: type=0x%02x entry=0x%04x 的父级是 0x%08x，"
                                     "不是预期的 0x%08x"
                                     % (module, type_id, entry_id, value, old))
                struct.pack_into("<I", buf, off, new)
                print("     type=0x%02x entry=0x%04x 0x%08x -> 0x%08x"
                      % (type_id, entry_id, old, new))
        left = scan(buf, "残留")
        if left:
            raise SystemExit("%s: 还有指向 androidhwext 的 bag，先补 FIXES" % module)
        path.write_bytes(bytes(buf))
        print("     已写回 %s" % path)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parents[1]))
