# 项目持久化、资源交付与隐私边界

研究日：2026-10-03。覆盖 Track B / D / G。下文“采用”是研究范围内的工程基线建议，不表示 schema、下载器或恢复逻辑已经实现。产品约束以第三轮用户授权为准；本轮未运行数据库、模型或网络隔离实验。

## 1. 最小项目形态

| 选项 | 优点 | 实际代价 | 判断 |
|---|---|---|---|
| 单个 JSON + 音频目录 | 易检查 | 修订、引用、任务提交和并发编辑都需自建事务/完整性机制 | 不作主存储 |
| SQLite 内含全部媒体 BLOB | 一个可搬运文件 | 大 take/媒体增加备份和迁移成本，外部媒体工具需提取 | 只放小结构数据 |
| 项目目录：SQLite + 受管不可变文件 | 元数据有事务，大产物适合流式媒体工具 | 必须明确数据库与文件不是同一事务 | 推荐基线 |
| 全量事件溯源 / 服务端数据库 | 可重放或协同 | 首版无协作需求，增加投影、运维和迁移复杂度 | 不采用 |

SQLite 官方把它作为可选择的应用文件格式；这里选择“目录 + DB”是针对音频产物量的工程推论，不是 SQLite 对本产品的背书。[应用文件格式](https://www.sqlite.org/appfileformat.html)

建议布局（名称可在实现设计时调整）：

```text
project/
  project.sqlite             元数据、完整文本修订、来源、任务、导出快照
  assets/takes/<artifact-id>  已提交音频；以 ID 定位，摘要负责完整性
  assets/evidence/            大型原始识别结果（小结果可在 DB）
  staging/<attempt-id>/       未提交产物，不能被播放器当作有效 take
  recovery/                  隔离的孤儿/损坏文件与恢复说明
  backups/                   受控一致性备份；不是简单复制打开的 DB
```

源视频/音频默认只引用，不复制或写入。机器上的原文件 locator、用户窗格偏好、凭据引用和可重建缓存置于用户级应用数据；项目记录媒体内容身份、显示名及可选的安全相对定位提示。移动项目需要重新定位外部媒体。用户音频 take 是成果，不属于可自动清理缓存；波形、代理、缩略图、解码临时音频才是可重建派生缓存。

首版不需要自定义 ZIP 单文件项目格式或跨机器模型同步。基础可搬运性是关闭项目后复制完整项目目录、重新定位源媒体、提示缺少的 runtime/model；也可在后续验证后提供受控“另存项目副本”。模型文件和 API 密钥不进入项目副本。项目可能包含个人字幕和语音，仍属于用户私有数据，不适合直接进 Git。

## 2. 数据结构的必要约束

下面是逻辑记录，不要求每行都实现成独立表，也不要求通用图数据库。

| 记录组 | 最小关键内容 |
|---|---|
| Project / MediaAsset / AudioSelection | project ID、schema version、内容摘要与核验状态、stream/channel、源时间范围；locator 与内容身份分开 |
| Entity / Revision | opaque stable ID、类型、revision ID、父修订、文本/时间/设置、作者类别、当前选用指针；历史修订不可原地改写 |
| ProvenanceEdge | 起点/终点 revision、关系类型、原始证据 segment ID、可选字符范围和时间映射、准确/估计/未知标记 |
| Derivation | 输入 revision 集合、实际邻句上下文、术语/模板/schema、engine/model/voice/resource digest、参数、attempt、处理位置 |
| Artifact / Take | ID、相对受管路径、字节数/hash、格式、采样率、实际长度、生成配方、有效性；选择 take 独立于生成 take |
| Task / Attempt / WorkUnit | 操作意图、尝试 ID、活动 fencing token、输入快照、可提交单元、状态、错误、退出与取消事实 |
| ReviewDecision / Lock | 被锁实体/修订、用户确认动作、核对到哪个输入修订；“接受旧结果”不改写其生成来源 |
| ExportSnapshot / ExportResult | 确切选用 revision/take/布局/混音/字体/编码参数/时间映射、输出路径记录、校验、partial/成功状态 |

关键不变量：

1. 当前 UI 行号、文件路径、文本内容、模型 token 均不是实体 ID。数据库用外键、唯一约束及应用校验保护引用；所有连接明确启用外键，而非依赖默认值。[SQLite 外键](https://www.sqlite.org/foreignkeys.html)
2. span 拆分/合并产生新实体及 provenance edge，旧实体保留在历史中。允许多对多来源。人工补写的词可标“人工插入/无精确证据范围”，不得制造虚假的逐字映射。
3. 字符范围绑定文本 revision 和坐标单位。建议协议采用 Unicode code point，GUI 转换为自身索引并保持字素边界。相同词数的改字也可能破坏对齐；不使用空格词数相等推定映射有效。
4. 恢复旧稿是新修订；锁定仅保护覆盖。机器返回结果提交时同时检查源输入、目标当前修订、锁状态和 attempt：即便源没变，用户已手改目标时也不能覆盖。
5. 保留生成事实与复核事实的区别。例如译文生成于 source r1，用户对照 r2 后选择保留：记录 reviewedAgainst=r2，仍保留 generatedFrom=r1。不能通过修改 srcRev 抹去实际来源。
6. 修改源文标记直接/上下文依赖需复核。译文未重新确认时，其配音链保持上游待复核状态；稿件文本未变时，不声称已有音频本体损坏。用户确认保留后可继续使用其 take，避免无理由强制付费/重新生成。
7. 样式与分行只失效渲染；若某配音窗口真的绑定了 cue 时间，时间变化另触发 placement 检查。词级对齐是特定文本与音频的证据，不能把译文强行对齐原语音。
8. 源语言动态，spoken language、written language、voice locale 分离。修改语言标注不能追溯改写旧 Run 的实际识别参数；是否允许 UI 中改标并建新 Run 属于 UI Gate。
9. 媒体时间采用统一原点、整数单位及原时基映射；VAD 多段拼接保存分段映射。显示 cue、源 span、take placement 的时间独立，不能靠数组位置对齐。
10. 导出快照保存实际 revision/take ID 集合，不能只存“总修订次数”。重试旧导出使用旧快照；若当前选项变更，建立新的导出。缺必要产物时明确阻断该输出。

这些是 [Round2 领域模型](../v2_discovery_round2/04_DOMAIN_WORKFLOW_MODEL.md) 的具体化；不继承 V1 数据库，也不把 HTML 示例数据结构提升为数据库设计。

## 3. 单写入者与 SQLite 基线

每个打开项目由一个应用控制器拥有写入队列；worker 无数据库写权。第二个应用实例请求同一项目写权限时拒绝或只读打开，不能靠“SQLite 只有一个 writer”替代应用独占编辑。DB 事务短小，文件 IO/推理不在事务中等待。写入遇 busy/full/IO error 时检查失败状态并回滚，不把重试按钮当成已保存。[事务规则](https://www.sqlite.org/lang_transaction.html)

研究建议采用 SQLite WAL + `synchronous=FULL`，外键开启，写入/检查点由同一受控存储服务管理；将读取快照保持短寿命。FULL 更适合人工编辑的持久性目标，具体延迟由切片测量，不默默以 NORMAL 换性能。WAL 仅本机文件系统；网络共享目录、云同步目录上的活跃多机编辑不属于支持范围。[WAL](https://www.sqlite.org/wal.html)、[synchronous](https://www.sqlite.org/pragma.html#pragma_synchronous)

**新增发行门：SQLite WAL-reset 修复。** 官方记录指出 3.7.0 至 3.51.2 存在多连接并发 write/checkpoint 的罕见损坏问题；修复为 3.51.3 及以后，另有 3.44.6/3.50.7 回移。发行必须记录实际 `sqlite_version()` 与 source ID，采用含修复的受支持版本；不能从 Python、Qt 或 Rust 包版本推定底层已修复。单 writer 设计降低复杂度，不替代依赖修复。[3.51.3 发布记录](https://www.sqlite.org/releaselog/3_51_3.html)、[缺陷条件](https://www.sqlite.org/wal.html#the_wal_reset_bug)

## 4. 文件提交、取消与恢复

数据库事务只涵盖数据库。本方案有意让外部文件先完成、引用后提交；因此可产生孤儿文件，不能宣称跨文件系统和 SQLite 的联合原子提交。[SQLite 原子提交的范围与底层假设](https://www.sqlite.org/atomiccommit.html)

提交协议建议：

1. 控制器登记 attempt 和输入快照，分配受管 staging；worker 只写该 attempt 的允许输出。
2. worker 关闭句柄并提交结果 manifest；控制器校验长度、路径、摘要、格式和可解码性。可信文件位置不能只用字符串前缀判断，还要处理路径逃逸、重解析点和源文件别名。
3. 对已完成文件进行必要的持久化 flush，在同卷上发布为不覆盖的唯一 artifact 路径；不修改现有 take。
4. 在一个短事务中再核对活动 attempt、输入/目标 revision、锁和取消意图，登记 artifact、结果和 WorkUnit；只有这里可以提升为当前结果。
5. 数据库成功返回后，UI 才显示已保存。若确认反馈丢失，使用 `(attempt, unit, output-role)` 唯一键查询，重复消息不重复建 take。

Windows 的 FlushFileBuffers 和文件替换/移动各有错误与卷边界条件；`rename` 成功不能自动等价于掉电持久。具体同卷发布策略须实测文件被占用、磁盘满、跨卷目标及突然终止；不承诺坏硬件也零丢失。[FlushFileBuffers](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-flushfilebuffers)、[MoveFileExW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-movefileexw)、[ReplaceFileW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-replacefilew)

| 故障窗口 | 重开时的状态 | 允许动作 |
|---|---|---|
| staging 只写了一半 | 未提交、不可选择 | 隔离/清理临时文件，重跑该单元 |
| 完整文件已发布但 DB 未提交 | orphan，不能直接认定成功 | 对照 attempt manifest 校验后显式恢复为候选，或清理 |
| DB 已提交但成功消息未显示 | DB 为准，结果已存在 | 验证引用后重绘 UI；不能再次收费生成 |
| DB 引用了缺失/损坏 take | 该 artifact 不可用 | 保留文本/历史，定位或重生该 take，阻断需要它的输出 |
| 用户取消与完成同时发生 | 由控制器串行处理的取消/提交次序决定 | 已提交单元保留；取消先登记后，剩余结果不能提升为当前 |
| 重试开始后旧进程返回 | 旧 attempt 无当前写资格 | 拒收或保留隔离诊断；不能挂到新 attempt |
| 外部请求超时/本机崩溃 | 远端结果未知，不等同失败 | 有 request ID 时查询；否则用户获知潜在重复计费后再重试 |
| 多文件导出完成一部分 | 每个 artifact 状态独立，整体 partial | 保留有效文件；不能把整批称成功或删掉用户既有文件 |

“resume”只适用于 adapter 声明的、已验证可独立提交的单元。ASR 连续解码的中途片段未必可作为无缝续算点；无能力时从固定音频 chunk 或完整阶段重跑，并做重叠边界去重和时间映射。未实现 chunk 协议前，UI 不应承诺“从第 N 个识别段继续”。

## 5. 备份、搬移与 V2 schema 演进

备份由控制器固定一个 project checkpoint，暂缓提交新结果及清理受引用文件；通过 SQLite backup API 产生一致 DB 副本，按该副本列出的 artifact 集合复制/校验文件，完成后发布备份 manifest。仅复制主 `.sqlite` 文件可能漏掉 WAL；DB backup 本身也不自动备份音频。[SQLite Backup API](https://www.sqlite.org/backup.html)

媒体 relink 的 size/mtime/局部摘要仅用于快速候选搜索；最终确认同一内容使用全文件 digest，并检测校验过程中源文件是否变化。身份未完成时可以标 provisional，不能显示“内容已验证”。不同内容建立新媒体版本并显示受影响工作，不静默替换。外部源媒体丢失只阻断依赖它的播放/重识别/视频输出；已有文字字幕导出或已完成 take 的纯音频导出，不因缺视频一律禁止。

清理按可达引用集合进行：当前指针、历史保留范围、导出快照、备份和活动 attempt 都是根。cache 可重建；take 不自动清除。对模型使用安装引用/任务 lease 防止运行中卸载；离线状态下删除唯一模型应明确解释后果。文件移动/回收都限定受管目录，不把用户源媒体当缓存。

项目内部记录 `schemaVersion/minReaderVersion`；未知更高版本拒绝写入。升级先关闭/终止写入任务、制作一致备份，在副本迁移并校验外键、revision/provenance、artifact 引用，再受控切换。升级失败保留原项目。旧应用回退不自动降级新 schema；用户可打开升级前备份。需要重建表时遵循 SQLite 文档步骤，不手改 sqlite_schema。[ALTER TABLE](https://www.sqlite.org/lang_altertable.html)

## 6. 资源 manifest 与状态

资源元数据区分上游原始声明、GlyphCue 分发决策与本机安装观测；模型卡不能直接给 `product-verified`。

| 字段组 | 必须记录 |
|---|---|
| 身份 | resource ID、kind（runtime/model/voice/font/media-tool）、不可变 revision、manifest schema、发布序号 |
| 获取 | 可信发行渠道、精确文件列表/路径、压缩与解压大小、逐文件 SHA-256、允许的重定向目标、许可证快照 |
| 来源 | 原仓库 revision、转换工具/参数、量化方法、父权重摘要、提供方/维护者；不接受可变 `latest` 作为复现实据 |
| 相容 | OS/arch、runtime protocol、模型格式/adapter范围、backend/driver/CPU instruction要求、依赖资源和测试配置 |
| 能力声明 | stage、源/目标语言对、voice locale、上游列出状态；GlyphCue 测试报告 ID 与配置条件另列 |
| 许可 | 精确 code/weight/voice/dependency license、NOTICE/attribution、源码获取义务、允许的分发方式、审核状态 |
| 安装事实 | 已安装路径、校验日期/结果、当前激活版本、最近 smoke、已占空间；仅本机保存 |
| 生命周期 | 旧版本、lease、失败/隔离、升级/回滚兼容范围；撤销/已知漏洞标记 |

不要使用一个互斥 enum 表示一切。建议分为 acquisition（缺失/下载/校验/已安装）、integrity、compatibility、activity（加载/运行/OOM）、availableUpdate 以及 capability evidence。旧版 ready 与新版 downloading/updateAvailable 可以同时成立；一次 OOM 不把模型标成损坏。

推荐交付：小应用安装器包括壳、项目编辑、已审媒体工具和必要字体；首次明确启用 ASR 时下载一个获选默认包，翻译和 TTS 各按需获取；加速包单独安装。提供相同校验规则的离线资源导入路径。没有模型时仍能打开/编辑已有项目，但不能声称新安装完全断网就可识别。Qt/WebView2 自带媒体库与独立 FFmpeg 同时存在时分别审计。首次下载同样可能是分发行为，不豁免许可证。

下载流程：获取并验证可信 catalog → 空间预算（下载+解压+旧版+staging）→ staging 下载 → 逐文件校验/完整依赖检查 → 本地 load smoke → 原子更新激活指针。部分下载续传必须核对服务器返回的内容版本/范围，否则丢弃不匹配分片重下；不能将不同 revision 拼接。[HTTP Range/If-Range 语义](https://www.rfc-editor.org/rfc/rfc9110.html)

资源包是数据或批准的 runtime 二进制，不是安装任意脚本的渠道：不允项目 manifest 指定任意下载站点、post-install shell、远程 Python module 或自动 `pip install`。离线导入也检查路径逃逸、大小、文件种类、哈希和许可证，不因为文件在本地而降低检查。

## 7. 下载真实性与更新回滚

hash 用于完整性，不能独自认证下载源。第一版使用随签名应用发布的可信 manifest/信任根；若新增在线 catalog 更新，先实现签名、版本防回退、过期、撤销与密钥轮换策略，不能下载一个 URL 后相信其自报 hash。TUF 提供对 rollback/freeze 等攻击的成熟定义，但本轮不要求自行重写或立即部署完整 TUF 服务。[TUF specification](https://theupdateframework.github.io/specification/latest/)

用户主动回选已安装的兼容资源与网络攻击诱导 metadata 降级不同：前者明确记录、避开已撤销版本并保留来源，后者拒绝。离线时最新 catalog 过期不应令已验证的既有本地工作突然不可用；阻止未经认证的新安装/更新，显示无法确认新鲜度。需要 revocation 在线检查的未来服务不能破坏本地 ASR 的离线承诺。

## 8. 隐私边界与凭据

| 组件 | 允许数据与网络 | 禁止默认行为 |
|---|---|---|
| ASR/aligner worker | 本地媒体片段、经验证本地权重、受管结果 | 远端 ASR、隐式模型下载、远程日志/遥测 |
| 本地翻译/TTS worker | 固定文本快照、所需本地资源 | 共享用户 API key、远端模型路由、自动读取项目外内容 |
| 资源获取器 | 发布方批准资源 URL；用户可见下载 | 发送源文件名、转录、take、项目 ID；继承 BYOK 认证头 |
| BYOK adapter | 用户批准的确切文本/邻句/术语或配音稿、目标 provider/model/voice | 音视频、路径、项目数据库、未披露上下文、克隆参考音频 |
| UI | 编辑数据、能力/状态、掩码 key 标识 | plaintext key 往返给 renderer、渲染未经清理的模型 HTML |
| 诊断导出 | 脱敏的版本/backend/耗时/错误码 | 默认全量字幕、原音、Authorization header、完整私有路径 |

实现上：ASR 的 adapter registry 根本不含 cloud 能力；处理器仅传本地资源路径，设置依赖 offline/local-only 选项并在干净机器的阻断出站环境测试。`HF_HUB_OFFLINE=1` 限制 Hub 请求，但不能控制任意第三方库网络；环境变量不等于 OS 沙箱。[Hugging Face offline 配置](https://huggingface.co/docs/huggingface_hub/en/package_reference/environment_variables)

独立 worker/Windows Job Object 提供生命周期隔离，不自动提供权限或网络沙箱。强 OS 出站隔离可研究 AppContainer/相应防火墙机制，但 GPU/DLL/文件访问与非管理员发行需验证；产品对“本地 ASR”的承诺通过受控 adapter、资源完整性、无隐式请求与断网验收实现，不能宣称抵御同用户恶意程序。若需要“即使被攻陷也不能联网”的保证，另设安全 Gate，不由本轮偷换承诺。[AppContainer](https://learn.microsoft.com/en-us/windows/win32/secauthz/appcontainer-isolation)

Windows BYOK 采用系统 Credential Manager 的用户凭据；项目只记 provider 配置 ID/非秘密端点。DPAPI CurrentUser 是需自管密文时的备选，不默认用 machine scope，也不随便携项目复制。凭据库能保护存储，不代表同用户进程间绝对隔离。读取/替换/删除 key 在控制器内完成；worker 不继承宽泛环境变量，renderer 只得到存在/缺失/需重配状态。[CredWriteW](https://learn.microsoft.com/en-us/windows/win32/api/wincred/nf-wincred-credwritew)、[CREDENTIALW](https://learn.microsoft.com/en-us/windows/win32/api/wincred/ns-wincred-credentialw)、[DPAPI](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata)

外部请求先物化 payload：精确 units/revisions、真实邻段/术语、目标、数据类别、字符数/费用规则；UI 披露这份对象，而不是另算一个摘要。确认与 payload digest 绑定；确认后输入变更不得替换待发内容，改变 endpoint/model/上下文范围时须重新取得对应授权。默认逐批确认，具体频率仍待 UI Gate；任何“记住”都不能扩展授权目的地或数据范围。URL/query 不带 key，重定向不向新 host 传认证或文本。

离线：本地任务正常；BYOK 保留待用户重试状态，不在网络恢复后静默发送此前未批准的内容。外部请求未知结果不能自动当成本地失败重新生成；处理位置、provider/model/voice/request ID（如有）记录于每个产物，用户手改后也保留历史来源。

日志默认仅结构化非内容元数据，限制滚动容量。provider 原始错误可能回显输入，先清洗再显示/持久化；诊断包由用户预览选择，默认不含项目文本/媒体，崩溃 dump 因可能含密钥或字幕不自动上传。产品离线不等于下载站点看不到访问 IP，这应在资源获取说明里简洁交代。

## 9. 后续最小故障验证（本轮未执行）

同一合成项目，使用固定输入快照和小型假 worker，逐点终止：写文件途中、文件发布后、DB 提交后、取消登记后、retry 后旧 attempt 返回；校验上述恢复表。再测试一致备份恢复、缺源视频时纯字幕/音频输出、更新损坏与旧资源 lease、凭据库不可用、断网和带邻段的外发确认。它们是工程契约的验收用例，不是已建立的实现票。

来源访问日均为 2026-10-03。数据库版本修复是上游事实；项目目录、schema、payload/lease、恢复和隐私策略是本文结合事实提出的工程决定。真实二进制、OS API 错误处理、故障注入与无出站行为须后续测量。
