# 本机 B1 HTTP 服务

在仓库根目录先 `uv sync --locked`，再运行 `uv run --locked python -m mini_learngraph.api`。默认只绑定
`127.0.0.1:8000`，固定单 worker、不信任代理头、不记录包含用户查询的访问日志。
`MINI_LEARNGRAPH_HOST` 只能为 `127.0.0.1` 或 `localhost`；端口由
`MINI_LEARNGRAPH_PORT` 设置（1..65535）。不支持 LAN/公网部署。

服务 settings 独立于模型 settings，缺少模型配置不阻止服务启动和查询。
模型仅在澄清/图谱生成入口使用。lifespan 在线程中初始化数据库并恢复中断资产，
不自动重放模型请求。`app.state.store` 和 `app.state.service` 可用于本机测试。

服务 settings 从项目 `.env` 和环境变量读取，但不创建模型 Settings。
`MINI_LEARNGRAPH_DB_PATH` 默认项目目录的 `data/learning.sqlite3`，相对路径按项目
目录解释。测试调用
`create_app(db_path=临时路径, generator=固定桩)`，不访问真实模型。

`MINI_LEARNGRAPH_ALLOWED_ORIGINS` **只接受 JSON 字符串数组**，例如：

```text
MINI_LEARNGRAPH_ALLOWED_ORIGINS='["http://127.0.0.1:5173","http://localhost:5173"]'
```

这是默认值；配置值替换默认数组。仅支持无路径、无凭据、无查询/片段的
`http(s)://127.0.0.1[:port]` 或 `http(s)://localhost[:port]`，不支持 `*`。
经 Host 校验后的请求同源地址也允许。无 Origin 的本机 CLI 允许；显式未知或
`null` Origin 对所有路由均拒绝。Host 只接受这两个本机主机及合法端口。
跨源预检仅允许 GET/POST/PUT 和 Content-Type，不允许凭据。

12 个业务路由位于 `/api/v1`。标准 `/docs` 和 `/openapi.json` 同样受安全边界保护。
所有写请求使用 `application/json`，严格 UTF-8 全文解析、拒绝重复键/非法数字，
总 body（包括 chunked）最多 512 KiB；GET 不接受 body。
错误仅返回固定安全摘要和定位字段，不回显原始异常、校验输入或请求头。

字段和生命周期的正式来源是
[B1 API 契约](../../docs/design-docs/learning-b1-api-contract.md)。

## 澄清失败的恢复

`generation_failed / invalid_output` 表示模型响应未通过消息协议、完整 JSON、Schema
或领域校验，不代表目标文本无效；未确定期限或投入时间可以保留为 null。
模型建议假设的 `key` 必须以 `suggested:` 开头，这项规则同时写入模型 JSON Schema
与澄清提示词；不自动补前缀、不修复模型响应，也不自动重试。

修正配置或更新代码后，重启服务并保留同一数据库，在 Web 读取最新资产后显式
重试原目标的澄清，不必删除草稿或另建目标。重试会再次调用模型，仍须在获准预算内。
公开错误只含安全摘要，不能仅凭 `invalid_output` 断定具体失败字段。
