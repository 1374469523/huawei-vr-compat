package com.huawei.systemmanager.notificationmanager;

import android.content.ComponentName;
import android.content.Context;
import android.service.notification.NotificationListenerService;
import android.util.Log;

/**
 * Huawei SystemManager's notification-listener helper.
 *
 * The desktop notification monitor builds one of these in its constructor
 * (VRNotificationMonitor.java:8) and then registers itself as a system service:
 *
 *     new HwNotificationListenerEx()
 *     registerAsSystemService(NotificationListenerService, Context,
 *                             ComponentName, int)
 *     unregisterAsSystemService(NotificationListenerService)
 *
 * On EMUI the helper reached the platform's privileged notification-listener
 * API. A normal application cannot do that, so both calls go through the public
 * platform API and report "unavailable" instead of killing the caller: not being
 * able to mirror phone notifications into the VR space must not take the whole
 * environment down. Everything else about the monitor stays original.
 */
public class HwNotificationListenerEx {
    private static final String TAG = "HwNotificationListenerEx";

    public HwNotificationListenerEx() {
    }

    public void registerAsSystemService(NotificationListenerService service,
                                        Context context,
                                        ComponentName component,
                                        int userId) {
        if (service == null || context == null || component == null) {
            Log.w(TAG, "registerAsSystemService: invalid parameter");
            return;
        }
        // 官方是 hidden 的 service.registerAsSystemService(ctx, name, userId)，
        // 不反射。通用安卓上让通知监听服务被系统绑定的公开接口就是
        // NotificationListenerService.requestRebind(ComponentName)：
        // 应用在设置里拿到通知使用权后由系统重新绑定，效果等价。
        try {
            NotificationListenerService.requestRebind(component);
        } catch (Throwable error) {
            Log.w(TAG, "requestRebind failed", error);
        }
    }

    public void unregisterAsSystemService(NotificationListenerService service) {
        if (service == null) {
            return;
        }
        // 官方是 hidden 的 service.unregisterAsSystemService()。公开 API 没有
        // 「注销系统通知监听」这一步：服务由系统绑定/解绑，应用侧能做的只是
        // 让自身停止处理事件。这里如实不动作，并记一次日志说明原因。
        Log.i(TAG, "unregisterAsSystemService has no public equivalent; "
                + "the listener stays bound until the user revokes notification access");
    }
}
