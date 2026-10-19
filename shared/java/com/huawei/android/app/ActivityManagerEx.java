package com.huawei.android.app;

import android.os.Process;

/**
 * Huawei's ActivityManager extension. Only the member the original APKs use is
 * implemented, on top of the public equivalent.
 */
public final class ActivityManagerEx {

    /** AOSP PER_USER_RANGE: uid = userId * PER_USER_RANGE + appId. */
    private static final int PER_USER_RANGE = 100000;

    private ActivityManagerEx() {
    }

    /**
     * 官方（原厂件/hwframework.jar 的 ActivityManagerEx.smali）就是这个公开调用：
     *
     *     invoke-static {}, Landroid/app/ActivityManager;->getCurrentUser()I
     *
     * 之前我方改成用 uid 区间算（`Process.myUid() / 100000`），值一般相同，
     * 但没必要绕：ActivityManager.getCurrentUser() 是公开 API，直接调用才是
     * 「只换指向」。
     */
    public static int getCurrentUser() {
        // 官方那行 `ActivityManager.getCurrentUser()` 在公开 SDK 里不存在
        // （它是 hidden 方法，android.jar 里没有），所以只能等价推导：
        // 一个进程只属于一个用户，uid / PER_USER_RANGE 就是它所在的用户 id，
        // 与 getCurrentUser() 的定义一致（AOSP UserHandle.getUserId）。
        return Process.myUid() / PER_USER_RANGE;
    }
}
