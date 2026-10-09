# 安全默认约束

项目落地时按实际数据与部署方式补齐：

- 认证、授权与敏感数据处理要求。
- 密钥管理、环境变量及日志脱敏规则。
- 外部 API、Webhook 和文件上传的输入边界。
- 运行环境的文件、网络权限与恢复方式。

依赖、SBOM 与 provenance 见 `docs/SUPPLY_CHAIN_SECURITY.md`；漏洞反馈流程见根目录 `SECURITY.md`。

## Agent 执行

- 沿用已配置的沙箱与授权边界，权限阻塞应记录并处理。
- Windows 原生执行方式见 `docs/WINDOWS.md`。
- nono 是可选的 macOS/Linux 外部沙箱扩展，配置及核验清单仅在模板源码仓库的 `docs/nono-profiles/` 维护，需要时手动引入。
- 引入外部沙箱前核验其真实隔离范围，不能仅凭提示词声称已有隔离就关闭现有保护。

本文件保持平台无关；具体沙箱路径、证书设置和审计操作由各平台指南维护。

## B1 本机 HTTP 与资产

- 官方启动入口绑定127.0.0.1（允许配置localhost）、固定单worker，不信任代理头，访问日志关闭；不支持LAN/公网/多人。固定学习者local-user不是认证方案。
- 所有路由（含OpenAPI）限制Host为127.0.0.1/localhost与合法端口；显式未知、null或重复Origin拒绝403。只允许配置的精确本机Web origin及合法请求的同源地址，无Origin本机CLI允许；没有通配CORS或凭据授权。
- Origin/Host在解析body及业务调用前检查。写请求必须application/json，UTF-8完整JSON、重复键/NaN/Infinity拒绝400；有界读取每个chunk（512KiB），不能靠伪造Content-Length绕过。GET有body为422。字段strict/extra forbid、NUL/长度/数值/资源UUID与归属校验；不接受learner_id、actor、模型地址或文件路径。
- 错误使用统一ApiError与安全摘要，不回显validation input/ctx、异常原文、模型原文、请求头或密钥；SQL只使用预定表名与参数，不拼接外部输入。未知route/method也规范化404/405。
- 模型输入是数据，不获得权限；tools=[]、仅stop/no tools的完整JSON对象可用。256KiB/32层限制、严格Schema与全图联合DAG守卫；无代码执行、无自动修复/默认成功、无自动发布。网络调用只发生在显式澄清/图谱生成入口。
- DB默认data/learning.sqlite3，含学习内容及不可变历史，作为本地私有资产保护；Git、初始化与源码包排除data目录/SQLite/sidecars。不要把真实数据置于发布目录。迁移/备份需关闭服务或使用SQLite backup API保持一致性；真实资产无删除重建授权。
- `scripts/verify_learning_model.py --stage b1`默认SKIPPED，不读配置、不联网；仅在获准范围追加`--allow-configured-model`发送合成输入，记录模型ID/UTC/安全结果，不存完整请求或响应。
