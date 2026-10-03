# V2 绿地 Windows 桌面架构比较

研究日期：2026-10-03。状态：供设计选择的技术建议；不构成已批准的框架、实现或发行承诺。本轮只读官方资料及 Round 1 调查，未构建框架样机、安装依赖、运行模型或测试性能。

## 1. 新前提与结论

V2 采用实用绿地设计。V1 不是架构基线：没有旧数据库迁移、旧 UI 兼容、旧领域对象保留要求。Round 1 的「Python/PySide6 为复用基线」「没有理由更换框架」不再是 V2 约束。旧字幕解析、原子写出、合成测试和发行审计经验，只有经独立评估确实更便宜且更安全时才可借用；原记录不改写。

首先建议验证 **PySide6 + Qt Quick/QML UI + Python 应用控制器 + 独立推理/媒体 worker**；强备选为 **Tauri 2 + TypeScript UI + 薄 Rust 应用控制器 + 同样的独立 worker**。这是维护面与交互成本的定性判断，不是性能排名。产品范围可以先冻结，框架仍由 CC Design 根据下面的证伪实验决定。

所有桌面壳都能运行 Python 或原生 CLI worker。Python 模型生态丰富，只说明计算层应保留 Python 接口，并不能证明 UI 必须使用 Python。Qt 首选的额外理由是：可用 QML 重做交互，同时将项目规则、任务编排和 worker 协议保留在一个 Python 代码体系，减少 TS→Rust→Python 的跨语言契约面；前提是 QML 的文本编辑、时间线及打包实验证明合适。

Qt Widgets 与 Qt Quick 是不同候选。前者适合标准表格和桌面控件，后者更适合可定制布局、绘制与动画；两者都不是现成字幕工作台。不能通过沿用 V1 Widgets UI 来兑现本轮的绿地设计。[Qt UI 比较](https://doc.qt.io/qt-6/topics-ui.html)

## 2. 同等候选比较

| 候选 | 最小边界与真实优点 | 主要代价 / 何时更合理 |
|---|---|---|
| PySide6 / Qt Widgets | Python 控制器、标准桌面编辑控件、独立 worker；表格式校订与键盘操作可直接利用 Qt 控件 | 高度定制时间线与响应式视觉需要更多自绘；若设计最后以密集表格为主，可比 QML 更便宜，不因 V1 用过就默认胜出 |
| PySide6 / Qt Quick-QML | QML 负责呈现，Python 提供模型与命令；便于自定义波形、轨道和布局；Qt Multimedia 可原生承接播放器 | QML/Python 状态桥、长列表虚拟化、中文输入法、焦点与撤销要验证；复杂富文本组件不一定比 web 生态省工；QML 是额外技能面 |
| Tauri 2 / web UI / Rust host | HTML/CSS/TS 编辑体验与可视化自由度；host 管文件、权限与进程；sidecar 官方支持任意语言二进制，含 Python 打包程序 | 加入 Rust 与 IPC 契约；WebView2 是发行依赖；HTML video 支持不等于 FFmpeg 支持；不能只比较空壳安装尺寸而忽略 Python、模型、WebView2 与 FFmpeg |
| Electron / web UI / Node host | TS 可同时覆盖 UI 与应用编排；自带 Chromium/Node，浏览器版本随应用可控；renderer 与 main 分离，成熟 web 交互路线 | Chromium/Node 安全更新由产品承担；再加 Python 与模型后，须测实际 RAM/安装体积；Node native 模块及媒体后端仍需打包验证，不能把 utilityProcess 当 Python 解释器 |
| .NET WPF / C# host | 成熟 Windows 数据绑定、模板、键盘和桌面集成；C# 控制器可调用同样的 Python/CLI worker；无需强制引入 WebView2 | Windows 专用；C#/XAML 与 Python 的协议仍要维护；自定义时间线、媒体 codec、推理包不会因 .NET 自动解决；团队熟悉 C# 时可优先于 Qt |
| .NET WinUI 3 / C# host | Windows 原生视觉与控件，适合明确重视系统一致性的设计 | Windows App SDK runtime 与 .NET runtime 是分开的部署面；是否打包 MSIX、是否 self-contained 需明确；Windows-first 本身不足以证明 WinUI 比 WPF 成本低 |

事实依据：[Qt UI](https://doc.qt.io/qt-6/topics-ui.html)、[Tauri sidecar](https://v2.tauri.app/develop/sidecar/)、[Electron process model](https://www.electronjs.org/docs/latest/tutorial/process-model)、[Electron utilityProcess](https://www.electronjs.org/docs/latest/api/utility-process)、[WPF overview](https://learn.microsoft.com/en-us/dotnet/desktop/wpf/overview/)、[Windows App SDK 自包含部署](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/self-contained-deploy/deploy-self-contained-apps)。表中成本及适用性为工程推论。

Electron 是 Tauri 的有力对照：若保持单一 TypeScript 控制层、固定 Chromium 与较快 UX 实作比安装体积重要，Electron 可能更便宜。Tauri 优势必须来自真实发行测量和权限边界，不能从营销的“小、快”直接得出。WPF/WinUI 也不因缺跨平台而淘汰；V2 当前只需 Windows-first。

## 3. 与桌面壳无关的最小架构

```text
UI（只发命令/显示状态，不直接改项目库或启动任意命令）
  ↓
一个应用控制器（任务状态、修订校验、资源调度、唯一项目写入队列）
  ├─ SQLite 项目库 + 不可变产物文件
  ├─ 模型/运行时资源管理器
  ├─ 本地 ASR worker
  ├─ 本地翻译/TTS worker 或显式 BYOK provider adapter
  └─ FFmpeg/ffprobe worker
```

控制器只选一个归属：Qt 方案为 Python 应用层；Tauri 为 Rust host；Electron 为 Node main 的应用层；.NET 为 C# 应用层。持久化写队列属于同一控制器，可以在其专用线程串行执行数据库事务。不要再加一个拥有同样任务规则和数据库写权的 Python supervisor。推理 worker 只接受版本化请求、产生结果和临时产物，不拥有项目事务或跨任务调度权。

首版无需常驻服务、localhost HTTP server、容器或微服务。worker IPC 可用受限长度的 stdin/stdout JSON 消息；stderr 留给经脱敏的诊断。大音频、波形和模型走受管理文件，不经 UI 消息传递。消息至少含 protocolVersion、jobId、attemptId、输入 revision、运行时/model revision、stage、进度依据与结果 manifest；控制器检查消息归属、尺寸、路径范围和 revision 后才提交。此为设计建议，不是上游框架自动提供的保障。

ASR adapter 只有本地实现；翻译/TTS 可有本地和显式 BYOK 两类实现。权限和任务计划必须记录处理位置、发送数据类别、端点与用户选择；运行失败只能进入错误/用户重试决策，不能改用云服务。模型下载与推理上传是不同操作；首次下载也须可见。worker 本地执行并不自动等于断网运行，需离线验收其依赖是否偷偷请求远端。

语言采用可扩展标识及分阶段 capability（转录、翻译方向、声线、对齐、书写变体）；EN/ZH/FR 为首批验收锚点。不要在数据库 enum 或 provider 接口硬编码只有三语，也不要用一个“支持语言列表”概括整条链的可用性。

## 4. 进程、取消、调度和恢复

Windows 应把每个任务的 worker 及其子进程纳入 Job Object 生命周期，先合作取消，再在宽限期后终止该任务进程组，并等实际退出。控制器退出时清理所属 worker；限制 breakaway 和句柄继承，避免父进程死后 FFmpeg/GPU 子进程继续占资源。创建与纳入 Job Object 的竞争窗口要通过受控 launcher/启动方案关闭，不能先启动任意 worker 后很久才分组。[Windows Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)

QProcess 在 Windows 的 kill 使用 TerminateProcess，文档只承诺杀该进程；.NET Kill(entireProcessTree) 后的 WaitForExit/HasExited 也不表示所有后代都已退出。因此任一路线都要测进程树、GPU 释放和最终状态，而非把单个 kill 返回视为完成。[QProcess](https://doc.qt.io/qt-6/qprocess.html#kill)、[.NET Kill](https://learn.microsoft.com/en-us/dotnet/api/system.diagnostics.process.kill?view=net-10.0)

推荐状态为 queued → preparing → running → validating → committed；旁路有 cancelling、cancelled、failed、interrupted。点击取消先显示 cancelling，只有确认进程结束并拒收该 attempt 的迟到结果后进入 cancelled。上次应用退出时未终结的任务重启后为 interrupted；从完整已提交阶段重试，不承诺在 native kernel 中点续算。

资源调度先只做一个重模型任务槽位，ASR→翻译→TTS 按需装载/卸载；ffmpeg 编码也纳入 CPU/GPU 预算。预览和编辑优先，模型下载有独立低并发限制。暂不做复杂自动 VRAM 最优装箱；设备能力与内存估计不可当作一定不会 OOM 的保证。退出整个 worker 是可验证的释放策略，常驻热模型优化以后再用测量决定。

任务先在独立临时目录完成产物、校验内容/时长/哈希，再由控制器以短事务登记；文件与 SQLite 无跨介质原子事务，故要定义重启时对 orphan 文件和缺失文件的 reconciliation。当前人工修订与 job 输入修订不同则保存为候选/过期结果，不能覆盖用户编辑。

SQLite WAL 允许读写并行，但仍一次一个 writer，且不适合把项目数据库直接放网络文件系统。首版一个项目一个写入队列；导出/备份使用数据库一致性方案，不能在 WAL 活跃时只复制主 db 文件。原媒体用 locator + 内容身份引用，模型缓存与密钥不进便携项目包。[SQLite WAL](https://www.sqlite.org/wal.html)

## 5. 媒体预览与最终输出

| 路线 | 可用预览入口 | 必须补足的产品行为 |
|---|---|---|
| Qt | QMediaPlayer + QVideoWidget 或 QML VideoOutput；当前 Qt Multimedia 以 FFmpeg 为主要后端 | 锁定 Qt/FFmpeg 配套版本并测 seek、VFR、音轨切换、音画同步；不要假定 GUI 播放器提供逐帧精确剪辑 |
| Tauri | WebView2 HTML media；受控本地 asset/custom protocol | 源容器/codec 无法播放时生成可播放代理；要处理 Range/seek、源时间映射及本地访问边界；禁止因 `<video>` 失败直接判素材不能处理 |
| Electron | Chromium HTML media；受控本地 protocol | 自带浏览器仍不等于支持 FFmpeg 的全部 demuxer/decoder；代理与源媒体映射同样必需 |
| WPF / WinUI | 原生媒体控件或独立媒体集成 | 精确目标 Windows/媒体组件/codec 组合须测；若引入 FFmpeg/libVLC 等，新增各自许可与打包依赖 |

Qt 的 Windows Media Foundation 后端自 6.10 标为 deprecated；选择 Qt 时应核对实际 FFmpeg 后端，不为新产品依赖旧后端兜底。视频压缩专利费用也不会因为使用系统 codec 而自动消失。[Qt Multimedia](https://doc.qt.io/qt-6/qtmultimedia-index.html)

推荐统一 ffprobe 预检 + 独立 FFmpeg 最终输出；预览代理只在必要时建立，不转码覆盖原素材。代理记录原媒体时间原点、选音轨、PTS/时长映射。双语字幕预览可以快速叠层；“最终效果预览”需用同一 ASS、字体与 FFmpeg/libass 路线渲染短段，以免 UI 字体排版被误当成成片事实。

字幕烧录需重新编码画面；仅音轨/软字幕封装在容器和 codec 兼容时可复制视频流。目标音轨、响度、配音溢出和字幕时间都由显式 export plan 控制，壳框架不承担这些领域决定。[FFmpeg filters](https://ffmpeg.org/ffmpeg-filters.html#subtitles-1)、[FFmpeg legal](https://ffmpeg.org/legal.html)

## 6. 运行时、模型与 Windows 发行

应用壳、每类推理 runtime、模型权重、FFmpeg 和字体分别版本化。资源 manifest 包含来源、精确 revision、哈希、许可、CPU/GPU 后端、支持 OS/架构、协议范围、模型所需附属文件及总空间。先下载到 staging，验证所有文件后原子切换当前版本；保留被现有任务引用的旧版，运行中不覆盖 DLL 或权重。

runtime 更新与 model 更新不能独立盲升：兼容表要覆盖 tokenizer、转换格式、量化、CUDA 等依赖；资源损坏、缺 tokenizer、离线缺件须在就绪检查中阻断。缓存不位于程序安装目录；卸载默认保留用户项目，模型缓存清理是明确选择。首版可用签名安装器手动升级，自动更新并非成熟性前提。

Tauri Windows 支持 NSIS/WiX 及 WebView2 的 bootstrapper、offlineInstaller、fixedRuntime 路线。**嵌入 bootstrapper 不等于离线安装**；offline installer 包含安装所需 runtime，Fixed Version 则由应用负责版本维护。无 WebView2 的干净离线 Windows 是必须验收的情形；不能假定系统已有。[Tauri Windows installer](https://v2.tauri.app/distribute/windows-installer/)、[Microsoft WebView2 distribution](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution)

Electron 自带 Chromium/Node，免去 WebView2 存在性检查，但产品需持续升级这些组件。Qt for Python 有 pyside6-deploy/PyInstaller 等发行路线，仍须实测 QML 插件发现、Qt Multimedia 和独立 worker 的完整包。WinUI self-contained 需同时考虑 Windows App SDK 与 .NET，不把一个开关当作全部离线依赖已封装。[Electron security](https://www.electronjs.org/docs/latest/tutorial/security)、[Qt Python deployment](https://doc.qt.io/qtforpython-6/deployment/index.html)、[Windows deployment](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/)

Windows Authenticode、更新包签名、下载资源 hash 分别证明不同事情。发行时对自有可执行文件及安装器建立签名策略并保留上游二进制来源；hash 只有结合可信 manifest 才能验证来源。Tauri updater 的签名验证不能替代 Windows 代码签名；签名本身不保证无 SmartScreen 提示。[Tauri updater](https://v2.tauri.app/plugin/updater/)、[Electron code signing](https://www.electronjs.org/docs/latest/tutorial/code-signing)

## 7. 许可边界

| 对象 | 本轮核验事实 | 商用/再分发含义 |
|---|---|---|
| PySide6 / Qt | Qt for Python 有 LGPLv3/GPLv3/商业路径；Qt Quick Controls 和 Multimedia 各有模块许可 | 商用并非必须买商业版，但选择 LGPL 时需满足库源码、通知、修改/重新链接及用户调试替换等适用义务；不要把整个 Qt 全称 LGPL；动态部署也非自动合规 |
| Tauri | 上游代码按组件为 MIT 或 MIT/Apache-2.0 | 可进入商业产品候选，保留所选许可及通知；前端依赖、插件、Windows WebView2 runtime、sidecar 权重分别审计；其 logo 另有条件，不随代码许可自动授权 |
| Electron | 自有源码 MIT，随包有 Chromium/Node 等第三方组件 | 商业分发可行，需保留对应 notices；媒体 codec/模型权利不在 MIT 保证中 |
| WPF / Windows App SDK | 两个上游代码仓库均 MIT | 不等于 Microsoft 所有二进制、系统 codec、字体、商店条款都 MIT；确切 NuGet/runtime 包、再分发条款和 notices 需落入 SBOM |
| FFmpeg | 默认主要 LGPL；启用 GPL 组件使相应构建适用 GPL；nonfree 组合不可再分发 | 商业收费与 copyleft 是不同问题；选择确切 build、配置、对应源码和第三方库，而不是只记录 ffmpeg.exe 名称；专利另审 |
| WebView2 | Microsoft 提供正式 Evergreen/Fixed Version 分发机制 | 使用官方分发渠道及附带条款；不能从 Tauri 的 MIT 推导 runtime 是 MIT，离线打包也仍有 runtime 安全更新责任 |

许可一手依据：[Qt for Python](https://doc.qt.io/qtforpython-6/licenses.html)、[Qt Quick Controls](https://doc.qt.io/qt-6/qtquickcontrols-index.html#license-and-attributions)、[Qt 收录的 LGPLv3 正文](https://doc.qt.io/qt-6/lgpl.html)、[Tauri LICENSE 信息](https://github.com/tauri-apps/tauri#licenses)、[Electron LICENSE](https://github.com/electron/electron/blob/main/LICENSE)、[WPF LICENSE](https://github.com/dotnet/wpf/blob/main/LICENSE.TXT)、[Windows App SDK LICENSE](https://github.com/microsoft/WindowsAppSDK/blob/main/LICENSE)、[FFmpeg legal](https://ffmpeg.org/legal.html)。这是工程筛选，最终判断针对精确发行物；未审计所有传递依赖。

## 8. 能推翻推荐的最小实验

这些是后续有限实验计划，本轮不执行。先用同一合成数据和 stub worker 比较 Qt Quick 与 Tauri；不是同时做两个产品。

| 实验 | 最小交付及观察 | 推翻/保留条件 |
|---|---|---|
| UI 编辑切片 | 视频旁源/译文本、可滚动大量 cue、单段试听、时间线拖动；中文输入法、法语重音、键盘焦点、撤销、DPI 与可访问性 | 若 Qt 必须大量自制文本编辑而 web 可用许可合适且经测试的组件明显减少工作，Tauri 升首选；若 QML 合格，不因视觉偏好直接换壳 |
| 播放/导出切片 | 同一有授权的 VFR/长 GOP/多音轨/Unicode 路径素材，预览 seek、代理、字幕叠层与短段成片 | 若 Qt 后端表现或发行许可阻碍无法在范围内解决，而 WebView2/代理路线可满足，则换壳；反之 WebView2 导致大量必需代理而 Qt 可直接可靠播放，则保留 Qt |
| worker 生命周期 | stub 生成子进程，模拟挂起/迟到完成/OOM 报告，取消并重启应用 | 无孤儿、无覆盖修订、无双 writer；若 Qt host 的 Job Object/打包集成成本显著高于 Tauri host，可调整；这是实现成本比较，不是 Python 天生不能取消 |
| 干净离线安装 | 无 Python、无开发工具、必要时无 WebView2 的 Windows；安装 UI + 一个小 stub runtime，不下载 AI 模型 | 比较真实完整包、冷启动、更新/回退与卸载保护；Tauri offline runtime 抵消壳体积优势时不能继续宣传“极小”；Electron 可因稳定 Chromium 与 TS 维护收益胜出 |
| 团队与设计契合 | 对同一个确认过的交互切片记录自制控件数、跨语言接口数、打包故障和可维护测试 | C# 能力或原生 Windows 控件需求明确占优时，WPF/WinUI 可升首选；不要用虚构工时、未测 RAM 或框架流行度作决策 |

模型效果、推理吞吐不用于给 UI 壳评分：候选应尽量调用相同 worker/runtime/model。真实 worker 通过模型实验后，再做壳与 worker 的发行 smoke；模型下载不应成为早期 UI 比较的前置条件。

## 9. 证据版本与交接边界

官方资料访问日均为 2026-10-03。Qt 文档本次页面呈现为 6.12.0/6.12，另核对了明确标注的 6.10 后端弃用信息；这不是对 6.12 稳定发行状态或 PySide wheel 可用性的确认。Tauri 文档为 v2，sidecar 页标注 2026-06-15 更新；Electron 为滚动 latest 文档；.NET Kill 为 net-10.0 参考；Windows 部署总览标注 2026-08-17。实现前须另锁稳定版本与实际包，不把滚动 docs URL 当 immutable build manifest。

CC Design 可立即使用：单控制器/单项目 writer、独立 worker、显式本地/BYOK 路由、按修订提交产物、可取消任务、时间映射、资源分包与离线就绪检查。CC Design 不应把本报告首选当硬性框架约束，也不重新引入 V1 兼容或迁移。尚需确认设计切片、最低硬件/Windows 范围、分发方式与许可路径，再执行最小壳实验。
