"""Replace the Huawei kernel device-node probe with a real hardware check.

The VR framework asks "are the glasses attached?" by testing for the node
Huawei's kernel driver creates:

    new-instance v0, Ljava/io/File;
    const-string v1, "/dev/hwvr1"
    invoke-direct {v0, v1}, Ljava/io/File;-><init>(Ljava/lang/String;)V
    invoke-virtual {v0}, Ljava/io/File;->exists()Z

in three methods of com.huawei.hvrsdkserverapp:

    VrSystemClient.isVRGlassExist()Z
    VrMonitor.isVRGlassDevExist()Z
    VrTouchService.isVRGlassExist()Z

No such node exists on a stock device, so the phone-controller path is skipped:

    W PhoneController: vr glass not exist, no need to bind service
    W VrControllerManager: bind VrTouchService failed

The bodies are rewritten to call com.huawei.vrframework.compat.VrPlatformCompat,
which answers the same question from the real external display and the 12d1:1092
USB gadget. Method names, signatures and every caller stay untouched; only the
probe implementation - the Huawei-specific part - is replaced.

The script asserts the original text, so a re-decode cannot silently produce a
half-patched tree.
"""
import re
import sys
from pathlib import Path

PACKAGE = "com.huawei.hvrsdkserverapp"
FRAMEWORK = Path("smali") / "com" / "huawei" / "vrframework"

REPLACEMENT_BODY = """    .locals 1

    invoke-static {}, Lcom/huawei/vrframework/compat/VrPlatformCompat;->isVrGlassPresent()Z

    move-result v0

    return v0
"""

TARGETS = {
    "VrSystemClient.smali": "isVRGlassExist",
    "VrMonitor.smali": "isVRGlassDevExist",
    "VrTouchService.smali": "isVRGlassExist",
}


def patch(path, method):
    with open(path, "r", encoding="utf-8", newline="") as handle:
        text = handle.read()
    eol = "\r\n" if "\r\n" in text else "\n"
    working = text.replace("\r\n", "\n")

    if "VrPlatformCompat;->isVrGlassPresent" in working:
        print("%s: already patched" % path.name)
        return

    block = re.search(r"(\.method [^\n]*\b%s\(\)Z\n)(.*?)(\n\.end method)"
                      % re.escape(method), working, re.S)
    if block is None:
        raise SystemExit("%s: %s()Z not found" % (path, method))
    if "/dev/hwvr1" not in block.group(2):
        raise SystemExit("%s: %s()Z does not contain the /dev/hwvr1 probe"
                         % (path, method))
    replacement = "%s%s%s" % (block.group(1), REPLACEMENT_BODY.rstrip("\n"),
                              block.group(3))
    working = working[:block.start()] + replacement + working[block.end():]

    if eol != "\n":
        working = working.replace("\n", eol)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(working)
    print("%s: %s() now probes the real hardware" % (path.name, method))


def main():
    repo = Path(__file__).resolve().parent.parent
    framework = repo / "decode" / PACKAGE / FRAMEWORK
    for name, method in TARGETS.items():
        path = framework / name
        if not path.is_file():
            raise SystemExit("missing %s" % path)
        patch(path, method)


if __name__ == "__main__":
    main()
