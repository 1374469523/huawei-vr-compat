package com.huawei.hvrsdkserverapp.compat;

import android.content.ComponentName;
import android.content.ContentResolver;
import android.content.Context;
import android.content.Intent;
import android.content.ServiceConnection;
import android.hardware.display.DisplayManager;
import android.os.Bundle;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.Message;
import android.os.Messenger;
import android.os.RemoteException;
import android.provider.Settings;
import android.util.Log;
import android.view.Display;
import android.view.Surface;

/**
 * The system side of the VR environment, which EMUI used to provide.
 *
 * Evidence taken from the original packages (nothing invented):
 *
 * - the desktop hosts the environment: {@code com.huawei.client.vrservice.VRService}
 *   in process {@code com.huawei.vrservice}, and publishes the {@code vr_system}
 *   service from there;
 * - EMUI's framework bound that service and pushed its own binder through a
 *   {@link Messenger} message {@code 0x3e9} with bundle key
 *   {@code system_service_binder} ({@code t0/a.smali});
 * - the desktop state machine then advances on the framework's messages
 *   ({@code t0/c.smali}): {@code 0x1} starts, {@code 0xf} advances one prepare
 *   step, {@code 0x3ea} carries the "system prepare done" reply and finally
 *   starts the VR space.
 *
 * On a generic Android device no framework component does any of that, so the
 * helmet never starts the environment and the desktop stays on the
 * "connect your HUAWEI VR Glass" screen. This class plays exactly that role,
 * driven by the real external display, and leaves the original code untouched.
 */
public final class VrSystemActor implements DisplayManager.DisplayListener {
    static final String TAG = "VrSystemActor";

    private static final String VR_SERVICE_PACKAGE = "com.huawei.vrlauncherx";
    private static final String VR_SERVICE_CLASS = "com.huawei.client.vrservice.VRService";
    private static final String KEY_SYSTEM_SERVICE_BINDER = "system_service_binder";

    private static final int MSG_SYSTEM_SERVICE_CONNECT = 0x3e9;
    private static final int MSG_START = 0x1;
    private static final int MSG_PREPARE_NEXT = 0xf;
    /**
     * Packed switch in {@code t0/c.F(Message)}: 0x3ea reads {@code Message.obj}
     * as an Integer, which cannot cross a process boundary; helmet-up is 0x3eb
     * and carries no payload. Its handler
     * ({@code t0/c.t()}, "handle Helmet Up") calls
     * {@code P(1)} once the environment reached state 4, and that starts the VR
     * space.
     */
    private static final int MSG_HELMET_UP = 0x3eb;

    /**
     * Huawei's iConnect system app asks the handle to reconnect with this action
     * when a paired accessory drops its link. The handle accepts it on its own
     * service (-&gt; {@code VRHandleService.n1} -&gt; {@code m1} -&gt; {@code e0}
     * -&gt; {@code connectGatt}), and the action is declared both in the service's
     * intent filter and in {@code VRHandleService}'s dispatch table, so this is
     * the original entry point rather than a new protocol.
     *
     * Nothing else on a stock device plays that role: the handle binds the
     * desktop's reconnect service successfully and therefore only asks the
     * desktop's near-field scan to wake the device (see PATCH_AUDIT 7.3), so
     * without this request it may sit idle for minutes before connecting on its
     * own. Measured on the SM-F731U1: request sent at 09:41:15, handle logged
     * "connected to gatt server" at 09:41:16.44.
     */
    private static final String HANDLE_SERVICE_PACKAGE = "com.huawei.vrhandle";
    private static final String HANDLE_SERVICE_CLASS =
            "com.huawei.vrhandle.service.VRHandleService";
    /**
     * 「VR 已启动，去把已配对的手柄接回来」这条原版契约由 vrservice 发给手柄：
     * 手柄的 intent-filter 里声明的是这个 action，`VRHandleService.p1()` 也是
     * 按它分支（→ S2 → 绑桌面的重连服务；绑不上就走它自己的
     * "bind fail, directly trigger reconnect" → connectGatt）。
     *
     * 之前这里发的是 `com.huawei.iconnect.ACTION_RECONNECT_MSG`（iConnect 断线
     * 重连那条），它在手柄里走 `m1()`，只查「已连接设备列表」：设备在列表里就
     * 直接返回，掉线后则停在 `service not init finish, cannot notify scan`，
     * 不会触发重连。真机 2026-09-16：掉线后 `deviceState = 4 / not retry connect`，
     * 发这个 action 无效；换成 vrservice 那条才能走到原版的直接重连。
     *
     * 桌面包里依赖华为 Nearby 的 `VrHandleReconnectService` 已按平台差异摘除
     * （patches/patch_vrhandle_reconnect_component.py），所以这里的绑定会如实失败，
     * 原版兜底路径得以执行。
     */
    private static final String ACTION_VRSERVICE_RECONNECT =
            "com.huawei.vrservice.ACTION_RECONNECT_MSG";
    /** The handle may still be starting when the helmet appears. */
    private static final long[] HANDLE_RECONNECT_DELAYS_MS = {3000L, 8000L, 15000L, 25000L};
    /**
     * Huawei's iConnect is a resident service: when the accessory drops its link
     * it keeps asking for a reconnect. The handle itself gives up after one
     * retry ("not retry connect", deviceState = 4), and its near-field path is
     * unavailable, so without a periodic nudge the controller stays gone for the
     * rest of the session. Repeating the original request while the helmet is
     * present reproduces that resident behaviour; the handle answers "device is
     * already connected" and returns when there is nothing to do.
     */
    private static final long HANDLE_RECONNECT_PERIOD_MS = 20000L;

    /** 进 VR 之前的手机方向设置；退出时按原样还回去（-1 = 还没存过）。 */
    private int savedAccelerometerRotation = -1;
    private int savedUserRotation = -1;

    private static final long STEP_DELAY_MS = 700L;

    private static VrSystemActor instance;

    private final Context context;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final ServiceConnection connection = new ServiceConnection() {
        @Override
        public void onServiceConnected(ComponentName name, IBinder service) {
            Log.i(TAG, "VRService connected: " + name);
            connected = true;
            vrServiceBinder = service;
            sendConnectHandshake(service);
        }

        @Override
        public void onServiceDisconnected(ComponentName name) {
            Log.w(TAG, "VRService disconnected: " + name);
            connected = false;
            vrServiceBinder = null;
        }
    };

    private IBinder vrServiceBinder;
    private boolean connected;
    private boolean helmetPresent;
    private boolean registered;

    /**
     * EMUI 的 VR 系统服务跟踪的「VR 模式状态」。桌面用
     * {@code t0/b.isVRmode()} → {@code z0/c.n()} 查询它（what=0x835），
     * 用户空间里的 Unity 活动启动后第一件事就是问它：
     *
     *     11:19:31.158 I UnityPlayerActivity: Not in VrMode. Then return!
     *     11:19:31.163 I HVRActivity: Not in VrMode. Then return!
     *     11:19:32.053 I UnityPlayerActivity: onDestroy: Not in VrMode. Then return!
     *
     * 状态跟着真实硬件走：眼镜在位、我们把环境推进到「戴上了」那一步
     * （0x3eb，原版框架在用户戴上眼镜时发的就是它）之后才算进入 VR 模式；
     * 眼镜拔掉立刻清零。这里不编状态：值就是环境实际走到哪一步。
     */
    private volatile boolean vrMode;

    private VrSystemActor(Context context) {
        this.context = context;
    }

    public static void start(Context context) {
        Context app = context.getApplicationContext();
        synchronized (VrSystemActor.class) {
            if (instance == null) {
                instance = new VrSystemActor(app);
            }
            instance.ensureRegistered();
            instance.refresh("start");
        }
    }

    private void ensureRegistered() {
        if (registered) {
            return;
        }
        DisplayManager manager =
                (DisplayManager) context.getSystemService(Context.DISPLAY_SERVICE);
        if (manager == null) {
            Log.w(TAG, "no DisplayManager, helmet supervision disabled");
            return;
        }
        manager.registerDisplayListener(this, handler);
        registered = true;
    }

    /** Re-reads the helmet state from the real external display. */
    private void refresh(String reason) {
        DisplayManager manager =
                (DisplayManager) context.getSystemService(Context.DISPLAY_SERVICE);
        if (manager == null) {
            return;
        }
        StringBuilder names = new StringBuilder();
        for (Display display : manager.getDisplays()) {
            names.append(display.getDisplayId()).append(':').append(display.getName())
                    .append(' ');
        }
        boolean present = com.huawei.vrframework.compat.VrPlatformCompat
                .isVrGlassPresent(context);
        Log.i(TAG, "refresh(" + reason + ") displays=[" + names.toString().trim()
                + "] helmet=" + present);
        if (present != helmetPresent) {
            helmetPresent = present;
            if (present) {
                onHelmetUp();
            } else {
                onHelmetDown();
            }
        } else if (present && !connected) {
            // Already plugged in when the watcher came up.
            onHelmetUp();
        }
    }

    private void onHelmetUp() {
        Log.i(TAG, "helmet present, starting the original VR environment");
        // 「HUAWEI VR Display」那块承载 VR 应用的虚拟屏由**启动方自己**创建
        // （见 HvrDisplayRouter：安卓只允许屏的拥有者往它上面启动活动），
        // 所以这里不再代建，避免出现两块同名虚拟屏、归属还不对。
        // 「进入 VR 模式」在眼镜被识别到的那一刻就成立：桌面 z0/c.A()
        // （VRPrepareActivity.onCreate 会调）在准备流程一开始就问
        // getVRModeState（what=0x835），答「不在 VR 模式」它会
        // moveTaskToBack + finish，日志是
        //   "VRPrepareActivity should not show when glass out."
        // （真机 14:22:34.905 看到过一次：桌面在 actor 发 0x1 之前就起了准备页。）
        // 状态仍由真实硬件驱动：只有眼镜外接屏在位才会走到这里，
        // onHelmetDown 会立刻把 vrMode 清零。
        if (helmetPresent) {
            vrMode = true;
        }
        lockLandscape();
        bindVrService();
        scheduleHandleReconnect();
    }

    /**
     * EMUI put the device into landscape for the whole VR session. Without it the
     * VR activity is a 1588x1080 landscape window inside a 1080x2640 portrait
     * display, and the glasses only receive that portrait screen scaled into the
     * 3200x1600 panel:
     *
     *   phone:  cur=1080x2640  layer bounds={0,1146,1588,1080}
     *   glasses mirror: scale 0.6061, tx=1272, ty=694.5      (small, offset band)
     *
     * Locking to landscape makes the display 2640x1080 and the same mirror scale
     * becomes 1.2121 (2640 * 1.2121 = 3200), i.e. full width of the panel.
     */
    private void lockLandscape() {
        try {
            // 先把手机原来的方向设置记下来：2026-09-16 用户报「手机画面被强制横屏」，
            // 原因就是这里只记不还 —— unlockRotation() 以前只恢复自动旋转，
            // user_rotation 永远停在 90，拔掉眼镜后整机卡在横屏。
            ContentResolver resolver = context.getContentResolver();
            savedAccelerometerRotation = Settings.System.getInt(
                    resolver, Settings.System.ACCELEROMETER_ROTATION, 1);
            savedUserRotation = Settings.System.getInt(
                    resolver, Settings.System.USER_ROTATION, Surface.ROTATION_0);
            Settings.System.putInt(context.getContentResolver(),
                    Settings.System.ACCELEROMETER_ROTATION, 0);
            Settings.System.putInt(context.getContentResolver(),
                    Settings.System.USER_ROTATION, Surface.ROTATION_90);
            Log.i(TAG, "display locked to landscape for the VR session");
        } catch (Throwable error) {
            Log.w(TAG, "landscape lock refused: " + error);
        }
    }

    /** 眼镜拔掉后把手机的方向设置**按原样**还回去。 */
    private void unlockRotation() {
        try {
            Settings.System.putInt(context.getContentResolver(),
                    Settings.System.ACCELEROMETER_ROTATION,
                    savedAccelerometerRotation >= 0 ? savedAccelerometerRotation : 1);
            Settings.System.putInt(context.getContentResolver(),
                    Settings.System.USER_ROTATION,
                    savedUserRotation >= 0 ? savedUserRotation : Surface.ROTATION_0);
            Log.i(TAG, "rotation restored (accelerometer="
                    + (savedAccelerometerRotation >= 0 ? savedAccelerometerRotation : 1)
                    + ", user=" + (savedUserRotation >= 0 ? savedUserRotation : Surface.ROTATION_0)
                    + ")");
        } catch (Throwable error) {
            Log.w(TAG, "rotation restore refused: " + error);
        }
    }

    /** Plays the part Huawei's iConnect app had on EMUI. */
    private void scheduleHandleReconnect() {
        for (final long delay : HANDLE_RECONNECT_DELAYS_MS) {
            handler.postDelayed(new Runnable() {
                @Override
                public void run() {
                    requestHandleReconnect();
                }
            }, delay);
        }
        handler.removeCallbacks(handleReconnectLoop);
        handler.postDelayed(handleReconnectLoop, HANDLE_RECONNECT_PERIOD_MS);
    }

    private final Runnable handleReconnectLoop = new Runnable() {
        @Override
        public void run() {
            if (!helmetPresent) {
                return;
            }
            requestHandleReconnect();
            handler.postDelayed(this, HANDLE_RECONNECT_PERIOD_MS);
        }
    };

    private void requestHandleReconnect() {
        Intent intent = new Intent(ACTION_VRSERVICE_RECONNECT);
        intent.setComponent(new ComponentName(HANDLE_SERVICE_PACKAGE, HANDLE_SERVICE_CLASS));
        try {
            ComponentName started = context.startService(intent);
            Log.i(TAG, "handle reconnect requested -> " + started);
        } catch (Throwable error) {
            Log.w(TAG, "handle reconnect request failed: " + error);
        }
    }

    private void onHelmetDown() {
        Log.i(TAG, "helmet removed");
        vrMode = false;
        handler.removeCallbacks(handleReconnectLoop);
        unlockRotation();
        if (!connected) {
            return;
        }
        try {
            context.unbindService(connection);
        } catch (IllegalArgumentException error) {
            Log.w(TAG, "unbind failed: " + error);
        }
        connected = false;
        vrServiceBinder = null;
    }

    private void bindVrService() {
        if (connected) {
            return;
        }
        Intent intent = new Intent();
        intent.setComponent(new ComponentName(VR_SERVICE_PACKAGE, VR_SERVICE_CLASS));
        try {
            if (!context.bindService(intent, connection, Context.BIND_AUTO_CREATE)) {
                Log.e(TAG, "bindService refused for " + intent.getComponent());
            }
        } catch (SecurityException error) {
            Log.e(TAG, "bindService denied: " + error);
        }
    }

    /** EMUI handshake: message 0x3e9 carrying our side of the interface. */
    private void sendConnectHandshake(IBinder service) {
        Message message = Message.obtain(null, MSG_SYSTEM_SERVICE_CONNECT);
        Bundle data = new Bundle();
        data.putBinder(KEY_SYSTEM_SERVICE_BINDER, new SystemServiceBinder(this));
        message.setData(data);
        try {
            new Messenger(service).send(message);
            Log.i(TAG, "connect handshake sent");
        } catch (RemoteException error) {
            Log.e(TAG, "connect handshake failed: " + error);
            return;
        }
        handler.postDelayed(startStep, STEP_DELAY_MS);
    }

    private final Runnable startStep = new Runnable() {
        @Override
        public void run() {
            // 「进入 VR 模式」从这一步开始算：桌面的准备页
            // （VRPrepareActivity.onCreate -> z0/c.A -> getVRModeState，what=0x835）
            // 在准备流程期间就会问这个状态，答「不在 VR 模式」它会
            // moveTaskToBack + finish，日志就是
            //   "VRPrepareActivity should not show when glass out."
            // 原版 EMUI 的系统 VR 服务在准备阶段已经是 VR 模式，这里对齐同一时机。
            // 仍然由真实硬件驱动：只有眼镜在位（helmetPresent）才会走到这一步，
            // 拔掉眼镜 onHelmetDown 会立刻把 vrMode 清零。
            if (helmetPresent) {
                vrMode = true;
            }
            sendEmpty(MSG_START);
            handler.postDelayed(prepareStepOne, STEP_DELAY_MS);
        }
    };

    private final Runnable prepareStepOne = new Runnable() {
        @Override
        public void run() {
            sendEmpty(MSG_PREPARE_NEXT);
            handler.postDelayed(prepareStepTwo, STEP_DELAY_MS);
        }
    };

    private final Runnable prepareStepTwo = new Runnable() {
        @Override
        public void run() {
            sendEmpty(MSG_PREPARE_NEXT);
            handler.postDelayed(prepareDone, STEP_DELAY_MS);
        }
    };

    private final Runnable prepareDone = new Runnable() {
        @Override
        public void run() {
            // Helmet worn: "handle Helmet Up" -> P(1) -> start the VR space.
            // 环境到这一步才算进入 VR 模式，桌面随后启动的用户空间会问这个值。
            vrMode = true;
            sendEmpty(MSG_HELMET_UP);
        }
    };

    /** 供 {@link SystemServiceBinder} 回答桌面的 what=0x835（getVRModeState）。 */
    boolean isVrMode() {
        return vrMode && helmetPresent;
    }

    /**
     * 供 {@link SystemServiceBinder} 回答 what=0x836（getHelmetBattery）。
     * 通用安卓口径：CV10 由手机供电、没有独立电池，这里给 Android 的电量百分比；
     * 拿不到返回 -1（不可用），不编数值。
     */
    int helmetBattery() {
        return com.huawei.vrframework.compat.VrAndroidSensors.batteryPercent(context);
    }

    /**
     * 供 {@link SystemServiceBinder} 回答 what=0x838（getProximityState）。
     * 通用安卓口径：眼镜的 HID 报告里没有接近这一项，改用 Android 自己的接近传感器；
     * 本机没有该传感器就返回 -1。
     */
    int proximityState() {
        return com.huawei.vrframework.compat.VrAndroidSensors.proximity(context);
    }

    void onSystemServiceConnected() {
        Log.i(TAG, "desktop acknowledged the system service binder");
    }

    private void sendEmpty(int what) {
        sendObject(what, null);
    }

    private void sendObject(int what, Object payload) {
        IBinder target = vrServiceBinder;
        if (target == null) {
            Log.w(TAG, "drop message 0x" + Integer.toHexString(what) + ": not connected");
            return;
        }
        Message message = Message.obtain(null, what);
        message.obj = payload;
        try {
            new Messenger(target).send(message);
            Log.i(TAG, "sent message 0x" + Integer.toHexString(what));
        } catch (RemoteException error) {
            Log.e(TAG, "send failed: " + error);
        }
    }

    @Override
    public void onDisplayAdded(int displayId) {
        refresh("displayAdded:" + displayId);
    }

    @Override
    public void onDisplayRemoved(int displayId) {
        refresh("displayRemoved:" + displayId);
    }

    @Override
    public void onDisplayChanged(int displayId) {
        refresh("displayChanged:" + displayId);
    }
}
