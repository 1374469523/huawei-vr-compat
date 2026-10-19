package com.huawei.android.content;

import android.app.Activity;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.os.Handler;
import android.os.UserHandle;

/**
 * Huawei's Context extension. registerReceiverAsUser is a hidden platform API;
 * on common Android the same registration is done with the public
 * Context.registerReceiver, which registers for the caller's own user. The
 * receiver, filter and handler are passed through unchanged.
 */
public final class ContextEx {
    /**
     * 本应用自己的 Application context，由兼容层注入的 provider
     * （com.huawei.vrframework.compat.HvrContextProvider）在进程启动时填进来。
     *
     * 为什么需要它：下面两条路都不是每个进程都能走通 ——
     * Unity 那条只在 Unity 进程成立；ActivityThread.currentApplication() 是
     * hidden API，反射在 targetSdk≥28 上会被拦。provider 是平台自己实例化的，
     * 这里拿到的就是真实 application context，没有任何合成。
     */
    private static volatile Context applicationContext;

    private ContextEx() {
    }

    public static void setApplication(Context context) {
        if (context == null) {
            return;
        }
        Context application = context.getApplicationContext();
        applicationContext = application != null ? application : context;
    }

    public static Context currentApplication() {
        Context known = applicationContext;
        if (known != null) {
            return known;
        }
        try {
            Class<?> player = Class.forName("com.unity3d.player.UnityPlayer");
            Object activity = player.getField("currentActivity").get(null);
            if (activity instanceof Activity) return ((Activity) activity).getApplicationContext();
        } catch (Throwable ignored) {
            // Not a Unity process.
        }
        // 之前还有一条 `ActivityThread.currentApplication()` 反射兜底（hidden API，
        // targetSdk≥28 上会被拦）。**已删除**：不再有 hidden API 反射。
        // 两条公开来源都没有就返回 null，调用方按自己的 null 分支处理。
        return null;
    }

    public static Intent registerReceiverAsUser(Context context, BroadcastReceiver receiver,
            UserHandle user, IntentFilter filter, String broadcastPermission, Handler scheduler) {
        if (context == null || receiver == null || filter == null) return null;
        try {
            // The user handle only selects whose registrations are touched; a
            // common Android app can only register for its own user, which is
            // the same user this process runs as.
            return context.registerReceiver(receiver, filter, broadcastPermission, scheduler);
        } catch (Throwable error) {
            return null;
        }
    }
}
