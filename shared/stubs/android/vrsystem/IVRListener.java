package android.vrsystem;

/**
 * Compile-time stub for the platform interface android.vrsystem.IVRListener.
 *
 * The six original APKs ship their own copies of this AIDL interface, so the
 * real class is present in every module at runtime; this stub exists only so
 * shared/java compiles against the exact same signatures. It is never packaged.
 */
public interface IVRListener {
    void onBatteryChanged(android.content.Intent intent);

    void onCallback(String key, java.util.List values);

    void onHeartBeatChanged(boolean alive);

    void onHelmetChanged(boolean connected);

    void onModeChanged(boolean vrMode);

    void onNetworkStateChanged(android.content.Intent intent);

    void onNewNotification(android.service.notification.StatusBarNotification notification);

    void onNewSMS(android.content.Intent intent);

    void onPhoneStateChanged(int state, int incomingNumber, String number);
}
