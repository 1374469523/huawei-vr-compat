package com.huawei.android.os;

import android.os.Build;

/**
 * Huawei's Build extension. Only VERSION.EMUI_SDK_INT is referenced by the VR
 * packages; on a common Android build there is no EMUI level, so it reports 0
 * the same way a non-EMUI build did.
 */
public final class BuildEx {
    private BuildEx() {
    }

    public static final class VERSION {
        private VERSION() {
        }

        public static final int EMUI_SDK_INT = readEmuiSdkInt();

        private static int readEmuiSdkInt() {
            // Read through the same reflective wrapper the rest of the compat
            // layer uses; a build without the EMUI property reports 0.
            return SystemPropertiesEx.getInt("ro.build.hw_emui_api_level", 0);
        }
    }

    public static String getRelease() {
        return Build.VERSION.RELEASE;
    }
}
