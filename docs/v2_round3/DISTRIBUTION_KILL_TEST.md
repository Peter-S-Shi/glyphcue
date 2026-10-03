# Shortlist 分发与许可 Kill-Test

核验日：2026-10-03。本文是工程筛选，不是法律意见或商业发行批准。只审当前 shortlist；每个制品仍需锁 revision、文件 hash、传递依赖和通知。

| 层 | 可进入候选的证据 | 必须在发行前关闭的条件 |
|---|---|---|
| Qt Quick/PySide | Qt for Python 提供 LGPL/GPL/商业路径；模块许可证需分别看 | 选择 LGPL 时提供适用源码/通知、允许重新链接和用户替换的合规方案；若无法交付，Qt bundle kill |
| Tauri/Rust | 代码主体 MIT/Apache 路线；sidecar/WebView2 是独立依赖 | 固定 WebView2 Evergreen/Fixed/offline 方案、插件许可、Rust/前端 SBOM 和 notices；WebView2 缺件或安全更新责任未解决则 kill 离线包 |
| FFmpeg/libass | FFmpeg legal 说明 build 配置决定 LGPL/GPL/nonfree 边界 | 固定 build、configure、第三方库和源码/notice；含不可再分发 nonfree 或未清 patent 的 build 不进入官方 bundle |
| Whisper/CT2/whisper.cpp | Whisper 与主要运行时源码候选许可可审 | 转换产物、native DLL、CUDA/ROCm/SYCL/Vulkan 部件和模型文件分别盘点；缺精确来源或 ABI manifest 则 kill 该 profile |
| Qwen ASR/aligner/翻译/TTS | 当前 shortlist 模型卡/源码声明 Apache-2.0 的候选 | 逐模型 revision、tokenizer/aligner、转换文件和 NOTICE；不能以 Qwen 家族名覆盖未核验模型 |
| llama.cpp/Ollama | 代码可审，Ollama cloud 条件独立于本地代码 | Ollama 只能作为用户管理 adapter；必须关闭 cloud、固定本地 digest、不能把其服务/模型/条款当 GlyphCue bundle 权利 |
| Kokoro/Misaki | 主代码/权重 Apache 线索；voice/attribution 单独列出 | `espeak-ng` GPL、phonemizer fork、词典/G2P DLL/voice 数据逐项审；无法说明链接和分发边界则 Kokoro 官方包 kill，保留用户自带资源候选 |
| Qwen CustomVoice | 所选模型/tokenizer 许可候选可审；预设 voice 不是现实人物身份 | 精确 speaker、跨语种声线、附属 tokenizer 和实际输出/通知闭合；不启用 Base 克隆或 VoiceDesign |
| 字体 | 精确 OFL/其他再分发文本可进入 manifest | 每个 CJK/Latin/RTL 文件和版本单独审；系统字体可显示不等于可随安装器分发 |
| BYOK 翻译/TTS | 连接器可设计为用户自带凭据和服务合同 | provider、region、model/voice、保留、费用、输出权利和商业使用必须明确；本地模型许可不覆盖服务条款 |

## 终止条件

以下任一条件直接阻止“官方随包”：来源只能是可变 latest、只验证 hash 未验证签名/信任根、依赖的许可证链缺失、模型/voice 与实际文件不一致、GPL/专利配置没有可执行分发方案、WebView2/offline 依赖未验证、G2P DLL 许可未闭合、或 provider 合同无法证明允许当前用途。可以保留“用户从上游自行导入”路径，但 UI 必须显示未审计状态，不能称 GlyphCue 已批准资源。

## 首轮建议的资源交付边界

官方安装器只携带应用壳、已审媒体工具和必要字体。ASR、翻译、TTS 按用户启用的阶段下载或离线导入；下载先 staging、签名 manifest/文件 hash 校验、依赖检查和本地 load smoke，再切换激活版本。旧版有活动任务引用时保留。首次下载仍需附带许可证和 notices；“不随包”不自动消除权利义务。

## BYOK 与隐私

BYOK 发送的是用户确认的文本 units/邻段/术语或配音稿；不发送 ASR 音频、视频、项目数据库或本地路径。key 进入系统凭据库，项目只保存 provider 配置 ID。服务超时的远端结果可能未知，不能自动重发或切换 provider。不同 endpoint、region、model、voice 或数据类别重新确认。

来源： [Qt for Python licenses](https://doc.qt.io/qtforpython-6/licenses.html)、[Tauri licenses](https://github.com/tauri-apps/tauri#licenses)、[WebView2 distribution](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution)、[FFmpeg legal](https://ffmpeg.org/legal.html)、[Kokoro model](https://huggingface.co/hexgrad/Kokoro-82M)、[espeak COPYING](https://github.com/espeak-ng/espeak-ng/blob/master/COPYING)、[Ollama FAQ](https://docs.ollama.com/faq)。滚动页面与当前模型卡须在发行前重新锁定。
