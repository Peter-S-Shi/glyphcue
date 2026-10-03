# 项目恢复、资源交付与隐私边界
Type: research
Status: resolved

## Answer

Use a controller-owned SQLite metadata store plus project artifacts, with stable IDs, revision-bound provenance, staged file publication, backup/restore, and orphan reconciliation. Workers do not write the database. The shipped SQLite source/version must be identified because the recent WAL-reset fix changes the release gate. See `docs/v2_round3/PERSISTENCE_RESOURCES_PRIVACY.md`.
Assignee: discovery-lead

## Question

如何以最小持久化、可回滚资源和明确外部发送语义落实 Track B/D/G，并将全部结论整合为范围候选与决策登记？
