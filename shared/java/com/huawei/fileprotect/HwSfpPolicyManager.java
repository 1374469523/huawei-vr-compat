package com.huawei.fileprotect;

import android.content.Context;
import android.util.Log;

/**
 * Huawei's Secure File Protection policy manager (SFP / IUDf).
 *
 * On EMUI this applies Huawei's file-protection labels and policies to files on
 * external storage. A common Android device has no such subsystem, so every
 * accessor reports "no policy" and every setter logs instead of claiming the
 * policy was applied. All call sites in the original APKs sit inside try/catch
 * blocks, so this is the "feature absent" branch they already handle.
 */
public class HwSfpPolicyManager {

    private static final String TAG = "HvrHwSfpPolicyManager";

    private static final HwSfpPolicyManager INSTANCE = new HwSfpPolicyManager();

    private HwSfpPolicyManager() {
    }

    /** EMUI-only feature; not present on a common Android device. */
    public static boolean isSupportIudf() {
        return false;
    }

    public static HwSfpPolicyManager getDefault() {
        return INSTANCE;
    }

    public void setEcePolicy(Context context, String path) {
        Log.i(TAG, "setEcePolicy is not available on this device: " + path);
    }

    public void setSecePolicy(Context context, String path) {
        Log.i(TAG, "setSecePolicy is not available on this device: " + path);
    }

    public String getLabel(Context context, String path, String key) {
        return null;
    }

    public int getFlag(Context context, String path, String key) {
        return 0;
    }

    public int setLabel(Context context, String path, String key, String value, int flag) {
        Log.i(TAG, "setLabel is not available on this device: " + path);
        return -1;
    }
}