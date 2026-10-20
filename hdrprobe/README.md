# 一加 12 原厂大师模式 Ultra HDR

已在原生相机 6.070.215 上实测接通原厂 TurboHDR → LocalHDR → MaskRefine → Gainmap → JPEG 链路。当前准入范围是后置主摄 LYT808、1×、普通 JPG、自动 ISO 和自动快门。相机仍使用 professional 模式，没有伪装为普通模式。

## 修复与诊断分离

- `tools/build_native_hdr_helper.py`：从本机私有提取文件生成 KernelSU systemless 修复包。检查相机 APK、原厂库、配置文件哈希；更新不匹配时拒绝挂载。
- `hdrprobe`：只读 LSPosed 诊断模块，作用域仅为原生相机。默认关闭日志；设置 `debug.noah.hdr.nativeconfig=1` 并重新打开相机才观察决策，不改参数或照片。
- 已删除 SDR 成片后生成增益图的代码，不依赖 OPCameraPro 闭源库。

修复包包含本机原厂文件，必须保存在私有目录，不能上传公共仓库或发布附件。公开仓库仅保存构建工具和研究说明。修复包使用全局文件绑定，其他使用同一原厂库的客户端也能看到文件；当前验证限原生相机。

## 原理

1. 开启大师主摄的 TurboHDR 和 MaskRefine 能力，增加 LocalHDR 模式 7 配置。
2. 为缺少 SAT 管线编号的大师主摄增加严格限定的原厂 HDR 决策准入分支，让原厂决定 RAW 格式、帧数与处理方案。
3. 原厂 TurboHDR V1 的两处模式名单加入模式 7，仅改变两个指令中的两个字节；其他模式位和检查保持不变。

没有在 JPEG 保存后估算增益图，没有绕过付费功能，也不修改系统分区原始文件。

## 实测范围

- 大师模式两次实拍：3072×4096，Android 解码器确认增益图 1536×2048，最大增益约 1.543。
- 原生追踪确认 mode 7 的 HDR mask 来自原厂 TurboHDR，经过原厂增益图编码。
- 关闭 SDK 配置修改后仍成功，修复不依赖诊断 Hook。
- 普通模式回归仍生成原厂增益图。
- KernelSU 修复启用后，不运行 Frida、诊断日志关闭，连续两次大师模式实拍和普通模式回归均成功。
- KernelSU Action 已实测立即撤销绑定并关闭相机，原厂库与配置恢复原始哈希；重新启用后复测成功。

以上证明原厂链路与有效编码；不等同于已完成所有场景、镜头或画质评测。手动曝光、RAW、其他焦段不在新增准入范围。后续设备验证见研究记录。

## 构建

```sh
./gradlew :hdrprobe:assembleDebug
python tools/build_native_hdr_helper.py --stock-dir /private/stock-camera --output /private/native-hdr-helper.zip
```

KernelSU 管理器的模块 Action 用于立即撤销并禁用修复，同时关闭相机。普通禁用开关要到重启后才撤销已存在的绑定；需要立即关闭请使用 Action。卸载脚本撤销本模块拥有的绑定；不需要清除相机数据。

`tools/GainmapProbe.java` 使用 Android 解码器只读验证增益图，不能单凭其结果判断增益图来源或画质。
