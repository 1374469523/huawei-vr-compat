package com.huawei.vrlauncherx.compat;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.net.Uri;
import android.os.Bundle;
import android.os.IBinder;
import android.util.Log;

import java.util.HashMap;
import java.util.Map;

/**
 * Cross-process registry for the "vr_system" binder, hosted by the desktop
 * package.
 *
 * Why it lives here and not in com.huawei.vrservice: on EMUI the name was kept in
 * the platform service registry (ServiceManagerEx is only a thin wrapper over
 * ServiceManager), so every process could look it up. An application cannot add
 * a name to the platform registry, so the port hosts the same name in a
 * ContentProvider instead - and a provider is only reachable when the platform
 * really parsed android:exported="true".
 *
 * The desktop package is the host because its AndroidManifest.xml is decoded and
 * rebuilt by apktool/aapt2 (text manifest), so the attribute is compiled exactly
 * like the platform expects. The same attribute written by hand into
 * com.huawei.vrservice's binary manifest was accepted by aapt2 and by our own
 * reader, but the running PackageManager still treated the provider as not
 * exported, and cross-process lookups were denied with
 *   SecurityException: ... that is not exported from UID ...
 * (see docs/PATCH_AUDIT.md 第 29 节).
 *
 * The registry stores whatever binder the provider of a name publishes; it never
 * invents an entry. Unknown names answer null.
 */
public final class VrSystemRegistryProvider extends ContentProvider {

    private static final String TAG = "HvrVrRegistry";

    public static final String AUTHORITY = "com.huawei.vrlauncherx.registry";
    public static final String METHOD_PUT = "putService";
    public static final String METHOD_GET = "getService";
    public static final String KEY_NAME = "name";
    public static final String KEY_BINDER = "binder";

    /*
     * VR 状态属性（SystemPropertiesEx 里那一组 key）也走这里。
     *
     * 原厂语义：这些 key 在 EMUI 上是普通的系统属性，七个模块靠它互相通知
     * （sys.glass.state / hw.vr.environment.status / hw.vr.virtualmode …）。
     * 通用安卓不允许普通应用写系统属性（property_service 直接拒绝），
     * 所以后端换成这个签名权限保护的注册表，并且落盘到 SharedPreferences ——
     * 「进程重启后还能读到」这一点和系统属性一致。
     */
    public static final String METHOD_GET_PROP = "getProp";
    public static final String METHOD_SET_PROP = "setProp";
    public static final String KEY_VALUE = "value";
    private static final String PROP_STORE = "hvr_vr_props";

    private static final Map<String, IBinder> SERVICES = new HashMap<String, IBinder>();

    /** onCreate 里拿到的 application context（静态辅助方法要用）。 */
    private static android.content.Context hostContext;

    /** 进程内直读，避免自己进程里的调用还要走一次 provider。 */
    public static String readProperty(String key) {
        if (key == null || hostContext == null) {
            return null;
        }
        return hostContext.getSharedPreferences(PROP_STORE, 0).getString(key, null);
    }

    public static void writeProperty(String key, String value) {
        if (key == null || hostContext == null) {
            return;
        }
        hostContext.getSharedPreferences(PROP_STORE, 0)
                .edit().putString(key, value == null ? "" : value).commit();
    }

    /** Same-process lookup, used when the caller is inside this package. */
    public static IBinder lookup(String name) {
        synchronized (SERVICES) {
            return SERVICES.get(name);
        }
    }

    public static void publish(String name, IBinder binder) {
        if (name == null || binder == null) {
            return;
        }
        synchronized (SERVICES) {
            SERVICES.put(name, binder);
        }
    }

    @Override
    public boolean onCreate() {
        // ActivityThread 在进程启动时会实例化本应用的 provider，
        // 兼容层可以借此拿到 application context（另见 CompatAppContext 的回退路径）。
        hostContext = getContext();
        com.huawei.vrservice.compat.CompatAppContext.set(hostContext);
        com.huawei.android.content.ContextEx.setApplication(hostContext);
        return true;
    }

    @Override
    public Bundle call(String method, String arg, Bundle extras) {
        String name = arg;
        if (name == null && extras != null) {
            name = extras.getString(KEY_NAME);
        }
        if (name == null) {
            return null;
        }
        if (METHOD_PUT.equals(method)) {
            if (extras == null) {
                return null;
            }
            IBinder binder = extras.getBinder(KEY_BINDER);
            if (binder == null) {
                return null;
            }
            publish(name, binder);
            Log.i(TAG, "published " + name);
            Bundle answer = new Bundle();
            answer.putBoolean("ok", true);
            return answer;
        }
        if (METHOD_GET.equals(method)) {
            IBinder binder = SERVICES.get(name);
            if (binder == null) {
                return null;
            }
            Bundle answer = new Bundle();
            answer.putBinder(KEY_BINDER, binder);
            return answer;
        }
        if (METHOD_GET_PROP.equals(method)) {
            String value = readProperty(name);
            Bundle answer = new Bundle();
            answer.putString(KEY_VALUE, value);
            return answer;
        }
        if (METHOD_SET_PROP.equals(method)) {
            String value = extras == null ? null : extras.getString(KEY_VALUE);
            writeProperty(name, value);
            Bundle answer = new Bundle();
            answer.putBoolean("ok", true);
            return answer;
        }
        return null;
    }

    @Override
    public Cursor query(Uri uri, String[] projection, String selection,
                        String[] selectionArgs, String sortOrder) {
        return null;
    }

    @Override
    public String getType(Uri uri) {
        return null;
    }

    @Override
    public Uri insert(Uri uri, ContentValues values) {
        return null;
    }

    @Override
    public int delete(Uri uri, String selection, String[] selectionArgs) {
        return 0;
    }

    @Override
    public int update(Uri uri, ContentValues values, String selection,
                      String[] selectionArgs) {
        return 0;
    }
}
