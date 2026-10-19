package com.huawei.android.media;

import android.media.AudioSystem;
import android.util.Log;

/**
 * 照官方实现移植（原厂件/hwframework.jar 的
 * com/huawei/android/media/AudioSystemEx.smali）：
 *
 *     getParameters(String keys)          -> android.media.AudioSystem.getParameters(keys)
 *     setParameters(String keyValuePairs) -> android.media.AudioSystem.setParameters(...)
 *     setForceUse(int,int)                -> android.media.AudioSystem.setForceUse(...)
 *
 * 也就是对 hidden 类 android.media.AudioSystem 的一行直连。这里保持同样的调用
 * 方式（编译期由 shared/stubs 提供存根，运行期用设备上真类），因此
 * `setParameters` 返回的是 **HAL 的真实返回码**，不再是我方旧版本写死的 0。
 *
 * 七个包只用到 setParameters（8 处）与 getParameters（1 处），setForceUse 一并
 * 按官方补齐签名。
 */
public final class AudioSystemEx {

    private static final String TAG = "HvrAudioSystemEx";

    private AudioSystemEx() {
    }

    public static String getParameters(String keys) {
        try {
            String value = AudioSystem.getParameters(keys);
            return value == null ? "" : value;
        } catch (Throwable error) {
            Log.w(TAG, "getParameters failed", error);
            return "";
        }
    }

    public static int setParameters(String keyValuePairs) {
        try {
            return AudioSystem.setParameters(keyValuePairs);
        } catch (Throwable error) {
            Log.w(TAG, "setParameters failed", error);
            return -1;
        }
    }

    public static int setForceUse(int usage, int config) {
        try {
            return AudioSystem.setForceUse(usage, config);
        } catch (Throwable error) {
            Log.w(TAG, "setForceUse failed", error);
            return -1;
        }
    }
}
