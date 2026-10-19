#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从原包里取出每个包的**官方签名证书**，生成模块用的 Certs.java。

七个原包各自一张证书（DN 一样，密钥不同），所以模块必须按包返回原证书，
不能拿一张顶七个。

    powershell -File tools/lsposed-signature-spoof/extract-certs.py   (或直接 python)

输入：
  build/orig-certs.txt      由 apksigner verify --print-certs 生成的
                            「包名 \t Signer #1 certificate SHA-256 digest: <hex> \t DN」表
  原包/*.apk                证书本体在 META-INF/*.RSA（PKCS#7）里
输出：
  tools/lsposed-signature-spoof/src/com/hvr/spoof/Certs.java
"""
import base64
import hashlib
import os
import re
import sys
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TABLE = os.path.join(REPO, "build", "orig-certs.txt")
OUT = os.path.join(REPO, "tools", "lsposed-signature-spoof", "src", "com", "hvr",
                   "spoof", "Certs.java")


def signer_digests():
    """{apk 文件名: sha256}，来自 apksigner 的权威输出。"""
    result = {}
    with open(TABLE, encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 2:
                continue
            digest = re.search(r"([0-9a-f]{64})", parts[1])
            if digest:
                result[parts[0]] = digest.group(1)
    return result


def candidates(payload):
    """PKCS#7 里所有 DER 对象（签名证书、CRL、属性证书混在一起）。"""
    index = 0
    while True:
        found = payload.find(b"\x30\x82", index)
        if found < 0:
            return
        length = int.from_bytes(payload[found + 2:found + 4], "big") + 4
        if found + length <= len(payload):
            yield payload[found:found + length]
        index = found + 1


def extract(apk_path, wanted):
    with zipfile.ZipFile(apk_path) as archive:
        for name in archive.namelist():
            upper = name.upper()
            if not (name.startswith("META-INF/")
                    and upper.endswith((".RSA", ".DSA", ".EC"))):
                continue
            for blob in candidates(archive.read(name)):
                if hashlib.sha256(blob).hexdigest() == wanted:
                    return blob
    return None


def main():
    digests = signer_digests()
    if not digests:
        print("缺少 %s（先跑 apksigner verify --print-certs）" % TABLE, file=sys.stderr)
        return 1
    packages, blobs = [], []
    for apk in sorted(os.listdir(os.path.join(REPO, "原包"))):
        if not apk.endswith(".apk") or apk not in digests:
            continue
        package = apk[:-len(".apk")]
        blob = extract(os.path.join(REPO, "原包", apk), digests[apk])
        if blob is None:
            print("没找到 %s 的证书" % apk, file=sys.stderr)
            return 1
        packages.append(package)
        blobs.append(base64.b64encode(blob).decode("ascii"))
        print("%-34s 证书 %d 字节" % (package, len(blob)))

    lines = ["package com.hvr.spoof;", "",
             "/** 由 tools/lsposed-signature-spoof/extract-certs.py 生成，勿手改。 */",
             "final class Certs {", "",
             "    static final String[] PACKAGES = {"]
    for package in packages:
        lines.append('        "%s",' % package)
    lines += ["    };", "", "    static final String[] BASE64 = {"]
    for blob in blobs:
        lines.append('        "%s",' % blob)
    lines += ["    };", "",
              "    private Certs() {", "    }", "}", ""]

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines))
    print("已写出 %s（%d 个包）" % (os.path.relpath(OUT, REPO), len(packages)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
