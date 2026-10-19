package com.huawei.nearbysdk.closeRange;

/**
 * Result handed to CloseRangeDeviceListener. The desktop only forwards it, so it
 * carries the discovered device description without inventing a device.
 */
public class CloseRangeResult {
    private final String deviceName;
    private final int businessTypeFlag;

    public CloseRangeResult(String deviceName, int businessTypeFlag) {
        this.deviceName = deviceName;
        this.businessTypeFlag = businessTypeFlag;
    }

    public String getDeviceName() {
        return deviceName;
    }

    public int getBusinessType() {
        return businessTypeFlag;
    }
}
