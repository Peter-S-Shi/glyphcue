# Worker 边界与硬件验证政策
Type: research
Status: resolved

## Answer

Use isolated capability workers behind a versioned controller protocol. Keep Whisper-family, Qwen ASR/alignment, local translation, and local TTS as measured candidates. Do not claim AMD/Intel support, timestamp quality, or offline success until the declared hardware matrix and fixture measurements pass. See `docs/v2_round3/WORKER_RUNTIME_VALIDATION.md`.
Assignee: runtime-research

## Question

如何以独立能力 worker、安全 IPC、取消和可重复测量落实 Track C/F？纠正前轮后端结论中的不确定性。
