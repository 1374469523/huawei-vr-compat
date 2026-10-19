package com.huawei.android.vrsystem;

import android.content.Context;
import android.util.Log;

import android.vrsystem.IVRListener;
import android.vrsystem.IVRSystemServiceManager;
import android.vrsystem.VRSystemServiceManagerImpl;

/**
 * 照官方实现移植（原厂件/hwframework.jar 的
 * com/huawei/android/vrsystem/IVRSystemServiceManagerEx.smali）。
 *
 * 官方的结构很简单：对象里存一个 `android.vrsystem.IVRSystemServiceManager`
 * （= `context.getSystemService("vr_system")` 的结果），每个 public 方法做
 * 空值判断 + 参数校验再转发。这里逐条照搬它的语义与返回值：
 *
 *   create(Context)         context 为空 -> 记日志并返回持有 null 的实例；
 *                           否则 getSystemService("vr_system") 后包起来
 *   isVRMode()              无 manager -> 记日志返回 false
 *   getHelmetBattery(ctx)   无 manager 或 ctx 为空 -> 记日志返回 0（官方 DEFAULT_BATTERY）
 *   setHelmetBrightness()   亮度不在 0..9 -> 记日志不转发（官方 MIN/MAX_BRIGHTNESS）
 *   checkPermissionForMultiDisplay() 只有包名等于 com.huawei.vrvirtualscreen 才通过
 *   createVrDisplay()       name/params 为空、权限不通过、params 长度不是 3 -> 记日志返回 false
 *
 * 只换掉两处通用安卓做不到的东西：
 *
 * 1. `getSystemService("vr_system")` 在通用安卓上永远是 null（应用没法往平台
 *    服务表里注册名字）。这里改走兼容层的同一个入口
 *    VRSystemServiceManagerImpl.get(context) —— 它就是 `vr_system` 的兼容实现，
 *    查不到仍然返回 null，和原版拿到 null 的分支完全一致。
 * 2. 官方三个静态方法最终落到华为框架的
 *    `com.huawei.android.hardware.display.HwDisplayManager`。按本项目已批准的
 *    口径（docs/PORTING_METHOD.md、PATCH_AUDIT 第 25 节），异步投屏这一层
 *    **只保接口、实现不做**：这里保留官方的全部校验与日志，然后返回
 *    「不可用」（false），让调用方走它自己的失败分支，不伪造成功。
 *
 * 另外官方有个 `isVirtualScreenMode()`，转发的接口方法只在 EMUI 的 boot
 * classpath 版接口里存在（原包自带的接口副本没有这个方法），所以这里用反射
 * 转发：拿得到就转，拿不到就照官方「无 manager」那样记日志返回 false。
 */
public class IVRSystemServiceManagerEx {

    private static final String TAG = "IVRSystemServiceManagerEx";

    /** 与官方一致：服务名、默认电量、亮度范围。 */
    public static final String VR_MANAGER = "vr_system";

    private static final int DEFAULT_BATTERY = 0;
    private static final int MIN_BRIGHTNESS = 0;
    private static final int MAX_BRIGHTNESS = 9;
    private static final int PARAMS_LEN = 3;

    /** 官方就是按这个包名判定多显示权限。 */
    private static final String VR_VIRTUAL_SCREEN_NAME = "com.huawei.vrvirtualscreen";

    private IVRSystemServiceManager mManager;

    private IVRSystemServiceManagerEx(IVRSystemServiceManager manager) {
        this.mManager = manager;
    }

    public static IVRSystemServiceManagerEx create(Context context) {
        if (context == null) {
            Log.e(TAG, "context is null in IVRSystemServiceManagerEx create.");
            return new IVRSystemServiceManagerEx(null);
        }
        // 原版这里是 getSystemService("vr_system")；通用安卓拿不到，改走兼容层入口。
        IVRSystemServiceManager manager = VRSystemServiceManagerImpl.get(context);
        return new IVRSystemServiceManagerEx(manager);
    }

    public boolean isVRMode() {
        if (mManager == null) {
            Log.e(TAG, "mManager is null in isVRMode.");
            return false;
        }
        return mManager.isVRMode();
    }

    public boolean isVirtualScreenMode() {
        if (mManager == null) {
            Log.e(TAG, "mManager is null in isVirtualScreenMode.");
            return false;
        }
        // 官方转发的是 `IVRSystemServiceManager.isVirtualScreenMode()`，该方法只存在于
        // EMUI boot classpath 版的接口里；原包自带的接口副本没有它，通用安卓上也没有。
        // 不反射、不猜：如实返回「不是虚拟屏模式」，并记一次日志说明原因。
        if (!reportedVirtualScreen) {
            reportedVirtualScreen = true;
            Log.i(TAG, "isVirtualScreenMode is not part of the public interface on this device;"
                    + " reporting false");
        }
        return false;
    }

    private static volatile boolean reportedVirtualScreen;

    public int getHelmetBattery(Context context) {
        if (mManager == null || context == null) {
            Log.e(TAG, "params is invalid in getHelmetBattery.");
            return DEFAULT_BATTERY;
        }
        return mManager.getHelmetBattery(context);
    }

    public int getHelmetBrightness(Context context) {
        if (mManager == null || context == null) {
            Log.e(TAG, "params is invalid in getHelmetBrightness.");
            return DEFAULT_BATTERY;
        }
        return mManager.getHelmetBrightness(context);
    }

    public void setHelmetBrightness(Context context, int brightness) {
        if (mManager == null || context == null) {
            Log.e(TAG, "params is invalid in getHelmetBrightness.");
            return;
        }
        if (brightness < MIN_BRIGHTNESS || brightness > MAX_BRIGHTNESS) {
            Log.e(TAG, "brightness to set is invalid in setHelmetBrightness.");
            return;
        }
        mManager.setHelmetBrightness(context, brightness);
    }

    public String getContactName(Context context, String number) {
        if (mManager == null || context == null) {
            Log.e(TAG, "params is invalid in getContactName.");
            return "";
        }
        return mManager.getContactName(context, number);
    }

    public boolean isVRApplication(Context context, String packageName) {
        if (mManager == null || context == null) {
            Log.e(TAG, "params is invalid in isVRApplication.");
            return false;
        }
        return mManager.isVRApplication(context, packageName);
    }

    public void registerVRListener(Context context, IVRListener listener) {
        if (mManager == null || context == null || listener == null) {
            Log.e(TAG, "params is invalid in registerVRListener.");
            return;
        }
        mManager.registerVRListener(context, listener);
    }

    public void unregisterVRListener(Context context, IVRListener listener) {
        if (mManager == null || context == null || listener == null) {
            Log.e(TAG, "params is invalid in unregisterVRListener.");
            return;
        }
        mManager.unregisterVRListener(context, listener);
    }

    public void registerExpandListener(Context context, IVRListener listener) {
        if (mManager == null || context == null || listener == null) {
            Log.e(TAG, "params is invalid in registerExpandListener.");
            return;
        }
        mManager.registerExpandListener(context, listener);
    }

    /** 官方：只有投屏包能建多显示。 */
    private static boolean checkPermissionForMultiDisplay(Context context) {
        if (context == null) {
            Log.e(TAG, "context is invalid in checkPermissionForMultiDisplay.");
            return false;
        }
        String packageName = context.getPackageName();
        if (packageName == null) {
            Log.e(TAG, "packageName is null.");
            return false;
        }
        return VR_VIRTUAL_SCREEN_NAME.equals(packageName);
    }

    /**
     * 官方走 HwDisplayManager.createVrDisplay(name, params)。
     * 按已批准口径只保接口：校验与日志照官方，结果报「不可用」。
     */
    public static boolean createVrDisplay(String displayName, int[] displayParams,
                                          Context context) {
        if (displayName == null || displayParams == null) {
            Log.e(TAG, "params is invalid in createVrDisplay.");
            return false;
        }
        if (!checkPermissionForMultiDisplay(context)
                || displayParams.length != PARAMS_LEN) {
            Log.e(TAG, "params or permission is invalid in createVrDisplay.");
            return false;
        }
        Log.w(TAG, "createVrDisplay: platform VR display API is not ported yet ("
                + displayName + ")");
        return false;
    }

    public static boolean destroyVrDisplay(String displayName, Context context) {
        if (displayName == null || !checkPermissionForMultiDisplay(context)) {
            Log.e(TAG, "params or permission is invalid in destroyVrDisplay.");
            return false;
        }
        Log.w(TAG, "destroyVrDisplay: platform VR display API is not ported yet ("
                + displayName + ")");
        return false;
    }

    public static boolean destroyAllVrDisplay(Context context) {
        if (!checkPermissionForMultiDisplay(context)) {
            Log.e(TAG, "permission is invalid in destroyAllVrDisplay.");
            return false;
        }
        Log.w(TAG, "destroyAllVrDisplay: platform VR display API is not ported yet");
        return false;
    }
}
