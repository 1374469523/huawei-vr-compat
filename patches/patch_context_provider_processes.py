"""Give the compat layer an application context inside *secondary* processes.

Why this is needed (measured, not guessed):

``ContextEx`` learns the application context from the injected content provider
``com.huawei.vrframework.compat.HvrContextProvider``. A content provider is only
instantiated in the process it is declared for, and without ``android:process``
that is the package's **default** process. Every module also declares
components that run in their own process (``com.huawei.vrlauncherx`` launches
``com.huawei.vrservice``, the handle uses ``:VRHandleService`` and so on), and
in those processes the provider never runs.

Symptom on device (SM-F731U1, 2026-09-16): the launcher's VR service runs in
``com.huawei.vrservice`` and tries to publish the ``vr_system`` binder to the
compat registry, but logs

    W HvrServiceManagerEx: no application context; vr_system stays process-local

once a second, so no other module can ever look the service up.

The fix stays on the manifest/平台层: declare one more instance of the same
provider per secondary process, with its own authority. No original code and no
original component is touched.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import axml_edit  # noqa: E402

PROVIDER = "com.huawei.vrframework.compat.HvrContextProvider"

# 布尔属性用 aapt 的整数编码；写成字符串平台会判成假。
TYPE_INT_BOOLEAN = 0x12
BOOL_TRUE = 0xFFFFFFFF
BOOL_FALSE = 0
NO_RAW_VALUE = 0xFFFFFFFF

ATTR_AUTHORITIES = 0x01010018
ATTR_PROCESS = 0x01010011


def bool_attribute(ns_index, name_index, value):
    return (ns_index, name_index, NO_RAW_VALUE, 8, 0, TYPE_INT_BOOLEAN,
            BOOL_TRUE if value else BOOL_FALSE)

# package -> process names declared with android:process in its manifest.
# Taken from `aapt2 dump xmltree --file AndroidManifest.xml` of the built APKs.
PROCESSES = {
    "com.huawei.vrlauncherx": ["com.huawei.vrservice"],
    "com.huawei.himovie.vr": [":player", ":pushservice"],
    "com.huawei.vrvirtualscreen": [":appDisplay", ":userGuide"],
    "com.huawei.vrhandle": [":VRHandleService"],
    "com.huawei.vrservice": ["com.huawei.vrinstaller"],
}


def authority(package, index):
    return "%s.hvrcompat.ctx%d" % (package, index)


def ensure_provider(working, name, auth, process):
    """Insert (or refresh) one non-exported provider bound to `process`."""
    # Drop a stale entry for this authority first so re-running is idempotent.
    stale = re.compile(
        r'\n[ \t]*<provider[^>]*android:authorities\s*=\s*"%s"[^>]*/>'
        % re.escape(auth))
    working = stale.sub("", working)

    anchor = re.search(r"\n(\s*)<application[^>]*>", working)
    if anchor is None:
        raise SystemExit("<application> not found")
    indent = anchor.group(1)
    block = ('\n%s    <provider android:name="%s" android:authorities="%s"'
             ' android:exported="false" android:process="%s"/>'
             % (indent, name, auth, process))
    at = anchor.end()
    return working[:at] + block + working[at:]


def main(root):
    decode = Path(root) / "decode"
    for package, processes in PROCESSES.items():
        manifest = decode / package / "AndroidManifest.xml"
        if not manifest.is_file():
            raise SystemExit("missing %s" % manifest)
        raw = manifest.read_bytes()
        if raw[:2] == b"\x03\x00":
            patch_binary(manifest, package, processes)
        else:
            patch_text(manifest, package, processes)
        print("%-32s 子进程上下文 provider %s" % (package, processes))


def patch_text(manifest, package, processes):
    with open(manifest, "r", encoding="utf-8", newline="") as handle:
        text = handle.read()
    if PROVIDER not in text:
        raise SystemExit(
            "%s: base context provider missing; run "
            "patch_platform_permissions.py first" % package)
    eol = "\r\n" if "\r\n" in text else "\n"
    working = text.replace("\r\n", "\n")
    for index, process in enumerate(processes, start=1):
        working = ensure_provider(working, PROVIDER,
                                  authority(package, index), process)
    if eol != "\n":
        working = working.replace("\n", eol)
    with open(manifest, "w", encoding="utf-8", newline="") as handle:
        handle.write(working)


def patch_binary(manifest, package, processes):
    """Same addition for a manifest that is still binary AXML."""
    document = axml_edit.BinaryXml(manifest.read_bytes())
    application = document.find_start_elements("application")
    if len(application) != 1:
        raise SystemExit("%s: expected exactly one <application>" % package)
    position = application[0][0]
    android_ns = document.pool.index_of(
        "http://schemas.android.com/apk/res/android")
    document.ensure_resource_id(ATTR_AUTHORITIES, "authorities")
    document.ensure_resource_id(ATTR_PROCESS, "process")
    for index, process in enumerate(processes, start=1):
        auth = authority(package, index)
        if any(document.attribute(child, "authorities") == auth
               for _, child in document.find_start_elements("provider")):
            continue
        document.append_children(position, [axml_edit.ElementTree(
            document.pool.add("provider"),
            [(android_ns, document.pool.add("name"),
              document.pool.add(PROVIDER)),
             (android_ns, document.pool.add("authorities"),
              document.pool.add(auth)),
             bool_attribute(android_ns, document.pool.add("exported"), False),
             (android_ns, document.pool.add("process"),
              document.pool.add(process))])])
    manifest.write_bytes(document.build())


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1
         else str(Path(__file__).resolve().parents[1]))
