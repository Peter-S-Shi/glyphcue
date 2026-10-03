# 桌面基础与代表性交互切片
Type: research
Status: resolved

## Answer

The framework remains an evidence-backed choice, not a closed winner. Qt Quick/QML and Tauri 2 both require the same 10k-span framework slice with IME, RTL, accessibility, focus, splitter, cancellation, stale/late result, and export-failure checks. Persistent editor state belongs in the model/controller rather than recycled delegates. See `docs/v2_round3/FOUNDATION_EVIDENCE.md` and `docs/v2_round3/FRAMEWORK_SLICE_CONTRACT.md`.
Assignee: foundation-research

## Question

Qt Quick 与 Tauri 哪些事实已足以决定架构边界，哪些需同一个代表性实验？覆盖 Track A，产物见桌面基础证据和框架切片契约。
