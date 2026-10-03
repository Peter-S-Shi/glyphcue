# 绿地本地 AI 运行时与资源策略

Type: research
Status: resolved
Assignee: round2-runtimes
Blocked by: none

## Question

排除 V1 继承义务后，ASR、翻译、TTS、对齐与 provider adapter 如何选择候选并隔离，如何分别评价质量、Windows 成熟度、资源与精确许可？

## Resolution

研究交付：`docs/v2_discovery_round2/03_LOCAL_AI_RUNTIME_STRATEGY.md`。
按绿地 Windows-first 重新建议同源 Whisper 两运行时首测、Qwen 条件挑战者、llama.cpp 内置翻译与可选 Ollama、本地预设 TTS 对照；无模型/依赖安装、API 推理或生产改动。
新增核实 CT2 v4.8.2 已有官方 Windows ROCm wheel，旧硬件页面不完整；真实 AMD Whisper 支持仍需针对设备验证。锁定代码与模型 revision，明确 BYOK 翻译/TTS 数据与合同边界，ASR 保持本地。
Resolved 表示研究完成，不表示性能、质量、捆绑许可或 Product Gate 已通过。
