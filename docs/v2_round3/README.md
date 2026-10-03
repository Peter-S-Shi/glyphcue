# GlyphCue V2 Round 3

第三轮把前两轮产品研究和 UI Design Gate 转成工程准备度输入。研究不修改 CC 的 HTML、V1 历史或生产代码，也不把合成 prototype 状态当成真实模型验证。

## 阅读顺序

1. [ENGINEERING_READINESS_REPORT](ENGINEERING_READINESS_REPORT.md)：整体结论、风险和实验顺序。
2. [DECISION_REGISTER](DECISION_REGISTER.md)：每项关闭、待实验、UI Gate、阻断和延后的状态。
3. [FOUNDATION_EVIDENCE](FOUNDATION_EVIDENCE.md)：Qt Quick/QML 与 Tauri 的证据和边界。
4. [FRAMEWORK_SLICE_CONTRACT](FRAMEWORK_SLICE_CONTRACT.md)：UI Gate 后的同 fixture 双框架实验。
5. [WORKER_RUNTIME_VALIDATION](WORKER_RUNTIME_VALIDATION.md)：worker、硬件和质量/安装验证政策。
6. [PERSISTENCE_RESOURCES_PRIVACY](PERSISTENCE_RESOURCES_PRIVACY.md)：SQLite、产物、资源下载、恢复、BYOK 和隐私。
7. [DISTRIBUTION_KILL_TEST](DISTRIBUTION_KILL_TEST.md)：shortlist 的分发终止条件。

## 关键状态

产品范围已具备设计输入条件，但 UI Design Gate 尚待人工评审；Qt/Tauri、模型、硬件和商业发行都保留明确的工程门。第三轮没有运行真实模型、安装包、框架切片、故障注入或网络阻断实验。

Canonical 范围候选位于 [docs/v2/V2_SCOPE_DRAFT.md](../v2/V2_SCOPE_DRAFT.md)。该文件是候选权威输入，须在人审通过 CC 原型和剩余工程 Gate 后才升级为最终 canonical scope。

日期：2026-10-03。官方文档、源码和模型卡会变化；实施前重新锁定 immutable revision、hash、许可证和硬件 profile。
