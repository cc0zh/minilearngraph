# 安全校验错误：稳定语义与脱敏可以同时成立

向客户端返回校验错误时，不能直接序列化框架异常。Pydantic的错误条目可能含被拒绝的input、ctx和自定义validator消息；陌生字段名也可能就是用户输入。安全目标不是“没有报错”，而是**保留可定位、稳定的错误语义，不让错误成为输入回显通道**。

## 固定错误码，不透传异常

应用已约定重复回答为duplicate_question、回答方式互斥错误为invalid_answer。如果HTTP层把所有自定义类型折叠成constraint，虽然没有泄漏内容，却破坏了前端已用的契约。

正确做法是白名单映射：只识别已定义的类型，使用服务端固定code/message；未知类型落到通用constraint。标准missing/type/extra也有固定摘要。不要为方便而使用 `entry['msg']` 或完整 `entry`；extra错误的陌生属性名应从定位路径中移除。

```python
if kind == "duplicate_question":
    code = "duplicate_question"
    message = "Each question must be answered once."
else:
    code = "constraint"
    message = "Field does not meet its constraints."
```

这里不是把框架类型当公开接口；公开接口仍由应用契约定义，映射层负责隔离框架变化。用HTTP回归验证code、定位及失败不落库，单测validator本身并不足够。

## 脱敏断言必须理解JSON类型

假设请求的Origin是字符串 `"null"`，服务拒绝后返回：

```json
{"resource_id": null, "message": "Origin is not allowed."}
```

若测试使用 `assert 'null' not in response.text`，合法缺省值也会失败。JSON的null不是字符串；响应契约可能要求可空字段必需，删除这些字段反而是在“为了测试绿而改坏接口”。

应先解码JSON，递归扫描所有键与字符串值，检查私有输入是否作为文字被回显；数字、布尔、null不当文本查找。递归不能只查顶层message，泄漏可能藏在issues/path或未知键。再补正反回归：合法null允许，真正的字符串 `"null"` 或私有值出现在嵌套message中仍必须失败。

这是**语义脱敏测试**，不是忽略泄漏：验证层仍要求统一strict错误对象，响应头不回显Origin另有断言。业务允许的ID/ref定位与不允许的原始内容，也应按字段边界区分。

## 自检

- 自定义错误在Schema和HTTP边界是否保留同一公开code？未知错误是否安全降级？
- 是否不小心透传了msg/input/ctx或陌生属性名？
- 测试检查的是解码后的类型，还是把序列化文本中的合法null误认为用户秘密？
- 错误定位、脱敏和“失败不修改资产”是否都验证，而非只检查HTTP422？

来源：[本次变更记录](../../histories/2026-10/20261009-1146-learning-loop-web-plan.md)。
