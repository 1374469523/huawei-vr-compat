package com.huawei.vrframework.compat;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.content.Context;
import android.content.Intent;
import android.database.Cursor;
import android.net.Uri;
import android.os.Build;
import android.util.Log;

import com.huawei.android.content.ContextEx;

/**
 * 让平台在进程启动时把 Application context 交给兼容层，外加一件事：
 * 打开「华为 VR」主应用时，把原版依赖「系统常驻」的那几个服务拉起来。
 *
 * 兼容层里有些类是「原版不传 Context」的静态封装（SystemPropertiesEx、
 * AudioManagerEx、PackageManagerEx…），换成通用安卓实现后需要 Context 才能
 * 落到真实组件上。平台会在进程起来时实例化声明的 provider（哪怕没有组件被
 * 启动），所以这是最省事、也最不侵入原版逻辑的接入点 —— 不改原版任何代码，
 * 只在 manifest 里加一个不导出的 provider。
 *
 * 每个包用各自的 authority（<包名>.hvrcompat.ctx），互不冲突。
 *
 * 环境启动（2026-09-16 用户口径）：不做开机自启，也不在页面上挂「正在启动 X」
 * 的闸门 —— 打开华为 VR 主应用时就启动，页面保持原样。这就是通用安卓里
 * 「应用自己拉起自己的后台组件」的标准做法：显式组件 + 目标应用自己声明的
 * 签名级权限（原厂清单里本来就有）。
 */
public final class HvrContextProvider extends ContentProvider {

    private static final String TAG = "HvrContextProvider";

    /** 只有主应用负责拉起环境，其余六个包进程启动时不做任何事。 */
    private static final String MAIN_APP_PACKAGE = "com.huawei.appmarket.vr";

    /** EMUI 上由框架常驻的眼镜监督（Runtime 包）。 */
    private static final String RUNTIME_PACKAGE = "com.huawei.hvrsdkserverapp";
    private static final String RUNTIME_SERVICE =
            "com.huawei.hvrsdkserverapp.compat.VrGlassWatchService";

    /** EMUI 上常驻的 VR 系统服务本体（从 HMA-AL00 EMUI 11 固件里提取的第七个包）。 */
    private static final String VRSERVICE_COMPONENT =
            "com.huawei.vrinstaller.service.VrParamsInitializeService";
    private static final String VRSERVICE_PACKAGE = "com.huawei.vrservice";

    @Override
    public boolean onCreate() {
        Context context = getContext();
        ContextEx.setApplication(context);
        startVrEnvironment(context);
        return true;
    }

    /**
     * 打开华为 VR 主应用时拉起 VR 环境。EMUI 上这两个组件是系统常驻，
     * 通用安卓里必须有人显式启动一次；这里就是那一次。
     */
    private static void startVrEnvironment(Context context) {
        if (context == null || !MAIN_APP_PACKAGE.equals(context.getPackageName())) {
            return;
        }
        Intent runtime = new Intent();
        runtime.setClassName(RUNTIME_PACKAGE, RUNTIME_SERVICE);
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(runtime);
            } else {
                context.startService(runtime);
            }
            Log.i(TAG, "VR environment start requested");
        } catch (Throwable error) {
            // 平台拒绝后台启动前台服务时如实记录；打开应用后由原页面继续可用，
            // 这里不替环境回答任何状态。
            Log.w(TAG, "runtime supervision start refused: " + error);
        }
        Intent params = new Intent();
        params.setClassName(VRSERVICE_PACKAGE, VRSERVICE_COMPONENT);
        try {
            context.startService(params);
        } catch (Throwable error) {
            Log.w(TAG, "vrservice wake-up refused: " + error);
        }
    }

    @Override
    public Cursor query(Uri uri, String[] projection, String selection,
                        String[] selectionArgs, String sortOrder) {
        return null;
    }

    @Override
    public String getType(Uri uri) {
        return null;
    }

    @Override
    public Uri insert(Uri uri, ContentValues values) {
        return null;
    }

    @Override
    public int delete(Uri uri, String selection, String[] selectionArgs) {
        return 0;
    }

    @Override
    public int update(Uri uri, ContentValues values, String selection,
                      String[] selectionArgs) {
        return 0;
    }
}
