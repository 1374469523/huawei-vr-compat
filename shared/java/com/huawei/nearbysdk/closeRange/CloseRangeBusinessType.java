package com.huawei.nearbysdk.closeRange;

/**
 * Huawei's near-field business type identifier. The desktop only reads iConnect;
 * the instance is kept so filters compare the same way as on EMUI.
 */
public class CloseRangeBusinessType {
    public static final CloseRangeBusinessType iConnect = new CloseRangeBusinessType("iConnect");

    private final String name;

    public CloseRangeBusinessType(String name) {
        this.name = name;
    }

    public String getName() {
        return name;
    }

    @Override
    public String toString() {
        return name;
    }
}
