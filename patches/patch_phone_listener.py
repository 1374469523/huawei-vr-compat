"""Drop the one PhoneStateListener event a normal app cannot be granted.

Both phone managers register a listener with the same event mask:

    const/16 v2, 0x920
    invoke-virtual {p1, v1, v2}, Landroid/telephony/TelephonyManager;
        ->listen(Landroid/telephony/PhoneStateListener;I)V

0x920 = 0x800 | 0x100 | 0x20. 0x800 is the bit the platform only hands to
carrier-privileged callers; on the Mate 20 X the desktop ran as the system user
and held it, on a stock device the registration is refused and the app is killed
while the VR space starts:

    FATAL EXCEPTION: main
    Caused by: java.lang.SecurityException: listen
      at com.android.internal.telephony.TelephonyPermissions
            .enforceCarrierPrivilege(TelephonyPermissions.java:694)
      at com.android.server.TelephonyRegistry.checkListenerPermission(...)
      at android.telephony.TelephonyManager.listen(TelephonyManager.java:7716)
      at l2.q.c(VRPhoneManagerForPie.java:10)
      at com.huawei.vrlauncherx.MainActivity.onCreate(MainActivity.java:17)

0x800 is not a changeable permission (READ_PRECISE_PHONE_STATE is
signature|privileged), so the request itself is what has to change. The mask
becomes 0x120 - the remaining bits (0x100 signal strengths, 0x20 call state) are
exactly what the ring/off-hook handling needs, so the original behaviour is kept
minus the carrier-only detail.

The script asserts the original text, so a re-decode cannot silently produce a
half-patched tree.
"""
import sys
from pathlib import Path

PACKAGE = "com.huawei.vrlauncherx"

# file -> how many times the exact block has to appear
TARGETS = {
    "smali/l2/q.smali": 1,
    "smali/l2/l.smali": 1,
}

ORIGINAL_EVENTS = "const/16 v2, 0x920"
PATCHED_EVENTS = "const/16 v2, 0x120"
LISTEN_CALL = ("invoke-virtual {p1, v1, v2}, Landroid/telephony/TelephonyManager;->"
               "listen(Landroid/telephony/PhoneStateListener;I)V")


def patch(path, expected):
    with open(path, "r", encoding="utf-8", newline="") as handle:
        text = handle.read()
    eol = "\r\n" if "\r\n" in text else "\n"
    working = text.replace("\r\n", "\n")
    found = working.count(ORIGINAL_EVENTS)
    patched = working.count(PATCHED_EVENTS)
    if found == 0 and patched == expected:
        print("%s: already patched (0x120 x%d)" % (path.name, patched))
        return
    if found != expected:
        raise SystemExit("%s: expected %d %r, found %d"
                         % (path, expected, ORIGINAL_EVENTS, found))
    if working.count(LISTEN_CALL) < expected:
        raise SystemExit("%s: listen() call not found next to the event mask" % path)
    working = working.replace(ORIGINAL_EVENTS, PATCHED_EVENTS)
    if eol != "\n":
        working = working.replace("\n", eol)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(working)
    print("%s: %d event mask(s) 0x920 -> 0x120" % (path.name, found))


def main():
    repo = Path(__file__).resolve().parent.parent
    decode = repo / "decode" / PACKAGE
    for relative, expected in TARGETS.items():
        path = decode / relative
        if not path.is_file():
            raise SystemExit("missing %s" % path)
        patch(path, expected)


if __name__ == "__main__":
    main()
