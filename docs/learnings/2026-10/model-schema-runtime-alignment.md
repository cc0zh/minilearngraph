# 让模型 Schema 与运行时校验对齐

模型输出被严格校验拒绝时，不一定只是模型不听指令。还要问：**它是否看到了服务端真正要求的约束？**

## 运行时规则不一定出现在 JSON Schema

Pydantic 的 `model_validator` 可以检查来源前缀、唯一性或跨字段预算，
但这些 Python 逻辑不会自动翻译成 JSON Schema。服务端要求假设 key 以
`suggested:` 开头，而模型看到的只是“最长 120 字符的字符串”，两端契约就存在缺口。

可用上下文专用类型表达约束：模型建议使用 SuggestedAssumption，公共读取仍使用
允许不同来源的 Assumption；不要为约束模型建议而禁止用户和跳过来源。

```python
class SuggestedAssumption(Assumption):
    key: Annotated[
        str,
        StringConstraints(min_length=1, max_length=120, pattern=r"^suggested:"),
        BeforeValidator(_text),
    ]
```

这里先定义字符串约束，再用 BeforeValidator 做文本清理。叠加在已有文本 alias 后的
pattern 在本项目当前 Pydantic 组合中没有出现在导出 Schema，虽然运行时会检查。
因此必须检查实际 `model_json_schema()`，不能仅凭声明中出现 pattern 就认为模型已知道。
回归应定位到 suggested_assumptions 的 item 定义，断言其 key 的实际 pattern。

## 明确告知，不偷偷修复

Schema 是机器约束；简短提示词和示例帮助模型理解来源含义。二者都应明确 key 的前缀。
但不应为了让结果成功就自动补前缀：这会把非法模型输出变成应用认可的来源，掩盖协议失败。
合法输出正常通过，非法来源仍失败，而且不能隐式增加模型请求。

自检：导出的 Schema 是否包含规则？公共读取是否被误收紧？非法输出是否仍被拒绝？
离线回归与真实模型效果是否分别记录？

来源：[本次修复记录](../../histories/2026-10/20261009-0631-b1-clarification-assumption-schema.md)。
