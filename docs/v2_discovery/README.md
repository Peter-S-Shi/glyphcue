# GlyphCue V2 Discovery

研究日期：2026-10-03。这里是 V2 产品重置的研究材料，不是 V1 状态文件，也不是已批准的实现计划。

阅读顺序：

1. [V2 Product Scope](01_V2_PRODUCT_SCOPE.md)：用户已确定的方向、Core/Optional/Deferred、候选架构和 PG-01–PG-08。
2. [Media Downloader ASR 调查](02_MEDIA_DOWNLOADER_ASR.md)：现有本地转录的实际实现、复用边界和许可/部署风险。
3. [LinguaClip 审查](03_LINGUACLIP_REVIEW.md)：AI 服务链、模型/代码/服务许可分层和不能继承的做法。
4. [技术候选](04_TECHNOLOGY_OPTIONS.md)：ASR、翻译、TTS、对齐、FFmpeg、部署与候选限制。
5. [V1 复用矩阵](05_V1_REUSE_REWORK_RETIRE.md)：V1 子系统的 REUSE / REWORK / RETIRE 分类。
6. [最小可行性实验](06_FEASIBILITY_EXPERIMENTS.md)：E1–E6 的材料、指标、顺序和建议门槛。
7. [V2 词汇表](CONTEXT.md)：设计阶段建议采用的产品术语。

Wayfinder 决策地图和每张研究票位于 [.scratch/v2-discovery](../../.scratch/v2-discovery)。该 tracker 记录研究决策，不替代 Product Gates 的用户确认。

## 证据边界

本轮只进行本地源码审阅、公开上游源码/文档/许可资料核查和静态架构分析。没有运行第三方 AI 代码、下载模型、调用云服务、上传媒体、安装依赖或修改生产代码。模型效果、运行速度、商业分发和完整离线行为仍需后续实验与发行审计。

研究报告中的上游版本、提交和模型卡是 2026-10-03 的证据快照；正式选型时必须重新锁定 immutable revision、哈希和准确许可文本。
