# V2 第三轮工程准备度与范围候选

Type: wayfinder:map
Status: research-complete; acceptance-pending

## Destination

完成独立工程研究与可审查的 V2_SCOPE_DRAFT；产品政策不重开，框架和模型以明确实验门收敛，UI Gate 留给用户。

## Notes

- 用户已明确七条调查轨及交付物；本轮直接执行研究，不再次访谈已定范围。
- wayfinder 的多研究票例外适用。仅决策研究票，不创建实现票。
- 使用 research 子代理和 Astra Medium；新目录分工隔离，不切换 CC 所在工作目录的分支，不编辑 CC 原型、V1 或前两轮记录。
- 所有本轮研究票完成代表证据整理完成，不等于后续实验或人工 Gate 通过。
- 最终交付限 docs/v2_round3/、docs/v2/V2_SCOPE_DRAFT.md；临时交接在系统临时目录。

## Decisions so far

- Candidate canonical product scope: `docs/v2/V2_SCOPE_DRAFT.md`.
- Engineering readiness and open gates: `docs/v2_round3/ENGINEERING_READINESS_REPORT.md` and `docs/v2_round3/DECISION_REGISTER.md`.
- Framework slice contract: `docs/v2_round3/FRAMEWORK_SLICE_CONTRACT.md`.
- Runtime validation plan: `docs/v2_round3/WORKER_RUNTIME_VALIDATION.md`.
- Persistence, resource, privacy, and recovery contract: `docs/v2_round3/PERSISTENCE_RESOURCES_PRIVACY.md`.
- Distribution kill tests: `docs/v2_round3/DISTRIBUTION_KILL_TEST.md`.

The research closes the scope baseline but leaves framework winner, exact model/backend/hardware profile, final bundle contents, and Human UI Gate open. No production implementation or UI acceptance claim is made.

## Not yet specified

调查中出现的跨轨矛盾，在整合时归入具名工程门。

## Out of scope

生产代码、框架原型执行、模型下载、付费调用、发布、V1 迁移和范围扩展。
