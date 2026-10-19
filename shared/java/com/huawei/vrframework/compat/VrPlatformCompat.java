package com.huawei.vrframework.compat;

import android.content.Context;
import android.hardware.display.DisplayManager;
import android.hardware.usb.UsbDevice;
import android.hardware.usb.UsbManager;
import android.util.Log;
import android.view.Display;

/**
 * Replacement for the Huawei kernel probe the VR framework uses.
 *
 * Three places decide whether the glasses are connected by looking for the
 * Huawei kernel device node:
 *
 *     new File("/dev/hwvr1").exists()
 *   VrSystemClient.isVRGlassExist()      -> "vr glass not exist, no need to bind service"
 *   VrMonitor.isVRGlassDevExist()
 *   VrTouchService.isVRGlassExist()
 *
 * That node is created by Huawei's kernel driver when the glasses are plugged
 * in; a stock device has no such driver, so the whole phone-controller path was
 * skipped even though the glasses really were attached:
 *
 *   W PhoneController: vr glass not exist, no need to bind service
 *   W VrControllerManager: bind VrTouchService failed
 *   E Unity_HVRController: Right controller is not available in Update
 *
 * The same question - "are the glasses attached?" - is answered here from the
 * two real signals this port relies on:
 *
 *   1. the USB identity the glasses present on the wire: vendor 0x12d1 with
 *      product 0x1092 ("HUAWEI GLASS CV10", the DisplayPort + HID composite) or
 *      0x107e ("HUAWEI GLASS HID", the HID pair the runtime and handle use);
 *   2. an external display being connected, which is the DisplayPort side of
 *      the very same cable.
 *
 * Neither signal is a device name. Any headset that comes up as an external
 * display on that Huawei USB identity answers true; any other external screen
 * without the identity answers false. No state is invented: with the glasses
 * unplugged both signals disappear and the check returns false, exactly like
 * the missing kernel node.
 */
public final class VrPlatformCompat {
    private static final String TAG = "VrPlatformCompat";

    /** Huawei's USB vendor id, used by every VR Glass generation. */
    public static final int HUAWEI_VENDOR_ID = 0x12d1;
    /** "HUAWEI GLASS CV10": DisplayPort + HID composite of the CV10 glass. */
    public static final int GLASS_CV10_PRODUCT_ID = 0x1092;
    /** "HUAWEI GLASS HID": the HID interface pair the runtime and handle use. */
    public static final int GLASS_HID_PRODUCT_ID = 0x107e;

    private VrPlatformCompat() {
    }

    public static boolean isVrGlassPresent() {
        Context context = application();
        if (context == null) {
            Log.w(TAG, "no application context, reporting glass absent");
            return false;
        }
        return isVrGlassPresent(context);
    }

    /**
     * Same answer, from the caller's context. Both real signals must agree: the
     * USB identity proves which device is on the cable, the external display
     * proves its DisplayPort side came up.
     */
    public static boolean isVrGlassPresent(Context context) {
        if (context == null) {
            return false;
        }
        boolean usb = hasGlassUsbIdentity(context);
        boolean display = hasExternalDisplay(context);
        Log.i(TAG, "glass probe: usb=" + usb + " externalDisplay=" + display);
        return usb && display;
    }

    /** True while a USB device with the Huawei glass identity is attached. */
    public static boolean hasGlassUsbIdentity(Context context) {
        if (context == null) {
            return false;
        }
        UsbManager manager =
                (UsbManager) context.getSystemService(Context.USB_SERVICE);
        if (manager == null) {
            return false;
        }
        try {
            for (UsbDevice device : manager.getDeviceList().values()) {
                if (device.getVendorId() == HUAWEI_VENDOR_ID
                        && (device.getProductId() == GLASS_CV10_PRODUCT_ID
                        || device.getProductId() == GLASS_HID_PRODUCT_ID)) {
                    return true;
                }
            }
        } catch (Throwable error) {
            // Listing can be restricted: report "no identity" instead of guessing.
            Log.w(TAG, "usb probe unavailable: " + error);
        }
        return false;
    }

    /** True when any display other than the built-in panels is connected. */
    public static boolean hasExternalDisplay(Context context) {
        return externalDisplay(context) != null;
    }

    /**
     * The external display the glasses present, or {@code null} when none is
     * connected. Selection is by public display state, never by name: the main
     * panel is {@link Display#DEFAULT_DISPLAY} and the foldable's cover panel
     * reports {@link Display#STATE_OFF} while the phone is open, so neither is
     * ever returned. This only ever *confirms* the USB identity above - on its
     * own it would also match the cover panel of a folded phone.
     */
    public static Display externalDisplay(Context context) {
        if (context == null) {
            return null;
        }
        DisplayManager manager =
                (DisplayManager) context.getSystemService(Context.DISPLAY_SERVICE);
        if (manager == null) {
            return null;
        }
        for (Display display : manager.getDisplays()) {
            if (display == null || display.getDisplayId() == Display.DEFAULT_DISPLAY) {
                continue;
            }
            if (display.getState() != Display.STATE_OFF) {
                return display;
            }
        }
        return null;
    }

    /** Real name of the connected external display, or {@code null}. */
    public static String externalDisplayName(Context context) {
        Display display = externalDisplay(context);
        return display == null ? null : display.getName();
    }

    /**
     * 走兼容层统一的 Context 来源（provider 注入的真实 application context）。
     *
     * 之前这里自己反射 `ActivityThread.currentApplication()`：Runtime 的 targetSdk 是
     * 26 时能用，但这个探测会被桌面等 targetSdk≥28 的进程调用，反射会被 hidden API
     * 拦掉，结果是「拿不到 context → 判定眼镜不在位 → 整条手柄链路被跳过」。
     */
    private static Context application() {
        return com.huawei.android.content.ContextEx.currentApplication();
    }
}
