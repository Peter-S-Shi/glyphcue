# Qt Quick 与 Tauri 代表性交互切片契约

状态：待 Human UI Gate；这是未来两条实现路径必须使用的同一工程实验，不是本轮原型，也不是框架选择。

## 目的与固定边界

用同一份合成项目数据验证框架承担 GlyphCue 编辑工作台的关键风险：长列表、文本输入、来源关系、时间线、媒体预览、布局、任务取消和恢复。两条切片禁止接入真实模型、付费 provider 或用户媒体。Qt 版本可用 QML + Python controller；Tauri 版本可用 TypeScript UI + Rust controller；两者调用同一个 stub worker 协议和同一 fixture。

切片不比较品牌视觉、空壳安装大小或未测模型速度。两边使用相同字体文件、色彩 tokens、窗口尺寸、DPI、合成媒体、任务延迟和失败注入。实现前冻结 OS build、Qt/PySide 与 Tauri/WebView2 版本、编译器、依赖 lockfile 和 fixture hash。

## 固定 fixture

- 10,000 个 Source Transcript span；每个 span 有稳定 ID、source revision、1–2 条 provenance 范围、估计或确认时间。
- 目标语言为 `en-US`、`zh-Hans`、`fr-FR`，再加入 `ar` 合成 RTL 文本以测试扩展边界；所有能力 chip 标为 synthetic。
- 至少一条跨 span 的 Dubbing Script、一个锁定且过期的翻译、一个迟到候选、一个过时 take、四条 Evidence/Transcript/Cues/Dub 轨道。
- 合成媒体同时提供可直接预览的短文件和需要代理的容器；包含多音轨、VFR/长 GOP、Unicode 和空格路径副本。
- stub worker 支持准备延迟、逐单元进度、协作取消、挂起、OOM、非零退出、迟到结果、损坏 manifest、attempt 重试和模拟磁盘不足。

## 必须完成的用户动作

1. 打开项目，确认源语言为 EN，再切换到 ZH 和 FR fixture；所有“源 → 目标”、方向文字、布局顺序和资源能力动态改变，不能出现硬编码 `EN →`。
2. 滚动到任意 span，编辑中文、法语重音（含 dead key）、组合 `é`、emoji、阿拉伯文和长文本；输入法组合期间不能提交或触发快捷键。滚出视口再回来，文本、焦点、selection、锁和 revision 必须仍属于同一 ID。
3. 在稳定光标处拆分、合并 span；两边显示新 ID、旧 ID 和 provenance 范围；旧翻译进入候选，不能按数组位置自动重挂。编辑后撤销、恢复为新 revision，再跳到下游翻译与配音段。
4. 在 0–45 秒时间窗拖动、输入和键盘微调 span/cue/take placement；播放器时钟、时间线光标、列表选中项保持同一媒体时间。隐藏或移动 Player、Inspector、Timeline，保存五个批准的预设/自定义布局，重启后恢复用户偏好并在损坏时回 Standard。
5. 运行 stub ASR/translation/TTS/export；取消后看到 `cancelling`，确认整棵进程树退出后才是 `cancelled`。重启应用后将未完成 attempt 显示为 `interrupted`，已提交单元可重试，迟到旧 attempt 不能覆盖新 revision。
6. 选择本地翻译和显式外部 provider 模拟；外部确认必须列出 provider、region、发送 units/revision、字符数、费用规则和“不自动切换”。切换离线后本地编辑/导出继续，外部按钮禁用；禁止把 key 显示给 UI 或 worker 日志。
7. 冻结 Export Snapshot，继续编辑，再验证导出结果仍指向旧快照；注入缺字体、过期翻译、未选 take、源媒体搬移和磁盘不足，看到清楚的 Review/Blocks 和可恢复操作。

## 可观察通过条件

只有下列事实全部在两边成立，才可称“切片行为通过”：

| 类别 | 记录的证据 |
|---|---|
| 数据正确性 | 稳定 ID、revision、provenance、locked/stale、snapshot 和 late-result 断言；不得只用截图判断 |
| 编辑器 | 10k 滚动无错行绑定；IME/重音/RTL/字素边界；焦点、selection、undo 和键盘替代操作可重复 |
| 时间媒体 | 源/代理映射、音轨选择、seek/播放头、四轨选中关系；播放器失败有代理/错误状态 |
| 生命周期 | 取消、hard-kill、OOM、crash、retry 的最终状态和残留进程清单；无 worker 直接写 DB |
| 外部边界 | 真实发送 payload 不执行；UI 模拟披露与 adapter manifest 一致；offline 不发请求 |
| 资源与包 | 干净普通用户安装、WebView2 方案、QML 插件/sidecar发现、Unicode/长路径、升级回滚记录 |
| 可访问性 | Narrator/UI Automation 或等价树中的名称、角色、行序、锁/过期状态、separator 键盘范围和焦点恢复；不以 `aria`/Accessible 属性存在代替测试 |

每类至少重复三次；性能另记录冷启动、UI-ready、首帧、编辑响应、私有 bytes/working set、worker ready、磁盘和 GPU 进程。不得把共享 working set 相加为 RAM；失败要保留原始日志的脱敏摘要。建议达到“没有数据错误、无残留进程、无意外网络、关键动作可访问”后，再比较维护成本与安装复杂度；效率数字没有预设通过线。

## 失败与停止规则

以下任一情况直接标记候选不通过或“证据不足”，不得通过减少 fixture 或关闭错误来取得通过：

- 任意 split/merge、翻译 late result、locked stale 或 snapshot 输出覆盖新版内容；
- 取消后残留属于该任务的 worker/FFmpeg/GPU 进程，或旧 attempt 能提交；
- 中文 IME 确认、法语重音、RTL/字素编辑破坏文本或焦点；
- 资源缺失时静默下载、静默切换云端/小模型/另一 provider，或将 key 进入 UI/日志；
- 媒体 seek/代理映射错误未进入可恢复状态；导出 preview 与最终 renderer 证据不一致；
- clean install、更新、回滚、WebView2/QML/sidecar 发现不能在固定支持范围内复现；
- 任意视觉优点被用来掩盖数据、隐私、许可或恢复失败。

实验可在修正后从同一 fixture 重跑；不得同时改框架、worker 协议、数据模型和阈值。若两边均无法满足，结论为范围或技术方案需重新开 Gate，而不是强选赢家。

## 交付记录

保存：fixture/hash、源码 lockfile、安装包/hash、Windows/驱动、屏幕尺寸/DPI、测试步骤、原始事件日志、脱敏内存/时间表、失败截图和每项 verdict。该契约本身不要求现在制作 Qt/Tauri 原型；它要求 UI Gate 通过后用同一行为切片关闭 PG-05。
