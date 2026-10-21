plugins {
    id("com.android.application")
}

android {
    namespace = "io.github.noahhhi.camera.hdrprobe"
    compileSdk = 36
    defaultConfig {
        applicationId = "io.github.noahhhi.camera.hdrprobe"
        minSdk = 35
        targetSdk = 36
        versionCode = 17
        versionName = "1.7-xpan-native"
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }
}

dependencies {
    compileOnly("de.robv.android.xposed:api:82")
}
