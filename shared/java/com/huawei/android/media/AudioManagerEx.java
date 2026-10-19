package com.huawei.android.media;

import android.content.Context;
import android.media.AudioManager;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;

import com.huawei.vrservice.compat.CompatAppContext;

import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.Executor;

/**
 * Huawei's AudioManager extension, limited to the audio-mode callback the
 * original code uses.
 *
 * The original VrAudioMonitor subscribes here to be told when the audio mode
 * changes (it then moves the volume between the phone and the helmet). The
 * common-Android equivalent is the public AudioManager#addOnModeChangedListener,
 * available from API 31. Below that the callback cannot be delivered and this
 * class says so in the log rather than firing made-up events.
 *
 * The constructor takes no Context (that is the original signature); the context
 * comes from the compat provider in this process, see CompatAppContext.
 */
public class AudioManagerEx {

    private static final String TAG = "HvrAudioManagerEx";

    private final Map<IAudioModeCallback, AudioManager.OnModeChangedListener> registered =
            new HashMap<IAudioModeCallback, AudioManager.OnModeChangedListener>();

    public AudioManagerEx() {
    }

    public void registerAudioModeCallback(final IAudioModeCallback callback, Handler handler) {
        if (callback == null) {
            return;
        }
        Context context = CompatAppContext.get();
        if (context == null) {
            Log.w(TAG, "no application context yet; audio mode callback not registered");
            return;
        }
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.S) {
            Log.w(TAG, "addOnModeChangedListener needs API 31+; audio mode callback not registered");
            return;
        }
        AudioManager manager = (AudioManager) context.getSystemService(Context.AUDIO_SERVICE);
        if (manager == null) {
            Log.w(TAG, "AudioManager unavailable");
            return;
        }
        final Executor executor = executorFor(handler);
        AudioManager.OnModeChangedListener listener = new AudioManager.OnModeChangedListener() {
            @Override
            public void onModeChanged(int mode) {
                callback.onAudioModeChanged(mode);
            }
        };
        try {
            manager.addOnModeChangedListener(executor, listener);
        } catch (Throwable error) {
            Log.w(TAG, "addOnModeChangedListener failed", error);
            return;
        }
        synchronized (registered) {
            registered.put(callback, listener);
        }
    }

    public void unregisterAudioModeCallback(IAudioModeCallback callback) {
        if (callback == null) {
            return;
        }
        AudioManager.OnModeChangedListener listener;
        synchronized (registered) {
            listener = registered.remove(callback);
        }
        if (listener == null) {
            return;
        }
        Context context = CompatAppContext.get();
        if (context == null) {
            return;
        }
        AudioManager manager = (AudioManager) context.getSystemService(Context.AUDIO_SERVICE);
        if (manager == null) {
            return;
        }
        try {
            manager.removeOnModeChangedListener(listener);
        } catch (Throwable error) {
            Log.w(TAG, "removeOnModeChangedListener failed", error);
        }
    }

    private static Executor executorFor(Handler handler) {
        if (handler != null) {
            final Handler target = handler;
            return new Executor() {
                @Override
                public void execute(Runnable command) {
                    target.post(command);
                }
            };
        }
        // The original call passes a null Handler; deliver on the main looper.
        final Handler main = new Handler(Looper.getMainLooper());
        return new Executor() {
            @Override
            public void execute(Runnable command) {
                main.post(command);
            }
        };
    }
}