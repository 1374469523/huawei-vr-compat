package com.huawei.nearbysdk;

import android.content.Context;

import com.huawei.nearbysdk.closeRange.CloseRangeDeviceFilter;
import com.huawei.nearbysdk.closeRange.CloseRangeDeviceListener;

/**
 * Huawei's Nearby SDK entry point (proprietary near-field pairing, used by the
 * original desktop to reconnect the handle).
 *
 * The compatibility layer keeps the exact interface but reports the SDK as
 * unavailable: createInstance records the callback and never claims an adapter,
 * so the caller stays on its own "no nearby adapter" path instead of talking to
 * a service that does not exist on a common Android device. Handle reconnection
 * is handled by the original handle service over Bluetooth instead.
 */
public class NearbyAdapter {
    private static NearbyAdapterCallback callback;

    private NearbyAdapter() {
    }

    public static void createInstance(Context context, NearbyAdapterCallback target) {
        callback = target;
    }

    public static void releaseInstance() {
        callback = null;
    }

    /** Signals the recorded callback that the SDK is unavailable. */
    public static void notifyUnavailable() {
        NearbyAdapterCallback target = callback;
        if (target != null) target.onBinderDied();
    }

    public boolean subscribeDevice(CloseRangeDeviceFilter filter,
            CloseRangeDeviceListener listener) {
        return false;
    }

    public boolean unSubscribeDevice(CloseRangeDeviceFilter filter) {
        return false;
    }
}
