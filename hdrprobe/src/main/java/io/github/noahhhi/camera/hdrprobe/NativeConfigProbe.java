package io.github.noahhhi.camera.hdrprobe;

import android.content.Context;
import de.robv.android.xposed.XC_MethodHook;
import de.robv.android.xposed.XposedBridge;
import de.robv.android.xposed.XposedHelpers;
import org.json.JSONArray;
import org.json.JSONObject;

/** Opt-in, bounded observations only. Never changes configuration or capture results. */
final class NativeConfigProbe {
    static void install(ClassLoader loader) {
        try {
            boolean enabled = "1".equals(XposedHelpers.callStaticMethod(
                XposedHelpers.findClass("android.os.SystemProperties", null),
                "get", "debug.noah.hdr.nativeconfig", "0"));
            if (!enabled) return;
            Class<?> helper = XposedHelpers.findClass(
                "com.oplus.ocs.camera.consumer.apsAdapter.update.UpdateHelper", loader);
            if (enabled) {
                Class<?> client = XposedHelpers.findClass(
                    "com.oplus.ocs.camera.consumer.apsAdapter.APSClient", loader);
                Class<?> decisionResult = XposedHelpers.findClass(
                    "com.oplus.ocs.camera.consumer.apsAdapter.adapter.ApsAdapterDecision$DecisionResult", loader);
                java.util.Set<String> decisions = java.util.Collections.synchronizedSet(new java.util.HashSet<>());
                XposedHelpers.findAndHookMethod(client, "fillDecisionResult",
                    java.util.HashMap.class, decisionResult, boolean.class, new XC_MethodHook() {
                    @Override protected void afterHookedMethod(MethodHookParam p) {
                        try {
                            if (p.hasThrowable() || p.args[1] == null || decisions.size() >= 12) return;
                            Object result = p.args[1];
                            String text = "mode=" + XposedHelpers.getObjectField(result,"mCaptureMode")
                                + ", burst=" + p.args[2]
                                + ", algos=" + java.util.Arrays.toString((String[])XposedHelpers.getObjectField(result,"mApsAlgoFlag"))
                                + ", frames=" + XposedHelpers.getIntField(result,"mMultiFrameCount")
                                + ", format=" + XposedHelpers.getIntField(result,"mRequestFormat")
                                + ", formats=" + java.util.Arrays.toString((int[])XposedHelpers.getObjectField(result,"mRequestFormatList"))
                                + ", ev=" + java.util.Arrays.toString((int[])XposedHelpers.getObjectField(result,"mCaptureEVList"))
                                + ", et=" + java.util.Arrays.toString((long[])XposedHelpers.getObjectField(result,"mCaptureETList"))
                                + ", feature=" + XposedHelpers.getIntField(result,"mApsDecisionFeatureType")
                                + ", bracket=" + XposedHelpers.getIntField(result,"mApsBracketMode")
                                + ", pipeline=" + XposedHelpers.getIntField(result,"mMasterPipeline")
                                + ", physicalId=" + XposedHelpers.getIntField(result,"mPhysicalCameraId")
                                + ", sensorMask=" + java.util.Arrays.toString((int[])XposedHelpers.getObjectField(result,"mSensorMask"))
                                + ", sensors=" + java.util.Arrays.toString((int[])XposedHelpers.getObjectField(result,"mRequestSensorModeList"))
                                + ", intent=" + XposedHelpers.getIntField(result,"mCaptureIntent");
                            synchronized (decisions) {
                                if (decisions.size() < 12 && decisions.add(text))
                                    XposedBridge.log("OnePlusNativeHdr: decision " + text);
                            }
                        } catch (Throwable error) {
                            try {
                                synchronized (decisions) {
                                    if (decisions.size() < 12 && decisions.add("error"))
                                        XposedBridge.log("OnePlusNativeHdr: decision observer " + error);
                                }
                            } catch (Throwable ignored) { }
                        }
                    }
                });
                Class<?> processor = XposedHelpers.findClass("com.oplus.ocs.camera.consumer.ApsProcessor", loader);
                java.util.Set<String> seen = java.util.Collections.synchronizedSet(new java.util.HashSet<>());
                XposedHelpers.findAndHookMethod(processor, "getPreviewRequestTag", new XC_MethodHook() {
                    @Override protected void afterHookedMethod(MethodHookParam p) {
                        if (p.hasThrowable() || p.getResult() == null || seen.size() >= 12) return;
                        try {
                            Object tag = p.getResult();
                            String text = "raw=" + XposedHelpers.getObjectField(tag,"mRawValue")
                                + ", iso=" + XposedHelpers.getIntField(tag,"mManualIso")
                                + ", exposure=" + XposedHelpers.getLongField(tag,"mExposureTime")
                                + ", zoom=" + XposedHelpers.getFloatField(tag,"mZoomRatio")
                                + ", cameraId=" + XposedHelpers.getIntField(tag,"mCameraId")
                                + ", cameraType=" + XposedHelpers.getObjectField(tag,"mCameraType")
                                + ", logicCameraType=" + XposedHelpers.getIntField(tag,"mLogicCameraType")
                                + ", focalLength=" + XposedHelpers.getIntField(tag,"mCurFocalLength")
                                + ", pipeline=" + XposedHelpers.getIntField(tag,"mMasterPipeline")
                                + ", sat=" + XposedHelpers.getBooleanField(tag,"mbSatOpen")
                                + ", sensorModes=" + java.util.Arrays.toString((int[])XposedHelpers.getObjectField(tag,"mCaptureSensorModeList"));
                            if (seen.add(text)) XposedBridge.log("OnePlusNativeHdr: input " + text);
                        } catch (Throwable ignored) { }
                    }
                });
            }
            java.util.Set<String> configs = java.util.Collections.synchronizedSet(new java.util.HashSet<>());
            XposedHelpers.findAndHookMethod(helper, "getValidConfigData", Context.class, String.class,
                new XC_MethodHook() {
                    @Override protected void afterHookedMethod(MethodHookParam p) {
                        if (configs.size() >= 12 || p.hasThrowable() || !(p.getResult() instanceof String)
                                || !(p.args[1] instanceof String)
                                || !((String)p.args[1]).contains("oplus_camera_algo_switch_config")) return;
                        try {
                            JSONObject data = new JSONObject((String)p.getResult());
                            JSONArray modes = data.getJSONArray("aps_capture_configs");
                            for (int i=0; i<modes.length(); i++) {
                                JSONObject mode = modes.getJSONObject(i);
                                if (!"professional".equals(mode.optString("mode"))) continue;
                                JSONArray entities = mode.getJSONArray("entity");
                                for (int j=0; j<entities.length(); j++) {
                                    JSONObject entity = entities.getJSONObject(j);
                                    if (entity.optInt("id",-1) != 0) continue;
                                    String text = "OnePlusNativeHdr: SDK professional capability turbo="
                                        + entity.optInt("aps_algo_turbo_hdr",0) + ", mask="
                                        + entity.optInt("aps_algo_mask_refine",0);
                                    synchronized (configs) {
                                        if (configs.size() < 12 && configs.add(text)) XposedBridge.log(text);
                                    }
                                }
                            }
                        } catch (Throwable error) {
                            try {
                                synchronized (configs) {
                                    if (configs.size() < 12 && configs.add("error"))
                                        XposedBridge.log("OnePlusNativeHdr: config observation skipped; " + error.getClass().getSimpleName());
                                }
                            } catch (Throwable ignored) { }
                        }
                    }
                });
            XposedBridge.log("OnePlusNativeHdr: read-only SDK observers installed");
        } catch (Throwable error) {
            XposedBridge.log("OnePlusNativeHdr: SDK observer unavailable; " + error.getClass().getSimpleName());
        }
    }
}
