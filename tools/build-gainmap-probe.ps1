param(
    [Parameter(Mandatory=$true)][string]$AndroidSdk,
    [Parameter(Mandatory=$true)][string]$JavaHome,
    [string]$Platform = "android-34",
    [string]$BuildTools = "35.0.0"
)
$ErrorActionPreference = "Stop"
$build = Join-Path $PSScriptRoot "../build/gainmap-probe"
$classes = Join-Path $build "classes"
New-Item -ItemType Directory -Force -Path $classes | Out-Null
$androidJar = Join-Path $AndroidSdk "platforms/$Platform/android.jar"
& "$JavaHome/bin/javac.exe" -source 8 -target 8 -classpath $androidJar -d $classes "$PSScriptRoot/GainmapProbe.java"
if ($LASTEXITCODE -ne 0) { throw "GainmapProbe Java compilation failed" }
$previousJavaHome = $env:JAVA_HOME
try {
    $env:JAVA_HOME = $JavaHome
    & "$AndroidSdk/build-tools/$BuildTools/d8.bat" --min-api 34 --lib $androidJar --output "$build/gainmap-probe.jar" "$classes/GainmapProbe.class"
    if ($LASTEXITCODE -ne 0) { throw "GainmapProbe DEX compilation failed" }
} finally {
    $env:JAVA_HOME = $previousJavaHome
}
Write-Output "$build/gainmap-probe.jar"
