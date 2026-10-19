"""扫描 `resources.arsc` 里所有指向 EMUI 扩展包（资源包 id `0x02`）的引用。

看的是三类地方，都是「通用安卓上解析不了」的：

  1. `ResTable_map_entry.parent`  —— style/array 的父级（style 继承链）
  2. `ResTable_map.name`          —— bag 条目的键（也就是属性 id）
  3. 普通 entry 的 `Res_value`    —— 值本身，类型 0x01(@ref)/0x02(?attr)/
                                     0x07(@dynref)/0x08(?dynattr)

用法：python tools/arsc-ref-scan.py [仓库根]
"""

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "patches"))
from patch_arsc_bag_parent import (  # noqa: E402
    RES_TABLE, RES_TABLE_PACKAGE, RES_TABLE_TYPE, FLAG_COMPLEX, FLAG_SPARSE,
    NO_ENTRY, iter_chunks, type_chunks, u16, u32)

HWEXT = 0x02
VALUE_TYPES = {0x01: "@ref", 0x02: "?attr", 0x07: "@dynref", 0x08: "?dynattr"}


def entry_offset(buf, cpos, flags, entry_count, entries_start, header_size, entry_id):
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


def scan(path):
    buf = path.read_bytes()
    hits = []
    for package_id, cpos, type_id, flags, count, start, hsize in type_chunks(buf):
        ids = ([u16(buf, cpos + hsize + i * 4) for i in range(count)]
               if flags & FLAG_SPARSE else range(count))
        for entry_id in ids:
            off = entry_offset(buf, cpos, flags, count, start, hsize, entry_id)
            if off is None:
                continue
            epos = cpos + off
            eflags = u16(buf, epos + 2)
            where = f"type=0x{type_id:02x} entry=0x{entry_id:04x}"
            if eflags & FLAG_COMPLEX and not eflags & 0x0008:
                parent = u32(buf, epos + 8)
                if (parent >> 24) == HWEXT:
                    hits.append(f"{where} parent=0x{parent:08x}")
                map_count = u32(buf, epos + 12)
                for i in range(map_count):
                    mpos = epos + 16 + i * 12
                    name = u32(buf, mpos)
                    vtype = buf[mpos + 8 + 3]
                    vdata = u32(buf, mpos + 8 + 4)
                    if (name >> 24) == HWEXT:
                        hits.append(f"{where} key=0x{name:08x}"
                                    f"({VALUE_TYPES.get(vtype, hex(vtype))}"
                                    f"0x{vdata:08x})")
                    elif vtype in VALUE_TYPES and (vdata >> 24) == HWEXT:
                        hits.append(f"{where} value={VALUE_TYPES[vtype]}"
                                    f"0x{vdata:08x}")
            elif not eflags & FLAG_COMPLEX:
                vtype = buf[epos + 8 + 3]
                vdata = u32(buf, epos + 8 + 4)
                if vtype in VALUE_TYPES and (vdata >> 24) == HWEXT:
                    hits.append(f"{where} value={VALUE_TYPES[vtype]}0x{vdata:08x}")
    return hits


def main():
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
    total = 0
    for tree in sorted((root / "decode").iterdir()):
        arsc = tree / "resources.arsc"
        if not arsc.is_file():
            continue
        hits = scan(arsc)
        total += len(hits)
        print(f"== {tree.name}: {len(hits)} 处")
        for hit in hits[:40]:
            print(f"   {hit}")
        if len(hits) > 40:
            print(f"   …还有 {len(hits) - 40} 处")
    print(f"合计 {total} 处指向 androidhwext（0x02）的引用")


if __name__ == "__main__":
    main()
