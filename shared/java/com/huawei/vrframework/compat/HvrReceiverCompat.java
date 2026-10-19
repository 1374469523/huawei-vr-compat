package com.huawei.vrframework.compat;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.os.Build;
import android.os.Handler;
import android.util.Log;

/**
 * 动态注册广播的平台兼容层：Android 14+ 要求显式声明导出属性。
 *
 * 真机崩溃（SM-F731U1 / Android 16，2026-09-16，`com.huawei.himovie.vr`）：
 *
 *     java.lang.RuntimeException: Unable to create application com.huawei.vrlab.VrPlayerApplication
 *     Caused by: java.lang.SecurityException: com.huawei.himovie.vr:
 *       One of RECEIVER_EXPORTED or RECEIVER_NOT_EXPORTED should be specified
 *       when a receiver isn't being registered exclusively for system broadcasts
 *         at android.app.ContextImpl.registerReceiver(ContextImpl.java:1990)
 *
 * 原版是 EMUI 9/10 时代写的（targetSdk 30），当时 `registerReceiver(receiver, filter)`
 * 不需要标志位；Android 14 起平台强制要求，不给就抛 SecurityException，
 * 于是视频包连 Application.onCreate 都过不去 —— 桌面点「VR 视频」自然没反应。
 *
 * 这里只补平台新增的那个参数，语义按 Android 14 之前的行为取：
 * **RECEIVER_EXPORTED**。理由是 pre-34 的动态注册接收器本来就能收到其它应用发的
 * 广播（我们自己的模块之间就是靠广播 + 显式组件通信的），选 NOT_EXPORTED 会
 * 把原版跨模块广播挡掉，属于改变语义。34 以下仍按原调用，不引入新行为。
 *
 * 调用点由 `patches/patch_receiver_exports.py` 把 `Context.registerReceiver`
 * 换成这里的同名同参入口，原版 Java 逻辑一个字不动。
 */
public final class HvrReceiverCompat {
    private static final String TAG = "HvrReceiver";

    private HvrReceiverCompat() {
    }

    private static boolean needsFlag() {
        return Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE;
    }

    /** 原版：registerReceiver(BroadcastReceiver, IntentFilter) */
    public static Intent registerReceiver(Context context, BroadcastReceiver receiver,
                                          IntentFilter filter) {
        if (context != null && receiver != null && filter != null && needsFlag()) {
            try {
                return context.registerReceiver(receiver, filter, Context.RECEIVER_EXPORTED);
            } catch (Throwable error) {
                Log.w(TAG, "registerReceiver(exported) failed: " + error);
            }
        }
        return context == null ? null : context.registerReceiver(receiver, filter);
    }

    /**
     * 原版：registerReceiver(BroadcastReceiver, IntentFilter, String, Handler)
     * 带权限的那种，导出属性照旧取 EXPORTED（权限本身才是访问控制）。
     */
    public static Intent registerReceiver(Context context, BroadcastReceiver receiver,
                                          IntentFilter filter, String broadcastPermission,
                                          Handler scheduler) {
        if (context != null && receiver != null && filter != null && needsFlag()) {
            try {
                return context.registerReceiver(receiver, filter, broadcastPermission,
                        scheduler, Context.RECEIVER_EXPORTED);
            } catch (Throwable error) {
                Log.w(TAG, "registerReceiver(exported, permission) failed: " + error);
            }
        }
        return context == null ? null
                : context.registerReceiver(receiver, filter, broadcastPermission, scheduler);
    }
}
