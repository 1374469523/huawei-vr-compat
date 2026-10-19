package android.os;

/**
 * Compile-time stub for the hidden platform class android.os.SystemProperties.
 *
 * EMUI 的 com.huawei.android.os.SystemPropertiesEx 里每个方法都是对这个类的
 * 直接调用（见 原厂件/hwframework.jar 的 SystemPropertiesEx.smali）：
 *
 *     invoke-static {p0, p1}, Landroid/os/SystemProperties;->set(...)
 *
 * 直接调用（而不是反射）在 targetSdk≥28 上照样可用：hidden API 限制只拦
 * 反射与 JNI。这个存根只参与编译，不会进包；运行时用的是设备上真正的
 * android.os.SystemProperties。
 */
public class SystemProperties {

    public static String get(String key) {
        throw new UnsupportedOperationException("compile-time stub");
    }

    public static String get(String key, String def) {
        throw new UnsupportedOperationException("compile-time stub");
    }

    public static int getInt(String key, int def) {
        throw new UnsupportedOperationException("compile-time stub");
    }

    public static long getLong(String key, long def) {
        throw new UnsupportedOperationException("compile-time stub");
    }

    public static boolean getBoolean(String key, boolean def) {
        throw new UnsupportedOperationException("compile-time stub");
    }

    public static void set(String key, String val) {
        throw new UnsupportedOperationException("compile-time stub");
    }
}
