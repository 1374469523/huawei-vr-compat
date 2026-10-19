package com.huawei.vrframework.compat;

import android.app.Activity;
import android.content.Context;
import android.content.pm.ApplicationInfo;
import android.util.Log;

import java.io.File;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;

import dalvik.system.DexClassLoader;

/**
 * 补上 EMUI 侧「系统/框架调用 SDK init」这一步。

 * 真机日志（com.huawei.vrlauncherx，2026-09-16）：
 *
 * <pre>
 *   E/HvrFramework: [HvrFramework.cpp:CallStaticBooleanMethod](463): CallStaticBooleanMethodV == false   (70199 次)
 *   E/VrHelmetExt: mVRDeviceExt is null                                                                   (8267 次)
 * </pre>
 *
 * 这两条同一个根因：SDK 的 Java 入口从没被调用过。
 *
 *   VrFramework.isHW6DoFHeaderAvailable()
 *       -> if (VrFramework.mAppActivity == null) { Log.e("VrFramework","App activity is null"); return false; }
 *   VrHelmetExt.isEnable()
 *       -> if (mVRDeviceExt == null) { ... VrInteractiveDeviceManager.getInstance().init(mActivity) }
 *       （而 mActivity / mDeviceExt 只在 VrHelmetExt.init(Activity) 里建立）
 *
 * 在 EMUI 上，这一步由系统/框架在 VR 应用起来时触发（原厂 SDK 集成里由应用或框架调用
 * `VrFramework.init(activity)` / `VrHelmetExt.init(activity)`）。通用安卓上没人替它调，
 * 于是 mAppActivity 恒为 null：native 每帧问一次静态 boolean 就得到 false，
 * VrHelmetExt 也永远建不出 VrInteractiveDeviceManager。
 *
 * 这里只做「把真实的 Activity 交给 SDK」这一件事，不代答任何状态、不编数据。
 * 用反射而不是直接引用，是因为 SDK 的类来自 LibUpdateClient 动态装载的代码，
 * 走反射可以避免类加载器差异；调用失败就如实记录，不伪造成功。
 */
public final class VrFrameworkBootstrap {
    private static final String TAG = "HvrVrFramework";
    private static final String VR_FRAMEWORK = "com.huawei.vrframework.VrFramework";
    private static final String VR_HELMET_EXT = "com.huawei.vrframework.VrHelmetExt";

    /** SDK 包：`VrFramework` / `VrHelmetExt` 这两个类只存在于它的 dex 里。 */
    private static final String SDK_PACKAGE = "com.huawei.hvrsdkserverapp";

    private static volatile Activity activity;
    private static volatile ClassLoader sdkLoader;

    private VrFrameworkBootstrap() {
    }

    public static void init(Activity source) {
        if (source == null) {
            return;
        }
        activity = source;
        boolean framework = callFrameworkInit(source);
        boolean helmet = callHelmetInit(source);
        Log.i(TAG, "vr framework bootstrap: framework=" + framework + " helmet=" + helmet);
    }

    private static boolean callFrameworkInit(Activity source) {
        try {
            Class<?> type = resolve(VR_FRAMEWORK);
            Method method = type.getMethod("init", Activity.class);
            Object result = method.invoke(null, source);
            return result instanceof Boolean ? (Boolean) result : result != null;
        } catch (Throwable error) {
            Log.w(TAG, "VrFramework.init failed: " + error);
            return false;
        }
    }

    private static boolean callHelmetInit(Activity source) {
        try {
            Class<?> type = resolve(VR_HELMET_EXT);
            Object instance = type.getMethod("getInstanceObject").invoke(null);
            if (instance == null) {
                Log.w(TAG, "VrHelmetExt.getInstanceObject() returned null");
                return false;
            }
            Method method = type.getMethod("init", Activity.class);
            Object result;
            try {
                result = method.invoke(instance, source);
            } catch (InvocationTargetException failure) {
                // 原版 init() 内部抛了什么，要如实打出来 —— 只报一个布尔等于没证据。
                Log.w(TAG, "VrHelmetExt.init threw: " + failure.getCause(), failure.getCause());
                return false;
            }
            // isEnable() 是原版自己判断「姿态链路是否可用」的口径，一起记下来。
            String enabled = "unknown";
            try {
                Object value = type.getMethod("isEnable").invoke(instance);
                enabled = String.valueOf(value);
            } catch (Throwable ignored) {
                // 读不到就算了，不代答。
            }
            Log.i(TAG, "VrHelmetExt.init returned " + result + ", isEnable=" + enabled);
            return result instanceof Boolean ? (Boolean) result : result != null;
        } catch (Throwable error) {
            Log.w(TAG, "VrHelmetExt.init failed: " + error);
            return false;
        }
    }

    /**
     * 先按应用类加载器找，找不到再用 SDK 包的 dex 加载器找。
     *
     * `VrFramework` / `VrHelmetExt` 不在本进程的 dex 里：原厂是 `LibUpdate` 用
     * `DexClassLoader` 打开已安装 SDK 包的 dex，再把类句柄交给原生层
     * （真机日志 `LibUpdateCall: loadRemoteClass succeed / Run update 2.0 succeed`）。
     * 之前这里只用 `Class.forName`，于是固定报
     * `ClassNotFoundException: com.huawei.vrframework.VrHelmetExt`，
     * 姿态链起不来（`Fail to GetPosture` 每帧刷）。
     *
     * 这里做的是同一件事：按包名拿到 SDK APK 的 dex 路径建一个 DexClassLoader。
     * 不复制类、不实现姿态，只把类解析到它本来就在的地方。
     */
    private static Class<?> resolve(String name) throws ClassNotFoundException {
        try {
            return Class.forName(name);
        } catch (ClassNotFoundException notInApp) {
            ClassLoader loader = sdkClassLoader();
            if (loader == null) {
                throw notInApp;
            }
            return Class.forName(name, true, loader);
        }
    }

    private static ClassLoader sdkClassLoader() {
        ClassLoader cached = sdkLoader;
        if (cached != null) {
            return cached;
        }
        synchronized (VrFrameworkBootstrap.class) {
            if (sdkLoader != null) {
                return sdkLoader;
            }
            Context context = com.huawei.android.content.ContextEx.currentApplication();
            if (context == null) {
                Log.w(TAG, "no application context; cannot load the SDK classes");
                return null;
            }
            try {
                ApplicationInfo info = context.getPackageManager()
                        .getApplicationInfo(SDK_PACKAGE, 0);
                StringBuilder path = new StringBuilder(info.sourceDir);
                if (info.splitSourceDirs != null) {
                    for (String split : info.splitSourceDirs) {
                        path.append(File.pathSeparator).append(split);
                    }
                }
                File optimized = new File(context.getCodeCacheDir(), "hvr-sdk");
                optimized.mkdirs();
                ClassLoader loader = new DexClassLoader(path.toString(),
                        optimized.getAbsolutePath(), info.nativeLibraryDir,
                        VrFrameworkBootstrap.class.getClassLoader());
                sdkLoader = loader;
                Log.i(TAG, "sdk class loader ready: " + info.sourceDir);
                return loader;
            } catch (Throwable error) {
                Log.w(TAG, "sdk class loader unavailable: " + error);
                return null;
            }
        }
    }
}
