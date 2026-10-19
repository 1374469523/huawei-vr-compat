package com.huawei.android.vrsystem;

import android.os.IBinder;
import android.os.Looper;
import android.view.InputEvent;

/**
 * Huawei's VR touch/input bridge. The original VR touch service registers a
 * callback and asks the platform to switch the panel power mode; the interface
 * and the call semantics are preserved here, while delivery depends on the VR
 * platform being present (see docs/PATCH_AUDIT.md).
 */
public final class VrTouchInterfaceEx {
    /** Implemented by the original VR touch service. */
    public interface VrInputEventCallback {
        boolean onInputEvent(InputEvent event);
    }

    private static volatile VrTouchInterfaceEx instance;

    private IBinder token;
    private Looper looper;
    private VrInputEventCallback callback;
    private int displayPowerMode = -1;

    private VrTouchInterfaceEx() {
    }

    public static VrTouchInterfaceEx getInstance() {
        if (instance == null) {
            synchronized (VrTouchInterfaceEx.class) {
                if (instance == null) instance = new VrTouchInterfaceEx();
            }
        }
        return instance;
    }

    public void registerInputEventCallback(IBinder token, Looper looper,
            VrInputEventCallback callback) {
        this.token = token;
        this.looper = looper;
        this.callback = callback;
    }

    public void unregisterInputEventCallback() {
        this.token = null;
        this.looper = null;
        this.callback = null;
    }

    public void setDefaultDisplayPowerMode(int mode) {
        this.displayPowerMode = mode;
    }

    /** Delivers an event to the registered callback, if any. */
    public boolean dispatch(InputEvent event) {
        VrInputEventCallback target = callback;
        return target != null && target.onInputEvent(event);
    }

    public int getDefaultDisplayPowerMode() {
        return displayPowerMode;
    }
}
