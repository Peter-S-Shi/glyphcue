# Media Downloader 的本地转录能否复用

Type: research
Status: resolved
Assignee: research-media-downloader
Blocked by: none

## Question

现有语音转字幕的实现、模型及运行时来源、许可证、硬件、时间戳、质量证据和部署边界是什么？V2 应复用哪些部分？

## Answer

已完成 Media Downloader 源码、运行时元数据和相关上游资料调查。它适合作为 faster-whisper/CTranslate2 的本地 ASR 基线；可复用独立 worker、路径/范围校验、资源清单与任务监督经验，必须重做词级结果持久化、严格离线、任务恢复、质量验收和分发审计。当前 CPU 路线没有三语正式质量证据，PyAV/FFmpeg 实际二进制不能直接批准捆绑。详见 [Media Downloader ASR 调查](../../../docs/v2_discovery/02_MEDIA_DOWNLOADER_ASR.md)。
