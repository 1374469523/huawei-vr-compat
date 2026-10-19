package com.huawei.systemmanager.notificationmanager.restrictedlock;

import android.content.ContentResolver;
import android.content.Context;
import android.provider.Settings;
import android.util.Log;

/**
 * 照官方实现移植（原厂件/hwframework.jar 的
 * com/huawei/systemmanager/notificationmanager/restrictedlock/HwLockPatternUtilsEx.smali）。
 *
 * 官方两步：
 *
 *     new LockPatternUtils(context)        // com.android.internal.widget，hidden
 *     setLockScreenDisabled(disable, userId)
 *     isLockScreenDisabled(userId)
 *
 * AOSP 的 `LockPatternUtils.setLockScreenDisabled` 落到的就是
 * `Settings.Secure` 里那个键（`lockscreen.disabled`），按 userId 读写；这正是我们
 * 能用公开接口复现的部分：
 *
 *     Settings.Secure.getIntForUser(resolver, "lockscreen.disabled", 0, userId)
 *     Settings.Secure.putIntForUser(resolver, "lockscreen.disabled", disabled?1:0, userId)
 *
 * 写这个键要 `WRITE_SECURE_SETTINGS`：本包（vrservice）已声明，install-six.ps1 里
 * `pm grant` 授权 —— 与原版作为 system UID 白拿这条权限等价。
 *
 * 之前我方版本是「查询恒 false、写入只打日志」，等于把 VR 期间关锁屏这件事整个丢掉；
 * 现在按官方语义真正读写那个键，写入被平台拒绝时如实记日志，不假装成功。
 */
public class HwLockPatternUtilsEx {

    private static final String TAG = "HvrLockPatternUtilsEx";

    /** LockPatternUtils 内部用的键名（Settings.Secure）。 */
    private static final String KEY_LOCKSCREEN_DISABLED = "lockscreen.disabled";

    private final Context context;

    public HwLockPatternUtilsEx(Context context) {
        this.context = context;
    }

    public boolean isLockScreenDisabled(int userId) {
        if (context == null) {
            return false;
        }
        if (!isCallingUser(userId)) {
            Log.w(TAG, "lockscreen.disabled of user " + userId
                    + " is not readable from this process (public API covers the caller's user)");
            return false;
        }
        try {
            ContentResolver resolver = context.getContentResolver();
            return Settings.Secure.getInt(resolver, KEY_LOCKSCREEN_DISABLED, 0) != 0;
        } catch (Throwable error) {
            Log.w(TAG, "read lockscreen.disabled failed", error);
            return false;
        }
    }

    public void setLockScreenDisabled(boolean disabled, int userId) {
        if (context == null) {
            return;
        }
        if (!isCallingUser(userId)) {
            Log.w(TAG, "refusing to write lockscreen.disabled for another user " + userId);
            return;
        }
        try {
            ContentResolver resolver = context.getContentResolver();
            Settings.Secure.putInt(resolver, KEY_LOCKSCREEN_DISABLED, disabled ? 1 : 0);
        } catch (Throwable error) {
            // 没有 WRITE_SECURE_SETTINGS 时平台会拒绝；拒绝就是没关成，如实记录。
            Log.w(TAG, "write lockscreen.disabled failed (needs WRITE_SECURE_SETTINGS)", error);
        }
    }

    /**
     * 公开 SDK 里 Settings.Secure 只有「当前用户」的 get/put（`*ForUser` 是 hidden），
     * 所以按进程所在用户判断；VR 流程本来也只作用在当前用户。
     */
    private static boolean isCallingUser(int userId) {
        return userId == android.os.Process.myUid() / 100000;
    }
}
