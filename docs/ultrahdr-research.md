# 大师模式原厂 Ultra HDR 研究

2026-10-20，在一加 12 原生相机 6.070.215 上接通原厂 HDR 链路。修复说明和当前范围见 [hdrprobe/README.md](../hdrprobe/README.md)。

## 证据链

原始普通模式执行 `TurboHDR(65) → MaskRefine(72) → Rotate(16) → Upscale(19)`，JPEG 有有效增益图；原始大师模式执行 `MFNR(74) → BasicTone(78) → Rotate(16) → Upscale(19)`，没有增益图。

SDK 传递的实际算法列表来自原生预览决策。大师自动 JPG 参数是 rawValue=none、ISO=-1、exposure=-1。isTurboHdrEnable 与 isFromMainMenu 均为真，但 currentPipeline=-1，因为没有 SAT 管线元数据；普通模式决策准入因此不适用。为 LYT808 主摄 1× 自动 JPG 加入限定分支后，原厂决策生成 7 帧 RAW 格式 32，执行 TurboHDR、BasicTone 和 MaskRefine。

后半段仍被 TurboHDR V1 内联模式名单阻止。向两处位掩码加入模式 7，并保留配置与其他检查后，追踪看到 `fillLocalHDRData → refineProcessExit → generateGainMap → jpegCodecProcess`，全过程保持模式 7。Android 实际解码新成片 hasGainmap=true，增益图 1536×2048。重复拍摄与普通模式回归通过。

## 实现边界

原厂库的两个指令窗口各只改变一个字节。构建器核验完整 SHA-256、ELF 架构、可执行段映射和原始指令。固件配置和库在本地生成私有 KernelSU 包，通过 systemless bind 提供；原始系统分区不改写。诊断 APK 仅做只读观察，默认关闭，不依赖闭源 OPCameraPro。

生成的私有包包含原厂文件，不能公开发布。独立公共仓库不包含 APK 提取物、原厂库、配置全文、个人照片、设备日志或连接信息。

## 已排除方案

公开 OPCameraPro 镜像基线为 `1fe8308`，其预览 HDR Hook 不能证明照片原生 HDR。曾验证过 SDR 成片后生成增益图，但不符合用户验收，当前代码已删除该路线。

早期强制 all-route HDR 会话格式造成过异常 JPEG 和原厂崩溃，已移除相关修改；当前修复只接通普通模式实际使用的原厂 LocalHDR 路径。

## 验证限制

2026-10-21，0.2 修复已在测试设备启用，自动 JPG 的 0.6×／1×／3×／6× 原厂 HDR 与可用画面均获验收；长焦物理镜头与 6× 裁剪元数据已核对。3×／6× 验收拍摄未运行 Frida。原厂 6× IZOOM 亮度迟滞保持不变，明亮场景分支尚未实机验证。有效增益图和原厂调用链并不证明所有高反差场景的画质；手动参数、RAW、任意连续倍率以及其他固件未获兼容性承诺。原厂更新后的哈希不匹配必须停止启用，不能盲用地址偏移。

## Dolby Vision 录像进展

主摄基线及临时长焦 4K60 测试已验证 10bit Dolby Vision profile 8.4 与逐帧 RPU；长焦拍摄确认实际 physical camera 4、13.3 mm，画面可用。此前暗光下曾发生 SAT 回退，因此仅有 3× UI 标记不算长焦验证。

超广角补光 Dolby 4K60 测试仍有约 192 行重复边缘，旋转后表现为侧边延展；同镜头补光 SDR 对照边缘正常。临时 EIS record-state 实验及 IPE 动态范围对照均未解决问题，不能据此发布永久解锁。当前没有部署永久录像解锁。

超广角 Dolby 4K30 对照边缘正常，缺陷仍集中在已测试的 4K60 路径。另一次临时传感器边界实验在 SSTAB deferred `GetMarginDimension` 中，将请求的传感器尺寸从 4096×2304 改为 4000×2250，保持输出 3840×2160。原厂函数返回成功，但重复边缘仍为 192 像素，未得到修复。该实验已撤销，不属于生产修复。

普通 4K 与 Dolby 配置的 separate_preview_video 均为 1，录像算子列表相同；不能把边缘问题归因于已证实不存在的单双流配置差异。后续继续比对实际 HAL 裁剪和缓冲区处理。有效 Dolby 标记及 RPU 不能代替画面验收。

## 公开诊断代码边界

`HdrProbe` 仅在原生相机主进程通过 APK 哈希核验后安装照片和录像观察器；当前入口不调用临时 EIS 修改实验。`NativeVideoProbe` 不写请求、结果或输出配置，仅记录限量会话与元数据。公共源码不包含设备网络端点、账户凭据、私有文件路径或照片内容。运行日志包含设备与拍摄元数据，应保留私有，不把原始日志提交仓库。
