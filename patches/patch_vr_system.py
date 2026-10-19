"""Route the original getSystemService("vr_system") lookups to the compat service.

EMUI registered a system service named "vr_system" in the framework. A common
Android device has no such name and an application cannot add one, so this is the
single system call site the port is allowed to touch: every occurrence is
replaced by a call to android.vrsystem.VRSystemServiceManagerImpl, which answers
the very same android.vrsystem.IVRSystemServiceManager interface.

Each module has an expected number of call sites; a mismatch means the decode
changed and the patch must be reviewed instead of silently doing nothing.
"""
import re
import sys
from pathlib import Path

EXPECTED = {
    "com.huawei.appmarket.vr": 2,
    "com.huawei.hvrsdkserverapp": 7,
    "com.huawei.vrlauncherx": 10,
}

# The desktop also *registers* a binder under the same name through
# com.huawei.android.os.ServiceManagerEx.addService. That is not a lookup and
# must stay untouched, but its count is asserted too so a decode change is loud.
EXPECTED_REGISTRATIONS = {
    "com.huawei.vrlauncherx": 1,
}

ADD_SERVICE = (r'^\s*invoke-static \{[^}]*\}, '
               r'Lcom/huawei/android/os/ServiceManagerEx;->addService')

CALL = ("invoke-static {{{context}}}, "
        "Landroid/vrsystem/VRSystemServiceManagerImpl;->"
        "get(Landroid/content/Context;)Landroid/vrsystem/VRSystemServiceManagerImpl;")


CONTEXT_CALL = (r'^\s*invoke-(\w+) \{([^}]*)\}, '
                r'Landroid/(?:content/Context|app/Activity|app/Service|'
                r'app/ContextImpl);->'
                r'getSystemService\(Ljava/lang/String;\)Ljava/lang/Object;\s*$')


def plan_file(path):
    """Return (new_text, replaced_count, registration_count) without writing."""
    # newline="" keeps the file's own CRLF/LF endings, so the diff of a patched
    # tree shows only the instructions that actually changed.
    with open(path, "r", encoding="utf-8", newline="") as handle:
        text = handle.read()
    lines = text.splitlines(keepends=True)
    eol = "\r\n" if lines and lines[0].endswith("\r\n") else "\n"
    out = []
    replaced = 0
    registrations = 0
    index = 0
    while index < len(lines):
        line = lines[index]
        match = re.match(r'^(\s*)const-string ([vp]\d+), "vr_system"\s*$', line)
        if match is None:
            out.append(line)
            index += 1
            continue
        indent, literal = match.group(1), match.group(2)
        # Find the getSystemService call that consumes exactly this register.
        lookup = None
        for probe in range(index + 1, min(index + 8, len(lines))):
            call = re.match(CONTEXT_CALL, lines[probe])
            if call is None:
                continue
            registers = [item.strip() for item in call.group(2).split(",")]
            if len(registers) == 2 and registers[1] == literal:
                lookup = (probe, registers[0])
                break
        if lookup is None:
            window = "".join(lines[index + 1:index + 9])
            if re.search(ADD_SERVICE, window, re.M):
                # A ServiceManagerEx.addService registration: keep it.
                out.append(line)
                index += 1
                registrations += 1
                continue
            raise SystemExit("unrecognised vr_system use at %s:%d"
                             % (path, index + 1))
        probe, context = lookup
        out.append(indent + CALL.format(context=context) + eol)
        out.extend(lines[index + 1:probe])
        index = probe + 1
        replaced += 1
    return "".join(out), replaced, registrations


def main(root):
    decode = Path(root) / "decode"
    planned = []
    for module, expected in EXPECTED.items():
        directory = decode / module
        if not directory.is_dir():
            raise SystemExit("missing decode tree: %s" % directory)
        count = 0
        registered = 0
        for smali in directory.rglob("*.smali"):
            text, replaced, regs = plan_file(smali)
            registered += regs
            if replaced:
                planned.append((smali, text))
                count += replaced
        if count != expected:
            raise SystemExit("%s: patched %d call sites, expected %d"
                             % (module, count, expected))
        expected_regs = EXPECTED_REGISTRATIONS.get(module, 0)
        if registered != expected_regs:
            raise SystemExit("%s: %d registrations, expected %d"
                             % (module, registered, expected_regs))
        print("%-32s lookups patched %d, registrations kept %d"
              % (module, count, registered))
    # Write only after every module matched its expected count.
    for path, text in planned:
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
    print("patched %d file(s)" % len(planned))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parents[1]))
