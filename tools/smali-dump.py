"""Print one or more methods from a decoded smali file.

    python tools/smali-dump.py <file.smali> <method name> [<method name> ...]

Comments and blank `.line` directives are dropped so the output is readable.
"""
import re
import sys


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    path, names = sys.argv[1], sys.argv[2:]
    with open(path, encoding="utf-8", errors="ignore") as handle:
        text = handle.read()
    for name in names:
        pattern = re.compile(r"\.method [^\n]*\b%s\([^\n]*\n.*?\n\.end method"
                             % re.escape(name), re.S)
        found = pattern.search(text)
        if not found:
            print("=== %s: not found" % name)
            continue
        print("=== %s" % name)
        for line in found.group(0).splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith(".line"):
                continue
            print(line)
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
