package android.media;

/**
 * Compile-time stub for the hidden platform class android.media.AudioSystem.
 *
 * EMUI 的 com.huawei.android.media.AudioSystemEx 每个方法都是对它的一行直连
 * （见 原厂件/hwframework.jar 的 AudioSystemEx.smali）：
 *
 *     invoke-static {p0}, Landroid/media/AudioSystem;->setParameters(...)I
 *
 * 直接调用（不是反射）在 targetSdk≥28 上依然可用：hidden API 限制只拦反射与
 * JNI。这个存根只参与编译，不进包；运行时用设备上真正的 AudioSystem。
 */
public class AudioSystem {

    public static int setParameters(String keyValuePairs) {
        throw new UnsupportedOperationException("compile-time stub");
    }

    public static String getParameters(String keys) {
        throw new UnsupportedOperationException("compile-time stub");
    }

    public static int setForceUse(int usage, int config) {
        throw new UnsupportedOperationException("compile-time stub");
    }
}
