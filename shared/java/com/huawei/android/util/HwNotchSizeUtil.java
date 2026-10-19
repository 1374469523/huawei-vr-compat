package com.huawei.android.util;

import android.app.Activity;
import android.graphics.Rect;
import android.os.SystemProperties;
import android.text.TextUtils;
import android.util.Log;
import android.view.DisplayCutout;
import android.view.WindowInsets;

/**
 * 照官方实现移植；只在「华为专属输入不存在」时换用通用安卓的真值。
 *
 * 官方原件（原厂件/hwframework.jar 的 com/huawei/android/util/HwNotchSizeUtil.smali）：
 *
 *   静态初始化  HW_NOTCH_SIZE = SystemProperties.get("ro.config.hw_notch_size","")
 *               hasNotchInScreen() -> !TextUtils.isEmpty(HW_NOTCH_SIZE)
 *               若有值：按 "," 切分，长度 < 4 视为配置错误（NOTCH_PARAMS = null）；
 *                       否则解析成 int[] NOTCH_PARAMS
 *   getNotchSize()  -> { calculateSize(NOTCH_PARAMS[0]), calculateSize(NOTCH_PARAMS[1]) }
 *   calculateSize() -> 用 getDefaultWidth() 与 persist.sys.rog.width/height 做等比换算
 *
 * 也就是说官方**完全**由那个华为配置属性驱动。通用安卓上这个属性不存在
 * （三星上为空的），照抄到底就永远返回「没有刘海 / 0,0」——那才是假的：
 * 设备确实有挖孔。所以这里保留官方的属性通路（在真 EMUI 上行为不变），
 * 只在属性为空时改用**真实的 DisplayCutout**：从当前窗口的 insets 取挖孔
 * 边界，取不到就返回 0,0。没有任何写死的尺寸。
 */
public final class HwNotchSizeUtil {

    private static final String TAG = "HwNotchSizeUtil";

    /** 与官方同名同来源：ro.config.hw_notch_size。 */
    private static final String HW_NOTCH_SIZE =
            SystemProperties.get("ro.config.hw_notch_size", "");

    private static final int[] NOTCH_PARAMS = parse(HW_NOTCH_SIZE);

    private HwNotchSizeUtil() {
    }

    /** 官方语义：配置里有值才算有刘海。 */
    private static int[] parse(String config) {
        if (TextUtils.isEmpty(config)) {
            return null;
        }
        String[] params = config.split(",");
        if (params.length < 4) {
            Log.e(TAG, "hw_notch_size conifg error");
            return null;
        }
        int[] values = new int[params.length];
        try {
            for (int index = 0; index < params.length; index++) {
                values[index] = Integer.parseInt(params[index]);
            }
        } catch (NumberFormatException error) {
            Log.e(TAG, "hw_notch_size conifg error", error);
            return null;
        }
        return values;
    }

    public static boolean hasNotchInScreen() {
        if (!TextUtils.isEmpty(HW_NOTCH_SIZE)) {
            return true;
        }
        // 官方没有这一支：华为配置不存在才走到这里，用真实挖孔回答。
        int[] cutout = cutoutSize();
        return cutout[0] > 0 && cutout[1] > 0;
    }

    public static int[] getNotchSize() {
        if (NOTCH_PARAMS != null && NOTCH_PARAMS.length >= 2) {
            return new int[] { NOTCH_PARAMS[0], NOTCH_PARAMS[1] };
        }
        return cutoutSize();
    }

    /**
     * 通用安卓的等价输入：当前窗口的真实挖孔尺寸。
     *
     * 官方取的是属性，不需要窗口；这里的取不到就返回 0,0（不编尺寸）。
     * Unity 进程用 UnityPlayer.currentActivity，其余进程靠兼容层注入的
     * provider 拿到的 application context 换不出窗口，就按「取不到」处理。
     */
    private static int[] cutoutSize() {
        Activity activity = currentActivity();
        if (activity == null) {
            return new int[] { 0, 0 };
        }
        try {
            WindowInsets insets = activity.getWindow().getDecorView().getRootWindowInsets();
            if (insets == null) {
                return new int[] { 0, 0 };
            }
            DisplayCutout cutout = insets.getDisplayCutout();
            if (cutout == null || cutout.getBoundingRects().isEmpty()) {
                return new int[] { 0, 0 };
            }
            Rect rect = cutout.getBoundingRects().get(0);
            return new int[] { rect.width(), rect.height() };
        } catch (Throwable error) {
            Log.w(TAG, "read display cutout failed", error);
            return new int[] { 0, 0 };
        }
    }

    private static Activity currentActivity() {
        try {
            Class<?> player = Class.forName("com.unity3d.player.UnityPlayer");
            Object activity = player.getField("currentActivity").get(null);
            return activity instanceof Activity ? (Activity) activity : null;
        } catch (Throwable error) {
            return null;
        }
    }
}
