package org.yorugram.ui;

import android.content.Context;
import android.graphics.Color;
import android.graphics.Typeface;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import org.telegram.messenger.AndroidUtilities;
import org.telegram.messenger.BuildConfig;
import org.telegram.messenger.R;
import org.telegram.ui.ActionBar.BaseFragment;
import org.telegram.ui.ActionBar.Theme;
import org.telegram.ui.LoginActivity;
import org.telegram.ui.ProxyListActivity;

public final class YoruIntroActivity extends BaseFragment {
    private static final int BACKGROUND = 0xFF101018;
    private static final int PANEL = 0xFF211B32;
    private static final int ACCENT = 0xFF7045E8;
    private static final int MOONLIGHT = 0xFFC5A0FF;
    private static final int FOREGROUND = 0xFFE2D8FF;

    @Override
    public View createView(Context context) {
        actionBar.setAddToContainer(false);
        setHasOwnBackground(true);
        ScrollView scroll = new ScrollView(context);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(BACKGROUND);
        LinearLayout body = new LinearLayout(context);
        body.setOrientation(LinearLayout.VERTICAL);
        body.setGravity(Gravity.CENTER);
        body.setPadding(dp(24), dp(28), dp(24), dp(28));
        scroll.addView(body);

        ImageView icon = new ImageView(context);
        icon.setImageResource(R.mipmap.yoru_launcher);
        icon.setScaleType(ImageView.ScaleType.FIT_CENTER);
        icon.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        body.addView(icon, new LinearLayout.LayoutParams(dp(132), dp(132)));

        TextView title = label(context, R.string.YoruAppName, 30, FOREGROUND);
        title.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        add(body, title, 20);
        add(body, label(context, R.string.YoruIntroDisclosure, 16, FOREGROUND), 10);
        if (BuildConfig.YORU_OFFLINE_SMOKE) {
            add(body, label(context, R.string.YoruIntroOffline, 14, MOONLIGHT), 12);
        }
        Button login = button(context, R.string.StartMessaging, ACCENT, Color.WHITE);
        login.setOnClickListener(view -> presentFragment(new LoginActivity(), true));
        add(body, login, 28);

        Button proxy = button(context, R.string.YoruConnectBeforeLogin, PANEL, MOONLIGHT);
        proxy.setOnClickListener(view -> presentFragment(new ProxyListActivity()));
        add(body, proxy, 10);

        fragmentView = scroll;
        return fragmentView;
    }

    @Override
    public boolean isLightStatusBar() {
        return false;
    }

    private static TextView label(Context context, int text, int size, int color) {
        TextView label = new TextView(context);
        label.setText(text);
        label.setGravity(Gravity.CENTER);
        label.setTextColor(color);
        label.setTextSize(size);
        return label;
    }

    private static Button button(Context context, int text, int color, int textColor) {
        Button button = new Button(context);
        button.setText(text);
        button.setAllCaps(false);
        button.setMinHeight(dp(48));
        button.setTextColor(textColor);
        button.setBackground(Theme.createSimpleSelectorRoundRectDrawable(dp(16), color, 0xFF413365));
        return button;
    }

    private static void add(LinearLayout layout, View view, int gap) {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, -2);
        params.topMargin = dp(gap);
        layout.addView(view, params);
    }

    private static int dp(float value) {
        return AndroidUtilities.dp(value);
    }
}
