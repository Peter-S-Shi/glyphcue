# GlyphCue V2 Round 3：能力 Worker、硬件与验证政策

核验日期：2026-10-03。Track C/F 研究交付；无模型下载、安装、推理、benchmark 或生产实现。以下接口和数值均为建议，不是已批准支持矩阵或产品通过记录。沿用 Round 2 绿地、本地 ASR、翻译/TTS 本地优先且显式 BYOK、无 silent fallback、许可预设单旁白政策；EN/ZH/FR 与六方向是首批锚点，能力表保持可扩展。

## 1. 应带入 Design 的结论

采用一个 controller 管理项目写入、修订、任务与资源预算；ASR、翻译、TTS 和媒体处理使用独立进程边界。共享的是协议、supervisor 与测试工具，不要求所有模型装进一个 Python 环境或长期运行的万能进程。一个能力 worker 可以内部完成紧密耦合的 ASR+必要 aligner；仍分别报告两段时间与内存。

第一轮比较仍是同源 multilingual Whisper large-v3-turbo 的 whisper.cpp 与 faster-whisper/CT2；Qwen3-ASR-0.6B+ForcedAligner-0.6B 为质量挑战者，1.7B 只在需要时升级对照。翻译限 Qwen3-4B-Instruct-2507 与关闭 thinking 的 Qwen3-8B、llama.cpp 私有进程及可选用户 Ollama。TTS 限 Kokoro-82M v1.0 与 Qwen3-TTS CustomVoice 1.7B/必要时0.6B；不扩 shortlist。

前轮的后端发现需要两项收紧：**CT2 Windows ROCm 发行物存在不等于 faster-whisper 实机通过；whisper.cpp 后端源码存在不等于其 Windows Vulkan/SYCL 包已发行。** 所有硬件档目前均为待验证目标。

## 2. 上游证据复核与纠正

### 2.1 CTranslate2 v4.8.2：发行、源码可行与推理兼容分开

官方附件页确有 `rocm-python-wheels-Windows.zip`，页面显示 131 MB、2026-08-31，SHA-256 `43da4baa5feaee49f77e176277a9647f99c493173c81a0bc60f491cac97532c2`。这是整组 zip 的摘要，不是其中某个 wheel 的摘要；本轮没有下载，Python ABI、wheel 文件清单和实际 DLL 随附完整性未知。[C1]

v4.8.2 Windows 构建脚本使用 ROCm 7.2.0.dev0 SDK，编译目标包含 gfx1030/1100/1101/1102/1150/1151/1200/1201。这是编译目标，不能逐项等同于 AMD 官方最终用户支持清单。CI 的普通 wheel 测试依赖 `build-python-wheels`，没有依赖 ROCm 构建任务；未找到该流程中的 Radeon 硬件 Whisper 测试。[C2][C3]

不能因为 Whisper 常见 CUDA 路线需要 cuDNN 就断言此 HIP wheel 必然不能识别：v4.8.2 HIP 分支将 GPU 源码按 HIP 编译，保留 `conv1d_gpu.cu`；该文件实现 im2col+GEMM 卷积。HIP 分支也定义 `CT2_WITH_CUDA` 和 `CT2_USE_HIP`，所以 API/日志中的 `cuda` 名称本身不能证明物理设备是 NVIDIA。该证据支持“具备源码上的实现路径”，仍不能证明该 wheel、驱动、dtype、Whisper encoder/decoder、词时间、VAD 与 faster-whisper 组合正确。[C4][C5]

实验须分别验：wheel 导入→设备枚举→模型载入→三语短片 decode→词时间→10分钟/长片→取消/OOM。记录实物 GPU、driver、HIP DLL、实际计算类型；禁用未经支持的 flash attention，不从 CUDA 开关复制优化。当前不将 AMD CT2 列为默认包；也不把它写成“不支持 AMD”。

### 2.2 whisper.cpp：Windows Vulkan/SYCL 的实际发行边界

核查 `v1.9.4`：release 引向 `b5130` nightly，v1.9.4 附件只有源码；b5130 附件列 Windows CPU、BLAS、CUBLAS 11.8/12.4，以及 ARM64 CPU/CUDA/OpenCL 包，没有标明 Vulkan 或 SYCL 的 Windows 二进制包。本轮没有打开这些 zip，因此不能从文件名以外确认内部 DLL；只能说这些官方附件**未提供明确 Vulkan/SYCL Windows 包证据**，不能泛化成所有历史 release 都没有。[W1][W2][W3]

v1.9.4 `README_sycl.md` 仍把 Windows 标作 Ongoing，验证机器来自 Linux 章节，Todo 仍有 Windows build。Round 2 提到的 Windows preset 只属于源码构建线索，不能覆盖此文档边界。Vulkan 保持优先工程实验候选；若采用，应安排固定源码、自建 Windows 包、DLL/驱动清单、三语完整推理与可再分发审计。SYCL 仅在明确 Intel 目标设备与维护收益后追加，不把 Linux Arc 成绩当 Windows 支持。[W4]

### 2.3 其余 shortlist 的工程边界

| 路线 | 本轮证据与实际约束 |
|---|---|
| Qwen ASR+aligner | 固定 README 同列 EN/ZH/FR，时间输出需配置 aligner；aligner 单次最长约5分钟。2026-06-26新增 `-hf` 原生 Transformers 资产是可调查的同家族封装变化，不能未经固定 revision 就替换原 shortlist 权重。模型名加载会联网，使用受控本地目录。原生 Windows整链未验证。[Q1] |
| llama.cpp | 固定 build 文档提供 CPU/CUDA/Vulkan/SYCL 路线。选定 build 与模型转换、模板、上下文、GPU卸载层数一并锁定；ASR 加速通过不自动批准 LLM。首轮私有 worker/私有 server，避免依赖用户全局环境。[L1] |
| Ollama | 官方 FAQ 提供 `OLLAMA_NO_CLOUD=1` / `disable_ollama_cloud`，修改需重启服务；`keep_alive=0` 可请求完成后卸载。对共享服务不可擅改全局配置、强杀或保证显存独占；验证本地 digest/执行位置，否则不标“已验证本地”。[O1] |
| Qwen TTS | 固定 CustomVoice README 有三语、预设 speaker；FR 使用跨语 speaker 需独立听评，不能称法语原生声线。按确切 checkpoint、tokenizer、attention/dtype 打包；示例 CUDA 不证明普通 Windows 冷安装。[Q2] |
| Kokoro | 沿用 Round 2 82M v1.0 候选与 G2P/voice 资产依赖结论。本轮固定 HF VOICES 链接读取失败，未新增声线权利或质量事实。Round 2 两报告分别使用不同中文试验声线，后续试验须先固定一条，不能混并分数；本稿建议沿 runtime 报告 `zf_xiaoxiao`，仍待清单/许可复核。 |

## 3. Controller 与能力 Worker 的最小契约

以下是拟议边界；不冻结语言、类结构、数据库 schema 或 UI 框架。

| 责任 | Controller | 能力 worker |
|---|---|---|
| 领域状态 | 唯一项目写入者；输入快照、人工锁定、候选晋升与历史 | 不直接写项目 DB、不改字幕当前修订 |
| 资源 | manifest、下载/导入校验、版本、调度、运行包位置 | 仅加载已批准的本地文件；报告真实 backend、dtype、模型状态 |
| 任务 | task/attempt、取消意图、资源租约、重试与提交 | 执行指定 unit；结构化进度、结果、错误；安全点停止 |
| 文件 | 只读源输入、独立 attempt 暂存、校验后发布 | 只写被分配暂存区，不选择最终导出路径 |
| 服务 | 明确处理位置和 BYOK 授权范围；凭据库取密钥 | 本地 worker 无云 ASR；外部 adapter 仅接收授权文本与临时凭据 |

**Generic host 的允许范围**：可以复用一个小型启动器/协议库，让独立进程选择能力入口；不能在同一地址空间同时 import 不兼容 torch/CT2/TTS 栈。runtime package ID 和 capability ID 分开：同一代码库可产多个包；只有版本、依赖、许可与回收均验证后才合包。Qwen ASR+aligner 可以共处一次 attempt；翻译/TTS 独立包避免升级耦合。首版无常驻系统服务，UI关闭由 controller 收尾或明确中断。

## 4. IPC、文件与进程所有权

建议私有继承管道上的长度前缀 UTF-8 JSON：4字节无符号小端长度+payload，默认单帧上限1 MiB，禁止非有限数字和重复关键字段；跨语言精确微秒用十进制字符串或严格受限整数，统一约定。大文本结果与音频放暂存制品，IPC只传逻辑ID、摘要、类型、长度。短读、拆帧、合帧、EOF半帧、过大长度都要有测试。日志走独立通道并限速；不得把第三方 stdout 文本当完成协议。

握手字段至少 `protocol_version / worker_instance / capability / runtime_manifest / backend_capabilities`；消息含 `task_id / attempt_id / snapshot_id / unit_id / seq / kind`。每 attempt 有新 nonce，启动握手核对版本与实例，旧进程无权接续新 attempt。控制消息包含 `start / cancel / shutdown`，事件有 `ready / progress / artifact_ready / failed / stopped`；artifact_ready 只是请求 controller 验收。不要在 UI 直接拼接命令字符串；执行固定可执行文件和分离参数。

worker 通过 controller 分配的逻辑 artifact ID 得到输入句柄或精确路径。对返回路径必须拒绝绝对路径、`..`、UNC、设备路径、ADS 与不允许的 reparse point；按最终句柄解析后的路径和文件身份检查归属，并在打开/发布时重核，避免字符串前缀检查和检查后替换。用户自行选中的源素材可以在任意合法位置，只读授权与worker输出归属分开。Windows `GetFinalPathNameByHandleW` 提供最终路径查询，但不是单函数完成的安全沙箱。[P1]

Windows 自有 worker 启动建议 suspended→分配 Job Object→resume；禁 breakaway，采用 kill-on-job-close，Job句柄不下传，显式限制继承句柄。Job Object 是进程生命周期工具，不是网络或文件安全沙箱；宿主崩溃、已有嵌套job、spawn失败、helper派生都须实验。终止后确认进程树退出；不能只依赖可能漏送的 completion-port 通知。共享 Ollama不加入自有Job、更不能终止。[P2]

## 5. Snapshot、Attempt fencing 与取消

snapshot 固定媒体内容版本/音轨/范围、实际源文与上下文修订、术语、语言方向、声线、模型与runtime hash、prompt/schema和参数。worker无权刷新为“当前输入”。controller在一次提交事务中核对 attempt仍active、nonce、unit未提交、snapshot和锁状态；同unit重复结果只认一次。变更源文后旧结果可留历史候选，不能覆盖当前人工稿。render绑定准确快照，不混入运行期间编辑。

| 事件 | 所需结果 |
|---|---|
| 取消排队任务 | 撤销资源请求；无需启动worker |
| 本地运行取消 | 先持久化cancel意图、撤销结果晋升权限，再协作cancel；建议5秒无安全退出后hard kill自有Job；这个超时是实验起点 |
| 收到stopped | 核实native/helper已退出，关管道、隔离未提交产物；不因一条ACK即显示已取消 |
| cancel与完成竞态 | 以controller事务顺序决定；完成先提交则显示已完成，取消先落账则迟到结果不晋升 |
| crash/restart | 未终结attempt为Interrupted；核验已提交单位，残缺输出隔离；新attempt有新ID，不根据PID恢复身份 |
| 外部超时/断连 | `OutcomeUnknown`：请求可能执行/计费；存私有provider request ID（若有），可查询则查询；不可盲重发 |
| 外部取消 | 区分本机已停止等待与远端确认撤销；远端迟到结果隔离，费用仍可能发生；重试须显示重复执行风险 |

禁止依赖“exactly once”网络执行假设。单次controller提交可以幂等；供应商执行是否幂等由服务契约决定。失败不隐式换模型、后端或云端；明确选择的新配置创建新attempt和provenance。取消恢复测试涵盖准备、载入、推理、写文件、校验、发布前后七个时点。

## 6. 加载、卸载、设备发现与资源预算

模型状态分 `absent / verified / loading / loaded / unloading / failed`；安装就绪与能力已验收另存。控制器核对完整依赖资产后才启动，模型名不进入可自动下载路径；离线标志和出站阻断验证一起使用。保持模型句柄仅在同能力连续任务有收益时；阶段切换先停任务、释放实例、确认GPU工作结束，无法可靠释放则退出自有worker。不得把Python GC或单次empty_cache视为已卸载证明。Ollama卸载是协作请求且共享资源不可独占。[O1]

默认同一物理GPU只有一个重任务租约，跨ASR/aligner/LLM/TTS/占显存的渲染统一排队；不是“每阶段各一个”。普通播放保留预算；CPU worker也限制线程和RAM。模型载入、推理、卸载完成前租约不交给下一重任务。估算不足时拒绝/排队，OOM后清理并提供用户选择，不能暗自换small或发云端。Job内存上限不等于VRAM上限。

| 探测层 | 保存/验证内容 | 不足以证明 |
|---|---|---|
| OS/CPU | 架构、ISA、逻辑核、可用/总RAM、OS build；worker自报实际CPU backend | x64或CPU品牌不保证特定量化/ISA包可运行 |
| GPU枚举 | DXGI adapter/设备ID、driver、专用/共享内存、预算，过滤软件adapter；ID只本机映射 | DXGI识别GPU不证明CUDA/HIP/Vulkan/SYCL可用 |
| 后端加载 | 固定包探测CUDA/HIP/Vulkan/SYCL设备及必要DLL/特性；探测在短命worker带超时 | 安装驱动不等于runtime ABI兼容 |
| 模型执行 | 加载具体模型并做小样，记录实际offload层/算子/设备、dtype与资源峰值 | 构造成功不证明全部GPU执行，也不证明质量 |

DXGI预算是动态OS建议量，超过可能导致分页/性能下降；专用VRAM、共享RAM不能简单相加后承诺大模型容量。[P3] NVIDIA CUDA、AMD HIP/Vulkan、Intel Vulkan/SYCL分别建证据记录，不能继承NVENC/AMF/QSV或V1 DirectML OCR结果。显存不可可靠读出时记录unknown，使用保守串行策略，不能填0。

## 7. 待验证 Windows 硬件档

以下是招募测试机器与预算的建议，**不是最低配置、推荐购买清单或现有支持承诺**。Windows 11 x64为首轮目标；OS具体build、driver及电源模式写进测试记录，ARM64/WSL另立范围。

| 目标档 | 拟用机器类别 | 要回答的问题 |
|---|---|---|
| H0 资源下限 | 4核以上CPU、8GB RAM、无独显 | small/轻量TTS是否有可接受等待与系统余量；可能只能提供部分能力，失败不降低质量门槛 |
| H1 CPU基线 | 6–8核、16GB RAM、SSD | turbo或small、Qwen4B量化、Kokoro串行完整字幕/旁白链；是否需要32GB |
| H2 NVIDIA | 32GB RAM、8GB VRAM | turbo、Qwen4B/8B、Qwen ASR/TTS逐项加载及完整链；8GB只是测试点 |
| H3 AMD | 32GB RAM、8–12GB独显 | 自建whisper.cpp Vulkan；有确切设备时加CT2 HIP，区分发行依赖与质量收益 |
| H4 Intel | 16–32GB共享内存iGPU与8GB Arc独显分别测 | Vulkan首测，SYCL条件实验；共享内存压力与独显不可合并平均 |

资源余量建议RAM至少留2GiB且不超过可用预算80%、VRAM峰值不超过测试时预算85%；这只是筛查预警，不代替长片压力/系统响应测试。所有模型有失败可能，不按参数位数算最低内存。

## 8. 可重复质量与工程评测方案

先批准测试集、预算和门槛，再运行。建议pilot每语30分钟、至少6名有授权说话人，每方向100条翻译、每语30条TTS；冻结holdout每语至少120分钟/12名说话人，每方向300条、每语100条TTS。按清晰/噪声/音乐/口音/数字专名/混语分层；FR-FR与FR-CA单列，ZH普通话与简繁规范分开。素材许可与原始内容私有留存，公开仅合成fixture和去标识汇总。不得用同一调参片段声称独立验收。

| 维度 | 记录方法 | Advisory筛查起点（待批准） |
|---|---|---|
| ASR EN/FR | WER=(S+D+I)/N；原始与规范化分数并列；逐语逐分层、宏平均/总词加权均报 | 清晰语音WER≤12%，挑战集≤25% |
| ASR ZH | 固定繁简/数字/标点规范后CER；原始CER另报；不拿字错率与WER作跨语排名 | 清晰CER≤10%，挑战集≤20% |
| 内容错误 | 数字/专名准确率；漏句、静音幻觉按片段列；人工改稿分钟/音频分钟 | pilot无整句捏造或关键数字意义反转未被复核发现；零观察事件不称零风险 |
| 时间质量 | 人工双人标注；start/end误差p50/p95，漏时间比例；仅正确可匹配词/字的条件误差与全部覆盖率同时报告 | 段边界p95≤500ms；若宣称词级编辑定位，词/字边界p95≤250ms且覆盖≥95% |
| 长片时间 | 10/60/120分钟材料，首中尾、VAD/分块接缝误差，源offset还原 | 无累计漂移；各位置沿用边界门槛；不能只测前30秒 |
| 六向翻译 | EN→ZH、ZH→EN、EN→FR、FR→EN、ZH→FR、FR→ZH各自双语盲评；忠实度1–5、漏译/新增/数字/术语/格式、后编辑时间 | 每方向忠实度均值≥4/5、关键意义错误0、非关键重大错误unit≤2%；schema/ID完整100% |
| TTS自然度 | 每语≥5名目标语言熟练听者；随机盲听1–5分，报告置信区间、漏读/误读、声线与口音 | 自然度均值≥3.8，95%区间下界≥3.5；关键数字读法正确100% |
| TTS长度 | 原始take样本数/采样率；actual/window比、原速fit率、溢出与静音；30/60/120分钟混音累计误差 | ≥90%候选片段在预设有限变速区间内可fit（建议0.9–1.1倍）；截断/掐尾0；不为过门槛删信息 |
| 速度 | 冷启动、模型加载、首结果、总wall time；ASR含解码/VAD/aligner；RTF=处理秒/输入音频秒，TTS用生成秒/输出音频秒；翻译tokens/s与100unit总时延 | H1 ASR RTF≤2，H2≤0.5；TTS RTF≤1；翻译100unit≤120秒作为讨论起点，不承诺全部候选 |
| 资源 | controller+worker整进程树private commit/working set、GPU dedicated/shared峰值、峰值时刻、包/模型/临时磁盘大小 | 不越已批准机器预算；三次重复加载无持续增长，连续10次后残留增长≤5%作排查线 |
| OOM/取消 | 载入与decode两处故障注入、七阶段cancel、driver失效、进程崩溃、断电模拟；每类≥10轮 | 已提交产物丢失0、迟到覆盖0、失控重试0、自有残留进程0；UI取消反馈≤1秒，结束清理p95≤10秒起点 |
| 安装/离线 | 无开发工具干净机、普通用户、Unicode/空格/长路径；断网冷启、缺DLL/模型、损坏/中断下载、低磁盘、升级回滚 | 每拟支持profile≥3次冷装全部成功；离线完整链成功；运行阶段意外出站0；缺件准确报因 |

三次冷启动使用新进程并标明OS文件缓存是否清除；五次热运行报告中位数/范围，小样本不伪称可靠p95。性能正式测量至少20次短任务，长片至少3次，报告原始样本数和区间。同源Whisper、VAD、beam、batch、线程、精度、输入重采样尽量一致；先比较相近浮点，再比较拟发行量化，不能把两者当完全同精度实验。

这些数字不是上游给出的质量保证，也不是已经批准的产品pass/fail。Product通过须具备：预先批准阈值、冻结holdout、全部锚点方向逐项通过、许可/冷装/离线/恢复通过、人工评价及准确硬件profile签收。失败单元、未测声线或GPU不可被总平均掩盖；若调整门槛须记录理由并重评，不能事后改线制造通过。设计评审可先通过契约，模型/包默认选择与发布支持表必须等待实验。

## 9. 脱敏诊断与复现实验包

默认诊断仅保存错误类别、阶段、粗粒度耗时、版本/hash、backend/dtype、资源峰值与合成correlation ID；不录媒体名/路径、字幕文本、完整prompt、HTTP body、密钥、账号、设备序列号或用户会话。第三方stderr先过字段白名单和长度限制；原始异常常夹路径，不能直接显示为可分享日志。

本机项目provenance可以保留必要私有映射；导出诊断另生成脱敏视图。公开repro只能用合成fixture、相对通用路径、固定seed/config、模型/runtime来源和哈希、测试步骤与预期/实际错误码。真实媒体hash与provider request ID也可能关联用户，不默认公开；不把完整环境变量、进程命令行、崩溃内存dump自动附上。用户预览并显式选择后才导出，不自动上传。

## 10. 后续实验的最小顺序与未决项

1. 先用假worker验证帧协议、进程树、取消竞态、快照/锁、文件发布与重启恢复；无需下载模型即可证伪控制边界。
2. 固定一条CPU ASR与一条NVIDIA候选、同源模型和pilot；再测试AMD/Intel Vulkan自建包。CT2 HIP与SYCL仅按设备和发行证据追加。
3. 逐能力验证本地完整资产、卸载与串行调度；再跑三语、六向与TTS盲评。比较Qwen须包括aligner，Kokoro须包括G2P。
4. 默认选型前完成冻结holdout、冷机、离线、OOM、许可与诊断复核；只为通过的具体profile发支持声明。

当前未知：CT2 zip内ABI/DLL及Windows Radeon Whisper实测、whisper.cpp自建Vulkan/SYCL发行成本、Qwen原生Windows完整安装、所有候选真实RAM/VRAM/质量/时长、产品阈值批准。上述未知不阻止Design画状态与修订流程，但阻止把候选写成已支持硬件或已达标性能。

## 一手来源索引

均访问于2026-10-03；固定tag/commit只固定本页事实，最终制品仍需不可变摘要。文中接口、调度和门槛为本稿建议。

- [C1 CT2 v4.8.2 官方附件](https://github.com/OpenNMT/CTranslate2/releases/expanded_assets/v4.8.2)
- [C2 Windows ROCm构建脚本 v4.8.2](https://github.com/OpenNMT/CTranslate2/blob/v4.8.2/python/tools/prepare_build_environment_windows_rocm.sh)
- [C3 CT2 CI v4.8.2](https://github.com/OpenNMT/CTranslate2/blob/v4.8.2/.github/workflows/ci.yml)
- [C4 CT2 CMake v4.8.2](https://github.com/OpenNMT/CTranslate2/blob/v4.8.2/CMakeLists.txt)
- [C5 CT2 GPU Conv1D v4.8.2](https://github.com/OpenNMT/CTranslate2/blob/v4.8.2/src/ops/conv1d_gpu.cu)
- [W1 whisper.cpp v1.9.4 release](https://github.com/ggml-org/whisper.cpp/releases/tag/v1.9.4)
- [W2 v1.9.4附件](https://github.com/ggml-org/whisper.cpp/releases/expanded_assets/v1.9.4)
- [W3 b5130附件](https://github.com/ggml-org/whisper.cpp/releases/expanded_assets/b5130)
- [W4 SYCL文档 v1.9.4](https://github.com/ggml-org/whisper.cpp/blob/v1.9.4/README_sycl.md)
- [Q1 Qwen ASR README 7c6daf7](https://github.com/QwenLM/Qwen3-ASR/blob/7c6daf77a2421100f5fb066495372c00129d39ff/README.md)
- [Q2 Qwen TTS README 022e286](https://github.com/QwenLM/Qwen3-TTS/blob/022e286b98fbec7e1e916cb940cdf532cd9f488e/README.md)
- [L1 llama.cpp build b92761a](https://github.com/ggml-org/llama.cpp/blob/b92761a515ea31e852e7fbc1fad5f874b46f3718/docs/build.md)
- [O1 Ollama FAQ（滚动文档）](https://docs.ollama.com/faq)
- [P1 Windows最终路径查询](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfinalpathnamebyhandlew)
- [P2 Windows Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)
- [P3 DXGI显存预算查询](https://learn.microsoft.com/en-us/windows/win32/api/dxgi1_4/nf-dxgi1_4-idxgiadapter3-queryvideomemoryinfo)

项目上下文：[Round 2 runtime](../v2_discovery_round2/03_LOCAL_AI_RUNTIME_STRATEGY.md)、[语言能力](../v2_discovery_round2/02_LANGUAGE_CAPABILITY_STRATEGY.md)、[领域流程](../v2_discovery_round2/04_DOMAIN_WORKFLOW_MODEL.md)、[范围契约](../v2_discovery_round2/06_V2_DESIGN_SCOPE_CONTRACT.md)、[Round 1技术候选](../v2_discovery/04_TECHNOLOGY_OPTIONS.md)。
