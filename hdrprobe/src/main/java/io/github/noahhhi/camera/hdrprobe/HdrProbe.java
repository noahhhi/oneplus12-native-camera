package io.github.noahhhi.camera.hdrprobe;

import java.io.FileInputStream;
import java.security.MessageDigest;
import de.robv.android.xposed.IXposedHookLoadPackage;
import de.robv.android.xposed.XposedBridge;
import de.robv.android.xposed.callbacks.XC_LoadPackage;

/** Version-pinned entry point for native HDR diagnostics; no post-save image processing. */
public final class HdrProbe implements IXposedHookLoadPackage {
    private static final String APK_SHA256 =
        "7833a1c3ca932503b77015d5d31493f99b0586580f68eb9ed14b93a2573fdd16";

    @Override public void handleLoadPackage(XC_LoadPackage.LoadPackageParam load) {
        if (!"com.oplus.camera".equals(load.packageName)
                || !"com.oplus.camera".equals(load.processName) || !load.isFirstApplication) return;
        try {
            if (!APK_SHA256.equals(hash(load.appInfo.sourceDir))) {
                XposedBridge.log("OnePlusHdr: unsupported camera APK; no hooks installed");
                return;
            }
            ClassLoader cl = load.classLoader;
            NativeConfigProbe.install(cl);
            XposedBridge.log("OnePlusHdr: camera APK verified; native diagnostics initialized");
        } catch (Throwable error) {
            XposedBridge.log("OnePlusHdr: setup skipped: " + error);
        }
    }

    private static String hash(String path) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        try (FileInputStream input = new FileInputStream(path)) {
            byte[] buffer = new byte[65536];
            int read;
            while ((read = input.read(buffer)) != -1) digest.update(buffer, 0, read);
        }
        StringBuilder hex = new StringBuilder();
        for (byte value : digest.digest()) hex.append(String.format("%02x", value & 255));
        return hex.toString();
    }
}
