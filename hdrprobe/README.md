# 一加 12 原厂大师／XPan Ultra HDR

照片 helper 0.3 已在原生相机 6.070.215 上安装，保留此前 0.2 已验证的大师模式自动 JPG 配置，并新增 **XPan 主摄 1×、自动 ISO／快门、JPG** 原厂 HDR。大师仍为 professional，XPan 实际原生模式为 29，没有伪装为普通模式。

## 修复与诊断分离

- `tools/build_native_xpan_helper.py`：构建当前 0.3 私有 KernelSU 包，核验相机、库和配置哈希。五个挂载目标为原厂算法库、三份 APS 配置和 `camera_unit_config`；不挂载 `oplus_camera_config`，避免占用录像配置。旧 `build_native_hdr_helper.py` 保留为大师 0.2 构建器。
- `hdrprobe` APK17+：必须在 LSPosed 中启用原生相机作用域。它不再完全只读：在 helper 设置 `debug.noah.hdr.xpan_native=1` 且 APK 哈希验证通过后，只覆盖 SDK 的 `com.oplus.xpan.multi.frame` Boolean，以启用配置中的 XPan RAW 会话；不在保存后改图。
- 照片、录像和 XPan 观察器仍只读，分别由 `debug.noah.hdr.nativeconfig`、`debug.noah.hdr.video`、`debug.noah.hdr.xpan` 控制。诊断默认关闭；只有上述诊断和原生控制全部关闭时，入口才跳过 APK 哈希读取。
- 已删除 SDR 成片后生成增益图的代码，不依赖 OPCameraPro 闭源库。

修复包包含本机原厂文件，必须保存在私有目录，不能上传公共仓库或发布附件。公开仓库仅保存构建工具和研究说明。修复包使用全局文件绑定，其他使用同一原厂库的客户端也能看到文件；当前验证限原生相机。

## 原理

1. 开启已验证大师镜头的 TurboHDR 和 MaskRefine 能力，增加 LocalHDR 模式 7 配置。
2. 为已验证镜头与倍率增加限定的原厂 HDR 决策准入分支，处理大师模式缺少 SAT 管线编号的情况，让原厂决定 RAW 格式、帧数与处理方案。
3. 原厂 TurboHDR V1 的两处模式名单加入模式 7，仅改变两个指令中的两个字节；其他模式位和检查保持不变。

0.3 在保留大师配置的基础上加入模式 29 的原厂 HDR 准入和对应名单位。XPan 使用本机 RAW32 4096×3072 输入，原生追踪确认 **5 帧 RAW → TurboHDR(65) → MaskRefine(72) → gainmap → JPEG**。

没有在 JPEG 保存后估算增益图，没有绕过付费功能，也不修改系统分区原始文件。

## 实测范围

以下大师多镜头及普通模式结果为此前 0.2 的验证；0.3 的新增验收范围是下述 XPan 主摄 1×。

- 大师模式两次实拍：3072×4096，Android 解码器确认增益图 1536×2048，最大增益约 1.543。
- 原生追踪确认 mode 7 的 HDR mask 来自原厂 TurboHDR，经过原厂增益图编码。
- 此前大师 0.2 在关闭 SDK 配置修改后仍成功；这个结论不适用于新增 XPan，后者依赖 APK17+ 的单项 SDK 控制。
- 普通模式回归仍生成原厂增益图。
- KernelSU 修复启用后，不运行 Frida、诊断日志关闭，连续两次大师模式实拍和普通模式回归均成功。
- KernelSU Action 已实测立即撤销绑定并关闭相机，原厂库与配置恢复原始哈希；重新启用后复测成功。

- 0.6×、1×、3×、6× 均已检查原厂链路、有效增益图和可用画面；长焦物理镜头与 6× 裁剪元数据已核对，3×／6× 验收拍摄未运行 Frida。

原厂 6× 长焦 IZOOM 亮度迟滞保持不变，其明亮场景分支尚未进行实机验证。手动曝光、RAW、任意连续倍率、其他固件和所有高反差场景的画质不在已验收范围。

0.3 安装后未运行 Frida，XPan 主摄 1× 自动 JPG 实拍通过：2912×7872、增益图 1456×3936；旋转前为 7872×2912／3936×1456。其他 XPan 镜头、黑白滤镜与水印尚未验证。当前大师复测使用手动 ISO 320，正确保持 SDR，不算新的自动大师 HDR 测试。最终安装后的普通模式复测在快门前被前台切换打断，未计为通过；安装前五路径试验中的普通模式成片有有效增益图。

## 录像仍属实验

录像 0.1 未随照片 0.3 改动，用户报告的闪退／稳定性问题仍是独立未解决任务。以下短片结果不代表录像已获稳定性验收。

临时测试已在实际长焦镜头（physical camera 4，13.3 mm）验证 4K60、10bit、Dolby Vision profile 8.4 与逐帧 RPU，画面可用。

超广角 4K60 的约 192 行边缘重复已定位到坐标原点问题。原生修正在固定场景中消除了延展，构图与 SDR 对照接近；初次验证的 347 帧对应 347 个有效 RPU，保持 10bit DV 8.4、约 59.10fps，L5 裁剪偏移全部为零。

加入逐引擎限定的文件补丁随后通过主摄 4K60、实际长焦 4K60、超广角 4K60／4K30 及 SDR 对照回归，未运行 Frida。独立录像模块 0.1 experimental 已安装，启用、Action 撤销及重新启用均通过：录像文件恢复原始哈希，照片 0.2 修复哈希不变。最终安装后的超广角拍摄复核通过：实际 physical camera 3、2.62 mm，352 帧／352 个 RPU，DV 8.4、约 59.10fps，边缘正常且 ffprobe 无警告。真实运动和长时间录像尚未验证；不承诺其他固件或所有场景兼容。

测试在正常停止录像后先返回 Home、等待相机客户端释放，再 force-stop。此前直接结束进程会使下一次启动的 HDR UI 状态不可靠；正常关闭后可正确显式选择 SDR。录像模块回滚会先停 provider 再撤销自有绑定，并在异常路径尝试重新启动。公开的[主机模拟测试](../tests/README.md)无需手机或固件样本。

录像诊断只读取相机 ID、焦距、曝光、裁剪、防抖状态和输出动态范围。每组最多 3 条结果、总共最多 24 条，预览最多 6 条；会话观察最多 8 次、每次最多 8 个输出。裁剪 vendor 元数据限制键数和长度。日志不读取图像像素、GPS、账户或网络地址，但仍应留在私有目录，不直接上传原始日志。

## 构建

```sh
./gradlew :hdrprobe:assembleDebug
python tools/build_native_hdr_helper.py --stock-dir /private/stock-camera --output /private/native-hdr-helper.zip
```

上例是保留的 0.2 构建命令。0.3 使用 `build_native_xpan_helper.py`，显式提供 `--stock-dir`、`--xpan-config-dir`、`--unit-config`、`--output` 和 `--experimental`；全部原厂输入与生成包保持私有。

KernelSU 管理器的照片模块 Action 用于关闭相机、撤销并禁用修复；确认五个自有绑定撤销后才清除 XPan SDK 控制。**先成功执行照片 helper Action，再停用 APK17+ 的 LSPosed 作用域。** 普通禁用开关不会立即撤销本次启动已有的绑定；不需要清除相机数据。

`tools/GainmapProbe.java` 使用 Android 解码器只读验证增益图，不能单凭其结果判断增益图来源或画质。
