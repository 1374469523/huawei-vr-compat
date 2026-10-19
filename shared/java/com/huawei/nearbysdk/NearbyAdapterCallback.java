package com.huawei.nearbysdk;

/**
 * Callback implemented by the original desktop. Kept as an interface with the
 * same two members the desktop implements.
 */
public interface NearbyAdapterCallback {
    void onAdapterGet(NearbyAdapter adapter);

    void onBinderDied();
}
