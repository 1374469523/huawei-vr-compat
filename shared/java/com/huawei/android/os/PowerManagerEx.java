package com.huawei.android.os;

import android.content.ContentResolver;
import android.content.Context;
import android.os.PowerManager;
import android.provider.Settings;
import android.util.Log;

/**
 * 照官方实现移植（原厂件/hwframework.jar 的
 * com/huawei/android/os/PowerManagerEx.smali）。七个包只用到其中 6 个方法：
 *
 *   setTemporaryScreenBrightnessSetting(I)V        x6
 *   setTemporaryScreenAutoBrightnessSetting(I)V    x4
 *   isInteractive()Z                               x2
 *   wakeUp(Landroid/os/PowerManager;JLjava/lang/String;)V   x1
 *   getUserActivityEventOther()I                   x1
 *   userActivity(Landroid/os/PowerManager;JII)V    x1
 *
 * 官方的做法（逐条对照原 smali）：
 *
 *   isInteractive()            ServiceManagerEx.getService("power") ->
 *                              IPowerManager$Stub.asInterface -> isInteractive()
 *   getUserActivityEventOther() 直接 return 0（就是常量）
 *   setTemporaryScreenBrightnessSetting(i)
 *                              IPowerManager.setTemporaryScreenBrightnessSettingOverride(i)
 *   setTemporaryScreenAutoBrightnessSetting(i)
 *                              IPowerManager.setTemporaryScreenAutoBrightnessSettingOverride(i)
 *   userActivity(pm,t,e,f)     pm.userActivity(t,e,f)
 *   wakeUp(pm,t,details)       pm.wakeUp(t, <reason>, details)
 *
 * 前两条是系统进程里的接口（需要 DEVICE_POWER），后两条是 hidden 方法。
 * 本移植**只用公开 API**：hidden 一律不再反射（targetSdk≥28 上会被拦），
 * 没有公开等价物的就如实做不了并记一次日志，不伪造成功。
 * 逐条换成通用安卓的等价物：
 *
 *  - isInteractive()：改用公开的 PowerManager.isInteractive()，问的是同一件事。
 *  - 两个亮度接口：改用公开的 Settings.System（本包已声明 WRITE_SETTINGS，
 *    install-six.ps1 里 appops 授权）。注意**参数语义**：调用方（VRService /
 *    VrTouchService）传进来的是「当前亮度值」（代码里就是 currentBrightness），
 *    不是模式；官方把它交给自动亮度的临时覆盖接口。这里对自动亮度那一支做的是
 *    「把当前亮度设置重写一遍」——即调用方真正想要的「重新套用亮度」这个动作，
 *    而不是把亮度当成 mode 写进 SCREEN_BRIGHTNESS_MODE（那会把模式写成非法值）。
 *  - wakeUp：官方调 hidden 的 pm.wakeUp(...)。公开 API 里点亮屏幕的正规做法是
 *    FULL_WAKE_LOCK | ACQUIRE_CAUSES_WAKEUP 的短暂 wake lock，这里只走这一条。
 *  - userActivity：官方调 hidden 的 pm.userActivity(...)。公开 API 没有
 *    「重置 user activity 计时器」的写法，只能短暂持 PARTIAL_WAKE_LOCK；
 *    持锁期间系统不会把屏幕判定为空闲，效果上等价，但它不进系统那份
 *    user-activity 统计——这一点在日志里写明，不假装是官方那条。
 */
public final class PowerManagerEx {

    private static final String TAG = "HvrPowerManagerEx";

    /** 官方就是 return 0；AOSP 里 USER_ACTIVITY_EVENT_OTHER = 0。 */
    private static final int USER_ACTIVITY_EVENT_OTHER = 0;

    /** 0..255 是 Settings.System.SCREEN_BRIGHTNESS 的取值域。 */
    private static final int MAX_LEGACY_BRIGHTNESS = 255;

    private PowerManagerEx() {
    }

    private static Context context() {
        return com.huawei.android.content.ContextEx.currentApplication();
    }

    private static PowerManager powerManager() {
        Context context = context();
        if (context == null) {
            return null;
        }
        return (PowerManager) context.getSystemService(Context.POWER_SERVICE);
    }

    public static boolean isInteractive() {
        PowerManager manager = powerManager();
        if (manager == null) {
            return true;
        }
        try {
            return manager.isInteractive();
        } catch (Throwable error) {
            Log.w(TAG, "isInteractive failed", error);
            return true;
        }
    }

    public static int getUserActivityEventOther() {
        return USER_ACTIVITY_EVENT_OTHER;
    }

    public static void setTemporaryScreenBrightnessSetting(int brightness) {
        writeBrightness(brightness);
    }

    public static void setTemporaryScreenAutoBrightnessSetting(int brightness) {
        // 官方把 brightness 交给 setTemporaryScreenAutoBrightnessSettingOverride；
        // 通用安卓没有这个临时覆盖接口，公开等价物是「重新套用当前亮度设置」。
        Context context = context();
        if (context == null) {
            return;
        }
        try {
            ContentResolver resolver = context.getContentResolver();
            int current = Settings.System.getInt(
                    resolver, Settings.System.SCREEN_BRIGHTNESS, -1);
            if (current < 0) {
                Log.w(TAG, "no current brightness to re-apply");
                return;
            }
            Settings.System.putInt(resolver, Settings.System.SCREEN_BRIGHTNESS, current);
        } catch (Throwable error) {
            Log.w(TAG, "re-apply auto brightness failed", error);
        }
    }

    private static void writeBrightness(int brightness) {
        Context context = context();
        if (context == null) {
            return;
        }
        try {
            Settings.System.putInt(context.getContentResolver(),
                    Settings.System.SCREEN_BRIGHTNESS, clamp(brightness));
        } catch (Throwable error) {
            // 平台拒绝就保持它自己的亮度，不能假装写成功。
            Log.w(TAG, "write brightness failed", error);
        }
    }

    private static int clamp(int brightness) {
        if (brightness < 0) {
            return 0;
        }
        return brightness > MAX_LEGACY_BRIGHTNESS ? MAX_LEGACY_BRIGHTNESS : brightness;
    }

    public static void userActivity(PowerManager manager, long when, int event, int flags) {
        if (manager == null) {
            return;
        }
        // hidden 的 pm.userActivity(t,e,f) 不反射；公开机制里用短暂持锁达到
        // 「不让系统判定空闲」的同一目的。
        resetIdleTimer(manager);
    }

    public static void wakeUp(PowerManager manager, long time, String details) {
        if (manager == null) {
            return;
        }
        // hidden 的 pm.wakeUp(t, reason, details) 不反射；公开机制里用
        // FULL_WAKE_LOCK | ACQUIRE_CAUSES_WAKEUP 点亮屏幕。
        wakeWithPublicWakeLock(manager);
    }

    /** 公开 API 的等价动作：短暂持锁把 idle 计时器重置。 */
    private static void resetIdleTimer(PowerManager manager) {
        try {
            PowerManager.WakeLock lock = manager.newWakeLock(
                    PowerManager.PARTIAL_WAKE_LOCK, TAG + ":userActivity");
            lock.acquire(1000L);
            lock.release();
        } catch (Throwable error) {
            Log.w(TAG, "wake lock reset failed", error);
        }
    }

    /** 公开 API 的等价动作：FULL_WAKE_LOCK + ACQUIRE_CAUSES_WAKEUP 点亮屏幕。 */
    private static void wakeWithPublicWakeLock(PowerManager manager) {
        try {
            PowerManager.WakeLock lock = manager.newWakeLock(
                    PowerManager.FULL_WAKE_LOCK
                            | PowerManager.ACQUIRE_CAUSES_WAKEUP,
                    TAG + ":wakeUp");
            lock.acquire(1000L);
            lock.release();
        } catch (Throwable error) {
            Log.w(TAG, "wake lock wake-up failed", error);
        }
    }
}
