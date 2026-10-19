package com.huawei.android.util;

/**
 * 照官方实现移植（原厂件/hwframework.jar 的
 * com/huawei/android/util/NoExtAPIException.smali）：四个构造函数，
 * 与官方逐字对齐（官方只多一个 serialVersionUID 私有常量）。
 *
 * 用途不变：通用安卓上遇到「只有华为扩展 API 才有的能力」时抛这个异常，
 * 调用方按它自己的分支处理，而不是被换成另一种静默行为。
 */
public class NoExtAPIException extends RuntimeException {

    private static final long serialVersionUID = -5362722363306815588L;

    public NoExtAPIException() {
        super();
    }

    public NoExtAPIException(String message) {
        super(message);
    }

    public NoExtAPIException(String message, Throwable cause) {
        super(message, cause);
    }

    public NoExtAPIException(Throwable cause) {
        super(cause);
    }
}
