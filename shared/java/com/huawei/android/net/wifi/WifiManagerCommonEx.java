package com.huawei.android.net.wifi;

import android.content.Context;
import android.net.ConnectivityManager;
import android.net.wifi.WifiManager;
import android.util.Log;

/**
 * 官方件 `com.huawei.android.net.wifi.WifiManagerCommonEx` 的移植版。
 *
 * 来源：`原厂件/hwframework.jar` 的 `classes.dex`（HMA-AL00 EMUI 11 固件，
 * 逐方法反汇编见 `docs/OFFICIAL_SOURCE_AUDIT.md`）。官方的五个方法**全部**是
 * 对隐藏接口 `android.net.wifi.HwInnerWifiManager` 的直转：
 *
 *     HwFrameworkFactory.getHwInnerWifiManager()
 *       -> HwInnerWifiManager.calculateSignalLevelHW(int) / (int,int)
 *       -> HwInnerWifiManager.getHwMeteredHint(Context)
 *       -> HwInnerWifiManager.getChannelListFor5G()
 *       -> HwInnerWifiManager.isRSDBSupported()
 *
 * 通用安卓没有那个隐藏接口，所以只把「哪来的」换成公开等价物，方法名、签名、
 * 静态语义一律照官方。取不到真实来源的（5G 信道表、RSDB 支持）返回中性值并记日志，
 * 不编数据。
 *
 * 主应用真机日志（2026-09-16）：
 *   E/AppGalleryVR.NetworkUtil: isMeteredWifi ClassNotFoundException,
 *     ex: java.lang.ClassNotFoundException: com.huawei.android.net.wifi.WifiManagerCommonEx
 * 本类补上之后该分支即可拿到真实答案。
 */
public final class WifiManagerCommonEx {
    private static final String TAG = "HvrWifiCommonEx";

    /** AOSP 的信号强度分级数与官方 HwInnerWifiManager 的实现一致。 */
    private static final int SIGNAL_LEVELS = 5;

    private WifiManagerCommonEx() {
    }

    /** 官方：HwInnerWifiManager.calculateSignalLevelHW(int rssi)。 */
    public static int calculateSignalLevelHW(int rssi) {
        return WifiManager.calculateSignalLevel(rssi, SIGNAL_LEVELS);
    }

    /** 官方：HwInnerWifiManager.calculateSignalLevelHW(int rssi, int numLevels)。 */
    public static int calculateSignalLevelHW(int rssi, int numLevels) {
        return WifiManager.calculateSignalLevel(rssi, numLevels);
    }

    /**
     * 官方：HwInnerWifiManager.getChannelListFor5G()。
     * 公开 API 没有「允许的 5G 信道表」这个概念，如实返回空表并记日志。
     */
    public static int[] getChannelListFor5G() {
        Log.i(TAG, "getChannelListFor5G: no public equivalent, returning empty list");
        return new int[0];
    }

    /**
     * 官方：HwInnerWifiManager.getHwMeteredHint(Context)。
     * 公开等价物是 ConnectivityManager 的「当前网络是否按流量计费」。
     * 拿不到 ConnectivityManager 时返回 false（与官方取不到服务的失败分支一致）。
     */
    public static boolean getHwMeteredHint(Context context) {
        if (context == null) {
            return false;
        }
        try {
            ConnectivityManager manager = (ConnectivityManager)
                    context.getSystemService(Context.CONNECTIVITY_SERVICE);
            return manager != null && manager.isActiveNetworkMetered();
        } catch (Throwable error) {
            Log.w(TAG, "getHwMeteredHint failed: " + error);
            return false;
        }
    }

    /**
     * 官方：HwInnerWifiManager.isRSDBSupported()（EMUI 的双 WiFi 并发能力）。
     * 通用安卓没有这个概念，返回 false 并记日志。
     */
    public static boolean isRSDBSupported() {
        Log.i(TAG, "isRSDBSupported: EMUI-only capability, reporting unsupported");
        return false;
    }
}
