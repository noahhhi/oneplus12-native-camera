package io.github.noahhhi.camera.hdrprobe;

import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.util.concurrent.atomic.AtomicBoolean;
import de.robv.android.xposed.XC_MethodHook;
import de.robv.android.xposed.XposedBridge;
import de.robv.android.xposed.XposedHelpers;

/** One opt-in SDK key override, installed only after HdrProbe verifies the camera APK. */
final class NativeXpanConfig {
    private static final String PROPERTY = "debug.noah.hdr.xpan_native";
    private static final String KEY = "com.oplus.xpan.multi.frame";

    private static boolean enabled(Class<?> properties) {
        try {
            return "1".equals(XposedHelpers.callStaticMethod(properties, "get", PROPERTY, "0"));
        } catch (Throwable ignored) {
            return false;
        }
    }

    static void install(ClassLoader loader) {
        try {
            final Class<?> properties = XposedHelpers.findClass("android.os.SystemProperties", null);
            if (!enabled(properties)) return;
            Class<?> helper = XposedHelpers.findClass(
                    "com.oplus.ocs.camera.producer.info.CameraConfigHelper", loader);
            Class<?> keyClass = XposedHelpers.findClass(
                    "com.oplus.ocs.camera.common.util.CameraConfigBase$Key", loader);
            Method getter = helper.getDeclaredMethod("getConfigValue", keyClass, Object.class);
            if (!Modifier.isStatic(getter.getModifiers()) || getter.getReturnType() != Object.class) {
                XposedBridge.log("OnePlusNativeXpan: unsupported typed config getter; no hook");
                return;
            }
            final Method keyName = keyClass.getMethod("getName");
            final Method keyType = keyClass.getMethod("getType");
            final AtomicBoolean appliedLogged = new AtomicBoolean();
            final AtomicBoolean errorLogged = new AtomicBoolean();
            XposedBridge.hookMethod(getter, new XC_MethodHook() {
                @Override protected void afterHookedMethod(MethodHookParam param) {
                    // Retain original failures and unexpected result types.
                    if (param.hasThrowable() || param.args == null || param.args.length != 2
                            || param.args[0] == null || !(param.getResult() instanceof Boolean)) return;
                    try {
                        Object key = param.args[0];
                        if (!KEY.equals(keyName.invoke(key)) || keyType.invoke(key) != Boolean.class
                                || !enabled(properties)) return;
                        param.setResult(Boolean.TRUE);
                        if (appliedLogged.compareAndSet(false, true)) {
                            XposedBridge.log("OnePlusNativeXpan: opt-in XPAN multi-frame usecase enabled");
                        }
                    } catch (Throwable error) {
                        if (errorLogged.compareAndSet(false, true)) {
                            XposedBridge.log("OnePlusNativeXpan: config override skipped; "
                                    + error.getClass().getSimpleName());
                        }
                    }
                }
            });
            XposedBridge.log("OnePlusNativeXpan: single-key config hook installed");
        } catch (Throwable error) {
            XposedBridge.log("OnePlusNativeXpan: config hook unavailable; "
                    + error.getClass().getSimpleName());
        }
    }
}
