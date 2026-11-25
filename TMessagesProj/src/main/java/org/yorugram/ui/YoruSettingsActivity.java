package org.yorugram.ui;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.graphics.Typeface;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import org.telegram.messenger.R;
import org.telegram.ui.ActionBar.ActionBar;
import org.telegram.ui.ActionBar.BaseFragment;
import org.telegram.ui.ProxyListActivity;

import java.io.IOException;
import java.io.OutputStream;

/** Local wallpaper gallery and a link to Telegram's existing proxy settings. */
public final class YoruSettingsActivity extends BaseFragment {
    private static final int EXPORT_FIRST = 24100;
    private static final int[] WALLPAPERS = {
        R.drawable.yoru_midnight, R.drawable.yoru_nebula, R.drawable.yoru_amoled
    };
    private static final String[] NAMES = {"Midnight Moon", "Purple Nebula", "Yoru AMOLED"};
    private static final String[] FILES = {"midnight-moon.png", "purple-nebula.png", "yoru-amoled.png"};
    private SharedPreferences preferences;
    private ImageView preview;
    private TextView selectedLabel;
    private int selected;

    @Override
    protected boolean useSimpleActionBar() { return true; }

    @Override
    public View createView(Context context) {
        setHasOwnBackground(true);
        simpleActionBar.setTitle(context.getString(R.string.YoruSettings));
        simpleActionBar.setBackButtonImage(R.drawable.ic_ab_back);
        simpleActionBar.setActionBarMenuOnItemClick(new ActionBar.ActionBarMenuOnItemClick() {
            @Override public void onItemClick(int id) { if (id == -1) finishFragment(); }
        });
        preferences = context.getSharedPreferences("yoru_appearance", Context.MODE_PRIVATE);
        selected = Math.max(0, Math.min(WALLPAPERS.length - 1, preferences.getInt("preview_index", 0)));

        ScrollView scroll = new ScrollView(context);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(Color.rgb(16, 16, 24));
        LinearLayout body = new LinearLayout(context);
        body.setOrientation(LinearLayout.VERTICAL);
        body.setPadding(dp(context, 20), dp(context, 24), dp(context, 20), dp(context, 24));
        scroll.addView(body);

        TextView title = label(context, "YoruGram • 0.1.0 Alpha", 24);
        title.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        body.addView(title);
        body.addView(label(context, context.getString(R.string.YoruWallpaperDescription), 15));
        preview = new ImageView(context);
        preview.setScaleType(ImageView.ScaleType.CENTER_CROP);
        body.addView(preview, new LinearLayout.LayoutParams(-1, dp(context, 300)));
        selectedLabel = label(context, "", 18);
        body.addView(selectedLabel);
        for (int i = 0; i < WALLPAPERS.length; i++) {
            final int index = i;
            Button choose = new Button(context);
            choose.setText(NAMES[i]);
            choose.setOnClickListener(v -> select(index));
            body.addView(choose);
        }
        Button export = new Button(context);
        export.setText(R.string.YoruExportWallpaper);
        export.setOnClickListener(v -> exportWallpaper());
        body.addView(export);
        body.addView(label(context, context.getString(R.string.YoruWallpaperHelp), 14));

        body.addView(label(context, "Yoru Connect", 20));
        body.addView(label(context, context.getString(R.string.YoruProxyHelp), 14));
        Button proxy = new Button(context);
        proxy.setText(R.string.YoruProxySettings);
        proxy.setOnClickListener(v -> presentFragment(new ProxyListActivity()));
        body.addView(proxy);

        select(selected);
        fragmentView = scroll;
        return fragmentView;
    }

    private void select(int index) {
        selected = index;
        preferences.edit().putInt("preview_index", index).apply();
        preview.setImageResource(WALLPAPERS[index]);
        preview.setContentDescription(NAMES[index]);
        selectedLabel.setText(NAMES[index]);
    }

    private void exportWallpaper() {
        Context context = getParentActivity();
        if (context == null) return;
        Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("image/png");
        intent.putExtra(Intent.EXTRA_TITLE, FILES[selected]);
        try {
            startActivityForResult(intent, EXPORT_FIRST + selected);
        } catch (android.content.ActivityNotFoundException e) {
            Toast.makeText(context, R.string.YoruExportError, Toast.LENGTH_LONG).show();
        }
    }

    @Override
    public void onActivityResultFragment(int requestCode, int resultCode, Intent data) {
        super.onActivityResultFragment(requestCode, resultCode, data);
        int index = requestCode - EXPORT_FIRST;
        Activity activity = getParentActivity();
        if (activity == null || index < 0 || index >= WALLPAPERS.length ||
                resultCode != Activity.RESULT_OK || data == null || data.getData() == null) return;
        Context context = activity.getApplicationContext();
        android.net.Uri uri = data.getData();
        new Thread(() -> {
            boolean success = false;
            Bitmap bitmap = null;
            try {
                bitmap = BitmapFactory.decodeResource(context.getResources(), WALLPAPERS[index]);
                if (bitmap == null) throw new IOException("Wallpaper unavailable");
                try (OutputStream out = context.getContentResolver().openOutputStream(uri, "w")) {
                    if (out == null || !bitmap.compress(Bitmap.CompressFormat.PNG, 100, out)) {
                        throw new IOException("Document unavailable");
                    }
                    out.flush();
                }
                success = true;
            } catch (IOException | RuntimeException ignored) {
                // Export may fail if the user revokes the document permission.
            } finally {
                if (bitmap != null) bitmap.recycle();
            }
            final boolean exported = success;
            new Handler(Looper.getMainLooper()).post(() ->
                Toast.makeText(context, exported ? R.string.YoruExported : R.string.YoruExportError, Toast.LENGTH_LONG).show());
        }, "yoru-wallpaper-export").start();
    }

    private static TextView label(Context context, String value, int size) {
        TextView text = new TextView(context);
        text.setText(value);
        text.setTextSize(size);
        text.setTextColor(Color.rgb(229, 221, 250));
        text.setPadding(0, dp(context, 8), 0, dp(context, 12));
        return text;
    }

    private static int dp(Context context, int value) {
        return Math.round(value * context.getResources().getDisplayMetrics().density);
    }
}
