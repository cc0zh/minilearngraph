# 固定模型桩不等于测试环境已经隔离

把数据库换成临时文件、把Provider换成固定桩，只隔离了数据写入和模型调用。应用工厂仍可能构造Settings；Settings的dotenv源会读取开发者配置，环境变量也可能改变Host、Origin或默认路径。测试可以全绿，却不能据此宣称“没有读取个人配置”。

## 隔离配置源，而不只是覆盖结果

传入临时DB路径并不阻止Settings先读取`.env`。要保护读取边界，应在测试入口关闭dotenv源，并清除会改变测试目标的环境值，再实例化应用。不要读取真实配置后抹去日志，更不要临时搬走或改写开发者的`.env`。

```python
@pytest.fixture(autouse=True)
def isolated_server(monkeypatch):
    monkeypatch.setitem(ServerSettings.model_config, "env_file", None)
    monkeypatch.delenv("MINI_LEARNGRAPH_HOST", raising=False)
```

fixture的作用域很重要：某个测试模块里的autouse fixture并不覆盖其他模块。共用领域测试可以放到conftest，并限制适用模块，避免破坏专门验证配置加载的测试。测试真实配置加载时，用自己创建的合成临时dotenv即可。

## 子进程是另一条入口

浏览器流程启动的Python服务不会继承pytest的monkeypatch。它需要在自己的测试入口隔离Settings与环境变量；生产启动入口不应为测试而改变。临时DB路径、固定Provider、监听地址仍需显式指定。

## 用负对照证明哨兵有效

在文件打开之前安装哨兵：如果尝试打开仓库`.env`就抛出断言。先恢复默认配置源并断言命中哨兵，再验证隔离后的API和浏览器fixture能启动。这同时证明“原路径会读取”和“新路径没有读取”，而不接触真实文件内容。哨兵测试不能只检查有没有网络请求，配置读取与联网是两个独立边界。

自检：

- 每个应用/子进程入口都隔离了吗，还是只保护了一个测试模块？
- 覆盖的是Settings最终字段，还是已经在读取前禁用了个人配置源？
- 哨兵有失败负对照吗，能否证明不是安装位置错误而一直放行？

来源：[B1整体独立复验记录](../../histories/2026-10/20261009-1146-learning-loop-web-plan.md)。
