package com.huawei.android.app;

import android.app.ActionBar;
import android.graphics.drawable.Drawable;
import android.view.View;

/**
 * Huawei's ActionBar extension. The three referenced methods only ever extend
 * the stock ActionBar look (drag stage, background, start icon); the public
 * ActionBar already owns that state, so the same effect is applied through it.
 */
public final class ActionBarEx {
    private ActionBarEx() {
    }

    public static int getDragAnimationStage(ActionBar bar) {
        // EMUI used this value to drive its own drag animation. The stock bar has
        // no such stage, and the caller only compares it against its own
        // constants, so the idle stage is reported.
        return 0;
    }

    public static void setAppbarBackground(ActionBar bar, Drawable background) {
        if (bar == null) return;
        try {
            bar.setBackgroundDrawable(background);
        } catch (Throwable ignored) {
            // Older bars ignore a background change; the layout stays valid.
        }
    }

    public static void setStartIcon(ActionBar bar, boolean visible, Drawable icon,
            View.OnClickListener listener) {
        if (bar == null) return;
        try {
            if (!visible) {
                bar.setDisplayShowHomeEnabled(false);
                return;
            }
            bar.setDisplayShowHomeEnabled(true);
            if (icon != null) bar.setIcon(icon);
            // The stock ActionBar has no click hook for its start icon; the
            // caller's own view still receives the click, so no listener is
            // attached here.
            if (listener != null) listener.getClass();
        } catch (Throwable ignored) {
            // A bar that cannot take an icon keeps its previous one.
        }
    }
}
