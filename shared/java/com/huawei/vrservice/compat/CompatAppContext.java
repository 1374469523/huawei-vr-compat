package com.huawei.vrservice.compat;

import android.content.Context;

import com.huawei.android.content.ContextEx;

/**
 * Application context holder for the compat layer.
 *
 * Some original Huawei platform APIs take no Context (AudioManagerEx is built
 * with `new AudioManagerEx()`), but the common-Android replacement needs one.
 * Two sources, in order:
 *
 *  1. the compat provider declared in com.huawei.vrservice - ActivityThread
 *     instantiates an app's providers when the process starts, for any
 *     component, so this is set as soon as the process is up;
 *  2. the processes that have no such provider fall back to the same reflective
 *     lookup the rest of the compat layer already uses (ContextEx).
 *
 * Both are real application contexts; nothing is synthesised here.
 */
public final class CompatAppContext {

    private static volatile Context applicationContext;

    private CompatAppContext() {
    }

    public static void set(Context context) {
        if (context == null) {
            return;
        }
        Context application = context.getApplicationContext();
        applicationContext = application != null ? application : context;
    }

    public static Context get() {
        Context context = applicationContext;
        if (context != null) {
            return context;
        }
        return ContextEx.currentApplication();
    }
}