"""Print the DT_NEEDED closure of native libraries inside an APK.

Used to decide which shared objects a package has to carry: the original handle
app loads libvrpose.so / libWalleDev.so / libWalleAlg.so / libMobileSensor.so
from the Runtime package's native library directory, and a missing transitive
dependency makes the dlopen fail (the static initialiser catches it, so the only
symptom is later UnsatisfiedLinkError on the JNI call).

    python tools/so-deps.py 原包/com.huawei.hvrsdkserverapp.apk libvrpose.so
"""
import struct
import sys
import zipfile

DT_NULL = 0
DT_NEEDED = 1
PT_DYNAMIC = 2


def needed(data):
    if data[:4] != b"\x7fELF":
        return []
    is64 = data[4] == 2
    if is64:
        e_phoff, = struct.unpack_from("<Q", data, 0x20)
        e_phentsize, e_phnum = struct.unpack_from("<HH", data, 0x36)
    else:
        e_phoff, = struct.unpack_from("<I", data, 0x1C)
        e_phentsize, e_phnum = struct.unpack_from("<HH", data, 0x2A)
    dynamic = None
    dynamic_size = 0
    for index in range(e_phnum):
        offset = e_phoff + index * e_phentsize
        if is64:
            p_type, = struct.unpack_from("<I", data, offset)
            p_offset, = struct.unpack_from("<Q", data, offset + 8)
            p_filesz, = struct.unpack_from("<Q", data, offset + 32)
        else:
            p_type, p_offset, _, _, p_filesz = struct.unpack_from("<IIIII", data,
                                                                  offset)
        if p_type == PT_DYNAMIC:
            dynamic, dynamic_size = p_offset, p_filesz
            break
    if dynamic is None:
        return []
    # First pass: locate the string table (DT_STRTAB).
    entries = []
    strtab = None
    step = 16 if is64 else 8
    fmt = "<qQ" if is64 else "<iI"
    for offset in range(dynamic, dynamic + dynamic_size, step):
        tag, value = struct.unpack_from(fmt, data, offset)
        if tag == DT_NULL:
            break
        if tag == 5:  # DT_STRTAB
            strtab = value
        entries.append((tag, value))
    if strtab is None:
        return []
    names = []
    for tag, value in entries:
        if tag != DT_NEEDED:
            continue
        start = strtab + value
        end = data.index(b"\x00", start)
        names.append(data[start:end].decode("ascii", "replace"))
    return names


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    apk, wanted = sys.argv[1], sys.argv[2:]
    with zipfile.ZipFile(apk) as archive:
        available = {}
        for name in archive.namelist():
            if name.startswith("lib/") and name.endswith(".so"):
                available.setdefault(name.split("/")[-1], []).append(name)
        seen = set()
        queue = list(wanted)
        while queue:
            current = queue.pop()
            if current in seen:
                continue
            seen.add(current)
            entries = available.get(current)
            if not entries:
                print("  MISSING  %s (not shipped in %s)" % (current, apk))
                continue
            for entry in entries:
                deps = needed(archive.read(entry))
                print("  %-34s -> %s" % (entry, ", ".join(deps) if deps else "(none)"))
                queue.extend(deps)
    return 0


if __name__ == "__main__":
    sys.exit(main())
