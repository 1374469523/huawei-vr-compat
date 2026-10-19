package android.vrsystem;

/**
 * Compile-time stub for the platform binder interface
 * android.vrsystem.IVRSystemService. Shipped by the original APKs; never
 * packaged from here.
 *
 * Method set and order are taken from the AIDL as it exists in the original
 * packages (decode/<pkg>/smali/android/vrsystem/IVRSystemService.smali and its
 * $Stub transaction table), including the checked RemoteException the generated
 * proxy declares. The nested Stub only exists so the compat layer can type-check
 * IVRSystemService.Stub.asInterface(binder); the real one is what runs.
 */
public interface IVRSystemService {

    boolean isVRmode() throws android.os.RemoteException;

    String getContactName(String number) throws android.os.RemoteException;

    void addVRListener(IVRListener listener) throws android.os.RemoteException;

    void registerExpandListener(IVRListener listener) throws android.os.RemoteException;

    void deleteVRListener(IVRListener listener) throws android.os.RemoteException;

    void acceptInCall() throws android.os.RemoteException;

    void endInCall() throws android.os.RemoteException;

    int getHelmetBattery() throws android.os.RemoteException;

    int getHelmetBrightness() throws android.os.RemoteException;

    void setHelmetBrightness(int brightness) throws android.os.RemoteException;

    /**
     * Compile-time stand-in for the AIDL-generated Stub. Not packaged: every
     * original APK already ships the real
     * android.vrsystem.IVRSystemService$Stub with the same descriptor
     * ("android.vrsystem.IVRSystemService") and the same static asInterface.
     */
    abstract class Stub extends android.os.Binder implements IVRSystemService {

        public static IVRSystemService asInterface(android.os.IBinder binder) {
            // Never executed: this class exists for javac only.
            throw new UnsupportedOperationException("compile-time stub");
        }
    }
}