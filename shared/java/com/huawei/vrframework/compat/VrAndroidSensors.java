package com.huawei.vrframework.compat;

import android.content.Context;
import android.hardware.Sensor;
import android.hardware.SensorEvent;
import android.hardware.SensorEventListener;
import android.hardware.SensorManager;
import android.os.BatteryManager;
import android.util.Log;

/**
 * 通用安卓上的等价数据源（用户口径：华为专有通道拿不到的，就用 Android 自己的）。

 * 背景：CV10 眼镜的 HID 报告描述符里没有接近(report 4)与电量(report 8)这两个报告，
 * 原版走 `/dev/ttyUSB1` 的读法在本机拿不到任何值（证据见
 * docs/evidence/proximity-battery-2026-09-16.md）。这两项改用 Android 自己的：
 *
 * - 接近：`Sensor.TYPE_PROXIMITY`（本机真实存在的接近传感器，事件值 near/far）
 * - 电量：`BatteryManager`（CV10 由手机供电，本身没有独立电池）
 *
 * 取不到一律返回 {@link #UNAVAILABLE}，不编数值、不兜底。语义差异也如实记录：
 * Android 的接近传感器测的是「手机贴近物体」，不是「眼镜戴在头上」，它只是同一
 * 物理量的通用等价信号。
 */
public final class VrAndroidSensors {
    private static final String TAG = "HvrAndroidSensors";

    /** 没有数据源时的返回值（与原版失败分支一致）。 */
    public static final int UNAVAILABLE = -1;

    private static volatile Float proximityValue;
    private static volatile boolean proximityRegistered;

    private static final SensorEventListener LISTENER = new SensorEventListener() {
        @Override
        public void onSensorChanged(SensorEvent event) {
            if (event != null && event.values != null && event.values.length > 0) {
                proximityValue = event.values[0];
            }
        }

        @Override
        public void onAccuracyChanged(Sensor sensor, int accuracy) {
        }
    };

    private VrAndroidSensors() {
    }

    /**
     * 无参重载：给没有 Context 参数的调用点用（例如原版
     * `VRHelmetUtils.getProximityNativeJNI()` / `getBatteryNativeJNI()`）。
     * Context 走兼容层统一的真实 application context 来源，拿不到就返回不可用。
     */
    public static int proximity() {
        return proximity(com.huawei.android.content.ContextEx.currentApplication());
    }

    /** 无参重载，见 {@link #proximity()}。 */
    public static int batteryPercent() {
        return batteryPercent(com.huawei.android.content.ContextEx.currentApplication());
    }

    /**
     * 0 = 远离（far），1 = 贴近（near），{@link #UNAVAILABLE} = 本机没有这个传感器
     * 或还没收到事件。
     */
    public static int proximity(Context context) {
        if (context == null) {
            return UNAVAILABLE;
        }
        ensureProximity(context.getApplicationContext());
        Float value = proximityValue;
        if (value == null) {
            return UNAVAILABLE;
        }
        // Android 接近传感器：靠近时读数小于量程（常见为 0），远离时等于 maxRange。
        return value > 0 ? 0 : 1;
    }

    private static void ensureProximity(Context context) {
        if (proximityRegistered || context == null) {
            return;
        }
        synchronized (VrAndroidSensors.class) {
            if (proximityRegistered) {
                return;
            }
            try {
                SensorManager manager =
                        (SensorManager) context.getSystemService(Context.SENSOR_SERVICE);
                Sensor sensor = manager == null
                        ? null : manager.getDefaultSensor(Sensor.TYPE_PROXIMITY);
                if (sensor != null) {
                    manager.registerListener(LISTENER, sensor, SensorManager.SENSOR_DELAY_NORMAL);
                } else {
                    Log.w(TAG, "no proximity sensor on this device");
                }
            } catch (Throwable error) {
                Log.w(TAG, "proximity sensor unavailable", error);
            }
            proximityRegistered = true;
        }
    }

    /** 0..100 的百分比；拿不到返回 {@link #UNAVAILABLE}。 */
    public static int batteryPercent(Context context) {
        if (context == null) {
            return UNAVAILABLE;
        }
        try {
            BatteryManager manager =
                    (BatteryManager) context.getSystemService(Context.BATTERY_SERVICE);
            if (manager == null) {
                return UNAVAILABLE;
            }
            int capacity = manager.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY);
            return capacity < 0 ? UNAVAILABLE : capacity;
        } catch (Throwable error) {
            Log.w(TAG, "battery probe failed", error);
            return UNAVAILABLE;
        }
    }
}
