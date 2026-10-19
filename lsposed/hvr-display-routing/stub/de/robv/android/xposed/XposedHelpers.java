package de.robv.android.xposed;

/** 编译期存根。 */
public final class XposedHelpers {
    public static void findAndHookMethod(String className, ClassLoader classLoader,
                                         String methodName, Object... parameterTypesAndCallback) {
    }

    public static Object getObjectField(Object object, String name) {
        return null;
    }
}
