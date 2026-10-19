package android.telephony;

/**
 * Compile-time stub for the hidden platform class android.telephony.PreciseCallState.
 *
 * EMUI 的 com/huawei/android/telephony/PreciseCallStateEx 就是它的包装：
 * 构造时存下这个对象，静态 getter 再逐条转发给下面这些方法。存根只参与编译，
 * 不进包；运行时用设备上真正的类。
 */
public class PreciseCallState {

    public int getRingingCallState() {
        throw new UnsupportedOperationException("compile-time stub");
    }

    public int getForegroundCallState() {
        throw new UnsupportedOperationException("compile-time stub");
    }

    public int getBackgroundCallState() {
        throw new UnsupportedOperationException("compile-time stub");
    }

    public int getDisconnectCause() {
        throw new UnsupportedOperationException("compile-time stub");
    }

    public int getPreciseDisconnectCause() {
        throw new UnsupportedOperationException("compile-time stub");
    }
}
