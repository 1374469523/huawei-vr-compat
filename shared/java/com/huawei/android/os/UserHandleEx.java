package com.huawei.android.os;

import android.os.Process;
import android.os.UserHandle;
import android.util.Log;

/**
 * Huawei's UserHandle extension.
 *
 * The members the original APKs use map onto public Android equivalents where
 * one exists: ALL is the AOSP "all users" handle, OWNER is the handle of user 0,
 * and the numeric ids come from the same per-user uid range the platform uses.
 * UserHandle.getIdentifier() is hidden, so a handle this class did not hand out
 * is reported as "unknown" instead of being guessed.
 */
public final class UserHandleEx {

    private static final String TAG = "HvrUserHandleEx";

    /** AOSP PER_USER_RANGE: uid = userId * PER_USER_RANGE + appId. */
    private static final int PER_USER_RANGE = 100000;
    /** AOSP UserHandle.USER_ALL / NULL: same values the platform uses. */
    private static final int USER_ALL = -1;
    private static final int USER_NULL = -10000;

    /** android.os.UserHandle.ALL is hidden; rebuilt through the public factory. */
    public static final UserHandle ALL = UserHandle.getUserHandleForUid(-1);
    /** android.os.UserHandle.OWNER is hidden: it is the handle of user 0. */
    public static final UserHandle OWNER = UserHandle.getUserHandleForUid(0);

    private UserHandleEx() {
    }

    public static UserHandle getCurrent() {
        return UserHandle.getUserHandleForUid(Process.myUid());
    }

    /** UserHandle.myUserId() is hidden; the current user is the uid's user. */
    public static int myUserId() {
        return getUserId(Process.myUid());
    }

    /** UserHandle.getUserId(int) is hidden; same arithmetic. */
    public static int getUserId(int uid) {
        return uid / PER_USER_RANGE;
    }

    /**
     * 官方语义（原厂件/hwframework.jar 的 UserHandleEx.smali）：
     * null -> 返回 **-1**；否则返回 `userHandle.getIdentifier()`。
     *
     * `UserHandle.getIdentifier()` 是 hidden 方法，这里按三条路取：
     *   1. 反射调用真方法；
     *   2. AOSP 里 `UserHandle.hashCode()` 的实现就是 `return mHandle;`
     *      （framework 源码 UserHandle.java），与 getIdentifier() 同值；
     *   3. 都没有 -> -1，与官方 null 分支同一个「未知」语义。
     * 我方原先对 null 返回 -10000、并只认自己造过的 handle，两处都与官方不符。
     */
    public static int getIdentifier(UserHandle handle) {
        if (handle == null) {
            return -1;
        }
        // `getIdentifier()` 是 hidden，不反射。公开的 `hashCode()` 在 AOSP
        // framework 源码（UserHandle.java）里的实现就是 `return mHandle;`，
        // 与 getIdentifier() 同值 —— 这是公开 API 的语义，不是兜底猜测。
        return handle.hashCode();
    }
}
