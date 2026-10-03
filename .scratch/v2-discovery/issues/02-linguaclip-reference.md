# LinguaClip 的 AI 服务架构与许可边界

Type: research
Status: resolved
Assignee: research-linguaclip
Blocked by: none

## Question

LinguaClip 的具体 AI 流程如何工作？源代码、依赖、模型权重和外部服务分别施加什么商业使用、分发、署名和隐私限制？哪些结构值得参考？

## Answer

已静态审查 2026-10-03 main 提交 d1bd35113d80dc1387241af7c7203179cbd97e5e，核实本地 whisper.cpp/Silero、可选云 ASR、OpenAI 兼容翻译、短句 TTS 与导入 FFmpeg 的真实边界。源码 AGPL、权重 MIT、实际 FFmpeg 构建、第三方组件及云服务合同已分层；非公开 Edge TTS 不进入商业配音候选。翻译仅支持目标 EN/ZH，未覆盖完整 EN/ZH/FR 六方向；没有完整配音/烧录输出链证据。无需执行 prototype。

详见 [LinguaClip 审查报告](../../../docs/v2_discovery/03_LINGUACLIP_REVIEW.md)。
