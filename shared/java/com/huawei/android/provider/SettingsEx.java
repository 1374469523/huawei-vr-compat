package com.huawei.android.provider;

import android.content.ContentResolver;
import android.provider.Settings;

/**
 * Huawei's Settings extension. Systemex is the same table as Settings.System on
 * common Android, which is exactly what EMUI forwards to as well.
 */
public final class SettingsEx {
    private SettingsEx() {
    }

    public static final class Systemex {
        private Systemex() {
        }

        public static int getInt(ContentResolver resolver, String name, int defaultValue) {
            if (resolver == null || name == null) return defaultValue;
            return Settings.System.getInt(resolver, name, defaultValue);
        }

        public static boolean putInt(ContentResolver resolver, String name, int value) {
            if (resolver == null || name == null) return false;
            return Settings.System.putInt(resolver, name, value);
        }

        public static float getFloat(ContentResolver resolver, String name, float defaultValue) {
            if (resolver == null || name == null) return defaultValue;
            return Settings.System.getFloat(resolver, name, defaultValue);
        }
    }
}
