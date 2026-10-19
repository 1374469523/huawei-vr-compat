package com.huawei.android.media;

import android.util.Log;

/**
 * 照官方实现移植（原厂件/hwframework.jar 的
 * com/huawei/android/media/AudioServiceEx.smali）。七个包只用到两个成员：
 *
 *   getInstance()           官方是加锁的单例，这里一致
 *   setBluetoothA2dpOn(Z)   官方：getServiceBinder() 取 "audio" 服务
 *                           （ServiceManager.getService("audio")），
 *                           再 IAudioService.setBluetoothA2dpOn(on)
 *
 * A2DP 开关从 AOSP 早期起就只有 hidden 接口（IAudioService / 被隐藏的
 * AudioManager.setBluetoothA2dpOn），公开 API 里没有对应能力：
 * MediaRouter2 是媒体路由、setCommunicationDevice 是通信设备，都不是 A2DP 开关。
 *
 * 所以本移植**不反射、不伪造**：如实记一次日志并保持设备自己的路由，
 * 由用户从系统 UI 切换音频输出。
 */
public class AudioServiceEx {

    private static final String TAG = "HvrAudioServiceEx";

    private static volatile AudioServiceEx instance;
    private static volatile boolean reported;

    private AudioServiceEx() {
    }

    public static AudioServiceEx getInstance() {
        if (instance == null) {
            synchronized (AudioServiceEx.class) {
                if (instance == null) {
                    instance = new AudioServiceEx();
                }
            }
        }
        return instance;
    }

    public void setBluetoothA2dpOn(boolean on) {
        if (!reported) {
            reported = true;
            Log.w(TAG, "setBluetoothA2dpOn has no public Android API; "
                    + "switch the audio output from the system UI instead");
        }
    }
}
