# 大师模式原厂 Ultra HDR 研究

2026-10-20，在一加 12 原生相机 6.070.215 上接通原厂 HDR 链路。修复说明和当前范围见 [hdrprobe/README.md](../hdrprobe/README.md)。

## 证据链

原始普通模式执行 `TurboHDR(65) → MaskRefine(72) → Rotate(16) → Upscale(19)`，JPEG 有有效增益图；原始大师模式执行 `MFNR(74) → BasicTone(78) → Rotate(16) → Upscale(19)`，没有增益图。

SDK 传递的实际算法列表来自原生预览决策。大师自动 JPG 参数是 rawValue=none、ISO=-1、exposure=-1。isTurboHdrEnable 与 isFromMainMenu 均为真，但 currentPipeline=-1，因为没有 SAT 管线元数据；普通模式决策准入因此不适用。为 LYT808 主摄 1× 自动 JPG 加入限定分支后，原厂决策生成 7 帧 RAW 格式 32，执行 TurboHDR、BasicTone 和 MaskRefine。

后半段仍被 TurboHDR V1 内联模式名单阻止。向两处位掩码加入模式 7，并保留配置与其他检查后，追踪看到 `fillLocalHDRData → refineProcessExit → generateGainMap → jpegCodecProcess`，全过程保持模式 7。Android 实际解码新成片 hasGainmap=true，增益图 1536×2048。重复拍摄与普通模式回归通过。

## 实现边界

原厂库的两个指令窗口各只改变一个字节。构建器核验完整 SHA-256、ELF 架构、可执行段映射和原始指令。固件配置和库在本地生成私有 KernelSU 包，通过 systemless bind 提供；原始系统分区不改写。诊断 APK 仅做只读观察，默认关闭，不依赖闭源 OPCameraPro。

生成的私有包包含原厂文件，不能公开发布。公共 fork 不包含 APK 提取物、原厂库、配置全文、个人照片、设备日志或连接信息。

## 已排除方案

公开 OPCameraPro 镜像基线为 `1fe8308`，其预览 HDR Hook 不能证明照片原生 HDR。曾验证过 SDR 成片后生成增益图，但不符合用户验收，当前代码已删除该路线。

早期强制 all-route HDR 会话格式造成过异常 JPEG 和原厂崩溃，已移除相关修改；当前修复只接通普通模式实际使用的原厂 LocalHDR 路径。

## 验证限制

当前准入限主摄 1×、JPG、自动 ISO/快门。有效增益图和原厂调用链并不证明所有高反差场景的画质；多镜头、手动参数以及其他固件未获兼容性承诺。原厂更新后的哈希不匹配必须停止启用，不能盲用地址偏移。

每轮拍摄后关闭相机。用户为本次充电研究会话允许保留 ADB，整个任务结束后断开任务连接。
