package com.huawei.vrframework.compat;

import android.content.Context;
import android.hardware.display.DisplayManager;
import android.util.Log;
import android.view.Display;

/**
 * 麒麟（HiSilicon）VRAR HAL 的 vsync 计数器，在高通平台上的等价实现。

 * 原版 `VrFramework$VrDisplay$HisiVsyncThread.getVsyncTimeStamp(int)` 调
 * `android.hardware.hivrar.IHivrarService.vrGetVsyncTimeStamp(int)`，而这个 HAL
 * 服务（`hisi.vrar`）只在麒麟平台存在；它还是通过 hidden API
 * `ServiceManager.getService/waitForService` 反射去取的，在通用安卓上被直接拒绝
 * （真机：`E/wei.vrlauncherx: hiddenapi: Accessing hidden method
 *  Landroid/os/ServiceManager;->waitForService(...) using reflection: denied`）。

 * 通用安卓公开 API 里没有「读硬件 vsync 计数器」的接口，但帧边界可以从
 * **真实显示刷新率 + System.nanoTime()** 推出来：Choreographer 的 frameTimeNanos
 * 本身就是基于 System.nanoTime() 的单调时钟，这里算出「下一个 vsync 边界」，
 * 与原版那个接口返回同一量纲（纳秒时间戳，double）且与显示同频。

 * 注意口径：这是由真实显示参数推算的帧边界，不是从硬件计数器读出来的实测值；
 * 在 Qualcomm 上没有 HiSilicon 计数器可用，这是可用的等价来源。取不到刷新率时
 * 退回 60Hz（Display.getRefreshRate() 的常规值），并如实记日志。
 */
public final class VrVsyncCompat {
    private static final String TAG = "HvrVsync";
    private static final double FALLBACK_REFRESH_HZ = 60.0;

    private VrVsyncCompat() {
    }

    /** 返回「下一个 vsync 边界」的纳秒时间戳（与 System.nanoTime() 同基准）。 */
    public static double timestamp(int displayIndex) {
        double refresh = refreshRate(displayIndex);
        double periodNs = 1_000_000_000.0 / refresh;
        long now = System.nanoTime();
        return (Math.floor(now / periodNs) + 1.0) * periodNs;
    }

    private static double refreshRate(int displayIndex) {
        try {
            Context context = com.huawei.android.content.ContextEx.currentApplication();
            if (context == null) {
                return FALLBACK_REFRESH_HZ;
            }
            DisplayManager manager =
                    (DisplayManager) context.getSystemService(Context.DISPLAY_SERVICE);
            if (manager == null) {
                return FALLBACK_REFRESH_HZ;
            }
            Display[] displays = manager.getDisplays();
            Display display = null;
            if (displays != null && displayIndex >= 0 && displayIndex < displays.length) {
                display = displays[displayIndex];
            }
            if (display == null) {
                display = manager.getDisplay(Display.DEFAULT_DISPLAY);
            }
            if (display == null) {
                return FALLBACK_REFRESH_HZ;
            }
            float rate = display.getRefreshRate();
            return rate > 0 ? rate : FALLBACK_REFRESH_HZ;
        } catch (Throwable error) {
            Log.w(TAG, "refresh rate probe failed", error);
            return FALLBACK_REFRESH_HZ;
        }
    }
}
