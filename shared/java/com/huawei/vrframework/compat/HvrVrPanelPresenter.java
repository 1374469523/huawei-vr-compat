package com.huawei.vrframework.compat;

import android.app.Presentation;
import android.content.Context;
import android.util.Log;
import android.view.Display;
import android.view.SurfaceHolder;
import android.view.SurfaceView;
import android.view.ViewGroup;

/**
 * 把 {@link HvrVrVirtualDisplay} 那块虚拟屏的画面送到眼镜面板上。
 *
 * 做法全是公开 API，没有自己写合成器：
 *
 *   1. 在**眼镜那块 display**（`HUAWEIAV03`，外接屏）上起一个 {@link Presentation}；
 *   2. Presentation 里放一个铺满的 {@link SurfaceView}；
 *   3. `surfaceCreated` 时把这块 Surface 交给 `createVirtualDisplay` 当输出目标。
 *
 * 于是：VR 应用渲染到虚拟屏 → SurfaceFlinger 把虚拟屏合成进这块 Surface →
 * 它本身就是眼镜面板上的一个窗口，画面直接出现在眼镜里。
 *
 * 由**拥有虚拟屏的那个包自己**调用（见 HvrVrVirtualDisplay 的归属说明）。
 */
public final class HvrVrPanelPresenter {
    private static final String TAG = "HvrVrPanel";

    private static Presentation presentation;
    private static SurfaceView surfaceView;

    private HvrVrPanelPresenter() {
    }

    /**
     * 眼镜在位时调用：把面板窗口建起来，Surface 一就绪就建虚拟屏。
     * 返回是否已经（或刚刚）把面板窗口挂上。
     */
    public static boolean start(Context context) {
        if (context == null) {
            return false;
        }
        if (presentation != null) {
            return true;
        }
        Display panel = VrPlatformCompat.externalDisplay(context);
        if (panel == null) {
            Log.w(TAG, "no external panel yet, presenter skipped");
            return false;
        }
        try {
            Context displayContext = context.createDisplayContext(panel);
            SurfaceView view = new SurfaceView(displayContext);
            final Presentation window = new Presentation(displayContext, panel);
            view.setLayoutParams(new ViewGroup.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.MATCH_PARENT));
            view.getHolder().addCallback(new SurfaceHolder.Callback() {
                @Override
                public void surfaceCreated(SurfaceHolder holder) {
                    Log.i(TAG, "panel surface created");
                    HvrVrVirtualDisplay.ensure(window.getContext(), holder.getSurface());
                }

                @Override
                public void surfaceChanged(SurfaceHolder holder, int format,
                                           int width, int height) {
                    // 只保证「有且只有一块」虚拟屏：SurfaceView 起屏时会先 created
                    // 再 changed，每次都重建会让虚拟屏 id 变来变去。
                    HvrVrVirtualDisplay.ensure(window.getContext(), holder.getSurface());
                }

                @Override
                public void surfaceDestroyed(SurfaceHolder holder) {
                    Log.i(TAG, "panel surface destroyed");
                    HvrVrVirtualDisplay.release();
                }
            });
            window.setContentView(view);
            window.setOnDismissListener(dialog -> {
                Log.i(TAG, "panel presentation dismissed");
                presentation = null;
                surfaceView = null;
                HvrVrVirtualDisplay.release();
            });
            window.show();
            presentation = window;
            surfaceView = view;
            Log.i(TAG, "panel presentation shown on display "
                    + panel.getDisplayId() + " (" + panel.getName() + ")");
            return true;
        } catch (Throwable error) {
            Log.w(TAG, "panel presentation failed: " + error);
            stop();
            return false;
        }
    }

    /** 眼镜拔出时调用：撤掉窗口并释放虚拟屏。 */
    public static void stop() {
        Presentation window = presentation;
        presentation = null;
        surfaceView = null;
        HvrVrVirtualDisplay.release();
        if (window != null) {
            try {
                window.dismiss();
            } catch (Throwable error) {
                Log.w(TAG, "panel dismiss failed: " + error);
            }
        }
    }
}
