package android.vrsystem;

import android.content.ContentResolver;
import android.content.Context;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Bundle;
import android.os.IBinder;
import android.os.RemoteException;
import android.text.TextUtils;
import android.util.Log;

/**
 * Context.getSystemService("vr_system") 在通用安卓上的落点。
 *
 * 原版结构（官方原件：原厂件/hwPartVr.jar 的
 * android.vrsystem.HwVrServiceManagerImpl）：
 *
 *     ServiceManagerEx.getService("vr_system")            // 华为的服务注册表
 *         -> IVRSystemService$Stub.asInterface(binder)     // 官方 AIDL
 *         -> 逐条转发 IVRSystemServiceManager 的方法
 *
 * 这里**只换掉第一行**：通用安卓的应用进程没法注册/查询系统服务表，
 * 所以查表改成走一个同签名权限保护的 ContentProvider 注册表（宿主是桌面包
 * com.huawei.vrlauncherx，见 com.huawei.vrlauncherx.compat.VrSystemRegistryProvider）。
 * 第二行起全部照官方：用官方 IVRSystemService$Stub 生成的代理，不再自己拼
 * Parcel、也不自己写事务号。
 *
 * 两条硬纪律（docs/PATCH_AUDIT.md 第 25-31 节）：
 *  * 不代答服务：查不到就返回 null，让原版走它自己的失败分支，绝不伪造 VR 状态。
 *  * 不改原版逻辑：调用点只把 getSystemService("vr_system") 改成
 *    VRSystemServiceManagerImpl.get(context)，其余原样。
 */
public final class VRSystemServiceManagerImpl implements IVRSystemServiceManager {

    private static final String TAG = "HvrVrSystem";

    /** 兼容注册表的 authority；宿主见 VrSystemRegistryProvider。 */
    public static final String REGISTRY_AUTHORITY = "com.huawei.vrlauncherx.registry";
    public static final String METHOD_GET_SERVICE = "getService";
    public static final String KEY_BINDER = "binder";

    /** 官方 HwVrServiceManagerImpl 里的同一对常量，用于 isVRApplication。 */
    private static final String VR_METADATA_NAME = "com.huawei.android.vr.application.mode";
    private static final String VR_METADATA_VALUE = "vr_only";

    /** 官方 AIDL 代理（android.vrsystem.IVRSystemService$Stub 产出）。 */
    private volatile IVRSystemService service;

    /** 与代理配对的 binder，用公开的 isBinderAlive() 判断缓存是否过期。 */
    private volatile IBinder binder;

    /** 重新解析注册表时要用；只为兼容层的失效恢复，不参与原版语义。 */
    private final Context context;

    private VRSystemServiceManagerImpl(Context context, IBinder binder,
            IVRSystemService service) {
        this.context = context == null ? null : context.getApplicationContext();
        this.binder = binder;
        this.service = service;
    }

    /** 被打补丁的 getSystemService("vr_system") 调用点用的入口。 */
    public static VRSystemServiceManagerImpl get(Context context) {
        IBinder binder = resolve(context);
        if (binder == null) {
            Log.w(TAG, "vr_system is not registered; returning null");
            return null;
        }
        IVRSystemService service = IVRSystemService.Stub.asInterface(binder);
        if (service == null) {
            Log.w(TAG, "vr_system binder is not an IVRSystemService");
            return null;
        }
        return new VRSystemServiceManagerImpl(context, binder, service);
    }

    /**
     * 取一个当前活着的代理。
     *
     * 原版在 EMUI 里问的是常驻系统服务表，binder 不会随某个应用进程消失；
     * 通用安卓上这条注册表由桌面包托管，桌面包或 Runtime 监督进程重启后，
     * 调用方手里缓存的 {@code VRSystemServiceManagerImpl} 仍然指向旧 binder，
     * 会永久抛 {@code DeadObjectException}。这里只在「旧 binder 已经死了」
     * 这个客观事实上重新问一次注册表，不做任何状态代答。
     */
    private IVRSystemService liveService() {
        IBinder currentBinder = binder;
        IVRSystemService current = service;
        if (currentBinder != null && current != null && currentBinder.isBinderAlive()) {
            return current;
        }
        synchronized (this) {
            currentBinder = binder;
            current = service;
            if (currentBinder != null && current != null && currentBinder.isBinderAlive()) {
                return current;
            }
            IBinder fresh = resolve(context);
            if (fresh == null) {
                binder = null;
                service = null;
                return null;
            }
            IVRSystemService resolved = IVRSystemService.Stub.asInterface(fresh);
            if (resolved == null) {
                binder = null;
                service = null;
                return null;
            }
            binder = fresh;
            service = resolved;
            return resolved;
        }
    }

    /** 调用失败说明缓存过期，下次调用重新解析，避免死在旧 binder 上。 */
    private void invalidate() {
        binder = null;
        service = null;
    }

    private static IBinder resolve(Context context) {
        // 注册表条目只存在于宿主进程内存里：宿主重启后会短暂为空，
        // 发布方每秒补发一次，这里给它一个有界的等待窗口（最多 1 秒）。
        for (int attempt = 0; attempt < 6; attempt++) {
            IBinder binder = lookup(context);
            if (binder != null) {
                return binder;
            }
            if (attempt == 5) {
                break;
            }
            try {
                Thread.sleep(200L);
            } catch (InterruptedException interrupted) {
                Thread.currentThread().interrupt();
                return null;
            }
        }
        return null;
    }

    /** 问桌面托管的注册表要 "vr_system" 那个 binder。 */
    private static IBinder lookup(Context context) {
        if (context == null) {
            return null;
        }
        try {
            ContentResolver resolver = context.getContentResolver();
            Bundle answer = resolver.call(
                    Uri.parse("content://" + REGISTRY_AUTHORITY),
                    METHOD_GET_SERVICE, VR_MANAGER, null);
            if (answer == null) {
                return null;
            }
            return answer.getBinder(KEY_BINDER);
        } catch (Throwable error) {
            // 注册表不可达 == 服务没注册，含义一致；不因此自造一个。
            Log.w(TAG, "vr_system registry lookup failed", error);
            return null;
        }
    }

    // --- IVRSystemServiceManager：逐条转发到官方 AIDL 代理 -----------------

    @Override
    public boolean isVRMode() {
        IVRSystemService target = liveService();
        if (target == null) {
            return false;
        }
        try {
            return target.isVRmode();
        } catch (RemoteException error) {
            invalidate();
            Log.w(TAG, "isVRmode failed", error);
            return false;
        }
    }

    @Override
    public boolean isVRApplication(Context source, String packageName) {
        // 官方语义：看目标包 manifest 的
        // com.huawei.android.vr.application.mode 是否等于 "vr_only"。
        if (source == null || TextUtils.isEmpty(packageName)) {
            return false;
        }
        try {
            PackageManager manager = source.getPackageManager();
            if (manager == null) {
                return false;
            }
            ApplicationInfo info = manager.getApplicationInfo(
                    packageName, PackageManager.GET_META_DATA);
            if (info == null || info.metaData == null) {
                return false;
            }
            return VR_METADATA_VALUE.equals(info.metaData.getString(VR_METADATA_NAME));
        } catch (Throwable error) {
            return false;
        }
    }

    @Override
    public int getHelmetBattery(Context source) {
        IVRSystemService target = liveService();
        if (target == null) {
            return -1;
        }
        try {
            return target.getHelmetBattery();
        } catch (RemoteException error) {
            invalidate();
            Log.w(TAG, "getHelmetBattery failed", error);
            return -1;
        }
    }

    @Override
    public int getHelmetBrightness(Context source) {
        IVRSystemService target = liveService();
        if (target == null) {
            return -1;
        }
        try {
            return target.getHelmetBrightness();
        } catch (RemoteException error) {
            invalidate();
            Log.w(TAG, "getHelmetBrightness failed", error);
            return -1;
        }
    }

    @Override
    public void setHelmetBrightness(Context source, int brightness) {
        // 官方 HwVrServiceManagerImpl 只在 0..9 之间转发。
        if (brightness < 0 || brightness > 9) {
            Log.w(TAG, "invalid brightness " + brightness);
            return;
        }
        IVRSystemService target = liveService();
        if (target == null) {
            return;
        }
        try {
            target.setHelmetBrightness(brightness);
        } catch (RemoteException error) {
            invalidate();
            Log.w(TAG, "setHelmetBrightness failed", error);
        }
    }

    @Override
    public String getContactName(Context source, String number) {
        IVRSystemService target = liveService();
        if (target == null) {
            return null;
        }
        try {
            return target.getContactName(number);
        } catch (RemoteException error) {
            invalidate();
            Log.w(TAG, "getContactName failed", error);
            return null;
        }
    }

    @Override
    public void registerVRListener(Context source, IVRListener listener) {
        if (listener == null) {
            return;
        }
        IVRSystemService target = liveService();
        if (target == null) {
            return;
        }
        try {
            target.addVRListener(listener);
        } catch (RemoteException error) {
            invalidate();
            Log.w(TAG, "addVRListener failed", error);
        }
    }

    @Override
    public void unregisterVRListener(Context source, IVRListener listener) {
        if (listener == null) {
            return;
        }
        IVRSystemService target = liveService();
        if (target == null) {
            return;
        }
        try {
            target.deleteVRListener(listener);
        } catch (RemoteException error) {
            invalidate();
            Log.w(TAG, "deleteVRListener failed", error);
        }
    }

    @Override
    public void registerExpandListener(Context source, IVRListener listener) {
        if (listener == null) {
            return;
        }
        IVRSystemService target = liveService();
        if (target == null) {
            return;
        }
        try {
            target.registerExpandListener(listener);
        } catch (RemoteException error) {
            invalidate();
            Log.w(TAG, "registerExpandListener failed", error);
        }
    }

    @Override
    public void acceptInCall(Context source) {
        IVRSystemService target = liveService();
        if (target == null) {
            return;
        }
        try {
            target.acceptInCall();
        } catch (RemoteException error) {
            invalidate();
            Log.w(TAG, "acceptInCall failed", error);
        }
    }

    @Override
    public void endInCall(Context source) {
        IVRSystemService target = liveService();
        if (target == null) {
            return;
        }
        try {
            target.endInCall();
        } catch (RemoteException error) {
            invalidate();
            Log.w(TAG, "endInCall failed", error);
        }
    }
}
