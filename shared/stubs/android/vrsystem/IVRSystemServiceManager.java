package android.vrsystem;

/**
 * Compile-time stub for the platform interface
 * android.vrsystem.IVRSystemServiceManager (service name "vr_system").
 *
 * The original APKs ship their own copies; this stub only lets shared/java
 * compile against the same signatures. It is never packaged.
 */
public interface IVRSystemServiceManager {
    String VR_MANAGER = "vr_system";

    boolean isVRMode();

    boolean isVRApplication(android.content.Context context, String packageName);

    int getHelmetBattery(android.content.Context context);

    int getHelmetBrightness(android.content.Context context);

    void setHelmetBrightness(android.content.Context context, int brightness);

    String getContactName(android.content.Context context, String number);

    void registerVRListener(android.content.Context context, IVRListener listener);

    void unregisterVRListener(android.content.Context context, IVRListener listener);

    void registerExpandListener(android.content.Context context, IVRListener listener);

    void acceptInCall(android.content.Context context);

    void endInCall(android.content.Context context);
}
