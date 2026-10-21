package io.github.noahhhi.camera.hdrprobe;

import de.robv.android.xposed.XC_MethodHook;
import de.robv.android.xposed.XposedBridge;
import de.robv.android.xposed.XposedHelpers;
import java.lang.reflect.Array;
import java.util.HashSet;
import java.util.HashMap;
import java.util.Map;
import java.util.Set;

/** Opt-in read-only XPan topology/recipe observations, installed after APK hash verification. */
final class XpanObserver {
    private static final Map<String, Set<String>> seen = new HashMap<>();
    private static int total;

    static void install(ClassLoader loader) {
        try {
            Class<?> props = XposedHelpers.findClass("android.os.SystemProperties", null);
            if (!"1".equals(XposedHelpers.callStaticMethod(props, "get", "debug.noah.hdr.xpan", "0"))) return;
        } catch (Throwable ignored) { return; }
        try {
            Class<?> camera = XposedHelpers.findClass("com.oplus.ocs.camera.producer.device.Camera2Impl", loader);
            XposedHelpers.findAndHookMethod(camera, "takePicture",
                XposedHelpers.findClass("com.oplus.ocs.camera.common.util.CameraRequestTag", loader),
                XposedHelpers.findClass("com.oplus.ocs.camera.metadata.parameter.Parameter", loader),
                android.os.Handler.class, boolean.class, boolean.class, new XC_MethodHook() {
                    @Override protected void beforeHookedMethod(MethodHookParam p) {
                        try {
                            Object tag = p.args[0];
                            if (tag == null || !String.valueOf(XposedHelpers.getObjectField(tag, "mCaptureMode")).contains("xpan")) return;
                            synchronized (seen) {
                                if (total >= 48) return;
                                Set<String> group = seen.computeIfAbsent("finalTakePicture", key -> new HashSet<>());
                                if (group.size() >= 8) return;
                                String value = "finalRequest=" + fields(tag, "mCaptureMode", "mCaptureEVList",
                                    "mCaptureEvList", "mCaptureEtList", "mRequestNum", "mRequestFormat",
                                    "mApsAlgoFlags", "mApsDecisionFeatureType", "mApsDecisionSceneMode", "mApsBracketMode",
                                    "mAddTargetSurfaces");
                                if (group.add(value)) {
                                    total++;
                                    XposedBridge.log("OnePlusXpanReadOnly: " + value);
                                }
                            }
                        } catch (Throwable ignored) { }
                    }
                });
        } catch (Throwable ignored) { }
        String cls = "com.oplus.ocs.camera.producer.mode.XpanMode";
        hook(loader, cls, "getSurfaceUseCase", p -> "usecase=" + p.getResult() + ", camera=" + p.args[0]);
        hook(loader, cls, "getSurfaceSize", p -> "surface=" + p.args[1] + ", camera=" + p.args[2] + ", sizePairs=" + p.getResult());
        hook(loader, cls, "onConfigure", p -> "sessionOperationMode=" + XposedHelpers.callMethod(p.args[0], "getOperationMode") + ", session=" + fields(p.args[3],
            "mModeName", "mOperationMode", "mCaptureStreamNumber", "mPreviewSize", "mbUltraHdrEnable"));
        hook(loader, cls, "createRequestTag", p -> {
            Object tag = p.getResult();
            if (tag == null) return null;
            return "stage=" + p.args[3] + ", tag=" + fields(tag, "mCaptureMode", "mCameraType", "mCameraId",
                "mZoomRatio", "mRawValue", "mManualIso", "mExposureTime", "mRequestNum", "mRequestFormat",
                "mRequestFormatList", "mApsAlgoFlags", "mCaptureEvList", "mApsDecisionFeatureType",
                "mApsBracketMode", "mMasterPipeline", "mbSatOpen", "mSensorSizes", "mXpanMfllOutputSize",
                "mXpanHsWatermarkHeight", "mbOutputSizeDownScaleEnable", "mbUltraHdrEnable");
        });
        hook(loader, "com.oplus.ocs.camera.consumer.apsAdapter.APSClient", "fillDecisionResult", p -> {
            Object result = p.args[1];
            String mode = String.valueOf(XposedHelpers.getObjectField(result, "mCaptureMode"));
            if (!mode.contains("xpan")) return null;
            return "decision=" + fields(result, "mCaptureMode", "mApsAlgoFlag", "mRequestFormat",
                "mMultiFrameCount", "mCaptureEVList", "mCaptureETList", "mApsDecisionFeatureType",
                "mApsBracketMode", "mMasterPipeline", "mPhysicalCameraId", "mSensorMask", "mRequestSensorModeList");
        });
    }

    private interface Read { String get(XC_MethodHook.MethodHookParam p) throws Throwable; }
    private static void hook(ClassLoader loader, String name, String method, Read read) {
        try {
            XposedBridge.hookAllMethods(XposedHelpers.findClass(name, loader), method, new XC_MethodHook() {
                @Override protected void afterHookedMethod(MethodHookParam p) {
                    try {
                        if (p.hasThrowable()) return;
                        synchronized (seen) {
                            if (total >= 48) return;
                            String groupName = method + ("createRequestTag".equals(method) ? ":" + p.args[3] : "");
                            Set<String> group = seen.computeIfAbsent(groupName, key -> new HashSet<>());
                            if (group.size() >= 8) return;
                            String value = read.get(p);
                            if (value != null && group.add(value)) {
                                total++;
                                XposedBridge.log("OnePlusXpanReadOnly: " + value);
                            }
                        }
                    } catch (Throwable ignored) { }
                }
            });
        } catch (Throwable ignored) { }
    }
    private static String fields(Object object, String... names) {
        StringBuilder text = new StringBuilder();
        for (String name : names) {
            try {
                Object value = XposedHelpers.getObjectField(object, name);
                text.append(name).append('=');
                if (value != null && value.getClass().isArray()) {
                    text.append('[');
                    for (int i = 0; i < Math.min(Array.getLength(value), 16); i++) {
                        if (i > 0) text.append(',');
                        text.append(Array.get(value, i));
                    }
                    text.append(']');
                } else text.append(value);
                text.append(';');
            } catch (Throwable ignored) { }
        }
        return text.toString();
    }
}
