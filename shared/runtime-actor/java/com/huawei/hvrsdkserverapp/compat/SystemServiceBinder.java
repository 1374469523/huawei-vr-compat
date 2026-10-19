package com.huawei.hvrsdkserverapp.compat;

import android.os.Binder;
import android.os.Parcel;
import android.os.RemoteException;
import android.util.Log;

/**
 * Server side of the launcher's {@code ISysServiceInterface}.
 *
 * The original desktop {@code VRService} talks to EMUI's VR system service over
 * this binder (descriptor and transaction codes are read straight out of the
 * desktop dex: {@code a3/a$a$a.smali}). On a generic device there is no system
 * service, so the port answers with the same wire format and the original code
 * keeps running unchanged.
 *
 * Methods (desktop names, obfuscated there):
 *   1 {@code h(int, List)} void    - setDisplayPowerMode / low power mode
 *   2 {@code v(int, List)} int
 *   3 {@code A(int, List)} String
 *   4 {@code r(int, List)} boolean
 *   5 {@code H(int, List)} boolean - 0x899 connect ack, 0x89a remote prepare
 */
final class SystemServiceBinder extends Binder {
    static final String DESCRIPTOR = "com.huawei.vrservice.ISysServiceInterface";

    static final int WHAT_CONNECT = 0x899;
    static final int WHAT_REMOTE_PREPARE = 0x89a;

    /**
     * 桌面 {@code z0/c.n()} 的 what，方法名在那边就叫 getVRModeState：返回值按位
     * 判 VR 模式（{@code z0/c.q()} 取的是 {@code state & 1}）。原版这是 EMUI 的
     * VR 系统服务在跟踪的状态，这里由 {@link VrSystemActor} 按真实硬件推进。
     */
    static final int WHAT_GET_VR_MODE_STATE = 0x835;

    /** 桌面 z0/c 的电量查询（getHelmetBattery）。 */
    static final int WHAT_GET_HELMET_BATTERY = 0x836;

    /** 桌面 z0/c 的接近查询（getProximityState）。 */
    static final int WHAT_GET_PROXIMITY_STATE = 0x838;

    private static final int TRANSACTION_H = 1;
    private static final int TRANSACTION_V = 2;
    private static final int TRANSACTION_A = 3;
    private static final int TRANSACTION_R = 4;
    private static final int TRANSACTION_H_BOOL = 5;

    private final VrSystemActor actor;

    SystemServiceBinder(VrSystemActor actor) {
        this.actor = actor;
    }

    @Override
    protected boolean onTransact(int code, Parcel data, Parcel reply, int flags)
            throws RemoteException {
        if (code < TRANSACTION_H || code > TRANSACTION_H_BOOL) {
            return super.onTransact(code, data, reply, flags);
        }
        data.enforceInterface(DESCRIPTOR);
        int what = data.readInt();
        int count = data.readInt();
        for (int index = 0; index < count; index++) {
            data.readInt();
        }
        Log.i(VrSystemActor.TAG, "system service call what=0x" + Integer.toHexString(what)
                + " transaction=" + code + " args=" + count);
        if (reply != null) {
            reply.writeNoException();
            switch (code) {
                case TRANSACTION_V:
                    // 0x835 = getVRModeState：眼镜在位且环境推进到「戴上」那一步才为真。
                    // 0x836 = getHelmetBattery / 0x838 = getProximityState：眼镜的 HID
                    // 报告里没有这两项（见 docs/evidence/proximity-battery-2026-09-16.md），
                    // 按通用安卓口径改问 Android 自己的电量服务与接近传感器；
                    // 取不到返回 -1，不编数值。其余查询仍保持 0。
                    int value = 0;
                    if (what == WHAT_GET_VR_MODE_STATE) {
                        value = actor.isVrMode() ? 1 : 0;
                    } else if (what == WHAT_GET_HELMET_BATTERY) {
                        value = actor.helmetBattery();
                    } else if (what == WHAT_GET_PROXIMITY_STATE) {
                        value = actor.proximityState();
                    }
                    reply.writeInt(value);
                    break;
                case TRANSACTION_A:
                    reply.writeString(null);
                    break;
                case TRANSACTION_R:
                case TRANSACTION_H_BOOL:
                    // 0x899 connect ack and 0x89a "remote prepare" both succeed:
                    // the port has no remote side to wait for.
                    reply.writeInt(1);
                    break;
                default:
                    break;
            }
        }
        if (what == WHAT_CONNECT) {
            actor.onSystemServiceConnected();
        }
        return true;
    }
}
