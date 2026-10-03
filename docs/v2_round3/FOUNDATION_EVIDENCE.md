# 桌面基础证据：Qt Quick/QML 与 Tauri 2

资料访问日期：2026-10-03。状态：研究完成，框架未选定；未实现切片、测性能、安装依赖或下载模型。下文明确区分上游事实与工程建议；本文不是法律批准或用户批准的性能门槛。

## 1. 决策边界

项目输入：[Round 2 架构](../v2_discovery_round2/01_GREENFIELD_ARCHITECTURE.md)、[范围契约](../v2_discovery_round2/06_V2_DESIGN_SCOPE_CONTRACT.md)、[领域模型](../v2_discovery_round2/04_DOMAIN_WORKFLOW_MODEL.md)、本地未纳入 Git 的 UI 说明 `UI Design/v2/DESIGN_NOTES.md` 及 HTML 的编辑/快捷键/布局相关片段。UI 正在修改，本稿不修改它，也不把原型当作 Human UI Gate 已通过。

用户政策：绿地、无 V1 兼容；本地 ASR；翻译/TTS 本地优先，外部仅显式 BYOK；可扩展语言，EN/ZH/FR 为锚点；单旁白预设声线；不做克隆、说话人分离、唇同步、云 ASR。布局为预设、splitter、显隐及左右互换，不研究自由 dock。源文字编辑单位是 **span**，不能沿用早期范围稿“按 cue 编辑源文”的措辞。

**本轮不能选赢家。** Qt 的媒体/列表基础与较少应用语言，Tauri 的 Web 文本生态与 Rust host，都是待测成本假设。按 [切片契约](FRAMEWORK_SLICE_CONTRACT.md) 比较；先等待 Human UI Gate，再锁设计快照和平台。Round 2 的 Qt 暂定首选不构成决定。

## 2. Windows 打包、许可与更新

| 问题 | 上游事实与来源 | 工程含义／未证实项 |
|---|---|---|
| PySide 打包 | `pyside6-deploy` 基于 Nuitka，支持 QML 部署配置。[Qt deploy](https://doc.qt.io/qtforpython-6/deployment/deployment-pyside6-deploy.html) | 能打包入口不证明 QML imports、Multimedia、worker DLL 与字体齐全。必须验证无 Python/开发工具的实际安装产物。 |
| Qt 许可 | Qt for Python 提供 LGPLv3/GPLv3/商业路径，模块与第三方组件分别有许可。[Qt Python licenses](https://doc.qt.io/qtforpython-6/licenses.html) | 先确定模块与构建再做 SBOM；商业收费不自动意味着必须买商业版，也不自动证明 LGPL 义务已满足。 |
| LGPL 义务 | Qt 官方列出通知、适用库源码、修改/重新链接或替换库、相关安装信息等义务。[Qt LGPL obligations](https://www.qt.io/development/open-source-lgpl-obligations) | 动态链接不是自动合规；须验证对应源码/构建材料、通知及实际替换路径。签名更新不能意外阻断适用替换权。商业合同另审，本稿不作法律批准。 |
| Tauri installer | 支持 NSIS/WiX MSI，列出 WebView2 bootstrapper、offline installer、Fixed Runtime 等分发选择。[Windows installer](https://v2.tauri.app/distribute/windows-installer/) | bootstrapper 不等于离线包；完整包比较必须包含 WebView2、VC runtime、worker、媒体依赖。 |
| WebView2 | Evergreen 可共享并自动更新；Fixed Version 随应用管理。必须考虑 runtime 不存在的设备。[Microsoft distribution](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution) | Evergreen 漂移影响复现；Fixed 可控但补丁由产品维护。Microsoft runtime 再分发条款不由 Tauri 源码许可替代。 |
| 签名 | Tauri updater 验证更新签名，Windows Authenticode 为独立发行步骤。[Updater](https://v2.tauri.app/plugin/updater/)、[Windows signing](https://v2.tauri.app/distribute/sign/windows/) | 更新签名、代码签名、资源 hash 不可互代。Qt 需同等可信更新方案；首版可用签名安装器手动升级。测试密钥不代表生产证书或 SmartScreen 信誉。 |

建议：壳、worker runtime、模型、FFmpeg、字体分别锁版本；运行任务固定资源，升级不原地替换占用中的二进制。安装器回退不等于项目 schema 可降级。SQLite 发行门核验实际链接的 `sqlite_version`；[SQLite WAL §11](https://www.sqlite.org/wal.html) 记录 WAL-reset bug 与修复版本，不能只依据 Python/Rust 包名判断。数据库恢复由本轮数据层研究细化。

## 3. 播放同步与代理

上游事实：Qt Multimedia 当前文档以 FFmpeg 为主后端，Windows Media Foundation 后端自 6.10 弃用；官方要求测试目标平台，也明确 Qt 许可不含 codec 专利费用。[Qt Multimedia](https://doc.qt.io/qt-6/qtmultimedia-index.html) 官方 [QML Media Player 示例](https://doc.qt.io/qt-6/qtmultimedia-video-mediaplayer-example.html) 证明可组合播放控件，不证明精确剪辑或长片同步。

HTML media 标准规定播放、seek、time ranges 和错误状态；可用 `<video>` 不代表支持 FFmpeg 的全部格式。`currentTime`、`seeked` 或 UI 定时器也不是实际音画输出同步的测量结果。[HTML media](https://html.spec.whatwg.org/multipage/media.html)

工程建议（两壳相同）：

- 播放器媒体时钟驱动播放头；墙钟只测延迟。保存源 PTS/timebase、音轨起点和代理到源映射，不以总片长比替代真实映射。
- 先试源文件；失败或交互不达已约定目标时生成可追溯代理。代理耗时、体积、必需比例和缓存成本计入比较，不覆盖原媒体。
- 最终效果预览使用共同字幕渲染器、字体与导出配置生成验证短片。HTML/QML 文本叠层仅作编辑辅助，不能声称与成片一致。
- 两壳使用同一音画标记及 seek 序列；分别测源播放和代理播放。缺音轨、损坏代理、Range/seek 失败进入可恢复状态。

## 4. 一万条 span、IME、重音和无障碍

| 主题 | 上游证据 | 必须通过切片确认 |
|---|---|---|
| Qt 列表 | ListView 按视口创建、可回收 delegate；官方禁止仅在 delegate 保存持久状态。可变行高影响尺寸估计，扩大缓存增加内存。[ListView](https://doc.qt.io/qt-6/qml-qtquick-listview.html) | 草稿、修订、锁、selection 按稳定 ID 存储；滚走/回来不丢字、不串行。改宽度导致换行时不跳错目标。 |
| Qt 文本 | TextEdit 有 composition、selection、方向相关 API。[TextEdit](https://doc.qt.io/qt-6/qml-qtquick-textedit.html) | API 存在不等于中文候选确认时全局 Enter/Esc 正确让路，须真实 Windows IME 手测。 |
| Web 文本 | UI Events 定义 composition 生命周期和 `isComposing`。[W3C UI Events](https://www.w3.org/TR/uievents/#events-compositionevents) | composition 中不能任意回收编辑节点；快捷键按编辑上下文路由。`contenteditable` 本身不是万行编辑器。 |
| 字符边界 | Unicode grapheme 规则区分用户感知字符与编码单元。[UAX #29](https://www.unicode.org/reports/tr29/) | Python code point、JS UTF-16、Qt/QML offset 不能直接互传。边界注明 revision 和单位，避免拆坏组合重音、emoji、复杂脚本。 |
| Qt 无障碍 | 自定义 Quick 元素需要 Accessible 名称、角色与操作。[Qt accessibility](https://doc.qt.io/qt-6/accessible-qtquick.html) | 用 Narrator/UI Automation 检查名称、行序、锁定/过期、焦点恢复；绘制出的时间线并不自动可访问。 |
| 分隔条 | APG 给出 separator 数值、面板关系及键盘模式；页面注明示例评审尚未完成。[WAI splitter](https://www.w3.org/WAI/ARIA/apg/patterns/windowsplitter/) | 作为模式参考，不作自动合规凭证。两壳均测数值读出、键盘上下限与隐藏面板后的焦点。 |

工程建议：EN/ZH/FR 均轮换为源语言；法语 dead keys、NFC/NFD、多行粘贴、撤销和 RTL 混排使用实际输入设备测。RTL 是可扩展编辑/显示测试，不意味着阿拉伯 ASR/TTS 已获验证。

## 5. 预设布局与时间线

上游事实：Qt SplitView 提供分隔调整、尺寸约束、saveState/restoreState。[SplitView](https://doc.qt.io/qt-6/qml-qtquick-controls-splitview.html) 它不自动实现预设目录、左右交换、用户偏好迁移与应用焦点策略。因此 UI 说明“直接覆盖全部能力”只能解释为可组合基础，不作为零成本结论；本轮不修改该说明。

Qt Quick Timeline 是关键帧属性动画类型，不是现成多轨字幕剪辑器。[Qt Timeline](https://doc.qt.io/qt-6/qml-qtquick-timeline-timeline.html)

工程建议：布局存用户偏好（schemaVersion、preset、显隐、side、尺寸、每工作区选择），不改变项目修订。换 DPI/窗口尺寸后 clamp，损坏偏好回 Standard。时间线分别显示 Evidence / Transcript / Cues / Dub，按可见时间区间绘制，波形按缩放级别使用摘要；拖动与键盘/数值框走同一领域命令。自由 dock 和浮窗不进入实验。

## 6. 成熟第一方实现证据

| 直接源码 | 本轮可观察机制 | 不能外推 |
|---|---|---|
| [Shotcut timeline.qml](https://raw.githubusercontent.com/mltframework/shotcut/master/src/qml/views/timeline/timeline.qml) | 实际产品使用 QML/Flickable、独立轨道与 ruler、缩放滚动协调、波形重绘和像素对齐。 | 它有自己的 C++/MLT 后端，不证明 PySide/QMediaPlayer 同等表现；文件 GPLv3+，仅研究职责分离，不直接复制进未确定许可的产品。 |
| [GitButler Tauri config](https://raw.githubusercontent.com/gitbutlerapp/gitbutler/master/crates/gitbutler-tauri/tauri.conf.json)、[Cargo manifest](https://raw.githubusercontent.com/gitbutlerapp/gitbutler/master/crates/gitbutler-tauri/Cargo.toml) | 真实产品提供可检查的 Tauri host、插件及发行配置。 | Git 客户端不证明视频同步、万行编辑或内存达标；其权限也不是本项目默认值。 |
| [VS Code ListView](https://raw.githubusercontent.com/microsoft/vscode/main/src/vs/base/browser/ui/list/listView.ts) | 产品源码分离行缓存、动态高度、可见范围、滚动和无障碍集合位置。 | 不是 Tauri/WebView2 对照成绩，也不是可拷走即用的独立字幕编辑器。只支持 Web 实现需要这些机制的判断。 |

上述机制证据比 API 存在更具体，但均未在本轮复现产品 benchmark。链接为滚动 main/master，未固定 commit；后续借鉴代码需锁 revision、查许可和依赖。没有同任务、同机器证据时，不能以成熟产品选型代替本产品实验。

## 7. IPC、崩溃和性能

上游事实：Tauri sidecar 支持外部二进制，target triple 与 shell 权限需配置；capabilities 约束暴露能力，不自动验证业务 revision 或产物路径。[Sidecar](https://v2.tauri.app/develop/sidecar/)、[Capabilities](https://v2.tauri.app/security/capabilities/) Qt QProcess 提供进程通信，Windows kill 使用 TerminateProcess 终止目标进程。[QProcess](https://doc.qt.io/qt-6/qprocess.html) Windows Job Objects 提供进程组管理/终止机制。[Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)

建议：Qt 的 Python 控制器与 Tauri 的 Rust host 分别作为唯一项目 writer，调用同一无模型 stub。有界协议含 task/attempt/inputRevision；stdout 仅协议，stderr 脱敏；大产物走受管 manifest。创建进程与 Job Object 归属必须避免竞态，取消等待整树退出，拒收迟到完成。独立 worker 是崩溃隔离，不是恶意代码沙箱。

WebView2 有 browser/renderer 等多进程及不同故障事件。[Process model](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/process-model)、[Process events](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/process-related-events) 不可据此假定 Tauri/wry 已暴露全部恢复钩子。需分别杀 worker、Qt GUI、Tauri host 与 WebView renderer，验证已提交数据和恢复边界。

微软提供进程内存采集 API。[PSAPI](https://learn.microsoft.com/en-us/windows/win32/psapi/collecting-memory-usage-information-for-a-process) 建议记录整树 private bytes、private working set、峰值和进程角色，包含 WebView2 browser/renderer/GPU；共享 working set 不可简单相加冒充物理 RAM。GPU 内存另计。冷/热启动、UI ready、项目可编辑、首帧和 worker ready 分开计时。没有测量前不宣传谁更轻或更快。

## 8. 版本与开放项

所有链接访问日为 2026-10-03。Qt 多数滚动页呈现 6.12.0，Timeline 页呈现 6.11.2；不构成稳定 wheel/SDK 可用性确认。Tauri 为 v2 滚动文档，微软/W3C/Unicode/源码也会变化。实验锁实际 Qt/PySide/Nuitka、Tauri/wry/WebView2、OS、驱动、字体、FFmpeg、SQLite 与构建摘要。

可固定的是单控制器、独立 worker、稳定 span 身份、输入修订、源时间映射、本地/BYOK 政策和非自由 dock 布局。尚待 Human UI Gate 与实验前确认：最低硬件/Windows、数值预算、发行/许可方案及框架赢家。允许的实验结论包括两者均不合格或证据不足；不为得出赢家而放宽数据正确性。
