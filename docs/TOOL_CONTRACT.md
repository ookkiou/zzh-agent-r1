# 代码修复工具契约 v0.1

schema 的唯一代码来源为 `code_repair/contracts.py` 中的 `TOOL_SCHEMAS`。`code_repair/environment.py` 已实现工具调度、工作区与 episode 状态；`code_repair/execution.py` 提供执行后端。当前尚未接入 Agent-R1 或模型。

| 工具 | 参数 | 允许的操作 |
|---|---|---|
| read_file | path: string | 只读 solution.py、public_tests.py |
| write_file | path: string, content: string | 只写 solution.py，完整替换，最多 16384 UTF-8 字节 |
| run_tests | 空对象 | 运行固定的公开测试，不能指定任意命令 |

参数不允许额外字段，路径必须精确匹配，不能传入绝对路径、`./`、`../`、参考答案或私有测试路径。写入源码需通过 Python 语法检查，保留唯一同步目标函数及参数签名；正文可修改。

执行器先验证参数，写入前验证源码，拒绝符号链接与工作区外路径；非法写入不改变原文件。每个 episode 使用独立工作区，公开测试不能通过工具修改。契约校验本身不提供 OS 隔离；本地 fixture 后端也不是沙箱。Docker 后端已在本机 Docker Desktop 的 Linux VM 完成真实执行与隔离验收；迁移目标 Linux 主机时需重跑。服务及验收说明见 [执行服务](EXECUTION_SERVICE.md)。

统一响应：

```json
{"ok": true, "output": "文件内容或结构化测试结果", "error": null}
```

```json
{"ok": false, "output": null, "error": {"code": "invalid_path", "message": "路径不可访问"}}
```

`run_tests` 的 output 包含 `status`、`tests`、`passed`、`failed`、`failures`、`timed_out`、`elapsed_seconds`。失败项只含公开 case ID 与错误原因。当前原型从固定公开测试中解析字面量用例，再执行候选函数；它不是任意 unittest/pytest 项目执行器。

工具错误代码包括 `invalid_arguments`、`invalid_path`、`invalid_source`、`infrastructure_error`，以及 `execution_timeout`、`execution_output_limit`、`execution_candidate_error`。签名变更属于 `invalid_source`。候选函数异常是正常测试失败，worker 整体未完成才是执行错误。

公开测试失败属于正常工具结果：`ok=true`、`failed>0`；工具本身没有运行成功才返回 `ok=false`。最终私有验收不是工具，不将其结果用于下一轮公开反馈。

最多 6 次决策，行动时间预算 120 秒，公开测试最多 5 秒；终局私有验收另有最多 5 秒的执行预算，Docker 清理可能额外耗时，HTTP 客户端保留执行预算加 15 秒的传输等待上限。120 秒不是整个请求链路的绝对墙钟上限。最终回复或步数耗尽触发终局验收；行动预算耗尽直接记 0。中间奖励为 0，终局奖励只返回一次。验收期望值保留在可信父进程；候选 worker 收到输入但不收到期望值、私有测试源码或参考补丁。客户端使用 `load_task(..., include_private=False)` 与 `RemoteEvaluator` 时，私有用例只存在于服务端。私有用例不进入模型消息，训练侧终局诊断仅保留通过数量等摘要。

后续 Agent-R1 与 ZzhClaw 适配器共用该 schema 与校验模块，在同条件对照前冻结工具返回格式。
