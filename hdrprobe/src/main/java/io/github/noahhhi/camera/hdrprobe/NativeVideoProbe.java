package io.github.noahhhi.camera.hdrprobe;

import android.hardware.camera2.CameraCaptureSession;
import android.hardware.camera2.CaptureRequest;
import android.hardware.camera2.CaptureResult;
import android.hardware.camera2.TotalCaptureResult;
import android.hardware.camera2.params.OutputConfiguration;
import de.robv.android.xposed.XC_MethodHook;
import de.robv.android.xposed.XposedBridge;
import de.robv.android.xposed.XposedHelpers;
import java.util.HashMap;
import java.util.Map;
import java.util.List;
import java.util.ArrayList;
import java.util.Locale;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicBoolean;

/** Opt-in observations of OEM preview/recording results; never changes metadata. */
final class NativeVideoProbe {
    private static final String PREFIX = "OnePlusNativeVideo: ";

    static void install(ClassLoader loader) {
        try {
            if (!"1".equals(XposedHelpers.callStaticMethod(
                    XposedHelpers.findClass("android.os.SystemProperties", null),
                    "get", "debug.noah.hdr.video", "0"))) return;
            installSessionObserver(loader);
            Class<?> callback = XposedHelpers.findClass(
                    "com.oplus.ocs.camera.producer.device.Camera2Impl$6", loader);
            final Map<String, Integer> counts = new HashMap<>();
            final int[] total = {0};
            final int[] previewTotal = {0};
            final AtomicBoolean reportedError = new AtomicBoolean();
            XposedHelpers.findAndHookMethod(callback, "onCaptureCompleted",
                    CameraCaptureSession.class, CaptureRequest.class, TotalCaptureResult.class,
                    new XC_MethodHook() {
                @Override protected void beforeHookedMethod(MethodHookParam p) {
                    try {
                        synchronized (counts) {
                            if (total[0] >= 24) return;
                        }
                        CameraCaptureSession session = (CameraCaptureSession) p.args[0];
                        CaptureRequest request = (CaptureRequest) p.args[1];
                        TotalCaptureResult result = (TotalCaptureResult) p.args[2];
                        if (session == null || request == null || result == null) return;
                        Integer intent = request.get(CaptureRequest.CONTROL_CAPTURE_INTENT);
                        boolean videoRecordIntent = intent != null
                                && intent == CaptureRequest.CONTROL_CAPTURE_INTENT_VIDEO_RECORD;
                        Boolean recordTagPresent = recordingTagPresent(p.thisObject);
                        boolean recording = Boolean.TRUE.equals(recordTagPresent);
                        String logical = session.getDevice().getId();
                        String physical = result.get(CaptureResult.LOGICAL_MULTI_CAMERA_ACTIVE_PHYSICAL_ID);
                        Float focal = result.get(CaptureResult.LENS_FOCAL_LENGTH);
                        Float zoom = result.get(CaptureResult.CONTROL_ZOOM_RATIO);
                        Long exposure = result.get(CaptureResult.SENSOR_EXPOSURE_TIME);
                        Integer iso = result.get(CaptureResult.SENSOR_SENSITIVITY);
                        // Zoom animation and changing AE must not consume recording samples.
                        String key = recordTagPresent + "|" + logical + "|" + physical
                                + "|" + rounded(focal);
                        int sample;
                        synchronized (counts) {
                            int previous = counts.containsKey(key) ? counts.get(key) : 0;
                            if (previous >= 3 || total[0] >= 24
                                    || (!recording && previewTotal[0] >= 6)) return;
                            sample = previous + 1;
                            counts.put(key, sample);
                            total[0]++;
                            if (!recording) previewTotal[0]++;
                        }
                        log("recordTagPresent=" + recordTagPresent
                                + ", videoRecordIntent=" + videoRecordIntent + ", intent=" + intent
                                + ", logical=" + logical + ", activePhysical=" + physical
                                + ", focalMm=" + focal + ", zoom=" + zoom
                                + ", exposureNs=" + exposure + ", iso=" + iso
                                + ", requestVideoStabilization=" + read(request, CaptureRequest.CONTROL_VIDEO_STABILIZATION_MODE)
                                + ", resultVideoStabilization=" + read(result, CaptureResult.CONTROL_VIDEO_STABILIZATION_MODE)
                                + ", requestOpticalStabilization=" + read(request, CaptureRequest.LENS_OPTICAL_STABILIZATION_MODE)
                                + ", resultOpticalStabilization=" + read(result, CaptureResult.LENS_OPTICAL_STABILIZATION_MODE)
                                + ", requestCrop=" + read(request, CaptureRequest.SCALER_CROP_REGION)
                                + ", resultCrop=" + read(result, CaptureResult.SCALER_CROP_REGION)
                                + ", requestFrameDurationNs=" + read(request, CaptureRequest.SENSOR_FRAME_DURATION)
                                + ", resultFrameDurationNs=" + read(result, CaptureResult.SENSOR_FRAME_DURATION)
                                + ", vendorEis=" + vendorEis(request, result)
                                + ", cropMetadata=" + cropMetadata(result)
                                + ", sample=" + sample);
                    } catch (Throwable error) {
                        if (reportedError.compareAndSet(false, true))
                            log("observation skipped; " + error.getClass().getSimpleName());
                    }
                }
            });
            log("read-only callback observer installed");
        } catch (Throwable error) {
            log("observer unavailable; " + error.getClass().getSimpleName());
        }
    }

    private static void installSessionObserver(ClassLoader loader) {
        try {
            Class<?> device = XposedHelpers.findClass(
                    "android.hardware.camera2.impl.CameraDeviceImpl", loader);
            final AtomicInteger sessions = new AtomicInteger();
            int hooked = XposedBridge.hookAllMethods(device, "createCaptureSessionInternal",
                    new XC_MethodHook() {
                @Override protected void beforeHookedMethod(MethodHookParam p) {
                    try {
                        int number = sessions.incrementAndGet();
                        if (number > 8) return;
                        int outputs = 0;
                        for (Object argument : p.args) {
                            if (!(argument instanceof List<?>)) continue;
                            for (Object item : (List<?>) argument) {
                                if (!(item instanceof OutputConfiguration)) continue;
                                if (outputs >= 8) break;
                                OutputConfiguration output = (OutputConfiguration) item;
                                String profile;
                                String physical;
                                try {
                                    profile = Long.toString(output.getDynamicRangeProfile());
                                } catch (Throwable ignored) {
                                    profile = "unavailable";
                                }
                                try {
                                    physical = String.valueOf(XposedHelpers.callMethod(output, "getPhysicalCameraId"));
                                } catch (Throwable ignored) {
                                    physical = "unavailable";
                                }
                                log("session=" + number + ", output=" + outputs
                                        + ", dynamicRangeProfile=" + profile
                                        + ", boundPhysical=" + physical);
                                outputs++;
                            }
                        }
                    } catch (Throwable ignored) { }
                }
            }).size();
            log("read-only session observer methods=" + hooked);
        } catch (Throwable error) {
            log("session observer unavailable; " + error.getClass().getSimpleName());
        }
    }

    private static String rounded(Float value) {
        return value == null ? "null" : Long.toString(Math.round(value.doubleValue() * 100.0));
    }

    private static Boolean recordingTagPresent(Object callback) {
        try {
            Object device = XposedHelpers.getObjectField(callback, "this$0");
            return XposedHelpers.getObjectField(device, "mRecordingTag") != null;
        } catch (Throwable ignored) {
            return null;
        }
    }

    private static <T> T read(CaptureRequest request, CaptureRequest.Key<T> key) {
        try {
            return request.get(key);
        } catch (Throwable ignored) {
            return null;
        }
    }

    private static <T> T read(CaptureResult result, CaptureResult.Key<T> key) {
        try {
            return result.get(key);
        } catch (Throwable ignored) {
            return null;
        }
    }

    private static String vendorEis(CaptureRequest request, CaptureResult result) {
        try {
            String name = "com.oplus.camera.video.eis.mode";
            Integer requested = read(request, new CaptureRequest.Key<Integer>(name, Integer.class));
            Integer returned = read(result, new CaptureResult.Key<Integer>(name, Integer.class));
            return "request:" + requested + "/result:" + returned;
        } catch (Throwable ignored) {
            return "unavailable";
        }
    }

    private static String cropMetadata(CaptureResult result) {
        try {
            List<CaptureResult.Key<?>> keys = result.getKeys();
            List<CaptureResult.Key<?>> selected = new ArrayList<>();
            String[] priority = {
                    "com.qti.cropregions.crop_regions",
                    "org.quic.camera.ifecropinfo.ResidualCrop",
                    "org.codeaurora.qcamera3.sessionParameters.EISMode"
            };
            for (String name : priority) {
                for (CaptureResult.Key<?> key : keys) {
                    if (name.equals(key.getName())) {
                        selected.add(key);
                        break;
                    }
                }
            }
            for (CaptureResult.Key<?> key : keys) {
                if (selected.size() >= 12) break;
                String name = key.getName().toLowerCase(Locale.ROOT);
                if ((name.contains("crop") || name.contains("eismode")) && !selected.contains(key))
                    selected.add(key);
            }
            StringBuilder text = new StringBuilder("{");
            for (CaptureResult.Key<?> key : selected) {
                try {
                    Object value = result.get(key);
                    String formatted = compactValue(value);
                    if (formatted == null) continue;
                    if (text.length() > 1) text.append("; ");
                    text.append(key.getName()).append('=').append(formatted);
                } catch (Throwable ignored) { }
            }
            return text.append('}').toString();
        } catch (Throwable ignored) {
            return "unavailable";
        }
    }

    private static String compactValue(Object value) {
        if (value == null) return "null";
        if (value instanceof android.graphics.Rect || value instanceof Number
                || value instanceof Boolean) return value.toString();
        if (value instanceof byte[]) {
            byte[] bytes = (byte[]) value;
            StringBuilder hex = new StringBuilder("bytes[").append(bytes.length).append("]:");
            char[] alphabet = "0123456789abcdef".toCharArray();
            for (int i = 0; i < Math.min(bytes.length, 96); i++) {
                int item = bytes[i] & 255;
                hex.append(alphabet[item >>> 4]).append(alphabet[item & 15]);
            }
            if (bytes.length > 96) hex.append("...");
            return hex.toString();
        }
        if (value instanceof int[] || value instanceof float[]) {
            int length = java.lang.reflect.Array.getLength(value);
            StringBuilder array = new StringBuilder("n=").append(length).append('[');
            for (int i = 0; i < Math.min(length, 24); i++) {
                if (i > 0) array.append(',');
                array.append(java.lang.reflect.Array.get(value, i));
            }
            if (length > 24) array.append(",...");
            return array.append(']').toString();
        }
        return null;
    }

    private static void log(String message) {
        try {
            XposedBridge.log(PREFIX + message);
        } catch (Throwable ignored) { }
    }
}
