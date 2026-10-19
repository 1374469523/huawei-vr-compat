package com.huawei.android.view;

import android.view.WindowManager;
import android.util.Log;

/**
 * 照官方实现移植（原厂件/hwframework.jar 的
 * com/huawei/android/view/WindowManagerEx.smali）。
 *
 * 官方 `LayoutParamsEx.addHwFlags(int)` 把 EMUI 私有 layout flags 写进平台的
 * WindowManager.LayoutParams。AOSP 里同义的 `extraFlags` 是 hidden 字段，
 * 公开 API 没有承载这组标志的位置，所以本移植**不反射**：
 * 标志只记在本包装对象上，并记一次日志说明它没有传到平台。
 */
public final class WindowManagerEx {
    private WindowManagerEx() {
    }

    public static final class LayoutParamsEx {
        private final WindowManager.LayoutParams params;
        private int hwFlags;

        public LayoutParamsEx(WindowManager.LayoutParams params) {
            this.params = params;
        }

        public void addHwFlags(int flags) {
            hwFlags |= flags;
            // 官方把 EMUI 私有 layout flags 写进平台的 LayoutParams。
            // AOSP 里同义的 `extraFlags` 是 hidden 字段（反射在 targetSdk≥28 上被拦），
            // 公开的 LayoutParams 没有承载这组标志的地方，所以**不反射、不瞎写**：
            // 标志只记在本包装对象上，并记一次日志说明它没有传到平台。
            if (!reported) {
                reported = true;
                Log.i(TAG, "Hw layout flags have no public field on WindowManager.LayoutParams; "
                        + "kept on the wrapper only");
            }
        }

        public int getHwFlags() {
            return hwFlags;
        }

        public WindowManager.LayoutParams getLayoutParams() {
            return params;
        }
    }

    private static final String TAG = "HvrWindowManagerEx";
    private static volatile boolean reported;
}
