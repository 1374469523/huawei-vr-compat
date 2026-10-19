package com.huawei.nearbysdk.closeRange;

/**
 * Huawei's near-field device filter. Built exactly like the original API, the
 * filter only carries the business type and the device name prefix.
 */
public class CloseRangeDeviceFilter {
    private final CloseRangeBusinessType businessType;
    private final String deviceName;

    private CloseRangeDeviceFilter(CloseRangeBusinessType businessType, String deviceName) {
        this.businessType = businessType;
        this.deviceName = deviceName;
    }

    public static CloseRangeDeviceFilter buildFilter(CloseRangeBusinessType businessType,
            String deviceName) {
        return new CloseRangeDeviceFilter(businessType, deviceName);
    }

    public CloseRangeBusinessType getBusinessType() {
        return businessType;
    }

    public String getDeviceName() {
        return deviceName;
    }
}
