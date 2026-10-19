package com.huawei.android.os;

import android.content.ContentResolver;
import android.content.Context;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.util.Log;

import com.huawei.android.content.ContextEx;

import java.util.HashMap;
import java.util.Map;

/**
 * Huawei's ServiceManager extension.
 *
 * On EMUI this is a thin wrapper over the platform ServiceManager, so a name
 * added by one process is visible to every other process. An application cannot
 * add a name to the platform registry on a common Android device, so the compat
 * layer keeps its own registry with the same addService semantics:
 *
 *   * same process  - a plain map, exactly as before;
 *   * other process - the entry is published to the desktop package's registry
 *     provider (content://com.huawei.vrlauncherx.registry), which is the compat
 *     stand-in for the platform registry. That package hosts it because its
 *     manifest is rebuilt by aapt2, so android:exported is compiled the way the
 *     platform expects (see docs/PATCH_AUDIT.md 第 29 节).
 *
 * Publishing is best effort: if the desktop package is not installed the entry
 * stays process-local and lookups from other processes report "not registered".
 * Nothing is invented.
 */
public final class ServiceManagerEx {

    private static final String TAG = "HvrServiceManagerEx";

    /** 注册表由桌面包托管，见 VrSystemRegistryProvider。 */
    private static final String REGISTRY_URI =
            "content://com.huawei.vrlauncherx.registry";
    private static final String METHOD_GET_SERVICE = "getService";
    private static final String KEY_BINDER = "binder";

    /**
     * 注册表由桌面包托管，条目只存在于它的进程内存里；桌面进程一旦重启就空了。
     * 原版是平台注册表，不存在这个问题。这里由发布方定时补发：代价是每秒一次
     * 本地 binder 往返，换来「消费者任何时候查都能拿到」。
     */
    private static final long REPUBLISH_INTERVAL_MS = 1000L;
    private static final Handler REPUBLISH_HANDLER = new Handler(Looper.getMainLooper());
    private static final Runnable REPUBLISH = new Runnable() {
        @Override
        public void run() {
            Map<String, IBinder> snapshot;
            synchronized (SERVICES) {
                snapshot = new HashMap<String, IBinder>(SERVICES);
            }
            for (Map.Entry<String, IBinder> entry : snapshot.entrySet()) {
                publishToRegistry(entry.getKey(), entry.getValue());
            }
            REPUBLISH_HANDLER.postDelayed(this, REPUBLISH_INTERVAL_MS);
        }
    };
    private static boolean republishScheduled;

    private static final Map<String, IBinder> SERVICES = new HashMap<String, IBinder>();

    private ServiceManagerEx() {
    }

    /**
     * 官方语义：任何进程都能按名字取回 binder（平台 ServiceManager 是全局的）。
     *
     * 先查本进程的 map；没有再问一遍桌面托管的注册表。注册表里存的就是发布方
     * 交上来的那个 binder，查不到就返回 null，让调用方走它自己的 null 分支
     * （实测桌面就是这么做的：{@code HvrVrSystem: vr_system is not registered;
     * returning null}）。
     *
     * 为什么必须查注册表：发布方和消费者不在同一个进程。桌面的 VRService 跑在
     * {@code com.huawei.vrservice} 进程里并把 {@code vr_system} 交给注册表，而
     * 真正要用它的 Unity 空间跑在桌面主进程 —— 只查本地 map 时主进程永远读到
     * null，空间直接退出（2026-09-16 真机日志：
     * {@code UnityPlayerActivity: IVRSystemServiceManager is null} →
     * {@code onDestroy: Not in VrMode. Then return!}）。
     */
    public static IBinder getService(String name) {
        if (name == null) {
            return null;
        }
        synchronized (SERVICES) {
            IBinder local = SERVICES.get(name);
            if (local != null && local.isBinderAlive()) {
                return local;
            }
        }
        return lookupInRegistry(name);
    }

    private static IBinder lookupInRegistry(String name) {
        Context context = ContextEx.currentApplication();
        if (context == null) {
            Log.w(TAG, "no application context; cannot look up " + name);
            return null;
        }
        try {
            Bundle answer = context.getContentResolver().call(
                    Uri.parse(REGISTRY_URI), METHOD_GET_SERVICE, name, null);
            if (answer == null) {
                return null;
            }
            IBinder binder = answer.getBinder(KEY_BINDER);
            if (binder == null) {
                return null;
            }
            // 缓存一份，避免每次查询都过一次 binder 往返；桌面每秒补发一次，
            // 条目被替换时 isBinderAlive() 会让上面那次本地查询重新去问。
            synchronized (SERVICES) {
                SERVICES.put(name, binder);
            }
            return binder;
        } catch (Throwable error) {
            Log.w(TAG, "cannot look up " + name + " in the registry", error);
            return null;
        }
    }

    public static void addService(String name, IBinder service) {
        if (name == null || service == null) return;
        synchronized (SERVICES) {
            SERVICES.put(name, service);
        }
        publishToRegistry(name, service);
        if (!republishScheduled) {
            republishScheduled = true;
            REPUBLISH_HANDLER.post(REPUBLISH);
        }
    }

    public static void removeService(String name) {
        synchronized (SERVICES) {
            SERVICES.remove(name);
        }
    }

    private static void publishToRegistry(String name, IBinder service) {
        Context context = ContextEx.currentApplication();
        if (context == null) {
            Log.w(TAG, "no application context; " + name + " stays process-local");
            return;
        }
        try {
            Bundle extras = new Bundle();
            extras.putString("name", name);
            extras.putBinder("binder", service);
            ContentResolver resolver = context.getContentResolver();
            Bundle answer = resolver.call(
                    Uri.parse("content://com.huawei.vrlauncherx.registry"),
                    "putService", name, extras);
            if (answer == null) {
                Log.w(TAG, "registry rejected " + name);
            }
        } catch (Throwable error) {
            Log.w(TAG, "cannot publish " + name + " to the registry", error);
        }
    }
}
