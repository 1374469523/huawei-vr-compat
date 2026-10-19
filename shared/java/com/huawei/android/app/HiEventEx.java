package com.huawei.android.app;

import android.content.Context;

import org.json.JSONObject;

/**
 * Huawei analytics event carrier. The VR packages build events and hand them to
 * HiViewEx.report; this port has no Huawei analytics backend (and no network),
 * so the object only carries the data so the caller's flow stays identical.
 */
public final class HiEventEx {
    private final int eventId;
    private final JSONObject payload = new JSONObject();
    private String packageName = "";
    private String appVersion = "";

    public HiEventEx(int eventId) {
        this.eventId = eventId;
    }

    public HiEventEx putAppInfo(Context context) {
        if (context == null) return this;
        try {
            packageName = context.getPackageName();
            appVersion = String.valueOf(context.getPackageManager()
                    .getPackageInfo(packageName, 0).versionName);
        } catch (Throwable ignored) {
            // A package without readable info keeps empty identity fields.
        }
        return this;
    }

    public HiEventEx put(String key, Object value) {
        if (key == null) return this;
        try {
            payload.put(key, value);
        } catch (Throwable ignored) {
            // A value that cannot be serialised is simply not carried.
        }
        return this;
    }

    public int getEventId() {
        return eventId;
    }

    public JSONObject getPayload() {
        return payload;
    }

    public String getPackageName() {
        return packageName;
    }

    public String getAppVersion() {
        return appVersion;
    }
}
