package com.huawei.android.os;

import android.content.Context;
import android.os.SystemProperties;
import android.text.TextUtils;
import android.util.Log;

import com.huawei.android.content.ContextEx;
import com.huawei.vrframework.compat.VrPropertyStore;

/**
 * 照官方实现：这就是 android.os.SystemProperties 的一层同名封装。
 *
 * 官方原件（原厂件/hwframework.jar 的 com/huawei/android/os/SystemPropertiesEx.smali）
 * 五个方法全部直连 android.os.SystemProperties：
 *
 *     get(String) / get(String,String) / getInt(String,int) /
 *     getBoolean(String,boolean) / set(String,String)
 *
 * 这里保持同样的调用方式（编译期由 shared/stubs 提供存根，运行期用设备上的
 * 真实类；直接调用不受 targetSdk≥28 的 hidden API 反射限制）。
 *
 * 唯一换掉的一层：**VR 状态键的后端**。
 * EMUI 上这组 key 是普通系统属性，七个模块靠读写它们互相通知状态；通用安卓
 * 不允许普通应用写系统属性（property_service 直接拒绝），所以这组 key 改成
 * 走签名权限保护的跨进程注册表（VrPropertyStore，桌面托管、落盘持久化）。
 * 读的时候先读真实属性、没有再读注册表 —— 在真 EMUI 上行为与原版一致。
 *
 * key 清单来自实测调用点，不是猜的：
 *
 *     python tools/vr-state-keys.py
 *
 *   sys.glass.state                  vrservice 写（进入/退出 VR）
 *   hw.vr.environment.status         vrservice 写（环境状态）
 *   hw.vr.virtualmode                投屏写
 *   vr.mode.enter                    vrservice 读
 *   persist.sys.vr_left_hand_mode    桌面写（左右手）
 *   persist.sys.vr_def_brightness    桌面读（默认亮度）
 *   persist.sys.vr_not_check_ver     vrservice 读
 *
 * 另外一个是「设备是否支持 VR」的只读断言：
 *   ro.vr.surport —— 由**兼容平台是否真的装着**回答（注册表 provider 是否存在），
 *                    不是写死的常量；
 *   ro.vr.mode    —— EMUI 的副屏 VR 模式，本移植没有实现，就不特判，
 *                    走真实属性（三星上为空 → 取调用方给的默认值 false），
 *                    不假装支持。
 */
public final class SystemPropertiesEx {

    private static final String TAG = "HvrVrProp";

    private static final String AUTHORITY = "com.huawei.vrlauncherx.registry";

    private static final String KEY_VR_SUPPORT = "ro.vr.surport";

    private static final String[] VR_STATE_KEYS = {
        "sys.glass.state",
        "hw.vr.environment.status",
        "hw.vr.virtualmode",
        "vr.mode.enter",
        "persist.sys.vr_left_hand_mode",
        "persist.sys.vr_def_brightness",
        "persist.sys.vr_not_check_ver",
    };

    /** 兼容平台是否装着：只算一次（装卸应用会重启进程）。 */
    private static Boolean platformInstalled;

    private SystemPropertiesEx() {
    }

    private static boolean isVrStateKey(String key) {
        for (String candidate : VR_STATE_KEYS) {
            if (candidate.equals(key)) {
                return true;
            }
        }
        return false;
    }

    /**
     * 兼容 VR 平台是否在这台设备上：问 PackageManager 里有没有那个 provider。
     * 这是真实可查的事实，不是常量。
     */
    private static boolean isVrPlatformInstalled() {
        if (platformInstalled != null) {
            return platformInstalled;
        }
        Context context = ContextEx.currentApplication();
        if (context == null) {
            return false;
        }
        try {
            boolean found = context.getPackageManager()
                    .resolveContentProvider(AUTHORITY, 0) != null;
            if (found) {
                platformInstalled = Boolean.TRUE;
            }
            return found;
        } catch (Throwable error) {
            Log.w(TAG, "resolve platform registry failed", error);
            return false;
        }
    }

    /** VR 状态键：先看真实属性（真 EMUI 上就是它），没有再看兼容注册表。 */
    private static String readVrState(String key, String defaultValue) {
        String platform = SystemProperties.get(key, "");
        if (!TextUtils.isEmpty(platform)) {
            return platform;
        }
        String stored = VrPropertyStore.get(key);
        return TextUtils.isEmpty(stored) ? defaultValue : stored;
    }

    public static String get(String key) {
        return get(key, "");
    }

    public static String get(String key, String defaultValue) {
        if (key == null) {
            return defaultValue;
        }
        if (KEY_VR_SUPPORT.equals(key)) {
            String platform = SystemProperties.get(key, "");
            if (!TextUtils.isEmpty(platform)) {
                return platform;
            }
            return Boolean.toString(isVrPlatformInstalled());
        }
        if (isVrStateKey(key)) {
            return readVrState(key, defaultValue);
        }
        return SystemProperties.get(key, defaultValue);
    }

    public static int getInt(String key, int defaultValue) {
        String value = get(key, null);
        if (value == null) {
            return defaultValue;
        }
        try {
            return Integer.parseInt(value.trim());
        } catch (NumberFormatException error) {
            return defaultValue;
        }
    }

    public static boolean getBoolean(String key, boolean defaultValue) {
        String value = get(key, null);
        if (value == null) {
            return defaultValue;
        }
        return Boolean.parseBoolean(value.trim());
    }

    public static void set(String key, String value) {
        if (key == null) {
            return;
        }
        // 原版是直接 set；通用安卓上普通应用没有写系统属性的权限，
        // 所以这一层要自己接住失败，不能让它抛回原版逻辑。
        try {
            SystemProperties.set(key, value);
        } catch (Throwable error) {
            Log.w(TAG, "platform refused set(" + key + "): " + error);
        }
        if (isVrStateKey(key)) {
            VrPropertyStore.set(key, value);
        }
    }
}
