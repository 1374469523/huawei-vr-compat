package com.huawei.vrframework.compat;

import android.app.ActivityOptions;
import android.content.Context;
import android.hardware.display.DisplayManager;
import android.util.Log;
import android.view.Display;

/**
 * 把 VR 应用启动到「HUAWEI VR Display」那块虚拟屏上 —— EMUI VR 框架做的路由，
 * 通用安卓上没有，由这一层补。
 *
 * 为什么必须补：
 *
 *   * 原版代码按屏名找 `HUAWEI VR Display`（桌面 `z0/c.w()`、vrservice 的
 *     `checkVrDisplayState` 等），说明 VR 应用本来就在那块屏上跑；
 *   * 投屏模块的启动闸门明确要求「不是在默认屏启动」
 *     （`b/a/c/k/b/d.b`：`displayId != 0`），否则 `app start on default display error, finish!`；
 *   * 眼镜那块外接屏在三星上是 `canHostTasks=false`，承载不了应用，
 *     真正承载应用的是虚拟屏（见 docs/PATCH_AUDIT.md 第 65 节）。
 *
 * 这里不新建任何东西，只做两件只读/一次性的平台动作：按名字找到那块屏、
 * 给启动参数补上 `setLaunchDisplayId`。屏不存在时原样返回，让调用方走它
 * 原本的失败分支（不伪造"已经在 VR 屏上"）。
 */
public final class HvrDisplayRouter {
    private static final String TAG = "HvrDisplayRouter";

    /** 与 Runtime 侧建屏时用的名字严格相同（原版判断依赖这个名字）。 */
    public static final String VR_DISPLAY_NAME = "HUAWEI VR Display";

    private HvrDisplayRouter() {
    }

    /** 按名字找那块虚拟屏；找不到返回 -1。 */
    public static int vrDisplayId() {
        Context context = com.huawei.android.content.ContextEx.currentApplication();
        return vrDisplayId(context);
    }

    public static int vrDisplayId(Context context) {
        if (context == null) {
            return -1;
        }
        try {
            DisplayManager manager =
                    (DisplayManager) context.getSystemService(Context.DISPLAY_SERVICE);
            if (manager == null) {
                return -1;
            }
            for (Display display : manager.getDisplays()) {
                if (display != null && VR_DISPLAY_NAME.equals(display.getName())) {
                    return display.getDisplayId();
                }
            }
        } catch (Throwable error) {
            Log.w(TAG, "vr display lookup failed: " + error);
        }
        return -1;
    }

    /**
     * 给启动参数补上「在 VR 屏上启动」。
     *
     * 如果本进程还没有那块屏，就先在本进程把面板窗口与虚拟屏建起来
     * （**由启动方自己建**：安卓只允许屏的拥有者往它上面启动活动，见
     * HvrVrVirtualDisplay 的归属说明）。建不出来（比如眼镜不在位）就原样返回，
     * 让调用方走它原本的失败分支。
     *
     * 调用点：桌面 `z0/c.B(Context, Class)`（所有 VR 页面的统一入口）。
     */
    public static ActivityOptions applyVrDisplay(ActivityOptions options) {
        if (options == null) {
            return null;
        }
        // 优先用**本进程自己建的**那块屏：只有它一定允许我们往上面启动。
        int displayId = HvrVrVirtualDisplay.displayId();
        if (displayId < 0) {
            // 本进程还没建过这块屏 —— 由我们自己建一块并挂到眼镜面板上。
            Context context = com.huawei.android.content.ContextEx.currentApplication();
            if (context != null && HvrVrPanelPresenter.start(context)) {
                displayId = HvrVrVirtualDisplay.displayId();
                // SurfaceView 的 surface 是异步回调的，这里可能还没建好；
                // 没建好就不强塞 displayId，下一次启动会自动接上。
            }
        }
        if (displayId < 0) {
            // 退回到原版语义：按屏名找那块既有的屏（例如 Runtime 先建好了）。
            displayId = vrDisplayId();
        }
        if (displayId < 0) {
            Log.i(TAG, VR_DISPLAY_NAME + " not up yet, keeping the original launch options");
            return options;
        }
        try {
            options.setLaunchDisplayId(displayId);
            Log.i(TAG, "vr activity routed to display " + displayId);
        } catch (Throwable error) {
            Log.w(TAG, "setLaunchDisplayId failed: " + error);
        }
        return options;
    }
}
