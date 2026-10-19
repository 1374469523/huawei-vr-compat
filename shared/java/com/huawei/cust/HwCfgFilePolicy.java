package com.huawei.cust;

import android.util.Log;

/**
 * EMUI's "cust" configuration directory policy.
 *
 * On EMUI this returns the carrier/customer configuration directories (for
 * example /cust/carrier/...), which the original code searches for a helmet
 * upgrade configuration. A common Android device has no such partition, so the
 * policy reports no directories. Nothing is invented: the caller finds no config
 * and therefore takes no upgrade action, which is exactly the offline result.
 */
public final class HwCfgFilePolicy {

    private static final String TAG = "HvrHwCfgFilePolicy";
    private static final String[] NO_POLICY_DIR = new String[0];
    private static boolean loggedOnce;

    /*
     * 官方（原厂件/hwframework.jar 的 com/huawei/cust/HwCfgFilePolicy.smali）
     * 的公开常量，逐字补齐：调用方用它们给 getCfgPolicyDir 传 type。
     */
    public static final int GLOBAL = 0;
    public static final int EMUI = 1;
    public static final int PC = 2;
    public static final int BASE = 3;
    public static final int CUST = 4;
    public static final int CLOUD_MCC = 5;
    public static final int CLOUD_DPLMN = 6;
    public static final int CLOUD_APN = 7;
    public static final int CUST_TYPE_CONFIG = 0;
    public static final int CUST_TYPE_MEDIA = 1;
    public static final int HW_CONFIG_STATE_SIM_LOADED = 1;
    public static final int HW_CONFIG_STATE_SIM_ABSENT = 2;
    public static final int HW_CONFIG_STATE_PARA_UPDATE = 3;
    public static final String HW_ACTION_CARRIER_CONFIG_CHANGED =
            "com.huawei.action.CARRIER_CONFIG_CHANGED";
    public static final String HW_CARRIER_CONFIG_CHANGE_STATE = "state";
    public static final String HW_CARRIER_CONFIG_OPKEY = "opkey";
    public static final String HW_CARRIER_CONFIG_SLOT = "slot";

    private HwCfgFilePolicy() {
    }

    /**
     * 官方是转给 `huawei.cust.HwCfgFilePolicy`（另一个华为类，本机固件里没有）。
     * 那个实现返回的是 EMUI 的 /cust 之类目录；通用安卓没有这些分区，所以返回空
     * 列表 —— 调用方（头盔升级配置查找）找不到配置即不升级，正是离线版该有的结果。
     */
    public static String[] getCfgPolicyDir(int type) {
        if (!loggedOnce) {
            loggedOnce = true;
            Log.i(TAG, "no cust partition on this device; policy dir list is empty");
        }
        return NO_POLICY_DIR;
    }
}
