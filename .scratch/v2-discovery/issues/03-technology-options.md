# V2 技术候选与最小可行性验证

Type: research
Status: resolved
Assignee: research-technology
Blocked by: none

## Question

本地 ASR、字幕翻译、TTS/配音、时间对齐和 FFmpeg 成片有哪些成熟候选？哪些事实可由文档判断，哪些必须基准测试？

## Answer

已完成候选、硬件/部署、许可与最小实验调查。faster-whisper 与 whisper.cpp 进入 ASR 对照；Qwen3-ASR/ForcedAligner、Qwen3/其他本地 LLM、Kokoro/Qwen3-TTS 进入有条件候选；Piper、F5-TTS、XTTS 等存在 GPL/NC/非商业或音色许可门槛。FFmpeg/libass 可支持字幕烧录、封装、混音，但实际二进制必须单独审计。详见 [技术候选与实验](../../../docs/v2_discovery/04_TECHNOLOGY_OPTIONS.md) 与 [最小可行性实验计划](../../../docs/v2_discovery/06_FEASIBILITY_EXPERIMENTS.md)。
