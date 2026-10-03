# Windows 本地 AI 桌面绿地架构选择

Type: research
Status: resolved
Assignee: round2-architecture
Blocked by: none

## Question

从零比较可信桌面框架、工作进程、存储、任务恢复、模型下载及 Windows 发行，哪种最小架构更适合 V2，哪些选择必须先实验？

## Answer

已交付 [绿地架构比较](../../../docs/v2_discovery_round2/01_GREENFIELD_ARCHITECTURE.md)。Qt Widgets、Qt Quick、Tauri 2、Electron、WPF、WinUI 3 从维护边界、交互、媒体、隔离、Windows 发行和许可分别比较。

建议先验证 Qt Quick/PySide6，Tauri 2 为强备选；不是继承 V1，也不因 Python worker 而要求 Python UI。框架不进入产品冻结的硬约束。报告列出可推翻首选的 UI、媒体、进程生命周期与干净离线发行实验；本轮未执行样机或性能测试。

跨框架共同约束：一个应用控制器和项目 writer，独立 worker 无项目写权；Windows 进程树取消；按修订验证结果；runtime/model 分包；本地 ASR、显式 BYOK，无隐式上传/回退。V1 无迁移或对象兼容要求。官方滚动文档的访问日与版本限制已记录。
