package com.huawei.android.app;

import android.content.ContentResolver;
import android.content.Context;
import android.os.RemoteException;
import android.provider.Settings;
import android.util.Log;

import com.huawei.vrservice.compat.CompatAppContext;

/**
 * Huawei's WindowManager extension.
 *
 * The original code saves the current animation scale, sets it to 0 while the VR
 * environment runs, and restores it afterwards. On a common Android device the
 * same three values live in Settings.Global; reading them needs no permission and
 * writing them needs WRITE_SECURE_SETTINGS (granted by install-six.ps1, the same
 * way the desktop package gets it).
 *
 * Only the animation-scale members are implemented here; nothing else of the
 * Huawei extension is used by the original APKs of this port.
 */
public final class WindowManagerEx {

    private static final String TAG = "HvrWindowManagerEx";

    /** Same order as the platform's animation types. */
    private static final int TYPE_WINDOW = 0;
    private static final int TYPE_TRANSITION = 1;
    private static final int TYPE_ANIMATOR = 2;

    private WindowManagerEx() {
    }

    public static float getAnimationScale(int type) throws RemoteException {
        Context context = CompatAppContext.get();
        String key = globalKey(type);
        if (context == null || key == null) {
            return 1.0f;
        }
        ContentResolver resolver = context.getContentResolver();
        return Settings.Global.getFloat(resolver, key, 1.0f);
    }

    public static void setAnimationScale(int type, float scale) throws RemoteException {
        Context context = CompatAppContext.get();
        String key = globalKey(type);
        if (context == null || key == null) {
            return;
        }
        try {
            Settings.Global.putFloat(context.getContentResolver(), key, scale);
        } catch (Throwable error) {
            // WRITE_SECURE_SETTINGS not granted: report it instead of hiding it,
            // and do not pretend the value was written.
            Log.w(TAG, "cannot write " + key + " (needs WRITE_SECURE_SETTINGS)", error);
        }
    }

    private static String globalKey(int type) {
        switch (type) {
            case TYPE_WINDOW:
                return Settings.Global.WINDOW_ANIMATION_SCALE;
            case TYPE_TRANSITION:
                return Settings.Global.TRANSITION_ANIMATION_SCALE;
            case TYPE_ANIMATOR:
                return Settings.Global.ANIMATOR_DURATION_SCALE;
            default:
                return null;
        }
    }
}
