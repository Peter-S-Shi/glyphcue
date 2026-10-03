# GlyphCue V2 Round 3 决策登记

日期：2026-10-03。“关闭”只表示当前决策层级已足够继续设计，不代表模型、发行包或质量已经通过。`PENDING — Requires Product Authority` 表示等待证据后的产品范围决定；`PENDING — Requires Artifact/Provider Audit` 表示尚无具体审计结论，不等同于已确认的外部阻断。

| 项目 | 状态 | 当前结论 / 关闭条件 |
|---|---|---|
| V2 产品方向 | CLOSED — Product Authority | 绿地本地媒体本地化；本地 ASR 是核心输入；V1 无兼容义务 |
| V2.0 产品工作流 | CLOSED — Product Authority | 双语字幕翻译与许可预设声线的单旁白配音均为必需工作流；许可或可行性失败时，须通过明确 Product Gate 重定范围 |
| 翻译/TTS 路由 | CLOSED — Product Authority | 本地优先；外部仅显式 BYOK；无静默上传/回退 |
| 配音范围 | CLOSED — Product Authority | 许可明确的预设声线、单旁白；克隆、多角色自动复刻、唇同步、分离延后 |
| 语言边界 | CLOSED — Product Authority | EN/ZH/FR 首批锚点，能力按阶段和有向 pair 扩展 |
| V2.0 语言发布矩阵 | PENDING — Requires Product Authority | 六方向可全部评价；先取得各阶段与有向 pair 的实测结果，再由产品方明确批准发布矩阵，不能默认为六方向全上 |
| 领域关系 | CLOSED — Evidence-backed Engineering Decision | Source Transcript 的 revision/provenance 是语义真源；Subtitle Cues 是派生显示单元；Evidence→Transcript→Cue/Translation→Dubbing→Take→Placement→Snapshot；稳定 ID、late-result fencing |
| 项目存储 | CLOSED — Evidence-backed Engineering Decision | SQLite 元数据 + 受管不可变产物目录；worker 无 DB 写权；源媒体引用而非覆盖 |
| SQLite 发行版本 | PENDING — Requires Prototype/Benchmark | 必须核验实际 sqlite_version/source ID，WAL 需 3.51.3+ 或批准回移版本；需故障注入/备份恢复 |
| worker 所有权 | CLOSED — Evidence-backed Engineering Decision | 一个 controller/项目 writer；能力 worker 独立进程；Windows Job Object；默认一个重 GPU 槽 |
| worker 协议 | PENDING — Requires Prototype/Benchmark | 需用同一个 stub 验证 framing、attempt fencing、取消、OOM、迟到和孤儿恢复 |
| Qt Quick vs Tauri | PENDING — Requires Prototype/Benchmark | Human UI Gate 是前置条件；通过后用 [切片契约](FRAMEWORK_SLICE_CONTRACT.md) 双实现并比较，不预选框架 |
| 媒体预览 | PENDING — Requires Prototype/Benchmark | 需 VFR/长 GOP/多音轨/代理/seek/同 renderer 短片验证 |
| ASR 引擎 | PENDING — Requires Prototype/Benchmark | 同源 Whisper CT2 vs whisper.cpp；Qwen ASR+aligner 质量挑战者；无纸面赢家 |
| AMD/Intel 后端 | PENDING — Requires Prototype/Benchmark | CT2 ROCm wheel/源码可行不等于 Radeon Whisper 通过；whisper.cpp 源码 preset 不等于发行包 |
| 翻译模型 | PENDING — Requires Prototype/Benchmark | llama.cpp + Qwen3 4B/8B 候选；六方向质量和结构校验未测 |
| TTS/声线 | PENDING — Requires Prototype/Benchmark | Kokoro 与 Qwen CustomVoice 候选；每 voice、G2P、法语口音、实际时长和许可逐项验收 |
| 资源 manifest/按需下载 | CLOSED — Evidence-backed Engineering Decision | staging、哈希、许可、依赖、能力证据和 rollback；首轮按阶段按需包 |
| 在线 catalog 信任 | PENDING — Requires Prototype/Benchmark | 需签名 manifest、反回滚/撤销/过期策略；hash 不能单独认证来源 |
| 精确商业捆绑 | PENDING — Requires Artifact/Provider Audit | Qt/FFmpeg/Kokoro G2P/voice/WebView2/weights 的精确发行制品与许可链待审计；发现明确禁止或无法满足的条款才标记外部阻断，本轮未批准发行 |
| BYOK provider | PENDING — Requires Artifact/Provider Audit | 服务/地区/模型/voice/留存/输出条款待按具体 provider 审计；adapter 可设计，不能预装承诺；明确不相容条款才构成外部阻断 |
| UI 设计契约 | PENDING — Requires Human UI Gate | CC 样本 correction pass 已记录，但无本轮截图级人工验收；设计说明不是批准记录 |
| V2 自身 schema 演进 | CLOSED — Evidence-backed Engineering Decision | format version、minReader、备份前迁移、副本校验、拒绝降级；不做 V1 迁移 |
| 复杂语言扩展 | DEFERRED — Outside V2.0 | 先保留 capability manifest；ES/IT/pt-BR 后续优先研究，RTL 先合成文本验证 |

决策条目与研究证据的关系见 [ENGINEERING_READINESS_REPORT](ENGINEERING_READINESS_REPORT.md) 及其来源索引。Round 1 文件中的 Optional 指用户可跳过的处理阶段；V2.0 发行范围以 [V2_SCOPE_DRAFT](../v2/V2_SCOPE_DRAFT.md) 第 3 节和本登记表的产品工作流决策为准。任何“product-supported”标签必须同时具备具体资源 revision、测试集、硬件 profile、质量/安装/隐私/许可证据。
