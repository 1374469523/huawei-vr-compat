package com.huawei.android.os;

import android.content.Context;
import android.hardware.display.DisplayManager;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.Display;

/**
 * Huawei's UEventObserver extension.
 *
 * Two platform problems had to be worked around, both with the original callers
 * untouched:
 *
 * 1. android.os.UEventObserver declares startObserving()/stopObserving() final, so
 *    this class cannot be a subclass that overrides them. Doing that killed the
 *    original desktop service at class link time:
 *      LinkageError: Method void ...UEventObserverEx.startObserving(java.lang.String)
 *      overrides final method in class Landroid/os/UEventObserver;
 *
 * 2. The platform observer thread opens /dev/socket/uevent, which SELinux denies to
 *    ordinary applications; the throw happens inside android.os.UEventObserver's
 *    own thread and kills the process:
 *      FATAL EXCEPTION: UEventObserver
 *      java.lang.RuntimeException: Unable to open socket for UEventObserver
 *      at android.os.UEventObserver.nativeSetup(Native Method)
 *
 * The desktop only ever watches one uevent - "DEVPATH=/devices/virtual/dp/vr", the
 * DisplayPort link of the glasses, and reads a single field, DP_LINK_STATE - so the
 * same information is taken from the real display connection through DisplayManager
 * and delivered as the same UEvent. The original public surface is preserved:
 * a no-arg constructor, startObserving(String), stopObserving() and the
 * overridable onUEvent(UEvent).
 */
public class UEventObserverEx implements DisplayManager.DisplayListener {
    private static final String TAG = "UEventObserverEx";

    /** Field the original desktop reads out of the DP link event. */
    private static final String KEY_LINK_STATE = "DP_LINK_STATE";
    private static final String LINK_GOOD = "GOOD";
    private static final String LINK_BAD = "BAD";
    private static final String DEVPATH = "/devices/virtual/dp/vr";

    private final Handler handler = new Handler(Looper.getMainLooper());
    private DisplayManager manager;
    private String match;
    private boolean observing;

    public UEventObserverEx() {
    }

    public void startObserving(String match) {
        this.match = match;
        Context context = application();
        if (context == null) {
            // No way to read the real link state: report nothing rather than
            // inventing events.
            Log.w(TAG, "startObserving(" + match + "): no application context,"
                    + " DP link monitoring stays inactive");
            return;
        }
        manager = (DisplayManager) context.getSystemService(Context.DISPLAY_SERVICE);
        if (manager == null) {
            Log.w(TAG, "startObserving(" + match + "): no DisplayManager");
            return;
        }
        observing = true;
        manager.registerDisplayListener(this, handler);
        Log.i(TAG, "startObserving(" + match + ") mapped to the display link state");
        deliverCurrentState("startObserving");
    }

    public void stopObserving() {
        if (!observing || manager == null) {
            return;
        }
        observing = false;
        try {
            manager.unregisterDisplayListener(this);
        } catch (Throwable error) {
            Log.w(TAG, "unregisterDisplayListener failed: " + error);
        }
    }

    /** Overridden by the original callers to receive kernel events. */
    public void onUEvent(UEvent event) {
    }

    private void deliverCurrentState(String reason) {
        if (!observing || manager == null) {
            return;
        }
        boolean present = hasExternalDisplay();
        Log.i(TAG, "link state (" + reason + "): present=" + present);
        deliver(present);
    }

    private void deliver(boolean present) {
        String state = present ? LINK_GOOD : LINK_BAD;
        onUEvent(new UEvent("DEVPATH=" + DEVPATH + " " + KEY_LINK_STATE + "=" + state));
    }

    private boolean hasExternalDisplay() {
        for (Display display : manager.getDisplays()) {
            if (display.getDisplayId() != Display.DEFAULT_DISPLAY) {
                return true;
            }
        }
        return false;
    }

    @Override
    public void onDisplayAdded(int displayId) {
        deliverCurrentState("displayAdded:" + displayId);
    }

    @Override
    public void onDisplayRemoved(int displayId) {
        deliverCurrentState("displayRemoved:" + displayId);
    }

    @Override
    public void onDisplayChanged(int displayId) {
        deliverCurrentState("displayChanged:" + displayId);
    }

    /**
     * 走兼容层统一的 Context 来源（provider 在进程启动时注入的真实
     * application context，见 HvrContextProvider / ContextEx）。
     *
     * 之前这里自己反射 `ActivityThread.currentApplication()`：桌面（targetSdk 29）
     * 上那是 hidden API，反射会被拦，结果是「拿不到 context → DP 链路监听整个不生效」。
     */
    private static Context application() {
        return com.huawei.android.content.ContextEx.currentApplication();
    }

    public static class UEvent {
        private final String raw;

        public UEvent(String message) {
            this.raw = message;
        }

        public String get(String key) {
            return fromMessage(raw, key);
        }

        /** "KEY=VALUE KEY=VALUE" as delivered in /sys/.../uevent. */
        private static String fromMessage(String message, String key) {
            if (message == null || key == null) {
                return null;
            }
            for (String field : message.split("\\s+")) {
                int split = field.indexOf('=');
                if (split > 0 && key.equals(field.substring(0, split))) {
                    return field.substring(split + 1);
                }
            }
            return null;
        }
    }
}
