"""扫描二进制 AXML 里指向 EMUI 扩展资源包（0x02）的引用。

用法：python tools/axml-ref-scan.py <目录或文件> [<目录或文件> ...]
"""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "patches"))
from axml_edit import BinaryXml, RES_XML_START_ELEMENT_TYPE  # noqa: E402

KINDS = {0x01: "@ref", 0x02: "?attr", 0x07: "@dynref", 0x08: "?dynattr"}


def scan(path):
    data = path.read_bytes()
    if len(data) < 8 or struct.unpack_from("<H", data, 0)[0] != 0x0003:
        return []
    xml = BinaryXml(data)
    hits = []
    for ctype, payload in xml.entries:
        if ctype != RES_XML_START_ELEMENT_TYPE:
            continue
        element = xml.pool.strings[payload.name_index]
        for (ns, aname, raw, size, res0, dtype, value) in payload.attributes:
            if dtype in KINDS and (value >> 24) == 0x02:
                hits.append((element, xml.pool.strings[aname], KINDS[dtype],
                             value, payload.line_number))
    return hits


def main():
    total = 0
    for target in sys.argv[1:]:
        root = Path(target)
        files = [root] if root.is_file() else [p for p in root.rglob("*") if p.is_file()]
        for path in files:
            for element, name, kind, value, line in scan(path):
                total += 1
                print(f"{path}|{line}|{element}|{name}={kind}0x{value:08x}")
    print(f"total={total}")


main()
