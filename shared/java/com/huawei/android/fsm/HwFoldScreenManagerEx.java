package com.huawei.android.fsm;

import android.util.Log;

/**
 * 照官方实现移植（原厂件/hwframework.jar 的
 * com/huawei/android/fsm/HwFoldScreenManagerEx.smali）。
 *
 * 官方 `getDisplayMode()`/`isFoldable()` 都转给 `com.huawei.android.fsm.HwFoldScreenManager`
 * —— 那是华为框架自己的类，AOSP 里不存在；通用安卓的公开 API 也没有
 * 「这台设备是不是折叠屏」这种概念。所以本移植**不反射、不猜**：
 * 如实返回中性值（不可折叠 / 模式未知）并记一次日志；
 * `registerFoldDisplayMode` 保留回调对象，让调用方的生命周期不变。
 * 不伪造任何折叠状态。
 */
public final class HwFoldScreenManagerEx {
    public static final int DISPLAY_MODE_UNKNOWN = -1;

    /** Implemented by the original VR touch service. */
    public interface FoldDisplayModeListener {
        void onScreenDisplayModeChange(int mode);
    }

    private static volatile FoldDisplayModeListener listener;

    private HwFoldScreenManagerEx() {
    }

    public static boolean isFoldable() {
        // 官方转给 `com.huawei.android.fsm.HwFoldScreenManager` —— 那是华为框架自己的类，
        // AOSP 里不存在，通用安卓的公开 API 也没有「这台设备是不是折叠屏」这个概念。
        // 所以**不反射、不猜**：如实返回 false（不是折叠屏管理器可用状态）并记一次日志。
        logOnce();
        return false;
    }

    public static int getDisplayMode() {
        logOnce();
        return DISPLAY_MODE_UNKNOWN;
    }

    private static void logOnce() {
        if (reported) {
            return;
        }
        reported = true;
        Log.i(TAG, "HwFoldScreenManager is Huawei-only; fold state is unavailable on this device");
    }

    private static final String TAG = "HvrFoldScreenManagerEx";
    private static volatile boolean reported;

    public static void registerFoldDisplayMode(FoldDisplayModeListener target) {
        listener = target;
    }

    public static FoldDisplayModeListener getRegisteredListener() {
        return listener;
    }
}
