package com.huawei.android.app;

import android.content.pm.FeatureInfo;

import com.huawei.android.content.ContextEx;

/**
 * Huawei's PackageManager extension. hasHwSystemFeature reports Huawei only
 * features, which do not exist here, so it returns false; the feature list is
 * the real one this device reports through PackageManager.
 */
public final class PackageManagerEx {
    private PackageManagerEx() {
    }

    public static boolean hasHwSystemFeature(String feature) {
        android.content.Context context = ContextEx.currentApplication();
        if (context == null || feature == null) return false;
        try {
            return context.getPackageManager().hasSystemFeature(feature);
        } catch (Throwable error) {
            return false;
        }
    }

    public static FeatureInfo[] getHwSystemAvailableFeatures() {
        android.content.Context context = ContextEx.currentApplication();
        if (context == null) return new FeatureInfo[0];
        try {
            FeatureInfo[] features = context.getPackageManager().getSystemAvailableFeatures();
            return features == null ? new FeatureInfo[0] : features;
        } catch (Throwable error) {
            return new FeatureInfo[0];
        }
    }
}
