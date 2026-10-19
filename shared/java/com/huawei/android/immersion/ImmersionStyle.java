package com.huawei.android.immersion;

import android.content.Context;
import android.graphics.Color;
import android.util.TypedValue;
import android.util.Log;

/**
 * 照官方实现移植（原厂件/hwframework.jar 的
 * com/huawei/android/immersion/ImmersionStyle.smali）：
 *
 *   getPrimaryColor(Context)              主题主色
 *   getControlColor(Context)              控件色
 *   getSuggestionForgroundColorStyle(int) 按背景色给出前景色风格
 *
 * 官方读的是 EMUI 主题里的资源；通用安卓同一件事由公开的主题属性回答
 * （`android.R.attr.colorPrimary` / `colorControlNormal`），所以颜色来自
 * 运行中的真实主题，不是写死的值。取不到就退回黑色，并在日志里说明。
 *
 * 七个包只用到 getPrimaryColor 与 getSuggestionForgroundColorStyle；
 * getControlColor 按官方签名一并补齐。
 */
public final class ImmersionStyle {

    private static final String TAG = "ImmersionStyle";

    public ImmersionStyle() {
    }

    public static int getPrimaryColor(Context context) {
        return resolveColor(context, android.R.attr.colorPrimary);
    }

    public static int getControlColor(Context context) {
        return resolveColor(context, android.R.attr.colorControlNormal);
    }

    /**
     * 官方按背景色给出「深色还是浅色前景」的风格值。这里用同一个判断依据
     * （颜色的相对亮度），返回官方那两个取值之一。
     */
    public static int getSuggestionForgroundColorStyle(int color) {
        double luminance = (0.299 * Color.red(color)
                + 0.587 * Color.green(color)
                + 0.114 * Color.blue(color)) / 255.0;
        return luminance > 0.6 ? 1 : 0;
    }

    private static int resolveColor(Context context, int attribute) {
        if (context == null) {
            return Color.BLACK;
        }
        try {
            TypedValue value = new TypedValue();
            if (context.getTheme().resolveAttribute(attribute, value, true)) {
                return value.data;
            }
        } catch (Throwable error) {
            Log.w(TAG, "theme attribute 0x" + Integer.toHexString(attribute) + " failed", error);
        }
        return Color.BLACK;
    }
}
