"""把重打包出来的 APK 按原包对齐压缩方式重写一遍 zip 结构。

为什么必须做这一步（真机证据，2026-09-16）：

    W System.err: java.util.zip.ZipException: invalid entry size
        (expected 3014459400 but got 483 bytes)
        at com.huawei.hwvrexternaldevice.WhiteListUtil.readApkFile(WhiteListUtil.java:87)
        at ...DeviceServices.getAllMetaData / awakeAllDeviceServices / init

原版有若干处代码用 `ZipInputStream` 读**自己 APK** 的内容
（`WhiteListUtil`、五个包里的 `LibUpdateClient`、vrservice 的 `UncompressTask`）。
apktool 2.10 重建出来的 zip 里，条目同时带着「data descriptor（flag 位 3）」和
**非零的本地头尺寸** —— 这两者互斥，`ZipInputStream` 会按本地头尺寸去读，读到
不同的长度就抛 invalid entry size。

对照数据（本次扫描）：

    原包 com.huawei.hvrsdkserverapp.apk   这类条目 0 个
    产物 com.huawei.hvrsdkserverapp-u3.apk 这类条目 107 个
    原包 com.huawei.vrlauncherx.apk        0 个
    产物 com.huawei.vrlauncherx-u4.apk     979 个

本脚本用 Python 的 zipfile 重写：对**可 seek 的输出**，zipfile 会把尺寸回填进本地头，
因此产物不带 data descriptor；同时按原包对齐每个同名条目的压缩方式
（原包 STORED 的就保持 STORED），新条目（注入的 compat dex、补的 provider）
沿用 apktool 产物里的方式。

构建期断言（不通过就非零退出，构建失败）：

  1. 没有任何条目带 flag & 0x8；
  2. ZipFile.testzip() 通过；
  3. resources.arsc 未压缩（平台要求）；
  4. 条目数与原 APK 相比没有丢掉任何原有条目。

用法：
    python tools/apk-rezip.py <重打包产物.apk> <原包.apk> <输出.apk>
"""

import sys
import zipfile
from pathlib import Path

DATA_DESCRIPTOR_FLAG = 0x8

# 不参与「条目是否丢失」比较的两类：
#   META-INF/  —— apktool 重建时按新签名重写这一目录；
#   res/       —— apktool 会把资源条目重命名（原包是 --.9.png / -Y.xml 这类
#                 混淆名，重建后是 res/xx.png），名字对不上但内容在。
IGNORED_PREFIXES = ("META-INF/", "res/")


def tracked(name):
    return not name.startswith(IGNORED_PREFIXES)


def compress_type_for(name, built_entry, original_types):
    """原包同名的条目用原包的压缩方式，新条目沿用产物里的方式。"""
    original = original_types.get(name)
    if original is None:
        return built_entry.compress_type
    return original


def rezip(built_path, original_path, output_path):
    with zipfile.ZipFile(built_path) as built, \
            zipfile.ZipFile(original_path) as original:
        original_types = {info.filename: info.compress_type
                          for info in original.infolist()}
        built_names = [info.filename for info in built.infolist()]
        missing = [name for name in original_types
                   if tracked(name) and name not in built_names]
        if missing:
            raise SystemExit(
                "重打包产物里缺少原包条目 %d 个，例如 %s"
                % (len(missing), ", ".join(sorted(missing)[:5])))
        stored = 0
        with zipfile.ZipFile(output_path, "w", allowZip64=True) as out:
            out.comment = built.comment
            for info in built.infolist():
                data = built.read(info.filename)
                compress_type = compress_type_for(info.filename, info,
                                                  original_types)
                if compress_type == zipfile.ZIP_STORED:
                    stored += 1
                new_info = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                new_info.compress_type = compress_type
                new_info.external_attr = info.external_attr
                new_info.internal_attr = info.internal_attr
                new_info.create_system = info.create_system
                out.writestr(new_info, data)
    return stored


def verify(path, original_path):
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise SystemExit("zip 校验失败，首个损坏条目：%s" % bad)
        descriptors = [info.filename for info in archive.infolist()
                       if info.flag_bits & DATA_DESCRIPTOR_FLAG]
        if descriptors:
            raise SystemExit("仍有 %d 个条目带 data descriptor，例如 %s"
                             % (len(descriptors), ", ".join(descriptors[:5])))
        for info in archive.infolist():
            if info.filename == "resources.arsc" and info.compress_type != zipfile.ZIP_STORED:
                raise SystemExit("resources.arsc 必须未压缩，当前 compress_type=%d"
                                 % info.compress_type)
        with zipfile.ZipFile(original_path) as original:
            lost = [name for name in original.namelist()
                    if tracked(name) and name not in archive.namelist()]
        if lost:
            raise SystemExit("输出里丢了原包条目 %d 个，例如 %s"
                             % (len(lost), ", ".join(sorted(lost)[:5])))


def main(argv):
    if len(argv) != 4:
        raise SystemExit(__doc__)
    built_path, original_path, output_path = argv[1], argv[2], argv[3]
    if not Path(built_path).exists():
        raise SystemExit("missing %s" % built_path)
    if not Path(original_path).exists():
        raise SystemExit("missing %s" % original_path)
    stored = rezip(built_path, original_path, output_path)
    verify(output_path, original_path)
    with zipfile.ZipFile(output_path) as archive:
        print("rezipped %s: %d entries (%d stored), no data descriptor"
              % (output_path, len(archive.infolist()), stored))


if __name__ == "__main__":
    main(sys.argv)
