package com.huawei.android.app;

import org.json.JSONObject;

/**
 * Huawei analytics entry point. Reporting is the only referenced behaviour and
 * there is no Huawei analytics backend here (the port has no network), so the
 * call is accepted and dropped instead of failing the caller's flow.
 */
public final class HiViewEx {
    private HiViewEx() {
    }

    public static HiEventEx byJson(int eventId, JSONObject json) {
        HiEventEx event = new HiEventEx(eventId);
        if (json != null) {
            java.util.Iterator<String> keys = json.keys();
            while (keys.hasNext()) {
                String key = keys.next();
                event.put(key, json.opt(key));
            }
        }
        return event;
    }

    public static void report(HiEventEx event) {
        // No analytics backend in the offline port; the event is intentionally
        // not sent anywhere.
    }
}
