package com.huawei.system;

import android.os.Build;
import android.text.TextUtils;

import com.huawei.android.os.SystemPropertiesEx;

/**
 * 照官方实现移植（原厂件/hwframework.jar 的
 * com/huawei/system/BuildEx.smali）。
 *
 * 官方两个方法：
 *
 *   getOsBrand()      Resources.getSystem().getString(0x104020b)
 *   getRadioVersion() SystemPropertiesEx.get("gsm.version.baseband","")，为空则 null
 *
 * `getRadioVersion()` 这里逐字照搬（同一个属性、同样的空值处理）。
 *
 * `getOsBrand()` 那行读的是**框架字符串资源** `0x104020b`：资源 ID 不是跨设备
 * 稳定的，三星的 framework-res 里同一个 ID 未必是同一句话，照抄反而会拿到错的
 * 文本。这一句的语义是「系统品牌的显示名」，公开等价物就是 `Build.BRAND`，
 * 所以这里用它，并在下面把官方字段一起补齐（值都取真实平台值）。
 */
public final class BuildEx {

    public static final String DISPLAY = Build.DISPLAY;
    public static final String FINGERPRINT = Build.FINGERPRINT;
    public static final String HOST = Build.HOST;
    public static final String INCREMENTAL = Build.VERSION.INCREMENTAL;
    public static final String SECURITY_PATCH = Build.VERSION.SECURITY_PATCH;
    public static final Long TIME = Build.TIME;

    private BuildEx() {
    }

    public static String getOsBrand() {
        return Build.BRAND;
    }

    public static String getRadioVersion() {
        String value = SystemPropertiesEx.get("gsm.version.baseband", "");
        return TextUtils.isEmpty(value) ? null : value;
    }
}
