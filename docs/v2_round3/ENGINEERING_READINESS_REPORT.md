# GlyphCue V2 第三轮工程准备度报告

日期：2026-10-03。状态：研究交付，供人审与 Claude Code Design；不是实现批准、商业发行批准或 Product Scope Freeze。

## 当前准备度

V2 的产品边界已经足够进入工程设计：本地视频/音频进入本地 ASR，产生带来源和时间证据的可编辑源转录；双语字幕翻译与单旁白预设配音均为 V2.0 必需产品工作流，字幕/媒体导出属于共同基础，许可或可行性失败时须经过明确 Product Gate 才能重定范围。V1 不提供迁移约束。领域、修订、时间、任务、资源和隐私语义已经能写成可测试契约。

技术上可以定下稳定骨架：一个桌面 controller 作为唯一项目 writer 和任务编排者；独立 ASR、翻译、TTS、对齐和 FFmpeg worker 只读受控输入并写暂存产物；结果用 input revision、attempt 和 manifest fencing；SQLite 只保存元数据与修订，媒体/音频保存于受管目录；默认单 GPU 重任务串行，失败可重试已提交单元。这个骨架不依赖具体 Qt、Tauri 或模型名称。

## 关键新增证据

1. CT2 v4.8.2 确有 Windows ROCm zip 和源码 HIP 路径，但没有 GlyphCue 的 Radeon Whisper 实测；不能把“发布物存在”改写成“AMD 已支持”。whisper.cpp 的 Windows 后端源码/preset 也不能替代对应发行包。
2. Qwen ASR 的时间证据需要 ForcedAligner，比较成本必须包含 aligner；翻译模型 JSON 合法不证明语义正确；TTS 82M/1.7B 主权重不等于完整 G2P、voice、tokenizer 和 native DLL 包。
3. SQLite WAL 官方披露并发 reset corruption 条件，3.51.3 修复；发行必须查询实际链接 SQLite source ID。SQLite 事务不涵盖受管音频文件，故必须保留 orphan reconciliation 和一致备份协议。
4. Kokoro 的 espeak/phonemizer 链具有独立 GPL/数据/词典审计面；Ollama 的 localhost 不能证明离线，必须关闭 cloud 并固定本地模型。Qt LGPL、Tauri MIT、FFmpeg build、WebView2 和模型许可证分层审计。

## 按轨道结论

| 轨道 | 已决策内容 | 尚未证明 |
|---|---|---|
| 桌面基础 | Qt Quick/QML 与 Tauri 保留为等价候选；无自由 dock 的预设/splitter 布局进入切片契约 | 10k 编辑、IME、RTL、媒体同步、无障碍、clean install、内存、进程树 |
| 持久化 | SQLite + 受管目录、revision/provenance、单 writer、快照和恢复状态 | 实际 SQLite 包、掉电/磁盘满/孤儿故障注入 |
| worker | controller + 能力 worker、版本化有界消息、Job Object、迟到拒收、单 GPU 槽 | hard-kill 竞态、GPU 释放、真实 OOM、跨壳实现 |
| 资源 | manifest 记录 revision/hash/license/capability/backend/lease；按阶段按需下载，旧版本受引用保护 | 签名 catalog、反回滚、断点/损坏、冷机离线安装 |
| 语言 | BCP 47、stage/pair/voice/alignment/rendering 分栏；三语为锚点 | 六方向质量、三语声线、字体、实际对齐与导出 |
| 分发 | 精确制品审计和 kill conditions 已定义 | 任何具体安装包均未获商用捆绑批准 |
| 隐私 | ASR adapter 不注册 cloud；BYOK payload 明示并绑定确认；keychain、脱敏日志、离线失败即停 | OS 出站隔离、具体 provider 条款和实际网络阻断 |

## 代表性实验顺序

先做不含模型的 stub worker：验证 IPC、输入快照、单 writer、取消/终止、迟到结果、文件发布和重启恢复。接着在 UI Gate 通过后，按 [FRAMEWORK_SLICE_CONTRACT](FRAMEWORK_SLICE_CONTRACT.md) 用相同 fixture 对 Qt Quick 与 Tauri 做一次代表性交互切片。框架实验不下载完整 AI 模型。

再固定一个 CPU ASR 和一个 NVIDIA 候选，使用同源 Whisper 与三语授权样本；Qwen 只有在时间/质量差距足够时加入。翻译分别测六方向，TTS 同时计入 G2P、声线、实际音频长度和许可。最后做 AMD 定向 smoke、资源冷安装/断网/损坏恢复、FFmpeg/字体/预览和精确分发审计。

所有报告保存 revision、hash、硬件/backend、输入集、原始样本数、失败单元和人工评价。未测状态不得提升为产品支持；后端构建成功不得提升为硬件支持。

## 风险和终止条件

- 若两种桌面壳都无法稳定维护 10k 编辑、IME、provenance 和取消恢复，重新审视 UI 范围或单独拆分重型时间线；不能以降低数据正确性来过门。
- 若候选 TTS 的精确 voice/G2P/字体许可无法闭合，字幕核心仍可进入实现，配音从 V2.0 发行包中移除或改为用户自带资源；不自动使用克隆或未经审计声线。
- 若 SQLite 实际版本低于修复线或备份无法覆盖 WAL/产物集合，停止发行准备，先更换 SQLite 包或回滚 journal 策略并重测。
- 若本地 backend 失败，保留明确 CPU/已验证 profile；不静默上传 ASR、不静默更换 provider、不把“运行成功一次”写成支持矩阵。

## 来源与边界

核心第一方来源已分别列于 [FOUNDATION_EVIDENCE](FOUNDATION_EVIDENCE.md)、[WORKER_RUNTIME_VALIDATION](WORKER_RUNTIME_VALIDATION.md)、[PERSISTENCE_RESOURCES_PRIVACY](PERSISTENCE_RESOURCES_PRIVACY.md) 和待补的 [DISTRIBUTION_KILL_TEST](DISTRIBUTION_KILL_TEST.md)。Round 2 文档保留为历史证据快照；本报告只收敛工程结论，不重写其内容。官方滚动页面访问日为 2026-10-03，实施前须重新锁定 immutable revision 和准确许可文本。
