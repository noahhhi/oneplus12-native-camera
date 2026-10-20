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
        versionCode = 13
        versionName = "1.3-idle-gated"
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }
}

dependencies {
    compileOnly("de.robv.android.xposed:api:82")
}
