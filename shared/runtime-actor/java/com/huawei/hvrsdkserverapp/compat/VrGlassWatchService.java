package com.huawei.hvrsdkserverapp.compat;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Intent;
import android.os.Binder;
import android.os.IBinder;
import android.util.Log;

/**
 * Keeps {@link VrSystemActor} alive.
 *
 * EMUI's framework watched the helmet for the whole lifetime of the device; the
 * equivalent on stock Android is a foreground service, which is also the only
 * way a background process is allowed to react to the glasses being plugged in
 * while the phone is idle. Nothing else is added: the service only owns the
 * watch and the binding to the original desktop service.
 */
public final class VrGlassWatchService extends Service {
    private static final String CHANNEL_ID = "vr_environment";
    private static final int NOTIFICATION_ID = 0x5652;

    @Override
    public void onCreate() {
        super.onCreate();
        goForeground();
        startOriginalMyService();
        VrSystemActor.start(this);
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        goForeground();
        startOriginalMyService();
        VrSystemActor.start(this);
        return START_STICKY;
    }

    /**
     * 拉起原厂的 `com.huawei.hvrsdkserverapp.MyService`。
     *
     * EMUI 上这个服务由系统在开机时拉起：`MyService.onCreate()` 起线程调 JNI
     * `startNative()`，加载 `libHVRSDKServerApp.so` 并触发 `VrHelmetExt.init()`，
     * 头盔姿态链路（`mVRDeviceExt` / `GetPosture`）从这里才成立
     * （见 docs/PATCH_AUDIT.md 第 14、15 节）。
     *
     * 上一版把它挂在一个模拟开机的 receiver 上，那个 receiver 按用户口径删掉之后，
     * 这个服务就再没人拉起过。现在环境由「打开华为 VR」触发，这里跟着一起拉起，
     * 语义和 EMUI 的「系统拉起常驻组件」一致。
     *
     * 按类名启动，避免编译期依赖原包类。
     */
    private void startOriginalMyService() {
        Intent original = new Intent();
        original.setClassName(getPackageName(), "com.huawei.hvrsdkserverapp.MyService");
        try {
            startService(original);
        } catch (Throwable error) {
            Log.w(VrSystemActor.TAG, "original MyService start refused: " + error);
        }
    }

    @Override
    public IBinder onBind(Intent intent) {
        // 绑定即「就绪」：主应用的启动闸门用 bindService 判断环境真的活着，
        // 而不是只看 startService 有没有抛异常。返回一个普通 Binder 就够。
        return new Binder();
    }

    private void goForeground() {
        NotificationManager manager =
                (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (manager == null) {
            return;
        }
        if (manager.getNotificationChannel(CHANNEL_ID) == null) {
            NotificationChannel channel = new NotificationChannel(
                    CHANNEL_ID, "VR environment", NotificationManager.IMPORTANCE_MIN);
            channel.setShowBadge(false);
            manager.createNotificationChannel(channel);
        }
        int icon = getApplicationInfo().icon;
        if (icon == 0) {
            icon = android.R.drawable.ic_menu_compass;
        }
        Notification notification = new Notification.Builder(this, CHANNEL_ID)
                .setSmallIcon(icon)
                .setContentTitle("VR")
                .setContentText("VR environment service is running")
                .setShowWhen(false)
                .build();
        try {
            startForeground(NOTIFICATION_ID, notification);
        } catch (RuntimeException error) {
            Log.w(VrSystemActor.TAG, "startForeground failed: " + error);
        }
    }
}
