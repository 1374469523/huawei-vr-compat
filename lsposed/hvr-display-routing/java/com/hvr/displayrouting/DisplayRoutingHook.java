package com.hvr.displayrouting;

import android.content.Context;
import android.content.pm.ActivityInfo;
import android.content.pm.PackageManager;
import android.os.Build;

import java.util.HashSet;
import java.util.Set;

import de.robv.android.xposed.IXposedHookLoadPackage;
import de.robv.android.xposed.XC_MethodHook;
import de.robv.android.xposed.XposedBridge;
import de.robv.android.xposed.XposedHelpers;
import de.robv.android.xposed.callbacks.XC_LoadPackage;

/**
 * 放行「把 VR 活动启动到自建虚拟屏上」这一个动作。
 *
 * 背景（真机 SM-F731U1 / Android 16，见 docs/PATCH_AUDIT.md 第 65 节）：
 * 原版由 EMUI 的 VR 模式把 VR 应用放到 `HUAWEI VR Display` 那块虚拟屏上；
 * 通用安卓里我们自己用公开 API 建了同一块屏（名字、尺寸都对齐），但往它上面
 * 启动活动会被平台拒绝：
 *
 *     SecurityException: Permission Denial: starting Intent {...}
 *       from ProcessRecord{...} (pid=..., uid=10421) with launchDisplayId=27
 *
 * 原因是 `ActivityTaskSupervisor.isCallerAllowedToLaunchOnDisplay` 先判
 * 「这块屏是否 trusted」—— 非系统进程建的虚拟屏都不 trusted，于是连屏的
 * 拥有者自己也不放行；要过这一关需要 `INTERNAL_SYSTEM_WINDOW`（signature 级），
 * 普通应用拿不到。
 *
 * 本模块只做一件事：当**调用方是我们这七个包之一**、且**目标屏不是默认屏**时，
 * 让那个判断直接返回 true。其它任何情况（别的应用、默认屏）一律不干预。
 *
 * 目标方法签名（从设备 `/system/framework/services.jar` 里查出来的）：
 *
 *     com.android.server.wm.ActivityTaskSupervisor
 *       isCallerAllowedToLaunchOnDisplay(int, int, int, ActivityInfo) : boolean
 */
public final class DisplayRoutingHook implements IXposedHookLoadPackage {
    private static final String TAG = "HvrDisplayRouting";

    private static final String SUPERVISOR = "com.android.server.wm.ActivityTaskSupervisor";
    private static final String METHOD = "isCallerAllowedToLaunchOnDisplay";

    /** 只放行华为 VR 这七个包（原版六个 + 从固件提取的 vrservice）。 */
    private static final String[] PACKAGES = {
            "com.huawei.vrlauncherx",
            "com.huawei.himovie.vr",
            "com.huawei.vrvirtualscreen",
            "com.huawei.appmarket.vr",
            "com.huawei.vrhandle",
            "com.huawei.hvrsdkserverapp",
            "com.huawei.vrservice",
    };

    private static Set<Integer> ourUids;

    @Override
    public void handleLoadPackage(XC_LoadPackage.LoadPackageParam param) {
        if (!"android".equals(param.packageName)) {
            return;
        }
        try {
            XposedHelpers.findAndHookMethod(SUPERVISOR, param.classLoader, METHOD,
                    int.class, int.class, int.class, ActivityInfo.class,
                    new XC_MethodHook() {
                        @Override
                        protected void beforeHookedMethod(MethodHookParam call) {
                            int callingUid = (Integer) call.args[0];
                            int launchDisplayId = (Integer) call.args[2];
                            if (launchDisplayId <= 0) {
                                return;   // 默认屏，原样走原逻辑
                            }
                            if (isOurUid(call.thisObject, callingUid)) {
                                XposedBridge.log(TAG + ": allow uid " + callingUid
                                        + " to launch on display " + launchDisplayId);
                                call.setResult(Boolean.TRUE);
                            }
                        }
                    });
            XposedBridge.log(TAG + ": hooked " + SUPERVISOR + "#" + METHOD);
        } catch (Throwable error) {
            XposedBridge.log(TAG + ": hook failed on SDK " + Build.VERSION.SDK_INT
                    + " -> " + error);
        }
    }

    /** 调用方的 uid 是否属于我们这七个包。 */
    private static boolean isOurUid(Object supervisor, int uid) {
        Set<Integer> known = ourUids;
        if (known != null) {
            return known.contains(uid);
        }
        Set<Integer> found = new HashSet<>();
        try {
            Context context = systemContext(supervisor);
            if (context != null) {
                PackageManager manager = context.getPackageManager();
                for (String packageName : PACKAGES) {
                    try {
                        found.add(manager.getPackageUid(packageName, 0));
                    } catch (Throwable ignored) {
                        // 该包没装，跳过
                    }
                }
                ourUids = found;
            }
        } catch (Throwable error) {
            XposedBridge.log(TAG + ": uid lookup failed: " + error);
        }
        return found.contains(uid);
    }

    /**
     * 从 ActivityTaskSupervisor 里取系统 Context：
     * `ActivityTaskSupervisor.mService` 是 `ActivityTaskManagerService`，
     * 它的 `mContext` 就是 system_server 的 Context。字段名跟 ROM 走，
     * 取不到就退化成「每次都重新查一遍」，不影响功能。
     */
    private static Context systemContext(Object supervisor) {
        try {
            Object service = XposedHelpers.getObjectField(supervisor, "mService");
            return (Context) XposedHelpers.getObjectField(service, "mContext");
        } catch (Throwable error) {
            XposedBridge.log(TAG + ": system context unavailable: " + error);
            return null;
        }
    }
}
