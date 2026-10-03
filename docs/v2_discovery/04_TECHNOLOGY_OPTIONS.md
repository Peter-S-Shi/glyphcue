# GlyphCue V2 — 技术候选、许可边界与最小验证

状态：Discovery 研究输入；不是实现方案或已通过的性能承诺。核验日期：2026-10-03。

首批语言：英语 EN、普通话中文 ZH、法语 FR；翻译覆盖 EN→ZH、ZH→EN、EN→FR、FR→EN、ZH→FR、FR→ZH。三种语言列入模型支持列表，只能证明值得测试，不能证明字幕质量、口音、术语或配音自然度已经达标。

## 1. 建议先保留的技术选择

| 环节 | 第一轮候选 | 暂不锁定的原因 |
| --- | --- | --- |
| 本地 ASR | faster-whisper + CTranslate2；Whisper multilingual small / large-v3-turbo / large-v3 | 可与现有 Python 技术路线接合，但 Windows CPU 与 NVIDIA 实际速度、中文/法语质量要按同一素材比较 |
| AMD / Intel GPU ASR | whisper.cpp + Vulkan；Intel 可另测 OpenVINO | 官方存在跨厂商后端，但这不等于已验证所有 Windows GPU、驱动和模型组合 |
| ASR 挑战者 | Qwen3-ASR-0.6B / 1.7B + Qwen3-ForcedAligner-0.6B | 2026 年已有正式开源代码/权重和三语支持；Windows 打包、资源、时间戳链更复杂，不能仅按排行榜取代 Whisper |
| 本地字幕翻译 | llama.cpp + Qwen3-4B-Instruct-2507；对照 Qwen2.5-7B-Instruct 或 Qwen3-8B 非思考模式 | 许可清楚、规模可控；六方向的忠实性/术语/字幕长度尚未评测；不宣称是最新或最强模型 |
| 高优先级可选配音 | Kokoro-82M v1.0 轻量基线；Qwen3-TTS-12Hz-1.7B-CustomVoice 质量/韵律候选 | 前者法语声音少、短句限制；后者 Windows/资源和法语声线需验证。配音是 V2 正式研究范围，不因为可选就自动延期 |
| 时间精修 | 先用 ASR 时间戳 + 人工编辑；按误差追加 WhisperX 或 Qwen3 ForcedAligner | ASR 文本质量、强制对齐和说话人区分是三个独立问题 |
| 成片 | FFmpeg + libass；具体可分发二进制待审计 | 过滤器、编码器、字体和编译选项决定功能及许可证，不能只检查“FFmpeg”项目名 |

这些是优先比较的候选，不是批准同时集成所有运行时。第一版应选择满足目标机器和语言门槛的最少组合。后文事实由一手来源支持；标为“建议”“估算”“拟议门槛”的内容是本次研究判断。

## 2. ASR：模型、运行时和硬件分开决定

### 2.1 Whisper 模型

OpenAI 明确 Whisper 代码和模型权重为 MIT；`large-v3-turbo` 是 large-v3 的加速转录版本。turbo 不支持可靠的 Whisper 内置“转成英语”任务；V2 应先保留源语言转录，再独立翻译，避免丢失可校对原文。英文专用 `.en` 不适合作三语默认。[Whisper 官方说明](https://github.com/openai/whisper)、[turbo 模型卡](https://huggingface.co/openai/whisper-large-v3-turbo)。

第一轮仅比较 multilingual small（低资源）、turbo（速度）和 large-v3（质量参照），无需下载全部尺寸。英语、法语用 WER；中文用 CER；另外独立看专名/数字、漏句、静音幻觉、混语、长音频漂移。供应商跨数据集成绩不能直接回答用户视频的质量。

### 2.2 faster-whisper / CTranslate2

faster-whisper 为 MIT，CTranslate2 也为 MIT；支持 CPU int8、NVIDIA CUDA、词时间戳、Silero VAD、批处理。按模型名加载会自动访问 Hugging Face，亦可从本地目录加载；PyAV 解码所含 FFmpeg 库仍要独立盘点。[faster-whisper](https://github.com/SYSTRAN/faster-whisper)、[CTranslate2 LICENSE](https://github.com/OpenNMT/CTranslate2/blob/master/LICENSE)。

当前 faster-whisper 文档列 CUDA 12 + cuDNN 9；CTranslate2 预构建 GPU 路线列 NVIDIA，CPU 列 x86-64/ARM64，并区分 Intel MKL 与其他 x86 的 oneDNN。**AMD CPU 支持不代表 AMD GPU 支持；V1 的 DirectML OCR 能力也不能自动转移到这个 ASR 后端。** Windows GPU 包必须固定 Python、CT2、CUDA/cuDNN、驱动兼容矩阵，不能用一次安装成功替代运行证据。[依赖要求](https://github.com/SYSTRAN/faster-whisper#requirements)、[CT2 硬件支持](https://opennmt.net/CTranslate2/hardware_support.html)。

### 2.3 whisper.cpp

MIT C/C++ 路线有 CPU、CUDA、Vulkan 和 OpenVINO 等后端。Vulkan 是 AMD/Intel GPU 的有价值候选；驱动支持、量化模型与 Windows 二进制必须实机验证。原生可执行文件有利于减少 Python 部署面，但不代表取消模型、音频预处理、取消/进度协议和许可证工作。其词级时间戳和部分说话人分段在官方 README 仍标为 experimental，不能直接承诺专业对齐精度。[whisper.cpp 官方 README](https://github.com/ggml-org/whisper.cpp)。

### 2.4 2026 挑战者：Qwen3-ASR

官方代码与具体 ASR 模型卡为 Apache-2.0；0.6B、1.7B 模型明确包含英语、中文、法语，独立 ForcedAligner 也包含三语。返回时间戳需加载 aligner；模型本身的文字结果不能当成已有时间字幕。官方提供 Transformers 和 vLLM 路线，本地目录加载可用。[官方仓库](https://github.com/QwenLM/Qwen3-ASR)、[1.7B 模型卡](https://huggingface.co/Qwen/Qwen3-ASR-1.7B)、[ForcedAligner 模型卡](https://huggingface.co/Qwen/Qwen3-ForcedAligner-0.6B)。

ForcedAligner 官方说明单次音频范围为最长约 5 分钟，长视频需要分块、偏移回写及边界测试。当前官方部署示例倾向 CUDA；vLLM 官方明确不原生支持 Windows，WSL/社区 fork 是额外运维选择。建议先按 Transformers 可行性评估，不把 vLLM/WSL 列入普通 Windows 用户的默认安装前提。[ASR 使用说明](https://github.com/QwenLM/Qwen3-ASR)、[vLLM 安装要求](https://docs.vllm.ai/en/latest/getting_started/installation/gpu/)。

### 2.5 资源数字应如何使用

| 数字 | 性质与适用边界 |
| --- | --- |
| OpenAI 参考实现 large 约 10 GB、turbo 约 6 GB VRAM | 上游近似表，非 CT2 / whisper.cpp 的最低要求，非 GlyphCue 实测 |
| faster-whisper 上游 large-v2 int8 约 2926 MB VRAM；batch=8 约 4500 MB | 上游 RTX 3070 Ti / CUDA 12.4 固定测试，不能外推 large-v3/turbo 或本机表现 |
| whisper.cpp small 磁盘 466 MiB / 内存约 852 MB；large 2.9 GiB / 约 3.9 GB | 上游模型参考表，不包含全部 GUI/解码/缓存/不同 GPU 后端成本 |
| 4B / 8B LLM 四位权重理论约 2 / 4 GB | 仅参数位数算术估算；GGUF 元数据、未量化层、KV cache、上下文和运行时会增加实际占用，不能写成最低配置 |
| Qwen 0.6B / 1.7B FP16 权重理论约 1.2 / 3.4 GB | 仅权重下界估算；ASR 的 aligner、TTS tokenizer、激活和依赖未计入；不构成 TTS 整包大小承诺 |

前三行来自 [Whisper](https://github.com/openai/whisper)、[faster-whisper benchmark](https://github.com/SYSTRAN/faster-whisper#benchmark)、[whisper.cpp memory](https://github.com/ggml-org/whisper.cpp#memory-usage)。建议顺序装载 ASR→LLM→TTS，释放前阶段模型；不要因单个模型能运行就假设三者可同时驻留显存。

## 3. 时间戳、可编辑字幕与对齐

建议保存 `source_text`、`start/end`、稳定 cue ID、人工修改状态、原始 ASR 结果与模型 provenance；词/字级时间戳是可选细节。分句、合并/拆分、可读时长、双语行布局均由字幕层处理，不能把 ASR segment 原样视作成片字幕。

- **ASR 时间戳**：模型推断某段/词出现的位置；可作为首次草稿，但修改文本后需要标记其词对齐失效。
- **强制对齐**：把给定文字与同语言实际语音匹配；可精修源字幕或对生成配音重新打点。它不能把中文译文直接对齐英语原声，也不能修复转录中本来不存在的内容。
- **说话人区分**：判断谁在何时说话；不等于识别真实身份，也不保证重叠语音准确。首版可支持人工 speaker 标签，不强迫每个用户加载 diarization 模型。

WhisperX 代码当前 BSD-2-Clause，使用语言相关对齐模型，数字/货币等字典外文字可能没有时间，重叠语音与 diarization 均有已知限制；当前 diarization 需接受 pyannote 模型条件并使用 Hugging Face 读取令牌。英语/法语有预设 alignment 路线；中文须核对具体模型、权重许可证、数字归一化和字符映射，不能继承 WhisperX 代码许可证。[WhisperX 官方限制与安装](https://github.com/m-bain/whisperX)。

建议先检测真实字幕误差是否超过门槛，再决定是整体引入 WhisperX、仅使用 aligner，还是沿用 ASR 时间戳加编辑器；避免仅为“词级时间戳”增加一整套 diarization 登录与下载成本。

## 4. 字幕翻译：LLM 是可替换生成器

### 4.1 本地候选与许可

| 具体模型 | 用途 | 权重许可与事实 |
| --- | --- | --- |
| Qwen3-4B-Instruct-2507 | 较小的第一候选 | Apache-2.0；纯非思考模式；模型卡的综合多语成绩不是六方向字幕翻译验收。[模型卡](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507) |
| Qwen2.5-7B-Instruct | 较成熟的对照基线 | 此确切 checkpoint 为 Apache-2.0；不要将这个结论推广到 Qwen2.5 所有尺寸/变体。[模型卡](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct) |
| Qwen3-8B | 若 4B 质量不够，作为更大对照 | Apache-2.0；官方有 `enable_thinking=False`，适合减少翻译步骤的推理文本与额外延迟。[模型卡](https://huggingface.co/Qwen/Qwen3-8B) |

llama.cpp 为 MIT，有 CPU、CUDA、Vulkan、SYCL、混合卸载、量化及服务器接口。推荐比较固定版本 GGUF 本地 worker，或者用户已安装的本地服务；不能把“兼容聊天接口”当成输出符合字幕协议。[llama.cpp 官方说明](https://github.com/ggml-org/llama.cpp)。

### 4.2 建议的产品约束

翻译请求以稳定 cue ID、源文、目标语言、术语表和有限前后文组成；返回译文而非让模型重写 SRT 时间戳。校验 ID 完整性、目标语言、空行、异常长度、数字和术语；失败允许仅重试对应块。保留源文和人工译文锁定状态，支持只重翻选中 cue。段落语境有助于代词/术语，但最终拆行必须回到字幕可读性规则。

字幕译文与配音稿应分开保存：字幕可以更接近原文，配音稿可为时间窗口调整表达；改写必须可审阅，不能偷偷删去信息以“配准”。六个翻译方向各有独立验收结果；ZH↔FR 不应因 EN↔ZH 表现好而免测。

### 4.3 云端适配器

保留用户明确启用的外部翻译/TTS adapter 选择，允许本地不满足质量或硬件要求时采用合法服务。协议兼容与 BYOK 不能证明可商用、可转售、可缓存或不训练；选择具体 provider / region / model 后必须核对输入留存、训练政策、DPA/跨境要求、输出使用权、语音政策、费用与重试限制。本次不绑定 provider，也未批准任何外部发送。

建议默认本地；首次启用云端显示实际发送内容和目的地。翻译通常只需指定文本与上下文，不需原媒体；配音若使用预设音色只发送目标文本；声纹参考音频的上传须是另一个明确动作。日志不记录密钥/完整字幕，凭据不写入可分享项目文件。

## 5. 高优先级可选 TTS / 配音

### 5.1 三语 shortlist

| 候选 | EN / ZH / FR | 适合的位置 | 明确限制 |
| --- | --- | --- | --- |
| Kokoro-82M v1.0 | 英语多音色 / 普通话 8 音色 / 法语 1 女声 | 轻量预设音色基线 | 官方提醒非英语覆盖薄、短句和很长文本可能变差；法语只列 `ff_siwis`，不能承诺男声或均衡口音质量 |
| Qwen3-TTS-12Hz-1.7B-CustomVoice | 三语均列出 | 更丰富韵律、表达控制候选 | 预设音色原生语言无 FR；法语自然度、数字读法及资源需实测；支持风格指令不等于精确时长控制 |
| Qwen3-TTS-12Hz-0.6B-CustomVoice | 三语均列出 | 较小规模速度对照 | 当前代码主动移除 0.6B 的 instruct；不能从模型卡的风格宣称得出同等韵律控制能力 |
| Piper 当前维护版 | 有 EN/ZH/FR voice 列表 | 仅在许可/声音审计通过后作为备选 | 当前引擎 GPL-3.0；每音色单独审计，现有华研中文示例数据许可 Unknown，不作为可商用默认 |

语言及质量边界见 [Kokoro VOICES](https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md)、[Qwen3-TTS 官方矩阵](https://github.com/QwenLM/Qwen3-TTS)、[Piper VOICES](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/VOICES.md)。Qwen 0.6B 模型卡与主仓矩阵存在差异；核对代码后以实际限制为准：[固定提交的 `generate_custom_voice`](https://github.com/QwenLM/Qwen3-TTS/blob/022e286b98fbec7e1e916cb940cdf532cd9f488e/qwen_tts/inference/qwen3_tts_model.py)。

Kokoro 代码和权重是 Apache-2.0，但 G2P 路径使用 Misaki，法语依赖 espeak-ng；espeak-ng 是 GPL，打包/链接方式必须审计。模型卡列出 CC BY 训练来源，应保留相应来源/署名说明并核对实际音色包，不能把 Apache 标签等同于所有组件均 Apache。[Kokoro 仓库](https://github.com/hexgrad/kokoro)、[模型卡](https://huggingface.co/hexgrad/Kokoro-82M)、[espeak-ng COPYING](https://github.com/espeak-ng/espeak-ng/blob/master/COPYING)。

Qwen3-TTS 代码和这里选定的 CustomVoice 模型卡均为 Apache-2.0；tokenizer 是另一个下载制品，部署时应一并固定 revision、清单和许可证。官方示例以 PyTorch/CUDA 为主，尚未以本次 Windows 冷安装验证；不要把 Linux vLLM 性能数字当成 Windows 桌面承诺。[Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS)、[1.7B CustomVoice](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice)、[0.6B CustomVoice](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice)。

### 5.2 不作为默认商业捆绑的候选

- Piper 旧 `rhasspy/piper` 历史代码是 MIT，但开发已迁移至 `OHF-Voice/piper1-gpl`；当前代码为 GPL-3.0。GPL 允许商业活动，但分发需承担相应义务；子进程调用本身不能作为豁免的法律结论。[旧仓](https://github.com/rhasspy/piper)、[维护仓](https://github.com/OHF-Voice/piper1-gpl)。
- Piper voice 仓根级 MIT 不能覆盖每个训练来源。`fr_FR-siwis-medium` 卡列 CC-BY 4.0 并记载从 lessac 微调；`zh_CN-huayan-medium` 卡列数据许可 Unknown。应追溯基础音色与训练数据而非只看下载页标签。[SIWIS 卡](https://huggingface.co/rhasspy/piper-voices/blob/main/fr/fr_FR/siwis/medium/MODEL_CARD)、[Huayan 卡](https://huggingface.co/rhasspy/piper-voices/blob/main/zh/zh_CN/huayan/medium/MODEL_CARD)、[lessac 卡](https://huggingface.co/rhasspy/piper-voices/blob/main/en/en_US/lessac/medium/MODEL_CARD)。
- F5-TTS 源码 MIT，但官方预训练权重为 CC-BY-NC。没有另获许可时，不选择它承载商业默认路线。[官方 License 段](https://github.com/SWivid/F5-TTS#license)。
- XTTS-v2 权重使用 CPML 1.0.0，明确限制模型和输出的非商业使用；源代码开源许可不能解除该条件。[具体 LICENSE.txt](https://huggingface.co/coqui/XTTS-v2/blob/main/LICENSE.txt)。

许可是候选筛选边界，不是法律意见。可商业使用、可再分发二进制/权重、输出权利、训练来源和说话者声音权利应分别记录。预设普通音色可先实现配音目标；声音克隆、声纹迁移、口型同步无需成为配音的先决条件。

### 5.3 “生成声音”与“完成配音”的距离

建议最小配音闭环包括：选择目标语言/预设音色→审阅配音稿→逐句生成→试听/重做单句→检查时长→组装完整目标音轨→选择原音处理→导出。还需明确重做某句后哪些下游文件失效。

建议保留每句实际时长和目标窗口。过长先标记、编辑措辞或重新合成，必要时有限变速；超界保持人工处理，不截掉尾句，不无限压缩。初试可用 0.85–1.15 倍速作为待验证上限，而非现成行业标准。短句补静音，时间轴按源媒体绝对时间放置，避免逐句累计漂移。

原音处理至少区分：替换全部原音、压低原音、保留独立原音轨。原素材若对话和音乐已经混在一轨，“保留音乐并干净删除说话”需要声源分离；不是 FFmpeg 音量混合即可完成，应作为单独质量门槛。首轮优先单主讲人/人工角色映射，不承诺多说话人自动复刻或原情绪重建。

## 6. FFmpeg / libass 成片与分发

FFmpeg `subtitles` 过滤器用 libass，需 `--enable-libass`；支持字体目录、样式覆盖等。`ass` 过滤器专门处理 ASS；双语布局建议生成受控 ASS 样式。Unicode 换行还取决于 libass/libunibreak 版本。libass 自身为 ISC，不能据此推导整个 FFmpeg 为同一许可证。[过滤器文档](https://ffmpeg.org/ffmpeg-filters.html#subtitles)、[libass COPYING](https://github.com/libass/libass/blob/master/COPYING)。

建议导出明确区分：SRT/VTT/ASS 文件、可选择字幕轨的封装、已烧录画面的媒体、目标配音音轨或配音媒体。烧录改变图像，需要视频重编码；只加兼容字幕轨通常可保留视频流，但具体容器/字幕编码仍需验证。烧录不是 OCR：前者是输出渲染步骤，与 V2 放弃输入 OCR 不冲突。[FFmpeg 转码与流复制说明](https://ffmpeg.org/ffmpeg.html#Streamcopy)。

FFmpeg 可提供定时放置、混音、响度和节奏处理；可使用 `adelay`、`amix`、`loudnorm`、`atempo` 等，但这些操作不提供语义分句或保证配音自然度。[FFmpeg audio filters](https://ffmpeg.org/ffmpeg-filters.html)。

**Binary Gate：** 按最终要分发的每个 FFmpeg/PyAV 二进制记录来源、SHA256、`-version`、`-buildconf`、`-L`、外部库和对应源代码。FFmpeg 默认 LGPL-2.1-or-later，启用 GPL 组件会改变整体许可证；例如 libx264 需要另看。`--enable-nonfree` 可能得到不可再分发构建。独立 EXE 与链接库的合规分析不同，但均不能省略许可证/源代码义务。[官方法律说明](https://ffmpeg.org/legal.html)、[FFmpeg LICENSE](https://ffmpeg.org/doxygen/trunk/md_LICENSE.html)。

编解码器专利、实际分发地区/商业模式、NVIDIA 等运行库的可再分发组件、字体授权需随最终包另审。硬件编码 NVENC/QSV/AMF 只列能力候选，检测实际 encoder/driver 后展示；保留经验证的软件编码回退。字体必须有再分发授权和中法英字形覆盖；不能默认打包操作系统字体。

## 7. 模型交付与隐私架构建议

建议安装程序、可选运行时和模型包分开管理。用户触发下载前展示用途、体积、来源、许可证、硬件要求；下载完成按 manifest 哈希验证、原子切换，可取消/续传/清理失败缓存。每包记录上游 repo、immutable revision、转换过程、文件散列、许可证和语言/后端能力；量化版也保留原始模型溯源。

推理阶段只从已验证本地目录加载。支持用户导入离线模型包；明确缺失 tokenizer、VAD 或 aligner 时的提示，避免“已下载主模型”后隐式联网。Hugging Face 官方接口可固定 revision，并支持缓存/本地目录工作流，能作为受控下载的基础，不应任由各推理库自行决定联网。[Hub 下载指南](https://huggingface.co/docs/huggingface_hub/guides/download)。

建议 worker 报告实际 backend、device、compute type 与模型版本；后端不可用时明确提示/允许 CPU 回退，不能只在配置界面显示 GPU。缓存与模型共享按 manifest 验证，不能直接把其他产品缓存目录视为安装接口。任务取消、失败重试和逐阶段恢复应依赖已有中间成果，避免更换译文后重跑 ASR。

“本地”验收应在断网下完成转录、编辑、本地翻译/TTS 和导出；模型初次下载是单独网络阶段。连接到 localhost 的服务也要核对其实际路由与日志配置，不能仅凭 URL 判断其不会转发云端。

## 8. 后续最小验证实验（本次未运行）

这些是拟议筛选门槛，需产品确认后成为验收标准。本轮只做文档/代码研究，未下载模型、安装依赖、调用 AI 服务、使用用户视频或创建实现原型。

| 实验 | 最小材料和比较 | 记录与拟议 pass/fail |
| --- | --- | --- |
| E1 三语 ASR 与打包 | 三语各 3 段约 1 分钟的获授权人工标注材料：干净、噪声/音乐、专名/混语；加 1 条约 20 分钟长片。先测 CT2 small/turbo 与 whisper.cpp 对应模型；仅不足时加 large-v3 或 Qwen | 同 beam/线程/量化条件；记录 WER/CER、漏句、静音幻觉、RTF、RAM/VRAM、backend。初筛：干净语音 EN/FR WER≤10%、ZH CER≤10%；困难场景逐类记录，不能平均掩盖失败；无整段丢失/凭空生成整句；30 个标注 cue 起止误差 P95≤500 ms。速度门槛由目标机器/可接受等待决定，不预先伪造 |
| E2 对齐增益 | 仅 E1 时间戳不达标时，选每语 10 个含数字/货币/专名 cue；ASR 原时间 vs WhisperX vs Qwen aligner，先任选一个挑战者 | 记录边界误差、无时间词率、额外下载/峰值内存；拟议 P95≤300 ms、全部 cue 可导出；没有覆盖的词必须保留可编辑状态，不能悄悄丢弃。若未显著降低人工修时成本，不纳入默认链 |
| E3 六方向字幕翻译 | 每方向 20 条连贯 cue，含术语、数字、代词、断句；先比较一个 4B 和一个 7B/8B，不同时评测大量模型 | 100% cue ID/原时间保留；无整句漏译、无新增事实；术语表约束≥95%；每方向双语人工评分语义中位数≥4/5。记录人工修改率、延迟、资源；不让综合分掩盖 ZH↔FR 失败 |
| E4 三语配音 | 每语 10 条短/中/长字幕，含专名、数字、问句；Kokoro vs Qwen 1.7B 预设声线；0.6B 只在资源必要时加测 | 每语人工自然度/清晰度中位数≥4/5；无漏读、数字关键错误、剪尾；记录句时长和术语读法。拟议至少 90% 句子在重做/少量编辑及 0.85–1.15 倍速内适配窗口，其余全部显式标记；不降低整条视频速度来掩盖问题 |
| E5 成片与离线交付 | 同一段约 2 分钟三语合成素材，横/竖版、Unicode 文件名、双语字幕；每种计划容器做软字幕/烧录/配音导出；冷机器安装与断网复跑 | 首尾无新增累计 A/V 漂移（拟议≤100 ms）；无裁切/缺字/重叠字幕；导出长度正确，保留选定音轨；失败不覆盖源文件。精确包许可证/来源/哈希齐全，断网无隐式模型请求 |

合成素材可用于格式/时序/隐私测试，但 ASR 和 TTS 自然度筛选仍应加入获授权真人语音，避免只在另一模型生成声音上评价“真实场景”。小样本只能筛选候选，不能作为发布级三语质量证明。

## 9. 尚未关闭的 Product / Architecture Gates

1. 最低硬件与等待时间：CPU 必须完成哪些操作？是否承诺 AMD/Intel GPU 加速？是否允许选装较大运行时？
2. 首批口音和文字：ZH 是普通话，简/繁输出如何处理；FR 是法国法语还是也覆盖加拿大法语；语言能力不能从 UI 翻译推导。
3. 翻译默认策略：完整本地、用户配置本地服务、明确云端 opt-in 如何排序；六方向最低质量由谁人工验收。
4. 配音定位：自然预设声音、单/多角色映射、是否必须保留背景音乐；是否允许声音克隆（建议另立后续 Gate）。
5. 时长策略：固定原视频时长下允许多少文本改写、句间借时与变速；冲突由用户编辑还是允许自动重排。
6. 商业与分发：应用许可证/收费方式、捆绑或下载的模型/runtime、GPL 组件接受度、最终 FFmpeg build、字体和音色许可。
7. 时间精度：普通字幕编辑足够还是必须每词高亮/精确口播同步；不要在答案未知时默认引入重型 alignment+diarization。

## 10. 证据版本记录

公开仓库 HEAD 在 2026-10-03 通过 GitHub API 读取；这是本次证据快照，不代表选择这些未发布提交为产品依赖。模型卡与在线文档读取于同日；正式选型需再锁定具体权重 revision 与二进制哈希。

| 仓库 | 读取的 HEAD |
| --- | --- |
| SYSTRAN/faster-whisper | `7b99be5376b41cd481dfc52e8caa00a497c3294e` |
| OpenNMT/CTranslate2 | `639afb3c4141a1146af476dd00af3102d60fcbfc` |
| openai/whisper | `86098128c0b4f24f0e2aa2994de830614b474227` |
| ggml-org/whisper.cpp | `60c0be6ac8fa71b1a2ae2dd938a31a34a508e774` |
| m-bain/whisperX | `771b4a14a9486f8fd5aef18ef49e35d639523dd3` |
| QwenLM/Qwen3-ASR | `7c6daf77a2421100f5fb066495372c00129d39ff` |
| ggml-org/llama.cpp | `99b95488cac0f00ce3f05af113a8c1e287753f87` |
| hexgrad/kokoro | `dfb907a02bba8152ca444717ca5d78747ccb4bec` |
| QwenLM/Qwen3-TTS | `022e286b98fbec7e1e916cb940cdf532cd9f488e` |
| OHF-Voice/piper1-gpl | `efffbfb226bfb511ebbcf55d0cecd8b35a89743d` |
| SWivid/F5-TTS | `283252563dbf91be625e0c27926acfaac449186c` |
| espeak-ng/espeak-ng | `ba90c8e9f440ad544f674a790bb5f53878b6ffc5` |

没有将上游的速度、参数规模、模型榜单或许可证标识写成 GlyphCue 已实测、已批准商业发布或已满足功能验收。具体 Media Downloader 复用结论和 LinguaClip 审计由同目录对应研究文档提供。
