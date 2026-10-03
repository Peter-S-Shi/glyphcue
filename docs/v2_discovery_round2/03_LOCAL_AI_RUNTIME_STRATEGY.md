# GlyphCue V2 Round 2：本地 AI 运行时与资源策略

核验日期：2026-10-03。状态：研究建议；未运行模型、安装依赖、调用付费 API 或验收硬件。
本文按绿地 Windows-first 产品重新选择，不要求沿用 V1/Python，也不把已有 Media Downloader 环境当默认发行包。
ASR 只允许本地；翻译、预设单旁白 TTS 本地优先，外部服务只能由用户明确启用 BYOK，失败不得静默转云端。
EN/ZH/FR 是首批质量锚点，语言能力由模型/声线清单描述，不写死为永远只有三种语言。

## 1. 建议先作出的选择

| 决策 | Round 2 建议 | 尚不能声称 |
| --- | --- | --- |
| ASR 首轮比较 | 同一个 multilingual Whisper large-v3-turbo，whisper.cpp 与 faster-whisper/CT2；资源不足再测 small | Media Downloader small 已满足三语质量；原生 C++ 必然更快 |
| ASR 质量挑战者 | Qwen3-ASR-0.6B + Qwen3-ForcedAligner-0.6B；不足再测 1.7B | 裸 ASR 已有可用词时间；上游榜单直接决定胜者 |
| 内置翻译候选 | 私有进程管理的 llama.cpp + 确切 Qwen3 4B/8B GGUF | 4-bit 参数体积就是整机最低内存 |
| 用户管理的本地翻译 | Ollama adapter 可选，要求已验证本地模型和本地模式 | localhost 就绝不转云端；可静默管理用户的全局服务 |
| 本地 TTS | Kokoro-82M v1.0 与 Qwen3-TTS-1.7B-CustomVoice 三语对照 | Apache 权重标签自动覆盖 G2P/native DLL；法国法语支持等于加拿大法语验收 |
| 对齐增强 | Whisper 路线先测原始时间与编辑成本；Qwen 路线将必要 aligner 算入基础成本 | 对齐可修复错字或把译文对齐源语音 |
| 发行数量 | 每阶段一个默认运行时，只有明显硬件/质量收益才加一个替代包 | 把所有候选都安装是成熟度保证 |

这是实验次序而非默认技术冻结。两条路线质量相近时，再以冷安装、离线完整性、取消恢复、维护负担决胜。
R1 的 ASR 源码调查仍有参考价值；其“迁移成本低”不再作为绿地默认路线的加分项。[R1-ASR]

## 2. 证据等级与需要纠正的事实

本报告区分：上游文档/代码声明、上游发布物存在、GlyphCue 实测通过。前两项均不能替代第三项。

**CTranslate2 已不能概括成仅有 NVIDIA GPU 路线。** 本次只读查询官方 `v4.8.2` release，存在 `rocm-python-wheels-Linux.zip` 和 `rocm-python-wheels-Windows.zip`。
固定源码含 `WITH_HIP`，Windows ROCm 准备脚本使用 AMD ROCm 7.2 开发 SDK，列出编译目标 gfx1030/1100/1101/1102/1150/1151/1200/1201。
同一官方硬件页面仍只列 NVIDIA；发行文件与源码比该旧页面提供更完整的边界。
CI 有 Windows ROCm wheel 构建，但普通 `test-python-wheels` 不依赖 ROCm 构建 job；因此不能从“有 zip”推导已经做过真实 Radeon Whisper 推理验收。[CT2-REL][CT2-HIP][CT2-CI][CT2-HW]

**CUDA 配置也有文档差异。** faster-whisper README 要求 CUDA 12/cuDNN 9；CT2 安装页面仍提 cuDNN 8。后续以实际固定 wheel/DLL 的依赖、官方构建脚本和冷机推理验证为准，不把两个页面拼成任意兼容组合。[FW][CT2-INSTALL]

**whisper.cpp 的 Intel SYCL Windows 文档不一致。** `README_sycl.md` 仍写 Windows ongoing，而固定树的 CMake preset 已有 Windows SYCL。可列实验路线，但不能直接列经过支持验证的产品配置。[WCPP-SYCL][WCPP-PRESET]

**Ollama 已提供 cloud 功能。** 必须区分本地服务、模型执行位置与账户云能力。官方支持 `OLLAMA_NO_CLOUD=1` 或 `disable_ollama_cloud`；GlyphCue 还需核对本地模型 digest、拒绝远端路由并做离线验证。[OLLAMA-FAQ]

## 3. ASR：模型质量和 Windows 工程成本分别评价

| 路线 | 质量/时间能力 | Windows 部署与运行成本 | 当前建议 |
| --- | --- | --- | --- |
| faster-whisper + CT2 + multilingual Whisper | 同一 Whisper 家族；段/词时间、Silero VAD；解码参数会影响质量 | Python、CT2 native 库、PyAV/FFmpeg、tokenizer/VAD；CPU 与 NVIDIA 路线有公开文档，AMD 是新增待验证路线 | 首轮必要对照；不迁入 MD venv |
| whisper.cpp + 同源 Whisper | 量化可能改变质量；词时间/DTW 必须独立测边界，不将 token 当人类词 | 原生 CLI/库、GGML、可选 GPU DLL；便于与 GUI 技术解耦；仍需媒体解码/时基规范化 | 绿地桌面发行的优先工程候选 |
| Qwen3-ASR 0.6B/1.7B + aligner | 官方明确覆盖 EN/ZH/FR；时间戳依靠单独 0.6B aligner | Transformers/PyTorch 优先；模型、processor、aligner 加重资产与启动成本；原生 Windows 成片链未实测 | 有条件质量挑战者 |

来源：[FW][WCPP][QASR]。这三项不存在本轮测得的质量排序。

Whisper 首轮固定 `openai/whisper-large-v3-turbo` 源 revision，分别可追溯转换到 CT2/GGML；不要将不同源权重、VAD、beam、线程、量化方式混成“运行时更好”。
先比较尽可能一致的浮点配置，再比较各引擎实际拟发行的 int8/Q5 配置。相同“8-bit”文字不意味着数值实现一致。
small 是硬件下限/速度参照；large-v3 是 turbo 未过质量门槛时的参照，首轮不下载全部尺寸。
Whisper 的任务设为源语言 transcribe；六方向翻译留给可编辑源文后的文本阶段。[FW][WHISPER-MODEL]

Qwen 官方 `return_time_stamps=True` 配合 `forced_aligner`；未配置时 demo 隐藏时间戳。应比较“ASR+aligner 的可编辑字幕结果”总时延与峰值，而不是只比较裸识别文本速度。
Qwen streaming 的时间能力和批次限制不同；V2 首期文件处理不需要为 streaming 引入额外运行时。
官方 vLLM GPU 部署不原生支持 Windows，WSL/社区 fork 会改变安装/运维门槛；首轮 Qwen 用 Transformers，避免将 FlashAttention 编译或 WSL 当默认前置要求。[QASR][VLLM]

### 是否需要再加一个“更强新模型”

本轮检查 `nvidia/parakeet-tdt-0.6b-v3` 与 `nvidia/canary-1b-v2`。两者官方列 25 种欧洲语言，包含 EN/FR，未包含中文；权重为 CC-BY-4.0。
它们可在未来特定语言包中比较，但无法独自覆盖当前三语锚点。为补中文再维护另一套模型/运行时会增大初版矩阵，因此不加入第一轮默认比较。[PARAKEET][CANARY]
这不是断言其 EN/FR 质量较差，也不是穷举所有 ASR。当前没有足够项目证据支持扩大到第四条默认候选链。

## 4. Windows 硬件矩阵：推理与视频编码分开

| 引擎 | CPU | NVIDIA GPU | AMD GPU | Intel GPU | 第一轮边界 |
| --- | --- | --- | --- | --- | --- |
| CT2/faster-whisper | x64 预构建，至少 SSE4.1；int8 候选 | CUDA；固定 wheel/DLL/驱动 | 官方 ROCm Windows wheel 已有；需固定 SDK/芯片/Whisper smoke | 未找到本候选官方 Windows Intel GPU 路线 | CPU + NVIDIA；AMD 有目标设备再加定向测试 |
| whisper.cpp | 原生 x64 | CUDA 或 Vulkan，分别构建/检测 | Vulkan 候选；HIP 另审 Windows 实际包 | Vulkan 候选；OpenVINO 是 encoder 卸载；SYCL 文档冲突待测 | CPU + 一条 Vulkan 包；CUDA 仅收益明确再加 |
| llama.cpp | 原生 CPU，允许部分卸载 | CUDA | Vulkan 或明确支持的 HIP 构建 | Vulkan / SYCL 按构建验证 | CPU + 已选 GPU 构建，不能继承 ASR 的成功状态 |
| Ollama | 官方 Windows 原生 | 官方 CUDA 路线 | 官方 Windows ROCm/Vulkan，按驱动清单 | 取决于当版 Vulkan/实际设备发现 | 用户管理的可选集成；不保证每台机器加速 |
| Qwen ASR/TTS Transformers | PyTorch CPU 是验证候选，不能承诺速度 | CUDA 为官方常用示例 | 框架有 ROCm 不等于该 checkpoint 的 Windows 链已验证 | PyTorch XPU 存在不等于全部算子/封装受支持 | 先 CPU 可行性与 NVIDIA；其余不作首版承诺 |
| Kokoro 官方 Python | 轻量 CPU 首测 | PyTorch CUDA 候选 | 未作 Windows AMD 成熟路线承诺 | 未作 Windows Intel 成熟路线承诺 | CPU baseline；转 ONNX 等是另一个转换/质量审计任务 |

依据：[CT2-HW][CT2-HIP][WCPP][LLAMA-BUILD][OLLAMA-WIN][OLLAMA-GPU][QASR][QTTS][KOKORO-CODE]。
“可构建”不是“当前安装包含此后端”，“模型成功加载”不是“实际 GPU 执行”。worker 必须记录真实 backend、设备、计算精度与卸载比例。
GPU 不可用时允许用户选择 CPU；保持模型/文本语义一致，不悄悄换小模型或把 ASR 发往云端。
FFmpeg 的 NVENC/AMF/QSV 是视频编码能力，不能证明 ASR/LLM/TTS 可用 CUDA/Vulkan/ROCm。能力探测与错误提示分别保存。

## 5. 本地字幕翻译：默认嵌入与外部本机服务

| 运行时 | 优点 | 成本/风险 | 建议地位 |
| --- | --- | --- | --- |
| llama.cpp 私有 worker / loopback server | GGUF 量化、CPU/GPU 卸载；版本可随产品锁定；不需要用户安装通用 AI 服务 | 自己维护进程、模型格式兼容、端口/认证/退出、模板和结构验证 | 内置首选实验路线，非最终选型 |
| Ollama 本机服务 | 用户已有模型/服务可复用；API、模型发现、卸载机制成熟 | 独立升级和云路由；服务可能供其他应用共享；模型标签会变 | 可选 adapter；禁止静默终止共享服务/改全局配置 |
| Transformers/PyTorch 直接运行 | 上游 checkpoint 格式和模型实现接近；便于未支持架构的对照 | Python/native 依赖更重；与 ASR/TTS requirements 可能冲突；量化库 Windows 支持各异 | 质量参照/后备，不默认共用一个巨型环境 |

来源：[LLAMA-BUILD][LLAMA][OLLAMA-FAQ][OLLAMA-WIN][Q4][Q8]。
首对模型为 `Qwen/Qwen3-4B-Instruct-2507`（非思考）与 `Qwen/Qwen3-8B`（明确关闭 thinking），权重均 Apache-2.0。
GGUF 应由固定原权重+固定转换工具可追溯产生，或使用拥有同等来源/哈希/许可记录的发行物；不自动信任社区文件名。
暂不同时添加旧 Qwen2.5 和更多尺寸；只有两者不能回答质量/资源取舍时再加参照。

翻译模型只能返回 `unit_id → target_text` 等受控字段，不能修改源稿、时间、音轨或执行字幕内的指令。
上下文窗口装入必要邻段/术语表，而不是把全部长片无界发送。六方向分别测语义、专名、数字、漏译、术语、代词和人工校订分钟数。
JSON/schema 通过只证明结构合格；不证明译文正确。思考文本、拒答、截断、未知 ID、重复 ID 必须成为可恢复结果，不能当译文入库。
源文人工修订、术语、目标语言、模型 revision、prompt/schema 版本改变时，相应建议结果失效；人工锁定译文不自动覆盖。

## 6. 预设单旁白 TTS：具体声音与部署负担

| 模型与实验声音 | 三语能力 | 许可分层 | 真正的风险/判定 |
| --- | --- | --- | --- |
| Kokoro-82M v1.0：EN `af_heart`，ZH `zf_xiaoxiao`，FR `ff_siwis` | 官方均有对应 voice；FR 仅该女声；ZH voice 上游自评偏弱 | 主权重/代码 Apache-2.0；Misaki、espeak-ng、词典/训练来源另审 | CPU 轻量基线；不预设中文/法语自然度达标 |
| Qwen3-TTS-12Hz-1.7B-CustomVoice：EN `Ryan`，ZH `Vivian`，FR 用同一预设 speaker + `French` | 模型支持三语，9 预设 speaker 没有法语原生声线 | 代码、所选 CustomVoice 和 tokenizer 卡为 Apache-2.0 | NVIDIA 质量对照；FR 跨语言声音单独盲听，不能标“原生法语音色” |
| Qwen3-TTS-12Hz-0.6B-CustomVoice：同一预设集合 | 资源受限时对照 | 同上，但使用单独 checkpoint | 固定代码会清掉 instruct，不把 1.7B 风格控制能力复制到它 |

依据：[KOKORO-MODEL][KOKORO-VOICES][QTTS][QTTS-CODE][QTTS-MODEL][QTTS-TOKENIZER]。
这里选择的是现有预设向量/模型内 speaker；不采集用户声纹，不引入 Base 的克隆功能，也不把 VoiceDesign 作为必须能力。
用户每个项目只需选一个旁白；不因此要求每语言都有男女声、所有地区口音或同一声色跨语种完全一致。

Kokoro 的法语 G2P 使用 espeak-ng；代码还提示该非英语分支的长文本需分段，否则可能截断。英语未知词 fallback 也可能依赖 espeak。
中文 Misaki extras 包括 jieba、pypinyin、cn2an 等；英语 extras 含 spaCy/phonemizer/espeakng-loader 等。82M 仅表示主网络，不代表只有一个小权重即可离线发音。
pipeline 按 voice 名会触发 `hf_hub_download`；发行适配器须预装/验证 voice 文件，改为受控本地加载。第三方 ONNX 包可能简化 torch 部署，但并不自动消除 G2P 依赖或改变授权。[KOKORO-PIPE][MISAKI-DEPS]

Kokoro 的 Apache 模型卡列有 CC-BY 训练来源；保留来源/NOTICE，并审计实际 voice/词典包。不能擅自推断所有生成音频都因此变为 CC-BY，也不能反向省掉分发义务。
espeak-ng GPL 的具体链接/分发方式要另作发行审计；把它放在另一个进程不是自动免责结论。[KOKORO-MODEL][ESPEAK]

Qwen TTS 须清点 checkpoint 内与附属 speech tokenizer 的实际文件，避免重复下载，也不能漏装。Processor、generation config、声线能力和 dtype 全部锁定。
官方 CUDA/FlashAttention 示例不是普通 Windows 冷安装证明；首测可验证兼容的普通 attention 路径，再判断优化包收益。[QTTS-CODE][QTTS-TOKENIZER]
任何 TTS 都输出实际 WAV/PCM 长度；自然语速/风格参数不保证指定毫秒时长。测得时长后由配音编排层处理窗口、留白、溢出与有限变速。

## 7. 最小运行包与资源治理

建议实验后最多形成以下按需包，用户不启用某阶段就不安装该阶段模型：

1. **ASR 基础包**：单一默认引擎 + 一个通过三语验收的 multilingual checkpoint + tokenizer/VAD（若使用）+ CPU 路线。
2. **ASR 加速包**：与基础包相同模型语义的已验证 GPU backend；若用第二引擎，必须证明额外维护值得。
3. **本地翻译包**：一个 llama.cpp build + 4B 或 8B 的胜出配置；Ollama adapter 不附带其整套服务。
4. **本地配音包**：一个胜出 TTS runtime + 所需三语预设声音/G2P；资源不同档只在质量/等待时间证据支持时提供。
5. **媒体包**：审计过的 FFmpeg/ffprobe/libass/字体；与推理 GPU 支持独立。

默认顺序加载 ASR→翻译→TTS，先释放模型再载下一个；持久保存项目结果不等于让模型长期驻留。
并发只在实测峰值预算允许时开启。取消请求、native 推理退出、进程回收和安全发布产物是不同状态。
跨语言、跨阶段或同名模型不能误用缓存；缓存 key 至少包含输入修订、模型哈希、参数、runtime/adapter 版本。

4B/8B 四位参数本体理论下界约 2/4 GB；1.7B 半精度参数约 3.4 GB，0.6B 约 1.2 GB。
这些只是参数算术，不是下载大小、峰值 RAM/VRAM 或最低配置；KV cache、激活、声码器/aligner、解码缓冲、GUI 和 native 库另计。
必须记录冷/热首结果延迟、整段 RTF、峰值 RAM/VRAM、CPU 占用、磁盘和完整包尺寸，不能只报告模型尺寸。

模型获取阶段可联网，处理阶段使用经验证的本地路径和失败即停策略；环境离线标志只是防线之一，仍需断网/拦截出站验证。
manifest 包含来源 repo/revision、文件 hash、转换工具、许可证/NOTICE、依赖资产、语言/声线、runtime 范围、backend/精度、发行签名。
离线导入、损坏校验、下载中断、升级回滚、磁盘不足与旧缓存删除均属于模型管理；不把下载代码散进模型推理函数。

## 8. 可选 BYOK：只用于翻译/TTS

ASR adapter 能力集合里不注册云 ASR。下面是可评估的正式服务例子，不表示本轮已经创建账户、发出文本或批准所有合同。

| 服务候选 | 具体用途/发现方式 | 内容与许可/隐私边界 |
| --- | --- | --- |
| Anthropic Direct API | LLM 翻译；Models API 查询实际账户可用 ID/能力，锁定请求时 model；按支持情况用结构化输出 | 发送选中源文、邻段、术语，不发音频；商业条款允许面向终端用户的产品，输出权利归客户且不训练客户内容，但受用途/地区限制；不等于服务转售许可或零留存 |
| Azure Speech 正式 TTS | 预设 voice；资源 endpoint 的 voices/list 查询 locale/style/采样率/状态；使用 GA voice | 仅发送目标口语稿/受控 SSML；实时预设合成文档说明不保留文本/音频内容；Long Audio/批处理有不同存储语义，不能套用实时承诺 |
| 自定义兼容接口 | 明确用户配置的翻译或 TTS adapter | HTTP 相似不等于 capability、许可、数据地区/保留、输出权利相同；未知项显示未知，不伪装为已审核供应商 |

来源：[ANTHROPIC-TERMS][ANTHROPIC-MODELS][ANTHROPIC-PRIVACY][AZURE-VOICES][AZURE-PRIVACY][AZURE-TRANSPARENCY]。
Anthropic 标准 API 留存有最多约 30 天及例外，某些 covered models 另有模型级保留要求，即使组织有 ZDR 也需核对；不能写“BYOK 永不存储”。[ANTHROPIC-COVERED]
Azure 最终商用分发/音频使用按客户实际订阅协议、Product Terms 和预设 voice 条件核对；公开技术 API 文档不是对全部再分发情形的法律许可证明。[AZURE-TERMS]

adapter 记录 `provider/entity/endpoint/region/model_or_voice/capabilities/terms_checked_at`；能力包括语言、最大输入、结构约束、样式、音频格式、异步/取消、计费单位。
首次明确选择外部处理后展示发送内容类别/目的地/费用规则；改变目的地、服务或数据类别需要重新知情选择。
模型列表可发现性不是质量证明。无 models endpoint 时只接受用户输入的明确 ID 并显示“未验证”，不任取别名代替。
密钥留在系统凭据库；项目/日志不保存 token、完整请求或完整字幕。服务端返回内容始终作为不可信数据验证。
网络失败、401、配额、429、超时、拒答分别处理；有费用的不确定提交不得盲目重新提交；取消本机等待不等于供应商任务撤销或退款。
禁止在本地失败后自动切换外部服务，禁止把外部 TTS 的“预设声音”变成传入用户原声进行克隆。

## 9. 许可结论按制品分层

| 制品 | 当前许可证据 | 工程放行状态 |
| --- | --- | --- |
| Whisper 原权重、whisper.cpp、faster-whisper、CT2 | MIT | 可商用/分发候选；保留版权/许可，核对转换与 native 依赖 |
| 所列 Qwen ASR/aligner、4B/8B、CustomVoice/tokenizer | 对应卡 Apache-2.0；代码 Apache-2.0 | 可商用/分发候选；具体卡未单列 LICENSE 文件时归档声明及标准条款，保留 NOTICE/修改说明；不泛化至所有 Qwen |
| llama.cpp / Ollama 代码 | MIT | 源码许可不覆盖任意导入模型与 Ollama 云服务合同 |
| Kokoro 主权重/代码、Misaki | Apache-2.0 | voice/G2P/native/词典逐项审计；不是整包无 copyleft 的证明 |
| espeak-ng | GPL-3.0-or-later 声明及 GPL 正文 | 商业使用可行；链接/分发义务未闭合，不直接批准捆绑 |
| CT2 CUDA/ROCm SDK、PyTorch/native wheel | 各有组件许可与可再分发规则 | 固定 DLL/wheel manifest 后审计，不直接拷 MD 环境 |
| PyAV / FFmpeg / libass / 字体 | 多个独立许可证，FFmpeg 取决于实际 build | 两套 FFmpeg 若同时存在，两套都审计；`nonfree` 构建不得假定可分发 |
| 云翻译/TTS | 服务合同、数据条款、voice/输出约束 | BYOK 不是豁免；逐供应商/地区/模型放行 |

依据：[FW][CT2-LICENSE][WCPP-LICENSE][QASR][QTTS][Q4][Q8][KOKORO-MODEL][MISAKI-LICENSE][ESPEAK][LLAMA-LICENSE][OLLAMA-LICENSE][FFMPEG-LEGAL]。
本轮没有批准任何安装包商业发布；这不会阻止用明确的候选和 Gate 进行 Design。未解决的捆绑方式由具体发行审计关闭。

## 10. 最小实验的 Round 2 增量

| 实验 | 最小比较 | 需要改变设计的证据 |
| --- | --- | --- |
| E1-R2 ASR | 同源 turbo：CT2 vs whisper.cpp；三语各 2 条 60–90 秒授权真人语音 + 静音/音乐对照；随后 20 分钟长片 | 各语错误/漏句/幻觉、可编辑段时间、实际 backend、资源/等待；small 仅不足资源时加入；Qwen 0.6B+aligner 仅质量差距值得时加入 |
| E2-R2 对齐 | Whisper 原始时间 vs 一个 aligner；Qwen 所需 aligner 计入 E1 | 同样校正任务的人工分钟数、失败词比例、起止误差；无明显编辑成本收益就不加到 Whisper 默认链 |
| E3-R2 翻译 | llama.cpp：Qwen3-4B-Instruct-2507 vs Qwen3-8B 非思考，六方向各 20 条连续 cue | 每方向人工修订成本/忠实度/术语与结构失败；同模型若 Ollama 集成，不重做模型排名，只验证配置与离线一致性 |
| E4-R2 配音 | Kokoro 三个指定 voice vs Qwen 1.7B 三语预设；每语短/中/长各数条 | 中文/法语自然度、关键数字/专名、漏读/截断、生成时长与窗口处理；失败不能靠大幅加速掩盖 |
| E5-R2 冷安装 | 选定最少包、完整 manifest，断网缺件/坏件/正常长片 | 无隐式下载、正确 backend、取消/重启、非管理员路径；先解决真正使用的后端，不扩张到所有 GPU |
| AMD 附加 smoke | 仅目标机器存在受支持 Radeon 且需要 CT2 时：官方 ROCm wheel + 同一 Whisper fixture | 完整依赖、真实 HIP 执行、音频卷积与时间戳、性能；失败保留 Vulkan/CPU 候选，不反推所有 AMD 不支持 |

阈值仍由产品硬件预算与审听/双语复核能力确定；R1 数值是建议，不自动成为发行 SLA。
文档已经能确定上述选择与不确定性。本票未触发 prototype；真实模型试验须另行按最小范围执行，不能以纸面研究结果冒充已跑通。

## 11. 来源与版本锁定

以下 GitHub HEAD 与 Hugging Face API revision 在研究日只读核对；网页 `main` 为访问快照，不是不可变依赖。未下载权重或发布资产。

| 代码库 | 本轮 revision |
| --- | --- |
| SYSTRAN/faster-whisper | `7b99be5376b41cd481dfc52e8caa00a497c3294e` |
| OpenNMT/CTranslate2 | `639afb3c4141a1146af476dd00af3102d60fcbfc`；发布资产检查 `v4.8.2` |
| ggml-org/whisper.cpp | `60c0be6ac8fa71b1a2ae2dd938a31a34a508e774` |
| QwenLM/Qwen3-ASR | `7c6daf77a2421100f5fb066495372c00129d39ff` |
| QwenLM/Qwen3-TTS | `022e286b98fbec7e1e916cb940cdf532cd9f488e` |
| ggml-org/llama.cpp | `b92761a515ea31e852e7fbc1fad5f874b46f3718` |
| hexgrad/kokoro | `dfb907a02bba8152ca444717ca5d78747ccb4bec` |
| hexgrad/misaki | `fba1236595f2d2bf21d414ba6e57d25256afada3` |
| ollama/ollama | `42e911bc3d05798cad729cb474bf62f378cb2e26` |

| 权重 repo | revision |
| --- | --- |
| openai/whisper-large-v3-turbo | `41f01f3fe87f28c78e2fbf8b568835947dd65ed9` |
| ggerganov/whisper.cpp | `5359861c739e955e79d9a303bcbc70fb988958b1`；具体 GGML 文件须另锁 hash |
| Qwen/Qwen3-ASR-0.6B | `5eb144179a02acc5e5ba31e748d22b0cf3e303b0` |
| Qwen/Qwen3-ASR-1.7B | `7278e1e70fe206f11671096ffdd38061171dd6e5` |
| Qwen/Qwen3-ForcedAligner-0.6B | `c7cbfc2048c462b0d63a45797104fc9db3ad62b7` |
| Qwen/Qwen3-4B-Instruct-2507 | `cdbee75f17c01a7cc42f958dc650907174af0554` |
| Qwen/Qwen3-8B | `b968826d9c46dd6066d109eabc6255188de91218` |
| Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice | `0c0e3051f131929182e2c023b9537f8b1c68adfe` |
| Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice | `85e237c12c027371202489a0ec509ded67b5e4b5` |
| Qwen/Qwen3-TTS-Tokenizer-12Hz | `7dd38ad4e9bad454aae9cd937d0cd577604fe229` |
| hexgrad/Kokoro-82M | `f3ff3571791e39611d31c381e3a41a3af07b4987` |

- [R1-ASR](../v2_discovery/02_MEDIA_DOWNLOADER_ASR.md)：历史实现/部署风险参考，本轮未重跑 MD。
- [FW](https://github.com/SYSTRAN/faster-whisper/blob/7b99be5376b41cd481dfc52e8caa00a497c3294e/README.md)、[CT2-INSTALL](https://opennmt.net/CTranslate2/installation.html)、[CT2-HW](https://opennmt.net/CTranslate2/hardware_support.html)。
- [CT2-REL](https://github.com/OpenNMT/CTranslate2/releases/tag/v4.8.2)、[CT2-HIP](https://github.com/OpenNMT/CTranslate2/blob/639afb3c4141a1146af476dd00af3102d60fcbfc/python/tools/prepare_build_environment_windows_rocm.sh)、[CT2-CI](https://github.com/OpenNMT/CTranslate2/blob/639afb3c4141a1146af476dd00af3102d60fcbfc/.github/workflows/ci.yml)、[CT2-LICENSE](https://github.com/OpenNMT/CTranslate2/blob/639afb3c4141a1146af476dd00af3102d60fcbfc/LICENSE)。
- [WCPP](https://github.com/ggml-org/whisper.cpp/blob/60c0be6ac8fa71b1a2ae2dd938a31a34a508e774/README.md)、[WCPP-PRESET](https://github.com/ggml-org/whisper.cpp/blob/60c0be6ac8fa71b1a2ae2dd938a31a34a508e774/CMakePresets.json)、[WCPP-SYCL](https://github.com/ggml-org/whisper.cpp/blob/60c0be6ac8fa71b1a2ae2dd938a31a34a508e774/README_sycl.md)、[WCPP-LICENSE](https://github.com/ggml-org/whisper.cpp/blob/60c0be6ac8fa71b1a2ae2dd938a31a34a508e774/LICENSE)。
- [WHISPER-MODEL](https://huggingface.co/openai/whisper-large-v3-turbo/tree/41f01f3fe87f28c78e2fbf8b568835947dd65ed9)、[QASR](https://github.com/QwenLM/Qwen3-ASR/blob/7c6daf77a2421100f5fb066495372c00129d39ff/README.md)、[VLLM](https://docs.vllm.ai/en/latest/getting_started/installation/gpu/)。
- [PARAKEET](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3)、[CANARY](https://huggingface.co/nvidia/canary-1b-v2)。
- [LLAMA](https://github.com/ggml-org/llama.cpp/tree/b92761a515ea31e852e7fbc1fad5f874b46f3718)、[LLAMA-BUILD](https://github.com/ggml-org/llama.cpp/blob/b92761a515ea31e852e7fbc1fad5f874b46f3718/docs/build.md)、[LLAMA-LICENSE](https://github.com/ggml-org/llama.cpp/blob/b92761a515ea31e852e7fbc1fad5f874b46f3718/LICENSE)。
- [OLLAMA-FAQ](https://docs.ollama.com/faq)、[OLLAMA-WIN](https://docs.ollama.com/windows)、[OLLAMA-GPU](https://docs.ollama.com/gpu)、[OLLAMA-LICENSE](https://github.com/ollama/ollama/blob/42e911bc3d05798cad729cb474bf62f378cb2e26/LICENSE)。
- [Q4](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507/tree/cdbee75f17c01a7cc42f958dc650907174af0554)、[Q8](https://huggingface.co/Qwen/Qwen3-8B/tree/b968826d9c46dd6066d109eabc6255188de91218)。
- [KOKORO-MODEL](https://huggingface.co/hexgrad/Kokoro-82M/blob/f3ff3571791e39611d31c381e3a41a3af07b4987/README.md)、[KOKORO-VOICES](https://huggingface.co/hexgrad/Kokoro-82M/blob/f3ff3571791e39611d31c381e3a41a3af07b4987/VOICES.md)、[KOKORO-CODE](https://github.com/hexgrad/kokoro/tree/dfb907a02bba8152ca444717ca5d78747ccb4bec)、[KOKORO-PIPE](https://github.com/hexgrad/kokoro/blob/dfb907a02bba8152ca444717ca5d78747ccb4bec/kokoro/pipeline.py)。
- [MISAKI-DEPS](https://github.com/hexgrad/misaki/blob/fba1236595f2d2bf21d414ba6e57d25256afada3/pyproject.toml)、[MISAKI-LICENSE](https://github.com/hexgrad/misaki/blob/fba1236595f2d2bf21d414ba6e57d25256afada3/LICENSE)、[ESPEAK](https://github.com/espeak-ng/espeak-ng/blob/master/COPYING)。
- [QTTS](https://github.com/QwenLM/Qwen3-TTS/blob/022e286b98fbec7e1e916cb940cdf532cd9f488e/README.md)、[QTTS-CODE](https://github.com/QwenLM/Qwen3-TTS/blob/022e286b98fbec7e1e916cb940cdf532cd9f488e/qwen_tts/inference/qwen3_tts_model.py)、[QTTS-MODEL](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice/tree/0c0e3051f131929182e2c023b9537f8b1c68adfe)、[QTTS-TOKENIZER](https://huggingface.co/Qwen/Qwen3-TTS-Tokenizer-12Hz/tree/7dd38ad4e9bad454aae9cd937d0cd577604fe229)。
- [ANTHROPIC-TERMS](https://www.anthropic.com/legal/commercial-terms)、[ANTHROPIC-MODELS](https://platform.claude.com/docs/en/api/models/list)、[ANTHROPIC-PRIVACY](https://privacy.anthropic.com/en/articles/7996866-how-long-do-you-store-my-organization-s-data)、[ANTHROPIC-COVERED](https://privacy.claude.com/en/articles/15425996-data-retention-practices-for-covered-models)。
- [AZURE-VOICES](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/rest-text-to-speech)、[AZURE-PRIVACY](https://learn.microsoft.com/en-us/azure/foundry/responsible-ai/speech-service/text-to-speech/data-privacy-security)、[AZURE-TRANSPARENCY](https://learn.microsoft.com/en-us/azure/foundry/responsible-ai/speech-service/text-to-speech/transparency-note)、[AZURE-TERMS](https://www.microsoft.com/licensing/terms/productoffering/MicrosoftAzure/all)。
- [FFMPEG-LEGAL](https://ffmpeg.org/legal.html)；本轮只给分层要求，具体媒体包审计由成片专题补充。
