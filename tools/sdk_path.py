"""解析 Android SDK 的位置 —— 工具脚本里不再写死绝对路径。

查找顺序（先命中先用）：
  1. 环境变量 HVR_ANDROID_SDK
  2. <仓库>/工具链/android-sdk
  3. <仓库>/../android-sdk          （工作区根目录那份，通常是 junction）
  4. <仓库>/android-sdk

用法：
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
    from sdk_path import find_android_sdk
    sdk = find_android_sdk()
"""

import os
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def sdk_candidates():
    env = os.environ.get("HVR_ANDROID_SDK")
    candidates = []
    if env:
        candidates.append(Path(env))
    candidates.append(REPO / "工具链" / "android-sdk")
    candidates.append(REPO.parent / "android-sdk")
    candidates.append(REPO / "android-sdk")
    return candidates


def find_android_sdk():
    """返回 SDK 根目录；都找不到就抛错并列出查过的位置。"""
    for candidate in sdk_candidates():
        if (candidate / "build-tools").is_dir():
            return candidate
    raise SystemExit("找不到 Android SDK，查过这些位置：\n  " +
                     "\n  ".join(str(c) for c in sdk_candidates()) +
                     "\n可以设环境变量 HVR_ANDROID_SDK 指到 SDK 根目录。")


def find_aapt2(version="35.0.0"):
    return find_android_sdk() / "build-tools" / version / "aapt2.exe"


def find_adb():
    return find_android_sdk() / "platform-tools" / "adb.exe"
