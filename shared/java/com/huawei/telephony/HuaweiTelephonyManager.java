package com.huawei.telephony;

import android.content.Context;
import android.os.Build;
import android.os.Message;
import android.telephony.SubscriptionInfo;
import android.telephony.SubscriptionManager;
import android.telephony.TelephonyManager;
import android.util.Log;

/**
 * 官方件 `com.huawei.telephony.HuaweiTelephonyManager` 的移植版。
 *
 * 来源：`原厂件/hwframework.jar` 的 `classes.dex`（HMA-AL00 EMUI 11 固件；
 * 七个原包里都没有这个类，所以只能用官方件补）。官方是 EMUI 双卡管理器的封装，
 * 内部走 `android.telephony.HwTelephonyManager` / MSim 那套隐藏接口。
 *
 * 移植规则（与已有 40 个平台类一致）：方法名、签名、常量值照官方；能映射到公开
 * API 的按真实语义实现（`SubscriptionManager` / `TelephonyManager`）；EMUI 独有的
 * 返回中性值并记一次日志，不编数据。
 *
 * 调用方（主应用 `com.huawei.appgallery.base.simopt.j`）是**反射**调用并且自带
 * 类名回退链，所以这里即使返回中性值也不会打断它自己的失败分支。
 */
public final class HuaweiTelephonyManager {
    private static final String TAG = "HvrHuaweiTelephony";

    // 官方字段值逐字照搬（whitelist 字段）。
    public static final int UNKNOWN_CARD = -1;
    public static final int SINGLE_MODE_SIM_CARD = 0xa;
    public static final int SINGLE_MODE_USIM_CARD = 0x14;
    public static final int SINGLE_MODE_RUIM_CARD = 0x1e;
    public static final int DUAL_MODE_CG_CARD = 0x28;
    public static final int CT_NATIONAL_ROAMING_CARD = 0x29;
    public static final int CU_DUAL_MODE_CARD = 0x2a;
    public static final int DUAL_MODE_UG_CARD = 0x32;

    private static HuaweiTelephonyManager mInstance;

    public HuaweiTelephonyManager() {
    }

    public static HuaweiTelephonyManager getDefault() {
        synchronized (HuaweiTelephonyManager.class) {
            if (mInstance == null) {
                mInstance = new HuaweiTelephonyManager();
            }
            return mInstance;
        }
    }

    private static SubscriptionManager subscriptions(Context context) {
        if (context == null) {
            return null;
        }
        try {
            return (SubscriptionManager)
                    context.getSystemService(Context.TELEPHONY_SUBSCRIPTION_SERVICE);
        } catch (Throwable error) {
            Log.w(TAG, "SubscriptionManager unavailable: " + error);
            return null;
        }
    }

    private static TelephonyManager telephony(Context context) {
        if (context == null) {
            return null;
        }
        try {
            return (TelephonyManager) context.getSystemService(Context.TELEPHONY_SERVICE);
        } catch (Throwable error) {
            Log.w(TAG, "TelephonyManager unavailable: " + error);
            return null;
        }
    }

    /** 卡类型（EMUI 专有枚举）。公开 API 无法判定，返回 UNKNOWN_CARD。 */
    public int getCardType(int slotId) {
        Log.i(TAG, "getCardType: EMUI-only, slot=" + slotId);
        return UNKNOWN_CARD;
    }

    /** 默认 4G 卡槽。公开等价物：默认数据订阅 → 槽位。 */
    public int getDefault4GSlotId() {
        Context context = com.huawei.android.content.ContextEx.currentApplication();
        SubscriptionManager manager = subscriptions(context);
        if (manager == null) {
            return UNKNOWN_CARD;
        }
        try {
            int subId = SubscriptionManager.getDefaultDataSubscriptionId();
            return getSlotIdFromSubId(subId);
        } catch (Throwable error) {
            Log.w(TAG, "getDefault4GSlotId failed: " + error);
            return UNKNOWN_CARD;
        }
    }

    /** ICC ATR（EMUI 专有）。公开 API 没有对应数据，返回 null。 */
    public String getIccATR() {
        Log.i(TAG, "getIccATR: EMUI-only, returning null");
        return null;
    }

    /** 运营商标识。公开等价物：TelephonyManager.getNetworkOperator()。 */
    public String getOperatorKey(Context context) {
        TelephonyManager manager = telephony(context);
        if (manager == null) {
            return null;
        }
        try {
            return manager.getNetworkOperator();
        } catch (Throwable error) {
            Log.w(TAG, "getOperatorKey failed: " + error);
            return null;
        }
    }

    /** 指定槽位的运营商标识，走该槽位的订阅。 */
    public String getOperatorKey(Context context, int slotId) {
        TelephonyManager manager = telephony(context);
        SubscriptionManager subscriptionManager = subscriptions(context);
        if (manager == null || subscriptionManager == null) {
            return getOperatorKey(context);
        }
        try {
            int subId = getSubidFromSlotId(slotId);
            SubscriptionInfo info = subscriptionManager.getActiveSubscriptionInfo(subId);
            if (info == null) {
                return null;
            }
            return info.getMccString() + info.getMncString();
        } catch (Throwable error) {
            Log.w(TAG, "getOperatorKey(slot) failed: " + error);
            return null;
        }
    }

    /** 公开等价物：SubscriptionManager.getSlotIndex(subId)。 */
    public int getSlotIdFromSubId(int subId) {
        try {
            return SubscriptionManager.getSlotIndex(subId);
        } catch (Throwable error) {
            Log.w(TAG, "getSlotIdFromSubId failed: " + error);
            return SubscriptionManager.INVALID_SIM_SLOT_INDEX;
        }
    }

    /** 公开等价物：SubscriptionManager.getSubscriptionId(slotId)。 */
    public int getSubidFromSlotId(int slotId) {
        try {
            return SubscriptionManager.getSubscriptionId(slotId);
        } catch (Throwable error) {
            Log.w(TAG, "getSubidFromSlotId failed: " + error);
            return SubscriptionManager.INVALID_SUBSCRIPTION_ID;
        }
    }

    /** EMUI 专有判定，公开 API 没有等价物，返回 false。 */
    public boolean isCTCdmaCardInGsmMode() {
        Log.i(TAG, "isCTCdmaCardInGsmMode: EMUI-only, reporting false");
        return false;
    }

    /** EMUI 专有判定，公开 API 没有等价物，返回 false。 */
    public boolean isCTNationRoamingEnable() {
        Log.i(TAG, "isCTNationRoamingEnable: EMUI-only, reporting false");
        return false;
    }

    /** 该槽位是否插卡。公开等价物：该槽位是否有活动订阅。 */
    public boolean isCardPresent(int slotId) {
        Context context = com.huawei.android.content.ContextEx.currentApplication();
        if (slotId < 0) {
            TelephonyManager manager = telephony(context);
            return manager != null && manager.hasIccCard();
        }
        SubscriptionManager manager = subscriptions(context);
        if (manager == null) {
            return false;
        }
        try {
            return manager.getActiveSubscriptionInfoForSimSlotIndex(slotId) != null;
        } catch (Throwable error) {
            Log.w(TAG, "isCardPresent failed: " + error);
            return false;
        }
    }

    /** EMUI 专有开关，公开 API 没有等价物，返回 false。 */
    public boolean isSetDefault4GSlotIdEnabled() {
        Log.i(TAG, "isSetDefault4GSlotIdEnabled: EMUI-only, reporting false");
        return false;
    }

    /** 公开等价物：该订阅 id 是否处于活动状态。 */
    public boolean isSubActive(int subId) {
        try {
            Context context = com.huawei.android.content.ContextEx.currentApplication();
            SubscriptionManager manager = subscriptions(context);
            if (manager == null) {
                return false;
            }
            for (SubscriptionInfo info : manager.getActiveSubscriptionInfoList()) {
                if (info != null && info.getSubscriptionId() == subId) {
                    return true;
                }
            }
            return false;
        } catch (Throwable error) {
            Log.w(TAG, "isSubActive failed: " + error);
            return false;
        }
    }

    /** EMUI 专有：设置默认 4G 槽位。公开 API 只能改默认数据订阅，语义不同 → 不动作。 */
    public void setDefault4GSlotId(int slotId, Message callback) {
        Log.i(TAG, "setDefault4GSlotId: EMUI-only, slot=" + slotId + ", no action taken");
    }

    /** EMUI 专有的双卡模式设置，公开 API 没有等价物，返回 false。 */
    public boolean setDualCardMode(int mode) {
        Log.i(TAG, "setDualCardMode: EMUI-only, mode=" + mode + ", reporting false");
        return false;
    }

    /** EMUI 专有的等待状态回调，公开 API 没有等价物，不动作。 */
    public void waitingSetDefault4GSlotDone(boolean done) {
        Log.i(TAG, "waitingSetDefault4GSlotDone: EMUI-only, done=" + done);
    }
}
