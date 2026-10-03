# LinguaClip：AI 服务架构与许可审查

研究日期：2026-10-03。研究基线：公开仓库 `main`，提交 [`d1bd35113d80dc1387241af7c7203179cbd97e5e`](https://github.com/Samuelxiaozhuofeng/LinguaClip/tree/d1bd35113d80dc1387241af7c7203179cbd97e5e)。仅静态阅读公开源码、模型卡和服务协议；未运行第三方代码、下载模型、调用付费推理或上传媒体。结论只覆盖这个源码快照，未核验安装包是否与源码一致。

## 结论

LinguaClip 是本地听写学习应用，能证明“桌面应用按需安装本地 ASR、生成带时间字幕，再用可选 AI 改善学习体验”这一结构已经有具体实现。它不是完整的视频本地化、配音与交付工具。可借鉴服务边界、资源下载校验、错误降级和缓存思想；不宜直接复制 AGPL 源码，也不宜继承其非公开 Edge 朗读接口、明文密钥存储、学习型断句规则或导入转码策略。

对 GlyphCue 首批 **EN、ZH、FR 六个有向组合**：本地 Whisper 路线覆盖三种输入语言的候选能力，但本次没有测量质量；LinguaClip 译文目标类型只有 `zh | en`，没有 FR 目标，无法证明 EN→FR 和 ZH→FR；其 EN/ZH/FR 朗读声音存在，也不能证明整段配音、时长适配或音画同步已经实现。必须分别验收 ASR、翻译、TTS 与成片质量。[翻译目标与请求](https://github.com/Samuelxiaozhuofeng/LinguaClip/blob/d1bd35113d80dc1387241af7c7203179cbd97e5e/pro/transPrep.ts#L12-L60)、[声音映射](https://github.com/Samuelxiaozhuofeng/LinguaClip/blob/d1bd35113d80dc1387241af7c7203179cbd97e5e/utils/speech.ts#L3-L24)

## 实际调用链

| 阶段 | 已实现行为 | GlyphCue 的判断 |
|---|---|---|
| 导入 | 本地媒体、自带 SRT、内嵌文本字幕；不兼容媒体转成可播放 MP4 | 文本字幕检测可借鉴，但 V2 输入以无可用字幕为主；保持原始媒体和选择音轨应独立建模 |
| 本地解码 | macOS 用系统音频转换；其他平台使用 Rust Symphonia；失败后按需下载 FFmpeg；输出 16 kHz 单声道 WAV | 本地解码与 ASR 解耦合理；具体格式矩阵需验证 |
| 本地 ASR | 独立 whisper-cli 子进程，Whisper + Silero VAD，SRT 与完整 JSON 输出 | 独立进程便于打包、取消和崩溃隔离；仅作为候选路线 |
| 云 ASR | Groq / 中国大陆百炼，分块上传，归一化为相同 SRT 与词时间数据 | 可借鉴归一化边界；不应成为本地 ASR 的隐式回退 |
| AI 断句 | 自带 OpenAI 兼容 endpoint/key/model，模型只返回词索引切点 | “只让模型选边界”可降低篡改原文风险；学习型词数规则不适合作为字幕排版标准 |
| 翻译 | 针对每条字幕生成中文或英文对照，JSON 数组，逐批缓存 | 有可借鉴的恢复能力；欠缺可编辑译文版本、六方向验收和字幕成品规则 |
| 朗读 | 先发文本给微软 Edge Read Aloud 非公开服务；失败后 Web Speech | 短句学习朗读，不等于 AI 配音；商业产品候选中排除这条非公开服务路线 |
| 输出 | ASR 过程落 SRT；导入媒体转换；原声片段供学习/Anki 使用 | 静态审查未找到完整配音轨拼接、响度处理、双语字幕导出或烧录字幕的生产流水线 |

证据：[解码与回退](https://github.com/Samuelxiaozhuofeng/LinguaClip/blob/d1bd35113d80dc1387241af7c7203179cbd97e5e/src-tauri/src/import.rs#L444-L489)、[本地推理参数](https://github.com/Samuelxiaozhuofeng/LinguaClip/blob/d1bd35113d80dc1387241af7c7203179cbd97e5e/src-tauri/src/import.rs#L496-L576)、[云 ASR 统一入口](https://github.com/Samuelxiaozhuofeng/LinguaClip/blob/d1bd35113d80dc1387241af7c7203179cbd97e5e/src-tauri/src/cloud_asr.rs#L1-L117)、[Tauri 命令注册](https://github.com/Samuelxiaozhuofeng/LinguaClip/blob/d1bd35113d80dc1387241af7c7203179cbd97e5e/src-tauri/src/lib.rs#L44-L85)。缺失结论来自这些模块、前端调用与全仓库相关命令搜索，不是对未公开产品版本的断言。

## 本地 ASR：来源、硬件、时间戳与下载

### 资源溯源

| 资源 | 源码锁定项 | 来源 / 包装 |
|---|---|---|
| 运行时 | whisper.cpp `v1.8.4` | Windows CPU 使用上游 release zip；Vulkan 使用 LinguaClip 自建包；Apple Silicon/Intel Mac 使用自建独立 CLI |
| 标准模型 | `ggml-large-v3-turbo-q5_0.bin`，574,041,195 bytes | `ggerganov/whisper.cpp` 的 GGML 量化文件；按需下载，非 LinguaClip 自训权重 |
| 轻量模型 | `ggml-small-q5_1.bin`，190,085,487 bytes | 同一模型仓库的多语言 small 量化文件 |
| VAD | `ggml-silero-v5.1.2.bin`，885,098 bytes | `ggml-org/whisper-vad` 的转换文件 |

每项有期望大小和 SHA-256；URL 顺序包含 GitHub/Hugging Face、第三方镜像或作者网站。下载采用 `.part`、HTTP Range 续传、超时、镜像切换、大小与摘要校验，验证后改名。这个模式值得参考，但 GlyphCue 应额外保存模型修订、上游许可证、转换方式、构建参数和资源清单；不能把镜像域名当作授权或来源证明。[资源清单](https://github.com/Samuelxiaozhuofeng/LinguaClip/blob/d1bd35113d80dc1387241af7c7203179cbd97e5e/src-tauri/src/whisper_setup.rs#L25-L148)、[下载校验](https://github.com/Samuelxiaozhuofeng/LinguaClip/blob/d1bd35113d80dc1387241af7c7203179cbd97e5e/src-tauri/src/whisper_setup.rs#L267-L394)

Windows 默认 CPU；可选 Vulkan，失败可重跑 CPU。macOS Apple Silicon 构建嵌入 Metal，Intel 构建关闭 Metal。Vulkan CI 用 Mesa 的软件设备和小型英文样本验证“确实走 Vulkan”，不足以承诺真实 NVIDIA/AMD/Intel 显卡上的性能、内存或三语质量。源码没有 LinguaClip 的 CUDA / DirectML 适配实现。[Mac 构建](https://github.com/Samuelxiaozhuofeng/LinguaClip/blob/d1bd35113d80dc1387241af7c7203179cbd97e5e/scripts/build-whisper-cli.sh#L9-L24)、[Vulkan 构建与测试](https://github.com/Samuelxiaozhuofeng/LinguaClip/blob/d1bd35113d80dc1387241af7c7203179cbd97e5e/.github/workflows/whisper-vulkan.yml#L1-L86)、[CPU 回退](https://github.com/Samuelxiaozhuofeng/LinguaClip/blob/d1bd35113d80dc1387241af7c7203179cbd97e5e/src-tauri/src/import.rs#L893-L908)

### 时间戳的能力边界

CLI 开启 DTW，显式关闭 flash attention，DTW preset 必须与模型对应。VAD 保留语音不足全片 20% 时，会取消 VAD 重跑；这只是作者依据素材经验的启发式，不能证明所有音乐、静音、噪声或低语素材适用。[参数与 VAD 回退](https://github.com/Samuelxiaozhuofeng/LinguaClip/blob/d1bd35113d80dc1387241af7c7203179cbd97e5e/src-tauri/src/import.rs#L496-L560)

实现将 VAD 压缩时间上的 token 线性映射回 segment 时间范围，合并子词，检查单调性；缺失或倒退时丢弃词级时间，保留 ASR 原始句级字幕。这是近似修复与降级，不是经人工基准验证的 forced alignment。词级结构只有 `w/from/to`，字幕只有 `id/startTime/endTime/text`，没有置信度、说话人、修订来源或对齐质量状态。[词时间恢复](https://github.com/Samuelxiaozhuofeng/LinguaClip/blob/d1bd35113d80dc1387241af7c7203179cbd97e5e/src-tauri/src/import.rs#L615-L703)、[降级与缓存](https://github.com/Samuelxiaozhuofeng/LinguaClip/blob/d1bd35113d80dc1387241af7c7203179cbd97e5e/src-tauri/src/import.rs#L936-L958)、[字幕结构](https://github.com/Samuelxiaozhuofeng/LinguaClip/blob/d1bd35113d80dc1387241af7c7203179cbd97e5e/types.ts#L1-L6)

AI 断句按约 10 词、最多 16 词、250 词一批，返回单调递增的切点索引，并保留原文词序；中文占多数时完全跳过该过程。末尾有 400 ms 的经验性延长。GlyphCue 需要面向 EN/ZH/FR 分别定义阅读速度、字数/字符数、最多行数、标点和断句约束，不能沿用“每条 10 词”作为字幕质量门槛。[断句算法](https://github.com/Samuelxiaozhuofeng/LinguaClip/blob/d1bd35113d80dc1387241af7c7203179cbd97e5e/utils/resegment.ts#L11-L195)

## AI 服务、隐私和失败语义

### 路由不是一个统一 AI 后端

- LLM：前端通过 Tauri HTTP plugin 直接请求用户配置的 `/chat/completions`；模型列表使用 `/models`。没有默认供应商，不代表所填兼容服务具有同样条款。自建本机兼容端点在接口形态上可行，但没有此项目的本地 LLM 安装、显存调度或模型许可管理证据。[配置](https://github.com/Samuelxiaozhuofeng/LinguaClip/blob/d1bd35113d80dc1387241af7c7203179cbd97e5e/utils/aiConfig.ts#L12-L85)
- Groq：Rust 适配器固定 `whisper-large-v3-turbo`，multipart 上传音频，要求 word/segment 时间戳与 `verbose_json`。[Groq](https://github.com/Samuelxiaozhuofeng/LinguaClip/blob/d1bd35113d80dc1387241af7c7203179cbd97e5e/src-tauri/src/groq.rs#L7-L42)
- 百炼：固定中国大陆 endpoint 与 `qwen3-asr-flash-filetrans`；上传临时 OSS 对象、提交异步任务、轮询、下载结果。该模型 ID 是托管服务标识，不能从其名称推定获得本地权重或重分发许可。[百炼](https://github.com/Samuelxiaozhuofeng/LinguaClip/blob/d1bd35113d80dc1387241af7c7203179cbd97e5e/src-tauri/src/bailian.rs#L1-L107)
- TTS：独立 Rust WebSocket 到微软 consumer Read Aloud，源码主动模拟 Edge 客户端环境；单次最多 300 字符、12 秒超时、MP3 返回，无词/句边界。与用户填写的 LLM 供应商无关，也不受本地 ASR 选择约束。[TTS](https://github.com/Samuelxiaozhuofeng/LinguaClip/blob/d1bd35113d80dc1387241af7c7203179cbd97e5e/src-tauri/src/tts.rs#L8-L18)、[输出与限制](https://github.com/Samuelxiaozhuofeng/LinguaClip/blob/d1bd35113d80dc1387241af7c7203179cbd97e5e/src-tauri/src/tts.rs#L82-L133)

因此应按每个动作披露出站数据：本地 ASR 的媒体留在机器；云 ASR 发音频；翻译/AI 断句发转录文本；Edge 朗读发短句文本。“视频不上传”不足以表达这些独立数据流。微软自己的 Edge 隐私页也说明朗读可能使用服务端语音库。[Edge Read Aloud 隐私](https://learn.microsoft.com/en-us/legal/microsoft-edge/privacy#read-aloud)

### 配置、缓存与取消

密钥直接保存在 WebView `localStorage`。自动备份跳过密钥配置，但手动备份会包括整份 AI / 转录配置，因此手动备份可能带出密钥。GlyphCue 应采用操作系统凭据库、导出默认去密钥和明确的网络授权；不要复制这种存储与备份语义。[密钥保存](https://github.com/Samuelxiaozhuofeng/LinguaClip/blob/d1bd35113d80dc1387241af7c7203179cbd97e5e/utils/aiConfig.ts#L21-L32)、[转录密钥](https://github.com/Samuelxiaozhuofeng/LinguaClip/blob/d1bd35113d80dc1387241af7c7203179cbd97e5e/utils/transcribeConfig.ts#L20-L40)、[备份过滤](https://github.com/Samuelxiaozhuofeng/LinguaClip/blob/d1bd35113d80dc1387241af7c7203179cbd97e5e/utils/backupData.ts#L16-L30)

翻译以原文 hash、目标语言和行数检查缓存有效性，失败行保留 `null`，逐批保存，可在下次补做；90 秒超时，失败重试一次。未见 model、prompt version、glossary 或 stable cue revision 进入缓存标识。数组长度校验防止缺条，但不能判断事实、专名、语义和翻译方向正确。取消设置标志阻止后续写入，没有将显式取消信号传入正在进行的 HTTP 请求；提供方调用可能继续完成。[翻译缓存与任务](https://github.com/Samuelxiaozhuofeng/LinguaClip/blob/d1bd35113d80dc1387241af7c7203179cbd97e5e/pro/transPrep.ts#L12-L128)

导入串行排队，本地子进程可终止，云端则主要在分块之间与结果返回后检查取消；没有看到云任务撤销与退款保证。百炼网络轮询错误最多短暂容忍三次，但不能把重新提交付费任务等同无成本重试。V2 应分别定义“取消等待/本地计算/网络传输/供应商任务”和“保留已完成检查点”。[导入队列](https://github.com/Samuelxiaozhuofeng/LinguaClip/blob/d1bd35113d80dc1387241af7c7203179cbd97e5e/src-tauri/src/import_queue.rs#L1-L128)、[分块检查](https://github.com/Samuelxiaozhuofeng/LinguaClip/blob/d1bd35113d80dc1387241af7c7203179cbd97e5e/src-tauri/src/cloud_asr.rs#L63-L102)、[轮询](https://github.com/Samuelxiaozhuofeng/LinguaClip/blob/d1bd35113d80dc1387241af7c7203179cbd97e5e/src-tauri/src/bailian.rs#L42-L69)

## 配音与成片：不能由现有能力推导的部分

LinguaClip 的短句 TTS 没有证明：完整影片配音轨、原声/背景声分离、翻译时长约束、合成音频回对齐、超时长冲突处理、说话人配音映射、受控变速、响度与峰值、可导出多音轨或烧录字幕。其 FFmpeg 逻辑是在导入时适配播放器：选择一个音轨，关闭输出字幕，必要时 H.264/AAC 转码，再另行抽取 SRT。这与尽量保留源媒体、生成最终交付物的任务不同。[导入转换参数](https://github.com/Samuelxiaozhuofeng/LinguaClip/blob/d1bd35113d80dc1387241af7c7203179cbd97e5e/src-tauri/src/convert.rs#L275-L311)

对 GlyphCue 应借鉴原理、独立设计：可编辑源稿 → 已确认译文 → 可试听配音片段 → 时长冲突处理 → 音轨与字幕渲染。首次配音实验应明确是单一合成声音、整轨替换还是保留背景声；后者不能由 TTS 本身完成。三语六方向均应验证译文变长带来的时间预算，不把语速无限加快作为自动成功条件。

## 许可分层与商业使用

以下是工程选型边界，不是“整个方案已经获得商业法律批准”。需要分别记录代码、权重、二进制、字体/词典与外部服务；免费访问、开源徽章、按需下载均不替代许可义务。

| 层 | 当前证据 | 对 GlyphCue 的约束与建议 |
|---|---|---|
| LinguaClip 源代码 | 根 LICENSE 是 AGPL v3 正文 | 允许商业收费；复制/改编后分发受覆盖作品须保留通知、标记修改、提供对应源码并遵守 AGPL。修改版提供网络交互还涉及第 13 条。不能把其文件拷入另一许可证产品后只补一条致谢；先决定许可证兼容性或取得另行授权 |
| 架构参考 | 本报告描述模块职责与行为，不附复制实现 | 可独立实现思路；避免带入源码、提示词、UI 资产等具体表达。是否构成衍生作品取决于实际复用方式，不能用“独立进程”口号自动豁免 |
| Whisper 运行时 | whisper.cpp v1.8.4 LICENSE 为 MIT | 商业/修改/分发可行，随副本保留版权和许可；打包还需核查其实际链接依赖 |
| Whisper 权重 | OpenAI 明示代码与权重 MIT；GGML 转换仓库标 MIT | 量化文件不是 LinguaClip 的 AGPL 权重。可进入商业候选，但应保留原始及转换来源、版本、摘要和许可 |
| Silero VAD 权重 | Silero 上游 MIT；GGML VAD 模型卡标 MIT | 单独归档其声明与版权通知；本次未验证转换产物的可复现过程 |
| Symphonia | Rust manifest 引入 0.5；上游 MPL-2.0 | 可商业使用；若分发相关二进制，需要满足受覆盖源码的提供/通知要求；修改受覆盖文件需保留相应开放义务，不应称全部依赖都 MIT |
| FFmpeg 二进制 | Windows 下载 Gyan `8.0.1 essentials`；作者构建站明确常规构建 GPLv3 | 商用本身不被禁止；再分发需保留许可、提供准确对应源码/构建信息并评估组合方式。不能统称 LGPL，也不能因为首次启动下载就声称无义务 |
| 字体和其他前端资源 | 锁文件包含 OFL-1.1、MIT、Apache-2.0 等不同声明 | 若复用整体前端/包必须逐项形成 SBOM 与通知；字体、词典内容的权利不由根 AGPL 统一赋予 |
| 微软 Read Aloud | 非公开 consumer 服务，非正规 Azure Speech API | 未找到授权本程序直接调用该端点并用于商业成片/再分发音频的正式条款证据；禁止将“无 key 可用”推导为商业许可。GlyphCue 候选排除这条非公开调用路线，改查正式 TTS API 或许可明确的本地模型 |

源码许可依据：[AGPL 基本权利](https://github.com/Samuelxiaozhuofeng/LinguaClip/blob/d1bd35113d80dc1387241af7c7203179cbd97e5e/LICENSE#L142-L160)、[收费、修改版与整体作品](https://github.com/Samuelxiaozhuofeng/LinguaClip/blob/d1bd35113d80dc1387241af7c7203179cbd97e5e/LICENSE#L184-L232)、[非源码形式分发](https://github.com/Samuelxiaozhuofeng/LinguaClip/blob/d1bd35113d80dc1387241af7c7203179cbd97e5e/LICENSE#L233-L311)、[网络交互](https://github.com/Samuelxiaozhuofeng/LinguaClip/blob/d1bd35113d80dc1387241af7c7203179cbd97e5e/LICENSE#L540-L559)。AGPL 不会仅因字幕由程序输出就自动覆盖普通用户字幕，参见第 2 条。

独立组件依据：[whisper.cpp LICENSE](https://github.com/ggml-org/whisper.cpp/blob/v1.8.4/LICENSE)、[Whisper 代码和权重声明](https://github.com/openai/whisper#license)、[Whisper LICENSE](https://github.com/openai/whisper/blob/main/LICENSE)、[GGML Whisper 模型卡](https://huggingface.co/ggerganov/whisper.cpp)、[Silero LICENSE](https://github.com/snakers4/silero-vad/blob/master/LICENSE)、[GGML VAD 模型卡](https://huggingface.co/ggml-org/whisper-vad)、[Symphonia MPL](https://github.com/pdeljanov/Symphonia/blob/rel-0.5/LICENSE)、[FFmpeg 法律说明](https://ffmpeg.org/legal.html)、[Gyan 构建许可](https://www.gyan.dev/ffmpeg/builds/#about-these-builds)、[前端锁文件字体声明](https://github.com/Samuelxiaozhuofeng/LinguaClip/blob/d1bd35113d80dc1387241af7c7203179cbd97e5e/package-lock.json#L730-L746)。

附加发现：FFmpeg 下载解压后，代码仅留下 executable 并删除其余目录（包括 docs）。这不是可复用的许可材料保留策略。自建 whisper/Vulkan 打包脚本也不足以证明最终分发包具备完整第三方通知。本次未下载二进制包验证，不能判定发布包整体合规或不合规。[FFmpeg 清理](https://github.com/Samuelxiaozhuofeng/LinguaClip/blob/d1bd35113d80dc1387241af7c7203179cbd97e5e/src-tauri/src/convert.rs#L78-L102)、[Vulkan 包装](https://github.com/Samuelxiaozhuofeng/LinguaClip/blob/d1bd35113d80dc1387241af7c7203179cbd97e5e/.github/workflows/whisper-vulkan.yml#L79-L95)

### 外部服务协议与数据处理

**Groq。** 2026-06-22 服务协议允许把 API 集成到客户应用并供终端用户使用；这不同于获得模型或服务再分发权。客户还需遵守模型条款、使用政策、授权与数据通知义务，未经批准的服务转售受限。输入/输出权利在双方关系中归客户；默认不用于训练，除非客户授权。数据文档仍保留可靠性/滥用调查等例外和使用元数据，ZDR 要实际配置，不能承诺“绝不保留”。[服务协议](https://console.groq.com/docs/legal/services-agreement)、[数据说明](https://console.groq.com/docs/your-data)

**百炼中国大陆版。** 2026-09-02 协议 4.6 限制未经书面许可的服务/模型转售及竞争模型开发；6.2 对业务数据处理、训练授权、保留和跨境处理作约定。5.2.2 对特定个人订阅/Coding Plan 有输入输出用于改进的授权，不能将其与普通 ASR API 混为一谈。源代码实际使用北京端点，不能用国际站 ZDR 政策替它担保。临时上传文档确认 48 小时后清理，并明确不推荐生产使用，推荐生产改用稳定存储。[中国大陆服务协议](https://terms.alicdn.com/legal-agreement/terms/common_platform_service/20230728213935489/20230728213935489.html)、[临时上传官方规则](https://help.aliyun.com/zh/model-studio/get-temporary-file-url/)

**自定义 OpenAI 兼容服务。** 这里只能验证 HTTP 兼容方式，无法预先确定任意地址的主体、模型许可证、数据地区、保留期限、输出权利、费用、署名或是否允许商业应用。GlyphCue 可设计供应商能力描述，但每个正式内置/推荐供应商必须单独核验条款；用户自行填写 key 也不消除应用的数据流披露责任。

**署名与分发要分对象。** OSS 组件按各自许可保留版权、许可和必要 NOTICE；云服务按合同、模型政策与品牌规则处理，不能将 OSS 的 MIT/AGPL 当作云服务输出许可证。用户视频、音乐、人声和翻译内容仍有独立权利来源。普通 TTS 与声音克隆的同意/使用范围也需分开立项，LinguaClip 无声音克隆授权流程证据。

## 可进入 Product Scope 的设计输入

1. **采纳思想：** 本地 ASR 为默认；安装包/运行时/模型拆分；资源清单与 hash；字幕原文保留；可选 AI 插件边界；逐批缓存；失败保留已有结果；词级时间不可用时可回退句级编辑。
2. **重新设计：** 统一版本化 transcript/cue/translation/dub schema；稳定 cue ID；源文编辑导致译文和配音失效的依赖追踪；进程与 HTTP 真正取消；隐私与凭据；三语字幕质量约束；媒体交付策略。
3. **排除参考路线：** 非公开 Edge TTS；把所有 CPU 核心占满当作通用默认；对 CJK 完全跳过字幕重排；只校验行数就认为翻译完成；删除许可材料；把云端临时存储当作成熟生产架构。
4. **不扩展产品：** 听写评分、词典、Anki、间隔复习、播客发现和课程学习均不由此参考自动进入 GlyphCue v2。

## 后续最小实验与待决 Gate

| Gate / 实验 | 最小范围 | 必须拿到的证据 |
|---|---|---|
| ASR 后端候选比较 | 选同一批有授权的 EN/ZH/FR 短素材，比较 whisper.cpp 与 Media Downloader 既有路线；覆盖安静、配乐、静音、长句 | WER/CER、漏识别/幻觉、句界偏差、实际 backend、RTF、峰值内存/显存；不凭模型名确定赢家 |
| 三语六方向翻译 | 每方向少量连续片段，含专名、数值、代词、跨句语境与较长译文 | 语义/方向/遗漏、ID 对齐、术语一致性、CPS 与显示行数；明确人工修改后缓存失效 |
| 配音时长与输出 | 首先许可明确的单一声音；一段约 60–90 秒视频，三种目标语言 | 正式授权来源、离线/云数据流、自然度、过长片段处理、静音/冲突、成片音画同步；不是只检查音频非空 |
| 许可与打包 | 选定确切 runtime/model/FFmpeg build 之后 | 二进制配置、源码对应关系、通知文件、模型卡/许可快照、分发方式、供应商条款版本 |

本轮文档足以识别上述 Gate，无需运行条件性 prototype。当前未证明任一三语质量阈值或性能阈值已达标；未证明 LinguaClip 的发布包与本源码快照相同；未核验全部传递依赖和镜像分发权；非公开 Edge 服务的商业授权仍没有可靠证据。以上限制不影响将已验证的模块边界用于独立设计。
