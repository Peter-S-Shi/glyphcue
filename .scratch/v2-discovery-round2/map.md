# GlyphCue V2 第二轮：绿地架构与设计契约

Type: wayfinder:map
Status: research-complete; acceptance-pending

## Destination

形成可评审的绿地架构、语言能力策略、AI 运行时方案、领域/交互模型与 V2 Design Scope Contract，让用户能有依据地决定 Product Scope Freeze。研究完成不等于冻结已获批准。

## Notes

- 新产品约束来自本轮用户授权，优先于第一轮建议；第一轮文件保持证据快照。
- ASR 仅本地；翻译/TTS 本地优先，外部提供方需显式选择；单旁白、许可明确的预设声线为配音最低闭环。
- 绿地重新评估；没有 V1 DB/UI/领域兼容要求。EN/ZH/FR 是锚点评测范围，语言架构可扩展。
- 主技能 wayfinder；其 research 子任务使用一手来源并行研究；prototype 仅解决静态资料无法消除的高影响可行性问题；结束使用 handoff。
- 本轮明确要求完成研究交付，使用多研究票例外；保持本地 Markdown tracker，不创建 GitHub issue、不提交、不切换共享工作区分支。
- 交付在 docs/v2_discovery_round2/。不收录提示草稿、个人媒体、会话数据、密钥或本机路径；不改 V1 记录及 Round 1。

## Decisions so far

- 研究票 01–04 已形成对应 Round2 文档：绿地架构、语言能力、运行时、领域模型。
- 设计范围契约已写入 `docs/v2_discovery_round2/06_V2_DESIGN_SCOPE_CONTRACT.md`，仍待用户评审，不代表 Product Scope Freeze。
- 产品门区分为用户已关闭的政策门、工程验证门和发行许可门；见 `05_PRODUCT_GATES.md`。
- 最小决策实验按语言闭环、运行时、桌面壳、媒体导出、资源恢复和扩展文字分组；见 `07_DECISION_EXPERIMENTS.md`。

## Not yet specified

- 用户是否接受设计范围契约并宣布 Product Scope Freeze。
- PG-05 桌面壳、PG-06 硬件、PG-07 语言质量、PG-08 许可、PG-09 资源交付和 PG-10 外部服务仍需相应证据或产品决定。

## Out of scope

- 生产实现、最终 UI 设计、下载大模型、调用付费 AI、上传内容、V1 迁移、声音克隆、自动多人复刻、唇形同步、干净去原人声。
