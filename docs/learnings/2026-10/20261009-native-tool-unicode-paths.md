# Native 工具的 Unicode 路径：cwd 不等于 argv

## 关键区别

Node 的文件 API 能操作中文目录，不代表被它启动的 native 工具也能解码命令行中的中文。Windows 子进程的 cwd 可以通过 Unicode 系统接口传递；工具自身如何解释 argv 则受实现和 locale 影响。远端 tar 把中文路径显示为问号时，问题发生在参数解码，不是目录不存在。

## 保留真实能力，而不是缩小测试范围

打包时让 Node 创建并校验临时目录，以该目录为 cwd，只给 tar 传 ASCII 相对参数：

```javascript
run('tar', ['-czf', 'repo-metadata.tgz', '-C', 'payload', '.'], { cwd: staging });
```

解包回归以中文目标目录为 cwd，通过 stdin 传入归档 Buffer：

```javascript
run('tar', ['-xzf', '-'], { cwd: extracted, input: archiveBuffer });
```

仍要断言解包内容、链接和命令入口。不要把中文测试改成 ASCII 或标记 skipped，那只隐藏了用户会遇到的限制。

这种方法针对根目录路径；**归档内 Unicode 文件名是另一条编码链路**，不能由本次 cwd 回归自动证明。大归档应使用流而不是整包 Buffer；这里的 Buffer 只用于小规模测试制品。

## 自检

- 乱码路径是由系统传递、shell展开，还是工具自己的locale转换产生？
- 改成相对参数后是否仍验证了中文cwd和真实解包？
- 是否误把根目录支持写成所有归档文件名支持？

来源：[v0.2.0 发布记录](../../histories/2026-10/20261009-1515-release-v0.2.0.md)。实现见 `scripts/release-package.cjs` 和 `tests/tooling.test.cjs`。
