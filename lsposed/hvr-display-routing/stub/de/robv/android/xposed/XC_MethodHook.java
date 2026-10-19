package de.robv.android.xposed;

/** 编译期存根。 */
public abstract class XC_MethodHook {
    protected void beforeHookedMethod(MethodHookParam param) throws Throwable {
    }

    protected void afterHookedMethod(MethodHookParam param) throws Throwable {
    }

    public static class MethodHookParam {
        public Object[] args;
        public Object thisObject;

        public void setResult(Object result) {
        }
    }
}
