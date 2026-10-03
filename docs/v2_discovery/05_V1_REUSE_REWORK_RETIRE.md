# GlyphCue V1 → V2：REUSE / REWORK / RETIRE

研究日期：2026-10-03。本文是 V2 Discovery 研究，不修改 V1 产品定义、ADR、状态或代码。

## 1. 核实的基线

- 本地审阅 HEAD：`ec631ee2c2097d3297c87a0a24655a88a3baeda1`，分支 `milestone/14-portfolio-packaging`。
- 实时远程 main：`7882562bf4812bf2b986bd729bfba4d5c5332f90`。GitHub compare 显示它比本地 HEAD 多一个合并提交、文件差异为空；因此本次审阅的已跟踪源代码与该远程快照一致。这不是一次 fetch 或本地分支同步。
- [远程比较证据](https://github.com/Peter-S-Shi/glyphcue/compare/ec631ee2c2097d3297c87a0a24655a88a3baeda1...7882562bf4812bf2b986bd729bfba4d5c5332f90)；[V1 发布](https://github.com/Peter-S-Shi/glyphcue/releases/tag/v1.0.0)。发布资产元数据已读取，未重新下载或验包。
- 本地未跟踪的 V1 Archive 属于既有用户材料；不将其视为已合并代码，也不删除、执行或合入其中补丁。
- V1 的既有测试与发行证据是历史证据。本次未运行应用、测试或模型，不能把旧通过数量当成 V2 验收结果。

## 2. 分类含义

**REUSE**：保留边界、实现或测试资产作为候选，接入 V2 后仍需回归；不代表逐字复制即可交付。**REWORK**：保留解决的问题与经验，但调整模型、实现或用户流程。**RETIRE**：退出 V2 产品主链，保留 V1 历史；不意味着现在删除文件。

## 3. 子系统判定

以下相对链接从本文件指向已审阅的源代码。行号是当前快照的定位提示。

| 子系统 | 判定 | 代码证据与原因 | V2 方向 / 必须重新验证的点 |
|---|---|---|---|
| 供应商适配器边界 | REUSE | [subtitle_io.py](../../src/glyphcue/adapters/subtitle_io.py)、[test_boundaries.py](../../tests/adapters/test_boundaries.py) 限制第三方对象进入领域层 | ASR、翻译、TTS、媒体生产各有能力边界；外部 DTO 转换为产品对象 |
| Qt 播放控制、选段复听、AB 循环 | REUSE | [playback_controller.py](../../src/glyphcue/ui/playback_controller.py):9,86,117，真实 QMediaPlayer/QAudioOutput | 视频及纯音频试听；核对变速、长视频、声轨选择和生成配音预览，不能假定已有双音轨混音 |
| 时间线与源媒体时间语义 | REWORK | [timeline_mapping.py](../../src/glyphcue/application/timeline_mapping.py) 用源文件秒数；[pyav_media_source.py](../../src/glyphcue/adapters/pyav_media_source.py) 使用 PTS | 明确容器起点、选段 offset、重采样、VAD 裁切的可逆映射；展示波形不应引入帧号/fps 时间假设 |
| SRT/VTT 解析、逐条导入警告 | REUSE | [pysubs2_subtitle_io.py](../../src/glyphcue/adapters/pysubs2_subtitle_io.py):34 | 兼容已有字幕作为可选导入/校正入口；语音转录仍是主入口 |
| 字幕原子写入、导出前提交编辑 | REUSE | 同文件:75；[export_controls.py](../../src/glyphcue/ui/export_controls.py):104 先拒绝源覆盖、再提交待保存编辑 | 保留防源覆盖、导出最新修订、不导出 discarded 内容。原子 rename 不等于整个多文件任务事务 |
| 文本转录导出 | REUSE | [transcript_export.py](../../src/glyphcue/adapters/transcript_export.py) | 继续提供纯文本；可增加保留词时间和来源的结构化交换格式 |
| Cue 与 LanguageLayer | REWORK | [cue.py](../../src/glyphcue/domain/cue.py):10；[language_layer.py](../../src/glyphcue/domain/language_layer.py):7 强制所有语言共用 Cue 时间 | 源转录修订、字幕分段、翻译片段、配音片段需要显式关联；不能让一个共享时间的层包办所有阶段 |
| 原始 Observation / Provenance | REWORK | [observation.py](../../src/glyphcue/domain/observation.py) 混有 OCR confidence、ROI、geometry、frame；[provenance.py](../../src/glyphcue/domain/provenance.py) 只有字幕导入与 OCR 来源 | 保留原始证据不可被人工结果覆盖的原则；新增 ASR run、音频范围、segment/word 证据、模型 revision、解码参数和编辑修订 |
| TrackGroup / ROI | RETIRE | [track_group.py](../../src/glyphcue/domain/track_group.py) 的产品身份就是视觉区域 + 预期语言 | 音轨、字幕轨、说话人不是视觉区域，不给 ASR 填虚假的 ROI |
| 编辑文本、改时间、split/merge、review state | REWORK | [cue_review_actions.py](../../src/glyphcue/application/cue_review_actions.py):37,62,83,149 已有纯函数动作 | `split_cue` 当前将整段文本复制给两半，不能当作词级切分实现。新增词边界/手工文字边界、撤销重做、修订与衍生产物失效 |
| QA 工作区、筛选、编辑提交纪律 | REWORK | [reconstruction_qa_workspace.py](../../src/glyphcue/ui/reconstruction_qa_workspace.py):254,629,684 | 保留复核交互经验，围绕音频/波形、源文/译文、配音试听重做信息组织；不沿用 Path A/Path B 标签 |
| Review Priority 思想 | REWORK | [review_priority.py](../../src/glyphcue/application/review_priority.py):30,111 明确分数不是校准概率，但输入仍为 OCR/视觉信号 | ASR 静音幻觉、疑似缺字、边界异常、译文漏段、术语违例、配音溢出分别解释；不把 OCR 分数映射成 ASR 正确率 |
| SQLite repository / 事务迁移 | REWORK | [repository.py](../../src/glyphcue/persistence/repository.py):84 按 source 全量替换；[migrations.py](../../src/glyphcue/persistence/migrations.py) 事务包含版本记录 | 复用事务与 repository 模式，重新设计项目/任务/修订/产物关系。建议 V2 独立数据空间，V1 只经可选导入进入 V2；不直接自动升级唯一 V1 DB |
| 源身份 | REWORK | [source_identity.py](../../src/glyphcue/application/source_identity.py) 用规范化绝对文件路径 | 本地路径可以是 locator，但不能唯一充当可迁移项目身份；媒体换位置、换内容都要可识别，导出报告不泄露路径 |
| 后台 Job / 取消 / 进度 | REWORK | [jobs/job.py](../../src/glyphcue/jobs/job.py):37,85 是 Python daemon thread、协作取消；异常只转 FAILED | 保留状态语义，增加独立 worker、结构化错误、阶段进度、资源释放、持久任务产物与安全重试。Qt 线程取消不会强制终止 GPU/native 调用 |
| 图像变化检测、选择性 OCR、跨帧共识、视觉语言分层 | RETIRE | `application/ocr_*`、`hybrid_*`、`consensus_reconstruction.py`、`language_layer_assignment.py` 等 | 不为新 ASR 入口继续维护核心算法；旧性能指标不适用于新路线 |
| PaddleOCR / DirectML / ROI 叠层与运行时模型绑定 | RETIRE | `adapters/paddleocr_*`、`directml_*`、`runtime_models.py`；`ui/video_roi_overlay.py` | 从 V2 默认运行时与下载依赖中去掉 OCR。DirectML OCR 成功不证明语音模型支持 DirectML |
| 滚动字幕重建、Cue Cleaner | REWORK | `application/reconstruction.py`、`cue_cleaning.py`、`adapters/cue_cleaner_v0_6_1.py` | 仅可选导入清理或明确预览后应用；ASR 的重复可能是真实口吃/强调，不能默认套视觉/滚动去重规则 |
| FFmpeg 媒体成片 | REWORK（需新实现） | [media_transform.py](../../src/glyphcue/adapters/media_transform.py):7 只有 Protocol；[ADR 0004](../adr/0004-media-architecture.md) 明确无具体实现；源码搜索与之吻合 | 新增真正的字幕烧录、软字幕/音轨封装、配音混音、进度/取消/失败处理；不能把接口存在报作功能复用完成 |
| UI tokens / splitter / 可折叠布局 | REUSE | `ui/design_tokens.py`、`collapsible_section.py` 及对应 UI 测试 | 是否沿用视觉样式交给设计阶段；沿用布局元件不要求沿用 OCR 三栏结构 |
| 评测脚手架、合成输入与隐私边界 | REWORK | `tests/`、`evaluation/`、`benchmarks/` | 复用 mock/边界/故障测试模式；新建 ASR、六方向翻译、三语言 TTS 和同步指标。旧 OCR ground truth 不能作 V2 质量证明 |
| 安装器、SBOM、模型清单、签名和卸载保护经验 | REWORK | `tools/packaging/`、`docs/v1_public_release_dependency_provenance.json` | 复用溯源、hash、干净环境、离线启动和不删用户数据的验收方法；运行时/模型/编解码器变更后重新发行审计 |

## 4. 两个容易误读的现状

README 提到 ASS 能力，但本地用户可见导出枚举 `ExportControls._FORMATS` 实际是 SRT、VTT、Readable Transcript、AI-ready Transcript。pysubs2 的通用格式能力与已交付的 UI 出口不是同一件事。V2 的 ASS 样式/烧录属于新增明确范围。

本地未纳入 Git 的旧 ASR 许可研究 `docs/asr_licensing_research.md` 将 ASR 限定为 OCR 的辅助证据。那是 V1 当时的范围；本次用户明确指定 ASR 为 V2 主输入，因此该产品限制不迁入 V2，旧文档保持原样。其按确切二进制、权重和来源审计的做法仍适用。

## 5. 设计约束建议

保持 UI → 应用服务 → 领域数据 → 适配器边界即可；当前证据不足以支持为 V2 更换全部语言或桌面框架。现有 Python/PySide6 是首个评估基线，设计代理仍可提出有依据的替代方案。

把耗时 ASR/TTS/FFmpeg 与界面生命周期分离；将「用户编辑后的源文」与「原始识别结果」分离。选区重跑产生新的结果候选，必须与已编辑范围合并或让用户选择，不能全项目重写。

字幕显示时间、原音频单词时间和配音实际长度是三个不同事实。V1 的同一 Cue 多语言层可作为简单双语显示视图，但不宜成为所有事实的唯一持久模型。

保留 Qt 不代表许可证无需复查。Qt for Python 的 LGPLv3/GPLv3/商业授权路径、实际 Qt 模块与第三方 FFmpeg 后端须单独盘点；这与本项目自身 MIT 是不同层次。[Qt for Python 官方许可说明](https://doc.qt.io/qtforpython-6/licenses.html)。

烧录字幕需要渲染过滤器并重新编码视频；只封装字幕或替换音轨在容器/codec 兼容时才可复制视频流。具体 FFmpeg 构建、libass、编码器、字体均需发行前核验。[FFmpeg filters](https://ffmpeg.org/ffmpeg-filters.html#subtitles-1)、[FFmpeg legal](https://ffmpeg.org/legal.html)。

## 6. 本票结论

采用选择性复用与领域模型改造；退出视觉 OCR 主链，不进行无依据的全部重写。本结论可供设计讨论，不授权本轮删除、迁移或实现任何生产模块。
