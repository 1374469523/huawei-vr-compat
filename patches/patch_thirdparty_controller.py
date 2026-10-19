"""Stop an uninitialised third-party controller from reporting "connecting".

How the deadlock shows up on the port (full logcat capture, 60 s run):

    I VrControllerManager: Controller init enter
    I ThirdPartyController: addCallback
    I VrControllerManager: Default controller init succeed
    I VrControllerManager: Controller init leave, all failed
    I ThirdPartyController: getStatus() = 0        <- 11625 times in one minute
    I VrControllerManager: ThirdPartyCtrl is connecting
    E Unity_HVRController: Right controller is not available in Update

`VrControllerManager.init()` only initialises the third-party controller when
the environment reports a Huawei 6DoF kit or a Nolo controller:

    if (VrFramework.isHW6DoFCtrlAvailable() || VrFramework.isNoloAvailable()) {
        mThirdPartyCtrl.init(activity)
    }

Neither is available here, so `ThirdPartyController.initVrController()` never
runs and its status field keeps the Java default 0. `checkConnecting()` treats
0 as "connecting" and is asked about the third-party controller *first*, so it
returns true and the manager never falls through to `DefaultController` - the
one that is actually bound and connected to the Huawei handle service:

    I DefaultController: onServiceConnected : ComponentInfo{com.huawei.vrhandle/
        com.huawei.vrhandle.service.VRHandleService}

The class already has a status for "cannot be used": `initVrController()` sets
`mStatus = -1` when its device manager refuses to initialise. This patch applies
the same value when the controller was never initialised at all, so the manager
walks on to the controller that really is connected. No connection state is
invented - the value reported is "unavailable", which is the truth for a
controller that was never started.

The script asserts the original text, so a re-decode cannot silently produce a
half-patched tree.
"""
import re
from pathlib import Path

PACKAGE = "com.huawei.hvrsdkserverapp"
CONTROLLER = (Path("smali") / "com" / "huawei" / "vrframework"
              / "ThirdPartyController.smali")

ANCHOR = re.compile(r"(monitor-enter p0\n)(\s*:try_start_0\n)")

INSERT = """    iget-boolean v0, p0, Lcom/huawei/vrframework/ThirdPartyController;->mVrCtrlInitialized:Z

    if-nez v0, :cond_init_ok

    const/4 v0, -0x1

    iput v0, p0, Lcom/huawei/vrframework/ThirdPartyController;->mStatus:I

    monitor-exit p0

    return v0

    :cond_init_ok
"""


def main():
    repo = Path(__file__).resolve().parent.parent
    path = repo / "decode" / PACKAGE / CONTROLLER
    if not path.is_file():
        raise SystemExit("missing %s" % path)
    with open(path, "r", encoding="utf-8", newline="") as handle:
        text = handle.read()
    eol = "\r\n" if "\r\n" in text else "\n"
    working = text.replace("\r\n", "\n")

    if "cond_init_ok" in working:
        print("%s: already patched" % path.name)
        return
    if "mVrCtrlInitialized:Z" not in working:
        raise SystemExit("%s: mVrCtrlInitialized field not found" % path)
    method = re.search(r"\.method public declared-synchronized getStatus\(\)I\n"
                       r".*?\n\.end method", working, re.S)
    if method is None:
        raise SystemExit("%s: getStatus() not found" % path)
    block = method.group(0)
    if len(ANCHOR.findall(block)) != 1:
        raise SystemExit("%s: getStatus() does not have the expected body anchor"
                         % path)
    patched = ANCHOR.sub(lambda m: m.group(1) + "\n" + INSERT + m.group(2),
                         block, count=1)
    working = working[:method.start()] + patched + working[method.end():]
    if eol != "\n":
        working = working.replace("\n", eol)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(working)
    print("%s: getStatus() now reports -1 until the controller is initialised"
          % path.name)


if __name__ == "__main__":
    main()
