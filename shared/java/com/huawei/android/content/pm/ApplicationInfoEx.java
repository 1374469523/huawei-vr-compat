package com.huawei.android.content.pm;

import android.content.pm.ApplicationInfo;
import android.util.Log;

/**
 * 照官方实现移植（原厂件/hwframework.jar 的
 * com/huawei/android/content/pm/ApplicationInfoEx.smali）。
 *
 * 官方 `getHwFlags()` 就是直接读 `ApplicationInfo.hwFlags` —— EMUI 加的
 * hidden 字段。AOSP 没有公开的这组标志，反射在 targetSdk≥28 上也会被拦，
 * 所以本移植**不反射**：构造时记一次日志，`getHwFlags()` 如实返回 0
 * （与「非 EMUI 构建上这个字段不存在」的结果一致），不猜任何标志位。
 */
public class ApplicationInfoEx {
    private final ApplicationInfo info;
    private final int hwFlags;

    public ApplicationInfoEx(ApplicationInfo info) {
        this.info = info;
        this.hwFlags = info == null ? 0 : readHwFlags(info);
    }

    private static int readHwFlags(ApplicationInfo info) {
        // 官方读的是 `ApplicationInfo.hwFlags`（EMUI 加的 hidden 字段）。
        // AOSP 的 ApplicationInfo 没有公开的这组标志，reflection 在 targetSdk≥28
        // 上也会被拦，所以**不反射、不猜**：如实返回 0，并记一次日志说明原因。
        if (!reported) {
            reported = true;
            Log.i(TAG, "ApplicationInfo.hwFlags is EMUI-only; reporting 0 flags");
        }
        return 0;
    }

    private static final String TAG = "HvrApplicationInfoEx";
    private static volatile boolean reported;

    public int getHwFlags() {
        return hwFlags;
    }

    public ApplicationInfo getApplicationInfo() {
        return info;
    }
}
