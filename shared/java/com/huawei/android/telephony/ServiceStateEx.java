package com.huawei.android.telephony;

import android.telephony.ServiceState;
import android.util.Log;

/**
 * 照官方实现移植（原厂件/hwframework.jar 的
 * com/huawei/android/telephony/ServiceStateEx.smali）：
 *
 *     getConfigRadioTechnology(ServiceState) -> state.getConfigRadioTechnology()
 *
 * `ServiceState.getConfigRadioTechnology()` 是 hidden 方法（`getRadioTechnology()`
 * 同样 hidden），公开 SDK 里没有对应接口，本移植**不反射**。
 *
 * 没有公开等价物可退：这个值本来就是 EMUI 额外加的「配置里的无线制式」，
 * 通用安卓上不存在这个概念。所以如实返回 0 —— AOSP 里
 * `ServiceTelephonyManager.NETWORK_TYPE_UNKNOWN` 就是 0，含义是「未知」，
 * 不是某个被猜测出来的制式。
 */
public final class ServiceStateEx {

    private static final String TAG = "HvrServiceStateEx";

    /** AOSP TelephonyManager.NETWORK_TYPE_UNKNOWN。 */
    private static final int NETWORK_TYPE_UNKNOWN = 0;

    private ServiceStateEx() {
    }

    public static int getConfigRadioTechnology(ServiceState state) {
        if (state == null) {
            return NETWORK_TYPE_UNKNOWN;
        }
        if (!reported) {
            reported = true;
            Log.w(TAG, "getConfigRadioTechnology is an EMUI-only hidden getter; "
                    + "returning NETWORK_TYPE_UNKNOWN on this device");
        }
        return NETWORK_TYPE_UNKNOWN;
    }

    private static volatile boolean reported;
}
