# 质量评分

依据实际实现与验证结果维护，不将模型桩或本地检查当作真实模型、远端 CI 验证。阶段 A 历史范围见 [阶段 A 状态](PHASE_A_STATUS.md)；B1 本轮事实源为 `docs/exec-plans/active/learning-loop-web.md`，见[计划目录](exec-plans/active/)（初始化会裁剪具体任务记录）。

## 阶段 A 历史验收

| 区域 | 当前状态 | 证据 | 下一步 |
| --- | --- | --- | --- |
| 产品与架构 | 阶段 A 已实现；B/C 未开展 | [架构](ARCHITECTURE.md) 的 Loop/Runner 边界与 CLI 路径已落地 | 阶段 B 复用内核验证节点讲解、练习与反馈 |
| 业务测试 | 已建立完整离线验收 | [Runner](../tests/test_runner.py)、[Loop](../tests/test_loop.py)、[Provider](../tests/test_provider.py) 检查消息配对、预算、错误、历史与协议 | 新增领域能力时补充真实学习路径验收 |
| 安全与可观测性 | 满足当前本地 CLI 边界 | [工具边界](../tests/test_tools.py)、[配置脱敏](../tests/test_config.py)、[Trace 隐私与取消](../tests/test_trace.py) 均有回归 | 接入领域写工具或服务化时定义对应权限和数据边界 |
| 工程交付 | 本地 CI、静态门禁与源码包验证通过 | 232 项 Python、21 项 Node 回归；全量应用 Ruff/Pyright 通过；58 文档 Markdown lint 通过；包内本地文件链接和 109 份文件比对通过，详见 [阶段 A 状态](PHASE_A_STATUS.md) | 按实际发布需求核查远端矩阵 |

## B1 当前工程自测与整体独立复验（待周经理最终接受）

2026-10-09 用户重启后后端受保护编辑成功，剩余HTTP错误码、Windows大param ID及null脱敏误报、Ruff缺陷已修复；前端严审#3独立检查通过。严审#4新增14项风险回归、关闭测试侧dotenv隔离缺口并独立实际执行完整默认CI，八项矩阵在本机固定Provider的软件契约范围可交付。完整根CI顺序执行两种Web流程，严格门禁及生成物排除回归保留；合同旧SHA已从checkpoint精确恢复，仅首段状态/链接变化、正文及换行字节无漂移。最终接受归周经理，B2–B4尚未实施，详细版本与逐项证据仅维护在唯一计划。

| 区域 | 当前状态与证据 | 未完成/下一步 |
| --- | --- | --- |
| API/资产 | 冻结12路由、动态澄清/三类回答与假设、严格完整JSON、图谱编辑/确认发布/正式修订、SQLite CAS/节点版本/不可变历史/重启已落盘；严审#4六组矩阵242 passed，新增真实HTTP三类竞争/历史写入故障回滚/逐内容版本等14项 | 无剩余必须修复项；待周经理核对#2/#4接受，不提前B2 |
| 安全 | Host/Origin/null、CORS、JSON/体积/chunk、strict输入、统一安全错误、未知库保护及取消测试通过；缺模型可启动查询 | 单机local-user不是认证，不支持LAN/公网/多人 |
| 默认门禁 | 严审#4独立 `npm.cmd run ci` 退出0/91.9秒；Node24/24、Python474/474、全应用Ruff通过/Pyright0errors，Webtypecheck/lint/build通过、单元14/14、Mock16/16、真实FastAPI临时SQLite3/3；最终文档lint67文件/0错误 | 远端三系统Actions未执行；模型固定Provider桩，不是真实效果 |
| 真实B1模型 | 默认smoke入口输出SKIPPED/退出2，不读取模型配置、不联网 | 获准真实配置/网络/预算后单独验证；阶段A历史真实模型不能替代B1 |
| 依赖状态 | 一个Starlette TestClient弃用warning；npm镜像audit404与上游弃用提示，不影响本轮锁定门禁通过 | 另行核验依赖兼容/漏洞，不将安装成功当安全审计通过 |
