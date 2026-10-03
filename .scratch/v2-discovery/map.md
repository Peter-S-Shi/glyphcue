# GlyphCue V2 Discovery 决策地图

Type: wayfinder:map
Status: complete

## Destination

形成有代码与一手资料支持的 V2 Product Scope，作为 Claude Code Design 的输入。V2 以无可用字幕的视频/音频与本地 ASR 为起点；V1 保持冻结历史基线。

## Notes

- 用户明确授权完整研究交付，覆盖多个研究票；不实施生产功能，不改变 V1 历史记录。
- 主技能 wayfinder；research 并行取证；prototype 仅在资料无法回答关键可行性问题时启用；最终使用 handoff。
- 使用本地 Markdown tracker，不发布 GitHub issues，不提交或推送研究材料。
- 文档以中文交流；只记录通用路径和公开技术证据，不收录个人媒体、日志、凭据或提示草稿。
- 最终规范放在 docs/v2_discovery/；该目录独立于 V1 治理记录。研究结论不等于产品决策已获用户批准。

## Decisions so far

- [Media Downloader 的本地转录能否复用](issues/01-media-downloader-asr.md)：复用路线和工程经验作为候选基线；不直接复用其运行环境、质量结论或 FFmpeg/PyAV 分发物。
- [LinguaClip 的 AI 服务架构与许可边界](issues/02-linguaclip-reference.md)：借鉴模块和资源校验；AGPL 源码、非公开 Edge TTS、仅 EN/ZH 目标翻译不能直接并入 V2。
- [V2 技术候选与最小可行性验证](issues/03-technology-options.md)：ASR、翻译、TTS 和媒体生产均保留可替换候选；用 E1–E6 按语言、质量、资源与发行门槛筛选。
- [V1 架构的复用、改造和退役边界](issues/04-v1-reuse.md)：复用播放、字幕 I/O、编辑安全、边界和发行经验；改造领域模型、任务、存储和媒体生产；退役视觉 OCR 主链。

## Not yet specified

- Product Gates PG-01–PG-08 尚未由用户关闭：外部服务边界、口音/文字、硬件预算、配音标准、商业分发、质量阈值、模型交付和 V1 数据导入。
- 设计阶段需要先确认领域对象、修订关系、原音处理和固定时长策略，再进入 E1–E6 实验实施。

## Out of scope

- 生产代码、依赖安装、模型下载、迁移执行、重写 V1 历史、自动发布、真实媒体上传、模型效果承诺。
