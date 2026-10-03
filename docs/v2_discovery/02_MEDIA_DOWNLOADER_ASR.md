# Media Downloader 本地 ASR 复用调查

研究日期及上游访问日期：2026-10-03。状态：Discovery 证据；不是实现、性能验收或分发许可批准。V2 的首批语言按产品确认采用英语、中文、法语（EN/ZH/FR）；六个翻译方向由独立翻译步骤实现。

## 结论

Media Downloader 已有可用的本地文件转字幕路径：**本地媒体 → 独立 Python 进程 → faster-whisper/CTranslate2 → 原语言、分段时间戳 → SRT/VTT**。可复用的是技术路线、任务校验、进程协议、路径安全经验与测试思路；不应直接复制整个运行环境、下载器 UI 或其队列领域模型。

该路径适合作为 GlyphCue V2 的 ASR 基准候选。现有实现没有可编辑逐字稿工程、翻译、配音、说话人管理、持久分段恢复或最终视频制作；base/small 也没有足够证据作为 V2 最终质量配置。V2 将 ASR 作为主输入，旧的“ASR 辅助 OCR”定位不适用于本次范围。

当前安装的 PyAV/FFmpeg 二进制存在许可元信息与构建标志不一致的问题，**不能直接打包复用这个环境**。本地代码没有发现完整可复现的运行时安装/下载脚本或锁定清单。不能把机器上运行成功等同于可移植、离线保证或可分发。[L1–L8][U1–U8]

## 1. 证据边界与快照

下文 `MD:` 均指 Media Downloader 项目根目录下的相对路径；`FW:` 指已安装 faster-whisper 1.2.1 包内的相对路径。该文件夹目前不是 Git 仓库，不能给出可信提交 SHA。本次仅检查源码、测试、产品文档、包元数据、模型下载元数据及 PyAV 库自报构建信息；没有读取私有音视频、转录内容、个人日志、账户配置或提示词草稿，没有下载模型、运行 ASR、安装依赖或修改 MD。

| 检查文件 | SHA-256 |
| --- | --- |
| `MD:local_asr.py` | `a9ffbd35ccdfa91411892b624a666e0ad573dbde3f59c866cdd5a39730d09764` |
| `MD:local_asr_worker.py` | `e86fea17abe7ad54f5cfa39ddeabcf8e3bef6c99dfd3db535af5d27a56fe3fd3` |
| `MD:app.py` | `b1ad631334ef27f7615fe4fb6a22197a13d35328b04df4663e7d9dd08047a4d6` |
| `MD:queue_store.py` | `0d166808e5c5483f4a9d9ada75c7d7d66753b635899d7aeae e1e8a2e50467012`（校正见下） |
| `MD:path_support.py` | `a50eec018747ca8a79e500d108366ba38754980fe87077dc4b82dbe5f98938ba` |

`queue_store.py` 的无空格 SHA-256 为 `0d166808e5c5483f4a9d9ada75c7d7d66753b635899d7aeaee1e8a2e50467012`。模型 revision 为下载元数据记录，并非本次重新计算模型大文件哈希。

## 2. 实际生产路径

1. **主 UI 和任务准备。** `MD:app.py:3566–3881` 提供本地文件/文件夹/批量导入、模型、声音语言、SRT/VTT，以及指定片段；`app.py:5202` 附近检查本地组件。主 UI 在 `3611–3614`，批量 UI 在 `3690` 附近均包含 `auto/zh/en/fr`。旧 `local_asr_ui.py:126` 独立窗口只映射自动/中文/英文；它不代表当前主流程的全部语言能力。
2. **任务边界。** `MD:local_asr.py:136–168` 校验源文件、输出目录、模型、语言、格式和片段；处理同名输出和 Windows 路径长度。`path_support.py:8–32` 在文件系统边界转为 Windows 扩展路径。默认整文件转录；选段必须在时长内、互不重叠。
3. **预检时长。** `local_asr.py:77–90` 调用已有 `ffprobe`。生产 ASR 没有先用外部 FFmpeg 导出 WAV；它直接把媒体文件交给 faster-whisper。独立验证脚本才用 FFmpeg 提取单声道、16 kHz PCM 片段。[L1][L4]
4. **隔离执行。** `local_asr.py:171–194` 固定查找 `tools/asr-runtime/venv/Scripts/python.exe`、`models/{base,small}`，通过参数传模型目录、输入、输出、语言、选段和控制开关。`app.py:5583–5598` 以隐藏子进程、UTF-8 stdout/stdin 管道启动；stderr 被丢弃。[L1][L3]
5. **推理。** `local_asr_worker.py:81–107` 明确使用 `WhisperModel(local_directory, device="cpu", compute_type="int8", cpu_threads=2, num_workers=1)`；Windows 进程优先级降低。参数为 `beam_size=5`、`vad_filter=False`、`condition_on_previous_text=False`、`word_timestamps=True`。调用默认原语言 transcribe，不调用语音翻译。
6. **解码。** 已安装 `FW:audio.py:19–66` 使用 PyAV/FFmpeg 库，重采样到 16 kHz，默认单声道，解码第一个音轨。当前产品没有显式音轨选择，也不适合把有多语言音轨的视频默认为正确轨道。[U1]
7. **输出。** worker 接受分段起止和文本，逐段发 JSON 事件，全部结束后生成 UTF-8 SRT/VTT。`word_timestamps=True` 的词级结果未进入协议或输出：`local_asr_worker.py:120–129` 只保留 `start/end/text`。生产路径没有 JSON transcript 工程文件；验证脚本里的 JSON 是评测结果，不能视为产品工程格式。[L2][L4]

现有主流程支持法语参数；它不是英语专用模型。Systran base/small 是 OpenAI 对应 **multilingual** 模型的 CTranslate2 转换版本，和 `base.en/small.en` 不同。模型卡列出 EN/ZH/FR，不能据此推断三语实际质量相同。[U3–U5]

## 3. 模型、运行时及部署来源

| 层 | 本次检查结果 | 复用含义 |
| --- | --- | --- |
| Python | 现有独立环境实际导入使用 Python 3.12.10 | 是 venv，不是经验证的独立嵌入式运行时；在新机器上应重新构建 |
| faster-whisper | `1.2.1`；安装 METADATA 与项目清单一致；MIT | 可以作为候选，后续锁定完整依赖并验证 |
| CTranslate2 | `4.8.2`；MIT | 当前 worker 只用 CPU；升级必须重新检查驱动/后端兼容 |
| PyAV | `18.1.0`；源码/包 metadata 为 BSD-3-Clause | 包内 FFmpeg 库有独立许可；见第 6 节 |
| 其他直接记录 | psutil `7.2.2`、huggingface-hub `1.30.0` | 与 `MD:docs/local-asr-third-party.md:8–14` 一致；完整传递依赖未完成发行审核 |
| base | `Systran/faster-whisper-base` revision `ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66` | 本地下载元数据一致；模型卡 MIT |
| small | `Systran/faster-whisper-small` revision `536b0662742c02347bc0e980a01041f333bce120` | 本地下载元数据一致；当前模型卡 MIT；该 pinned README 本次网页工具读取失败 |

两个模型目录均有 `model.bin/config.json/tokenizer.json/vocabulary.txt`。base 模型卡说明转换文件存为 FP16；本机运行通过 `compute_type=int8` 使用量化推理，不能把“INT8 运行”写成“下载了 INT8 权重”。[U3]

现有安装是从验证环境迁入 `tools/asr-runtime/`；源代码和文档没有给出可重复完成 Python、wheel、模型、哈希校验、升级/回滚的 bootstrap。`runtime_status()` 只检查 Python 可执行文件和两个 `model.bin` 是否存在，既不导入测试，也不验证 tokenizer/config、兼容性或文件哈希；而单任务构建只需所选模型存在。主界面“就绪”因此还要求两个模型都在，不能直接当作 V2 按需安装设计。[L1][L5]

### 离线与隐私必须准确表述

完整本地资产路径下，生产代码没有上传媒体或调用云 ASR 的步骤，应用也没有静默替换模型的下载器。**但这不是已验证的绝不联网保证**：worker 没有显式配置严格离线；faster-whisper 1.2.1 的 `FW:transcribe.py:678–708` 在本地 tokenizer 缺失时会调用 `tokenizers.Tokenizer.from_pretrained(...)`。文件目录存在且 model.bin 存在并不足以阻止该分支。模型下载元数据还只是来源记录，未落实安装器的供应链校验。[L1][L2][L6]

V2 应把“用户主动获取组件”和“本地推理”划成明确阶段：经许可审核的版本/模型 revision/哈希清单、完整性检查、失败即停的本地资源加载、可见的网络行为、清晰磁盘占用和删除/升级入口。下载器自行联网不等于上传媒体；转录文本也不应默认为可上传翻译或 TTS。MD 原验证并未把断网作为验收项。[L5]

## 4. 硬件、质量和时间戳的真实边界

**当前产品能力：CPU only。** 没有 GPU 检测、CUDA/DirectML/Vulkan/Metal 选择、显存预算或自动降级协议。CTranslate2 当前预构建支持 x86-64（至少 SSE 4.1）和 ARM64 CPU；官方 GPU 路径为 NVIDIA CUDA。faster-whisper 当前安装指引要求 CUDA 12/cuDNN 9 对应组合，但具体 wheel/驱动与平台仍须验证；AMD CPU 可用不等于 AMD GPU 可用。GlyphCue V1 的 DirectML OCR 支持不能自动迁移成 faster-whisper DirectML ASR。[U1][U2]

| 项目 | 已有证据 | 尚未证明 |
| --- | --- | --- |
| 工作流能跑通 | `PROJECT_STATUS.md:121–130` 记录真实短片和 UI→worker smoke；源码具有对应通路 | 本次没有重新运行转录，不作为当前端到端通过报告 |
| 识别质量 | 状态文档记录三段各一分钟、人类有限复核；其中中文有同音字问题 | 没有完整听校 reference，无正式 WER/CER；法语、口音、术语、数字、混语、噪声、重叠、静音/音乐尚未验收 |
| 耗时 | 历史状态记录 base 比 small 快，低线程串行 CPU 可跑短片 | 数据受共享机器和样本限制，不能作为用户硬件承诺、GPU推断或最终模型排序 |
| 时间戳 | 输出毫秒格式、分段起止、原媒体选段坐标；单元测试覆盖格式/片段参数 | 合法起止不等于语音边界精确；没有独立 forced alignment；没有词级持久化 |
| 长文件 | 批量任务和原媒体选段代码存在 | 长音频解码内存、跨窗口重复/遗漏、持续多小时稳定性无当前合格证据 |
| 字幕可读性 | SRT/VTT 可导出，VTT 文本做 HTML escaping | 没有 CPS、行长、行数、最短/最长显示时长、语义断句及跨语言重排质量保证 |

`scripts/asr_validation.py:106–127` 明确要求 `verified=True` 才算 CER/WER；`run_asr_validation.py:59` 固定传 `verified=False`。首轮仅覆盖一个中文、两个英文片段，没有法语。因此 UI 的 “Small 更准确” 是产品文案，不是本项目对三语的有效实测结论。[L4][L5]

生产 worker 的基础校验只要求起点非递减、起点非负、终点大于起点、文本长度上限；它没有要求 `end <= duration` 或相邻 cue 不重叠。父进程协议会验证有限浮点数，但没有字幕语义、单词、置信度或终点越界审核。V2 需要自己的规范 transcript/字幕数据模型，不能把 raw ASR segment 直接当作发布级字幕。[L1][L2]

## 5. 暂停、取消、失败和恢复

- **暂停是协作暂停。** stdin `pause/resume` 在模型初始化之后监听；worker 在 `next(segments)` 之前等待，不能打断正在执行的 native 推理。UI/事件可先报告 paused，而在途计算仍可能完成一段。已加载模型保留在内存，无磁盘 checkpoint。初始化完成后再启动控制线程来自曾发生的 Windows 启动阻塞修复，应保留这个经验。[L2][L3]
- **取消/看门狗。** 旧窗口直接 terminate；主流程根据进度/阶段处理超时：加载与准备 300 s、转录无进度 900 s、写出 120 s，超时 terminate 后可升级 kill。心跳只证明线程活着，不证明推理前进。[L3]
- **尚有复用前必须重做的失效边界。** `app.py:5610–5641` 的 watchdog 是收到 stdout 一行之后才执行；若整个进程停止输出且不退出，父进程阻塞读行，时限检查也不会执行。正常心跳可避免部分情况，但不是独立 supervisor。stderr 丢弃与宽泛错误码也不足以支撑发行版诊断。[L3]
- **恢复是重新排队。** `queue_store.py:20–59` 保存 waiting/downloading 任务，并将恢复状态改成 waiting；没有已完成 cue 的持久化，因此重启任务不是从最后一句继续。
- **输出保护有价值但不是崩溃原子提交。** worker 先暂存序列化结果，再以 `open("xb")` 逐个创建最终文件；Python 可捕获写失败时回滚已登记的文件。然而强制杀进程/断电，或本次文件写入在加入 `created` 前异常，可能留下一部分最终文件；不能原样继承“永不发布不完整字幕”的绝对承诺。V2 应将项目恢复与最终导出事务分开设计。[L2]
- **不要迁移源媒体删除选项。** MD 批量流程可选择成功后删除源媒体；这不自然支持 GlyphCue 可编辑工程与重做配音的长期源文件需求。该选项不应随 ASR 移植。[L3]

## 6. 商用、分发、来源与许可

这张表按组件区分代码、权重和二进制；公开、免费可下载、API 可调用均不自动等于可商用/可重分发。

| 对象 | 当前证据 | 对 GlyphCue 的决策 |
| --- | --- | --- |
| faster-whisper 1.2.1 / CTranslate2 4.8.2 代码 | 官方指定版本 LICENSE 为 MIT | 条件允许商业使用、修改和分发，保留版权/许可；不能据此批准其全部二进制依赖 [U6][U7] |
| Whisper 原始代码与权重 | OpenAI README 明确两者 MIT | 保留许可，并记录选用权重来源、版本和转换链 [U5] |
| Systran base/small 转换权重 | 模型卡 MIT，来自 OpenAI multilingual 对应模型 | 原则上是合理商业候选；发行时保存对应 revision 卡片、许可和文件哈希，不仅保留当前网页 [U3][U4] |
| PyAV 源码 | BSD-3-Clause | 保留版权/条款/免责声明，不能借贡献者名义背书；不覆盖 FFmpeg 库 [U8] |
| **现有 PyAV wheel 的 FFmpeg** | 实际导入 `av._core.library_meta`：FFmpeg `8.1.2`；自报 `LGPL version 3 or later`；含 `--enable-version3 --enable-libx264 --enable-libx265` | **阻止直接捆绑复用**：自报许可证和可能的 GPL 编解码依赖须按具体构建核实；需要构建来源、对应源代码、wheel/DLL 完整清单和权利依据 [U9] |
| 外部 `ffmpeg/ffprobe` 工具 | MD 时长预检/验证脚本使用另一套可执行文件 | 与 PyAV 内嵌库是两条依赖链，不能只审其中一套；本票未批准外部可执行文件分发 |
| MD 自有源码 | 项目根未发现 LICENSE，且不是 Git 仓库 | 用户拥有/可转移哪些代码权利需由项目方确认；研究架构与复用技术路线可继续，不能虚构其开源许可 |

FFmpeg 官方说明，默认 LGPL，启用相关 GPL 部件可改变整体 FFmpeg 许可；它的许可清单还要求对应源代码、构建方式和通知，并单独提示商用编解码专利问题。进程隔离有助于工程边界，但并不能自行解除所分发二进制的义务。本次观测到的许可矛盾不等于已判定侵权，也不等于可按 LGPL 放行。[U9]

## 7. 对 GlyphCue 的复用建议

| 现有内容 | 建议 | 原因/需调整 |
| --- | --- | --- |
| 独立 ASR worker 技术路线 | **REUSE 概念；REWORK 协议** | 保持 GUI 与原生推理隔离；增加协议版本、任务 ID、模型/后端 provenance、词级数据、可分类错误、取消确认 |
| 路径校验/选段范围/覆盖保护 | **REUSE 规则与测试；适配实现** | 解决真实 Windows 边界；由 GlyphCue 工程路径和导出层拥有规则 |
| base/small 模型 | **REUSE 为对照基线** | 不锁定为最终默认；EN/ZH/FR 需要与更高质量候选比较 |
| JSONL 阶段/心跳/实际进度思路 | **REWORK** | 独立 supervisor、超时与无输出检测、可取消阻塞读取，不能只依赖心跳 |
| SRT/VTT renderer | **REUSE 格式经验；优先对齐 GlyphCue 已有导出** | 避免重复字幕模型；ASR segment 进入规范工程后再导出 |
| 保存待处理队列 | **REUSE 语义参考；REWORK 持久化** | V2 需要保存编辑、原始 ASR、衍生翻译/配音及失效关系，不只重排文件 |
| 安装好的 venv、模型缓存和工具目录 | **不直接迁移/发布** | 可移植性、完整依赖锁、离线缺件行为、许可证尚未闭合 |
| MD 主窗口/在线平台下载/账户/字幕清洗/源删除 | **不转移** | 不属于新字幕本地化核心，也会引入无关耦合与隐私表面 |

**推荐候选而非定案：** faster-whisper + CTranslate2 值得进入第一轮实验，因为已掌握 CPU 路径与现有工程经验；Windows 非 NVIDIA GPU/更轻部署若成为硬要求，应与 whisper.cpp 等候选比较。不因为已有 base/small 就默认它们能承担成熟双语字幕/配音输入质量。

## 8. 最小后续可行性实验（本次未执行）

1. **三语 ASR 决策实验。** 先每种语言两个 60–90 s 的合法/自有片段：清晰独白与一个现实困难场景；保留人工听校 reference、人物/数字/术语错误、遗漏/重复、CER/WER、首段延迟、总耗时、峰值内存。现有 small 作基线，加一个更高质量 multilingual 模型；先在目标硬件单一后端比较，避免同时混入大量变量。通过后才做一个 20–30 分钟长片稳定性检查。六个翻译方向另做翻译评估，不把它们乘进 ASR 样本数。
2. **时间轴与编辑实验。** 只比较 raw word timestamps 能否满足可编辑字幕；手动改词、分合句、重定时后，检查原始 ASR 保留和翻译/配音标记过期。如果边界误差影响验收，再测试一个 forced-aligner，不先把它强制纳入核心。
3. **部署/断网/取消边界实验。** 在全新本地测试目录构建锁定环境，验证缺 tokenizer/坏模型时不联网，断网冷启动，加载/推理/写文件三阶段取消，无 stdout 卡死与重启恢复。所有输出用合成媒体，模型下载必须显式操作。
4. **分发审计 Gate。** 对候选 wheel、FFmpeg 可执行文件/DLL、模型建立物料与 license/NOTICE/hash 清单，确认实际构建来源和对应源代码。该 Gate 通过前，开发环境能运行也不批准 portable 包。

实验目标是决定 ASR 默认质量档、最小硬件、是否需要额外对齐、如何封装运行时；不是现在增加产品功能。文档已能回答复用路线问题，因此本票未触发 prototype。

## 来源索引

### 本地第一手文件

- **L1** `MD:local_asr.py:13–194,196–242`：候选、任务、预检、运行时、进程命令、事件校验；`MD:path_support.py:8–32`：长路径边界。
- **L2** `MD:local_asr_worker.py:15–181`：真实配置、事件、暂停、输出、命令行。
- **L3** `MD:app.py:98–103,1021–1066,3566–3881,3941–3951,5583–5700`；`MD:queue_store.py:20–59`：当前 UI、队列、监督和重启行为。
- **L4** `MD:scripts/asr_validation.py:19–127`；`MD:scripts/run_asr_validation.py:20–79,143–149`；`MD:tests/test_asr_validation.py:12–65`；`MD:tests/test_local_asr.py:15–365`：评测与合成回归。阅读测试不等于本次执行通过。
- **L5** `MD:docs/asr-validation.md:3–54`；`MD:docs/local-asr-third-party.md:3–30`；`MD:PROJECT_STATUS.md:75–140`：历史验证边界、机器安装记录和未过 Gate；本次未改写这些历史记录。
- **L6** 本次读取已安装 `faster_whisper-1.2.1.dist-info/METADATA`、`ctranslate2-4.8.2.dist-info/METADATA`、`av-18.1.0.dist-info/METADATA`；`FW:transcribe.py:621–708`；`FW:audio.py:19–66`。
- **L7** 本次读取 `MD:tools/asr-runtime/models/{base,small}/.cache/huggingface/download/*.metadata` 前两行，仅记录上游 revision，未使用私人数据。
- **L8** 本次使用已有环境只读导入 `av._core.library_meta` 和版本信息；初次沙箱无法启动该外部 Python，批准只读外部执行后成功。未实例化 ASR 模型。

### 上游第一手来源（访问 2026-10-03）

- **U1** [faster-whisper 官方 README](https://github.com/SYSTRAN/faster-whisper)：后端、PyAV、CUDA、词级时间戳和 VAD。
- **U2** [CTranslate2 4.8.2 硬件支持](https://opennmt.net/CTranslate2/hardware_support.html)：预构建硬件边界。
- **U3** [Systran base 指定 revision 模型卡](https://huggingface.co/Systran/faster-whisper-base/blob/ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66/README.md)：MIT、multilingual、转换来源、FP16 存储。
- **U4** [Systran small 当前模型卡](https://huggingface.co/Systran/faster-whisper-small/blob/main/README.md)：MIT、multilingual、转换来源。指定 revision 由本地元数据与清单交叉验证；该 revision 卡片本次网页未成功读取，不宣称已完成发行时归档。
- **U5** [OpenAI Whisper 官方 README](https://github.com/openai/whisper)：multilingual 与 .en 区别、模型任务限制、代码和权重 MIT。
- **U6** [faster-whisper v1.2.1 LICENSE](https://github.com/SYSTRAN/faster-whisper/blob/v1.2.1/LICENSE)。
- **U7** [CTranslate2 v4.8.2 LICENSE](https://github.com/OpenNMT/CTranslate2/blob/v4.8.2/LICENSE)。
- **U8** [PyAV 官方 LICENSE](https://github.com/PyAV-Org/PyAV/blob/main/LICENSE.txt)。
- **U9** [FFmpeg License and Legal Considerations](https://ffmpeg.org/legal.html)：源码/二进制许可、分发和专利边界。
