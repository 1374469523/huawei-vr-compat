package android.os;

/**
 * Compile-time stub for the hidden platform class android.os.UEventObserver.
 *
 * It exists only so shared/java can be compiled against the public SDK; the file
 * is never packaged (the platform provides the real class at runtime).
 */
public abstract class UEventObserver {

    // The platform declares these final; mirroring that here turns the mistake
    // into a compile error instead of a LinkageError inside the original app.
    public final void startObserving(String match) {
        throw new UnsupportedOperationException("stub");
    }

    public final void stopObserving() {
        throw new UnsupportedOperationException("stub");
    }

    public abstract void onUEvent(UEvent event);

    public static class UEvent {
        public UEvent(String message) {
            throw new UnsupportedOperationException("stub");
        }

        public String get(String key) {
            throw new UnsupportedOperationException("stub");
        }
    }
}
