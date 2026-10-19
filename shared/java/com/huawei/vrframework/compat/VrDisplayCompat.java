package com.huawei.vrframework.compat;

import android.content.Context;
import android.util.Log;

/**
 * EMUI 用一块名为 {@code "HUAWEI VR Display"} 的框架虚拟屏承载眼镜，
 * 所以原版多处直接写 {@code display.getName().equals("HUAWEI VR Display")}
 * 来判断「VR 屏在不在」。通用安卓上没有这块虚拟屏：眼镜就是一块普通外接屏，
 * 于是那些判断恒为 false，桌面因此认为「vr display is off」，
 * 跳过唤醒面板那一步，眼镜保持黑屏
 * （真机日志：{@code should not wake up when vr display is off.}）。
 *
 * 这里只回答「本机真实的 VR 屏叫什么」：眼镜在位（USB 身份 + 外接屏两个真实信号
 * 同时成立，见 {@link VrPlatformCompat}）就返回那块外接屏的真实名字，
 * 否则返回 EMUI 的常量，让原版保持原本的失败分支。调用点仍然是原来的
 * {@code equals}，原版逻辑没有改动，也没有按屏名去猜设备。
 */
public final class VrDisplayCompat {
    private static final String TAG = "HvrVrDisplay";

    /** EMUI 框架给眼镜建的虚拟屏名，原版代码里写死的那个。 */
    private static final String EMUI_VR_DISPLAY_NAME = "HUAWEI VR Display";

    private VrDisplayCompat() {
    }

    public static String vrDisplayName() {
        Context context = com.huawei.android.content.ContextEx.currentApplication();
        if (context == null) {
            return EMUI_VR_DISPLAY_NAME;
        }
        try {
            if (!VrPlatformCompat.isVrGlassPresent(context)) {
                return EMUI_VR_DISPLAY_NAME;
            }
            String name = VrPlatformCompat.externalDisplayName(context);
            if (name != null) {
                Log.i(TAG, "real VR display name: " + name);
                return name;
            }
        } catch (Throwable error) {
            Log.w(TAG, "vr display probe failed", error);
        }
        return EMUI_VR_DISPLAY_NAME;
    }
}
