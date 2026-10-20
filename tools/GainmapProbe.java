import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Gainmap;
import java.util.Arrays;

/**
 * Android 14+ on-device decoder check. No image is altered or uploaded.
 * Run through app_process with a DEX jar on CLASSPATH.
 * Exit: 0 = all images have a decoded gain map; 1 = at least one failed;
 * 2 = no input. Presence alone does not establish HDR image quality.
 */
public final class GainmapProbe {
    public static void main(String[] paths) {
        if (paths.length == 0) {
            System.err.println("Usage: GainmapProbe image.jpg [image.heic ...]");
            System.exit(2);
        }
        boolean failed = false;
        for (String path : paths) {
            Bitmap bitmap = null;
            try {
                BitmapFactory.Options options = new BitmapFactory.Options();
                options.inPreferredConfig = Bitmap.Config.ARGB_8888;
                bitmap = BitmapFactory.decodeFile(path, options);
                if (bitmap == null) {
                    throw new IllegalArgumentException("Android could not decode image");
                }
                System.out.println(path + ": " + bitmap.getWidth() + "x" + bitmap.getHeight()
                    + " hasGainmap=" + bitmap.hasGainmap());
                if (!bitmap.hasGainmap()) {
                    failed = true;
                    continue;
                }
                Gainmap map = bitmap.getGainmap();
                Bitmap contents = map.getGainmapContents();
                System.out.println("  gainmap=" + contents.getWidth() + "x" + contents.getHeight()
                    + " ratioMin=" + Arrays.toString(map.getRatioMin())
                    + " ratioMax=" + Arrays.toString(map.getRatioMax())
                    + " gamma=" + Arrays.toString(map.getGamma())
                    + " minDisplayRatioForHdrTransition=" + map.getMinDisplayRatioForHdrTransition()
                    + " displayRatioHdr=" + map.getDisplayRatioForFullHdr());
            } catch (Exception error) {
                failed = true;
                System.err.println(path + ": " + error);
            } finally {
                if (bitmap != null) bitmap.recycle();
            }
        }
        System.exit(failed ? 1 : 0);
    }
}
