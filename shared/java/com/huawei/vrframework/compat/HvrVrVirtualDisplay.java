package com.huawei.vrframework.compat;

import android.content.Context;
import android.hardware.display.DisplayManager;
import android.hardware.display.VirtualDisplay;
import android.util.Log;
import android.view.Surface;

/**
 * EMUI VR 模式那块「承载 VR 应用的虚拟屏」的通用安卓等价物。
 *
 * 原版七个包里到处是同一个判断：
 *
 *     display.getName().equals("HUAWEI VR Display")
 *
 * `HUAWEI VR Display` **不是**眼镜那块 DP 面板（三星给它的属性是
 * `canHostTasks=false`，只能做 Presentation，承载不了应用），而是 EMUI 的 VR 模式
 * 自己建的一块**虚拟屏**：VR 应用被启动到它上面，它的图像再送到眼镜面板。
 * 证据与推导见 docs/PATCH_AUDIT.md 第 65 节。
 *
 * **归属很重要**：安卓的 `isCallerAllowedToLaunchOnDisplay` 只放行「这块屏的拥有者
 * 本人」或持有 `INTERNAL_SYSTEM_WINDOW`（signature 级）的调用者。实测从 Runtime
 * 建屏、由桌面启动 VR 活动会被拒：
 *
 *     SecurityException: Permission Denial: starting ... with launchDisplayId=25
 *
 * 所以这块屏由**启动方自己**（也就是负责拉起 VR 页面的那个包）创建，
 * 归属与启动方同 uid，路由就不需要任何特权。
 */
public final class HvrVrVirtualDisplay {
    /** 与 Runtime 侧建屏时用的名字严格相同（原版判断依赖这个名字）。 */
    public static final String DISPLAY_NAME = "HUAWEI VR Display";

    private static final String TAG = "HvrVrDisplay";

    /** 面板真实分辨率（dumpsys display 读到的 HUAWEIAV03 值）。 */
    private static final int WIDTH = 3200;
    private static final int HEIGHT = 1600;
    private static final int DENSITY_DPI = 320;

    private static VirtualDisplay display;

    private HvrVrVirtualDisplay() {
    }

    /**
     * 建立这块屏；已经建好就复用。{@code surface} 必须是一块有效 Surface
     * （眼镜面板上 SurfaceView 的 Surface），否则不建——宁可不建，也不建一块
     * 没人看的屏。
     */
    public static synchronized void ensure(Context context, Surface surface) {
        if (display != null) {
            return;
        }
        if (context == null) {
            Log.w(TAG, "no context, cannot create " + DISPLAY_NAME);
            return;
        }
        if (surface == null || !surface.isValid()) {
            Log.w(TAG, "no valid panel surface yet for " + DISPLAY_NAME);
            return;
        }
        DisplayManager manager =
                (DisplayManager) context.getSystemService(Context.DISPLAY_SERVICE);
        if (manager == null) {
            Log.w(TAG, "no DisplayManager, cannot create " + DISPLAY_NAME);
            return;
        }
        try {
            int flags = DisplayManager.VIRTUAL_DISPLAY_FLAG_PUBLIC
                    | DisplayManager.VIRTUAL_DISPLAY_FLAG_PRESENTATION
                    | DisplayManager.VIRTUAL_DISPLAY_FLAG_OWN_CONTENT_ONLY;
            // 试过再带 VIRTUAL_DISPLAY_FLAG_TRUSTED（@hide，1<<10），平台直接拒绝：
            //   SecurityException: Requires ADD_TRUSTED_DISPLAY permission to create
            //   a trusted virtual display.
            // 所以「可信屏」这条路对普通应用是死的，只能靠 LSPosed 放行判断
            // （见 lsposed/hvr-display-routing）。
            display = manager.createVirtualDisplay(DISPLAY_NAME, WIDTH, HEIGHT,
                    DENSITY_DPI, surface, flags);
            if (display == null) {
                Log.w(TAG, DISPLAY_NAME + " creation refused");
                return;
            }
            Log.i(TAG, DISPLAY_NAME + " created: displayId="
                    + display.getDisplay().getDisplayId()
                    + " " + WIDTH + "x" + HEIGHT);
        } catch (Throwable error) {
            Log.w(TAG, "cannot create " + DISPLAY_NAME + ": " + error);
            display = null;
        }
    }

    /** VR 会话结束时释放。输出 Surface 归 SurfaceView 所有，这里不 release。 */
    public static synchronized void release() {
        if (display == null) {
            return;
        }
        try {
            display.release();
        } catch (Throwable error) {
            Log.w(TAG, "release failed: " + error);
        }
        display = null;
        Log.i(TAG, DISPLAY_NAME + " released");
    }

    /** 当前虚拟屏 id（本进程创建的），未建立时返回 -1。 */
    public static synchronized int displayId() {
        return display == null ? -1 : display.getDisplay().getDisplayId();
    }
}
