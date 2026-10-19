package com.huawei.android.iawareperf;

/**
 * Huawei's iAware performance hint API (CPU/GPU frequency boost).
 *
 * There is no generic Android equivalent: perf hints are a vendor capability.
 * The class therefore keeps the interface and reports "no hint applied" (-1)
 * instead of inventing a result. It is a performance hint only - nothing in the
 * original flow depends on its return value.
 */
public class UniPerfEx {

    private static final UniPerfEx INSTANCE = new UniPerfEx();
    private static final Object LOCK = new Object();

    private UniPerfEx() {
    }

    public static UniPerfEx getInstance() {
        // 官方是加锁单例；这里 INSTANCE 已经是常量，锁只为与原实现同形。
        synchronized (LOCK) {
            return INSTANCE;
        }
    }

    /**
     * 官方：`android.iawareperf.UniPerf.getInstance().uniPerfEvent(cmdId, pkgName, payload)`
     * （hidden 的华为性能提示服务）。通用安卓没有等价服务，按项目口径返回
     * 「不可用」-1，不伪造提示已生效。原流程也不依赖它的返回值。
     */
    public int uniPerfEvent(int eventId, String arg, int[] data) {
        return -1;
    }
}
