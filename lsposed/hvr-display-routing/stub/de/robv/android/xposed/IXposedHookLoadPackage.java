package de.robv.android.xposed;

import de.robv.android.xposed.callbacks.XC_LoadPackage;

/** 只为编译本模块用的存根；运行时由 LSPosed 提供真类。 */
public interface IXposedHookLoadPackage {
    void handleLoadPackage(XC_LoadPackage.LoadPackageParam lpparam) throws Throwable;
}
