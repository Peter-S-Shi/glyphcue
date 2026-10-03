# 候选栈的许可与分发终止条件
Type: research
Status: resolved

## Answer

Distribution is a release gate, not an implementation detail. Verify exact model weights, native libraries, G2P/phonemizer chain, FFmpeg profile, fonts, WebView/runtime, and provider terms. Mutable latest resources, incomplete license chains, unsigned catalogs, or unresolved offline behavior are kill conditions. See `docs/v2_round3/DISTRIBUTION_KILL_TEST.md`.
Assignee: distribution-research

## Question

对限定候选的代码、权重、声线、依赖、字体和外部服务分别核查商用/再分发，给出可执行 kill conditions，覆盖 Track E。
