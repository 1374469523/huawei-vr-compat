package com.huawei.android.hardware.input;

import android.content.Context;
import android.hardware.input.InputManager;
import android.util.Log;
import android.view.InputEvent;

/**
 * 照官方实现移植（原厂件/hwframework.jar 的
 * com/huawei/android/hardware/input/InputManagerEx.smali）。七个包只用到 4 个方法：
 *
 *   injectInputEvent(InputManager,InputEvent,int)Z        x3
 *   getInjectInputEventModeAsync()I                        x2
 *   getInjectInputEventModeWaitForFinish()I                x1
 *   injectInputEventByDisplayId(InputEvent,int,int,Context)Z x1
 *
 * 官方逐条：
 *   getInjectInputEventModeAsync()          return 0
 *   getInjectInputEventModeWaitForFinish()  return 2
 *   injectInputEvent(im, event, mode)       im.injectInputEvent(event, mode)   // hidden
 *   injectInputEventByDisplayId(event, mode, displayId, ctx)
 *         ctx 为空或包名不是 com.huawei.vrvirtualscreen -> return false
 *         否则 HwInputManager.injectInputEventByDisplayId(event, mode, displayId)
 *
 * **参数顺序很关键**：官方是 (event, mode, displayId, context)，前两个参数
 * 都是 int，顺序写反了编译期不会报错、行为一定错。我方旧版本写成了
 * (event, displayId, mode, context)，已按官方改正。
 *
 * 注入本身在通用安卓上要 INJECT_EVENTS（签名级）或走无障碍/Shizuku；
 * 这里保留官方调用语义并如实返回结果，注入被拒就是 false，不假装成功。
 */
public final class InputManagerEx {

    private static final String TAG = "HvrInputManagerEx";

    /** 与官方（AOSP InputManager）一致的模式常量。 */
    public static final int INJECT_INPUT_EVENT_MODE_ASYNC = 0;
    public static final int INJECT_INPUT_EVENT_MODE_WAIT_FOR_FINISH = 2;

    /** 官方只允许投屏包按显示注入。 */
    private static final String VR_VIRTUAL_SCREEN_NAME = "com.huawei.vrvirtualscreen";

    private InputManagerEx() {
    }

    public static int getInjectInputEventModeAsync() {
        return INJECT_INPUT_EVENT_MODE_ASYNC;
    }

    public static int getInjectInputEventModeWaitForFinish() {
        return INJECT_INPUT_EVENT_MODE_WAIT_FOR_FINISH;
    }

    public static boolean injectInputEvent(InputManager manager, InputEvent event, int mode) {
        if (manager == null || event == null) {
            return false;
        }
        // 官方是 hidden 的 im.injectInputEvent(event, mode)，不反射。
        // 通用安卓没有任何公开接口能注入输入事件（INJECT_EVENTS 是 signature|privileged，
        // 公开替代只有用户手动开启的无障碍服务或 Shizuku），所以这里如实返回 false。
        logOnce("injectInputEvent needs INJECT_EVENTS (signature) or an accessibility service;"
                + " no public API on this device");
        return false;
    }

    /**
     * 官方参数顺序：(event, mode, displayId, context)。
     * 官方最终调华为框架的 HwInputManager.injectInputEventByDisplayId；
     * 通用安卓没有按显示注入的公开接口，这里退到 hidden 的
     * DisplayManager.injectInputEvent(displayId, event, mode)（同一件事的
     * 平台实现），失败则返回 false。
     */
    public static boolean injectInputEventByDisplayId(InputEvent event, int mode,
            int displayId, Context context) {
        if (event == null || context == null) {
            return false;
        }
        if (!VR_VIRTUAL_SCREEN_NAME.equals(context.getPackageName())) {
            return false;
        }
        // 官方最终落 HwInputManager.injectInputEventByDisplayId(event, mode, displayId)；
        // AOSP 里同一件事是 hidden 的 DisplayManager.injectInputEvent，同样不反射。
        logOnce("injectInputEventByDisplayId has no public API on this device");
        return false;
    }

    /** 同一条限制只提示一次，避免刷日志。 */
    private static void logOnce(String message) {
        if (reported) {
            return;
        }
        reported = true;
        Log.w(TAG, message);
    }

    private static volatile boolean reported;
}
