package com.huawei.vrframework.compat;

import android.content.ContentResolver;
import android.content.Context;
import android.net.Uri;
import android.os.Bundle;
import android.util.Log;

import com.huawei.android.content.ContextEx;

/**
 * VR 状态属性的跨进程存储（客户端侧）。
 *
 * 原厂：这些 key 是 EMUI 的系统属性，七个模块（vrservice / 桌面 / 投屏 …）
 * 靠读写它们互相通知状态，例如
 *
 *     com.huawei.vrservice.manager.AndroidAdapterManager
 *         SystemPropertiesEx.set("sys.glass.state", ...)
 *         SystemPropertiesEx.set("hw.vr.environment.status", ...)
 *     com.huawei.vrvirtualscreen.b.a.c.k.b.f
 *         SystemPropertiesEx.set("hw.vr.virtualmode", "false")
 *     com.huawei.vrlauncherx.i2.g1
 *         SystemPropertiesEx.set("persist.sys.vr_left_hand_mode", ...)
 *
 * 通用安卓上普通应用写不了系统属性（property_service 拒绝，且会抛
 * RuntimeException），所以后端换成桌面托管的注册表 provider（同一个
 * authority 已经在托管 vr_system 这个 binder），值落盘到 SharedPreferences，
 * 语义与「全局属性」一致：谁写谁读、跨进程、进程重启后仍在。
 *
 * 这里**不制造状态**：写进去的值就是调用方传进来的值；读不到就返回 null，
 * 让原版走它自己的默认分支。
 */
public final class VrPropertyStore {

    private static final String TAG = "HvrVrProp";

    /** 与 VrSystemRegistryProvider.AUTHORITY 一致（那个类只编进桌面包）。 */
    private static final String AUTHORITY = "com.huawei.vrlauncherx.registry";
    private static final String METHOD_GET = "getProp";
    private static final String METHOD_SET = "setProp";
    private static final String KEY_VALUE = "value";

    private VrPropertyStore() {
    }

    private static Uri uri() {
        return Uri.parse("content://" + AUTHORITY);
    }

    public static String get(String key) {
        if (key == null) {
            return null;
        }
        Context context = ContextEx.currentApplication();
        if (context == null) {
            return null;
        }
        try {
            ContentResolver resolver = context.getContentResolver();
            Bundle answer = resolver.call(uri(), METHOD_GET, key, null);
            return answer == null ? null : answer.getString(KEY_VALUE);
        } catch (Throwable error) {
            // 注册表不可达 == 这个值没被设置过，含义一致；不因此编一个值出来。
            Log.w(TAG, "read " + key + " failed", error);
            return null;
        }
    }

    public static void set(String key, String value) {
        if (key == null) {
            return;
        }
        Context context = ContextEx.currentApplication();
        if (context == null) {
            Log.w(TAG, "no application context yet, drop " + key);
            return;
        }
        Bundle arguments = new Bundle();
        arguments.putString(KEY_VALUE, value == null ? "" : value);
        try {
            context.getContentResolver().call(uri(), METHOD_SET, key, arguments);
        } catch (Throwable error) {
            Log.w(TAG, "write " + key + " failed", error);
        }
    }
}
