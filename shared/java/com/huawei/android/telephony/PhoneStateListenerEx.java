package com.huawei.android.telephony;

import android.os.Looper;
import android.telephony.PhoneStateListener;
import android.telephony.PreciseCallState;
import android.telephony.SignalStrength;

/**
 * 照官方实现移植（原厂件/hwframework.jar 的
 * com/huawei/android/telephony/PhoneStateListenerEx.smali）。
 *
 * 官方的关键接线只有一条：
 *
 *     onPreciseCallStateChanged(PreciseCallState callState) {
 *         onPreciseCallStateChangedCallBack(new PreciseCallStateEx(callState));
 *     }
 *     onPreciseCallStateChangedCallBack(PreciseCallStateEx callState) { }   // 子类覆写
 *
 * 应用侧（桌面的 l2/s）就是覆写 `onPreciseCallStateChangedCallBack`，再由
 * `l2/u` 调用 `PreciseCallStateEx.getRingingCallState/getForegroundCallState/...`
 * 判断「通话中不进 VR」。
 *
 * 之前我方版本只保留了 onSignalStrengthsChanged，把这条链断掉了：监听器收不到
 * 任何精确通话状态，桌面的判断永远走默认分支。现在按官方补回。
 *
 * 三个构造函数与官方一致；`onPreciseCallStateChanged` 覆写的是平台的 hidden
 * 方法（编译期靠 shared/stubs 里的 PreciseCallState 存根，运行期是平台自己的
 * 类，签名一致才会被回调）。
 */
public class PhoneStateListenerEx extends PhoneStateListener {

    /** 官方常量（与 android.telephony.PhoneStateListener 的 LISTEN_* 同值）。 */
    public static final int LISTEN_PRECISE_CALL_STATE = 0x800;
    public static final int LISTEN_OEM_HOOK_RAW_EVENT = 0x8000;
    public static final int LISTEN_CALL_DISCONNECT_CAUSES = 0x2000000;

    public PhoneStateListenerEx() {
        super();
    }

    public PhoneStateListenerEx(int subId) {
        super();
    }

    public PhoneStateListenerEx(int subId, Looper looper) {
        // 官方的 `PhoneStateListener(Looper)` 是 hidden 构造；公开 SDK 只有
        // `PhoneStateListener()` 与 API 30 起的 `(Executor)`。这里退回无参构造，
        // 回调仍会送到监听器所属进程的主线程（平台对无参构造的默认行为）。
        super();
    }

    @Override
    public void onSignalStrengthsChanged(SignalStrength signalStrength) {
        // 应用侧会 invoke-super 到这里，保持送达。
        super.onSignalStrengthsChanged(signalStrength);
    }

    public void onPreciseCallStateChanged(PreciseCallState callState) {
        onPreciseCallStateChangedCallBack(new PreciseCallStateEx(callState));
    }

    /** 子类覆写；基类与官方一样什么都不做。 */
    public void onPreciseCallStateChangedCallBack(PreciseCallStateEx callState) {
    }
}
