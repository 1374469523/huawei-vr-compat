package com.huawei.android.media;

/**
 * 照官方实现移植（原厂件/hwframework.jar 的
 * com/huawei/android/media/IAudioModeCallback.smali）：
 *
 *   - 它是一个 **abstract class**（不是接口、也不是 Binder），
 *     无参构造函数里会建一个内部回调对象；
 *   - 子类覆写 `onAudioModeChanged(int)`。
 *
 * 原代码就是继承它（`VrAudioMonitor$1 extends IAudioModeCallback`），所以这里的
 * 形态必须与被继承的方式一致：无参构造 + 可覆写方法。
 *
 * 官方那份通过 `HwAudioServiceManager` 把回调交给华为音频服务；本移植改成
 * `AudioManagerEx` 用公开的 `AudioManager.addOnModeChangedListener` 投递，
 * 见那个类的注释。
 */
public abstract class IAudioModeCallback {

    public IAudioModeCallback() {
    }

    /** 音频模式变化时回调（官方就是这一个抽象方法）。 */
    public abstract void onAudioModeChanged(int mode);
}
