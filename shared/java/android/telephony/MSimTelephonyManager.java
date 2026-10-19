package android.telephony;

import android.content.Context;
import android.util.Log;

/**
 * Multi-SIM telephony manager used by the original desktop code.
 *
 * {@code w0.b.r(VRManager.java:4)} asks it whether a call is in progress before
 * entering VR, and {@code l2.q} watches the same state. The class only exists on
 * Huawei/MTK builds; on stock Android its resolution failed with
 *
 *   Caused by: java.lang.ClassNotFoundException: android.telephony.MSimTelephonyManager
 *     at w0.b.r(VRManager.java:4)
 *     at w0.b.e(VRManager.java:1)
 *     at t0.c.f(VRWorkThread.java:2)
 *
 * and killed the environment thread. The same call state is available through
 * the public TelephonyManager, so {@code slotId} is accepted and ignored on a
 * single-SIM view.
 */
public class MSimTelephonyManager {
    private static final String TAG = "MSimTelephonyManager";

    private static boolean reportedUnavailable;

    private final TelephonyManager delegate;

    private MSimTelephonyManager(Context context) {
        delegate = (TelephonyManager) context.getSystemService(Context.TELEPHONY_SERVICE);
    }

    public static MSimTelephonyManager from(Context context) {
        if (context == null) {
            return null;
        }
        // 官方就是单例：sContext 为空时建一次，之后都返回 sInstance。
        MSimTelephonyManager instance = sInstance;
        if (instance == null) {
            synchronized (MSimTelephonyManager.class) {
                if (sInstance == null) {
                    sInstance = new MSimTelephonyManager(context);
                }
                instance = sInstance;
            }
        }
        return instance;
    }

    /**
     * 官方：`TelephonyManager.getDefault().getCallStateForSlot(subscription)`
     * ——两者都是 hidden 方法。通用安卓的公开等价物是 `TelephonyManager.getCallState()`
     * （VR 只需要知道「当前有没有通话」，单卡视图足够），因此 slotId 接受但忽略。
     */
    public int getCallState(int slotId) {
        if (delegate == null) {
            return TelephonyManager.CALL_STATE_IDLE;
        }
        try {
            return delegate.getCallState();
        } catch (Throwable error) {
            // READ_PHONE_STATE is a runtime permission; without it the platform
            // refuses. Reported once, then treated as "no call in progress".
            if (!reportedUnavailable) {
                reportedUnavailable = true;
                Log.w(TAG, "getCallState unavailable: " + error);
            }
            return TelephonyManager.CALL_STATE_IDLE;
        }
    }

    private static volatile MSimTelephonyManager sInstance;
}
