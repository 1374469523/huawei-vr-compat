package com.huawei.android.telephony;

import android.telephony.PreciseCallState;
import android.util.Log;

/**
 * 照官方实现移植（原厂件/hwframework.jar 的
 * com/huawei/android/telephony/PreciseCallStateEx.smali）。
 *
 * 官方结构：**公开构造函数** `PreciseCallStateEx(PreciseCallState)` 存下平台的
 * PreciseCallState，五个静态 getter 再转发给它；null 输入一律 -1
 * （官方 `PRECISE_CALL_STATE_NOT_VALID`）。
 *
 * 之前我方版本把构造函数写成了 private、只靠反射读一个 `Object state`，
 * 结果应用侧根本构造不出这个对象，桌面那条「通话中不进入 VR」的判断永远拿不到
 * 真实状态。现在按官方补回公开构造函数（EMUI 的 PhoneStateListenerEx 就是
 * 在 onPreciseCallStateChanged 里 new 一个出来交给应用的）。
 *
 * 常量与官方逐字一致（同样来自 android.telephony.PreciseCallState）。
 */
public final class PreciseCallStateEx {

    private static final String TAG = "PreciseCallStateEx";

    public static final int PRECISE_CALL_STATE_IDLE = 0;
    public static final int PRECISE_CALL_STATE_ACTIVE = 1;
    public static final int PRECISE_CALL_STATE_HOLDING = 2;
    public static final int PRECISE_CALL_STATE_DIALING = 3;
    public static final int PRECISE_CALL_STATE_ALERTING = 4;
    public static final int PRECISE_CALL_STATE_INCOMING = 5;
    public static final int PRECISE_CALL_STATE_WAITING = 6;
    public static final int PRECISE_CALL_STATE_DISCONNECTED = 7;
    public static final int PRECISE_CALL_STATE_NOT_VALID = -1;

    private final PreciseCallState mCallState;

    public PreciseCallStateEx(PreciseCallState callState) {
        mCallState = callState;
    }

    private PreciseCallState getCallState() {
        return mCallState;
    }

    public static int getForegroundCallState(PreciseCallStateEx state) {
        PreciseCallState inner = inner(state);
        return inner == null ? PRECISE_CALL_STATE_NOT_VALID : read(inner, "getForegroundCallState");
    }

    public static int getBackgroundCallState(PreciseCallStateEx state) {
        PreciseCallState inner = inner(state);
        return inner == null ? PRECISE_CALL_STATE_NOT_VALID : read(inner, "getBackgroundCallState");
    }

    public static int getRingingCallState(PreciseCallStateEx state) {
        PreciseCallState inner = inner(state);
        return inner == null ? PRECISE_CALL_STATE_NOT_VALID : read(inner, "getRingingCallState");
    }

    public static int getDisconnectCause(PreciseCallStateEx state) {
        PreciseCallState inner = inner(state);
        return inner == null ? PRECISE_CALL_STATE_NOT_VALID : read(inner, "getDisconnectCause");
    }

    public static int getPreciseDisconnectCause(PreciseCallStateEx state) {
        PreciseCallState inner = inner(state);
        return inner == null
                ? PRECISE_CALL_STATE_NOT_VALID
                : read(inner, "getPreciseDisconnectCause");
    }

    private static PreciseCallState inner(PreciseCallStateEx state) {
        return state == null ? null : state.getCallState();
    }

    /**
     * 官方是直接调 PreciseCallState 的对应方法。这里先直连（编译期有存根），
     * 若设备上的实现变了（例如取不到方法）再退一次反射，最后才 -1。
     */
    private static int read(PreciseCallState state, String method) {
        try {
            if ("getForegroundCallState".equals(method)) {
                return state.getForegroundCallState();
            }
            if ("getBackgroundCallState".equals(method)) {
                return state.getBackgroundCallState();
            }
            if ("getRingingCallState".equals(method)) {
                return state.getRingingCallState();
            }
            if ("getDisconnectCause".equals(method)) {
                return state.getDisconnectCause();
            }
            if ("getPreciseDisconnectCause".equals(method)) {
                return state.getPreciseDisconnectCause();
            }
            return PRECISE_CALL_STATE_NOT_VALID;
        } catch (Throwable error) {
            Log.w(TAG, method + " failed", error);
            return PRECISE_CALL_STATE_NOT_VALID;
        }
    }
}
