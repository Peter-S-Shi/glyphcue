# V1 架构的复用、改造和退役边界

Type: research
Status: resolved
Assignee: discovery-lead
Blocked by: none

## Question

基于现有代码，V1 主要子系统应如何分类为 REUSE / REWORK / RETIRE，哪些质量与发行经验仍然适用？

## Answer

已完成源码调查。字幕 I/O、播放、边界与发行校验可复用；领域关系、任务、编辑、数据空间需改造；视觉 OCR 主链退役。FFmpeg 成片仅有 Protocol，必须作为新增实现范围。详见 [V1 复用矩阵](../../../docs/v2_discovery/05_V1_REUSE_REWORK_RETIRE.md)。
