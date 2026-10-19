package com.huawei.vrframework.compat;

import android.app.ActivityManager;
import android.content.ComponentName;
import android.content.Context;
import android.util.Log;

import java.util.List;

/**
 * 原版 {@code z0/c.g(Context)}（日志名 getForeActivity）用
 * {@code ActivityManager.getRunningTasks(1)} 取前台 activity：

 * <pre>
 *     I/VRService_Client_VRManager: top activity is null
 *     E/VRService_Client_VRManager: error, RunningTaskInfo wrong.
 * </pre>
 *
 * `getRunningTasks` 从 Android 5 起只返回**调用者自己的**任务；要看别人的任务需要
 * `android.permission.REAL_GET_TASKS`（签名级，通用安卓不可能拿到，本包 manifest
 * 里虽然申请了也不会被授予）。真机上它常常返回空列表或 topActivity=null，于是
 * 原版那个「记住当前前台 activity」的字段一直是 null。
 *
 * 调用方是 VRManager 自己，关心的是「本应用自己的栈顶 activity」，公开 API
 * {@code ActivityManager.getAppTasks()} 正好给出这个信息（无需任何权限）。
 * 这里只换数据来源，语义保持不变：取不到就返回 null，让原版走它自己的失败分支。
 */
public final class VrTopActivity {
    private static final String TAG = "HvrTopActivity";

    private VrTopActivity() {
    }

    public static ComponentName current(Context context) {
        if (context == null) {
            return null;
        }
        try {
            ActivityManager manager =
                    (ActivityManager) context.getSystemService(Context.ACTIVITY_SERVICE);
            if (manager == null) {
                return null;
            }
            List<ActivityManager.AppTask> tasks = manager.getAppTasks();
            if (tasks == null || tasks.isEmpty()) {
                return null;
            }
            ActivityManager.RecentTaskInfo info = tasks.get(0).getTaskInfo();
            if (info == null) {
                return null;
            }
            return info.topActivity;
        } catch (Throwable error) {
            // 拿不到就返回 null：与原版失败分支一致，不自造前台 activity。
            Log.w(TAG, "top activity probe failed", error);
            return null;
        }
    }
}
