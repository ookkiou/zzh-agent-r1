# 第 4–5 天：独立执行服务与真实容器验收

服务持有固定 train/dev 任务及私有用例，客户端只加载任务说明、初始源码和公开测试。候选源码在新的 Docker 容器中执行，期望结果在容器外比较。服务启动时校验资源 SHA256，不读取参考实现。

## 本机环境

本次使用 macOS arm64 + Docker Desktop 4.93.0 的 Linux VM，Docker Engine 29.8.1，官方 Python 3.12.15 镜像。镜像及平台记录在 `SANDBOX_LOCK.json`；无需 GPU、模型权重或 Docker 账号。最终 AutoDL/Linux 机器需重跑同样的验收，当前结果仅证明本机这一运行环境。

Docker 已安装在 `/Applications/Docker.app`。打开 Docker Desktop，确认 Engine running。当前终端可这样设置路径及固定镜像：

```bash
export PATH="/Applications/Docker.app/Contents/Resources/bin:$PATH"
export CODE_REPAIR_DOCKER_IMAGE="$(python3 -c 'import json; print(json.load(open("SANDBOX_LOCK.json"))["image"])')"
docker version
```

本机已经拉取该镜像。迁移机器时先执行 `docker pull "$CODE_REPAIR_DOCKER_IMAGE"`。执行器使用 `--pull=never`，不会在执行候选代码时自动联网下载。

## 重跑当天验收

```bash
python3 scripts/verify_sandbox.py
python3 scripts/verify_service.py
python3 scripts/check_day45.py
```

第一条实际探测非 root、清空 capabilities、禁止提权、只读根目录、禁网、宿主文件和环境隔离、16MiB 临时目录、1 CPU、256MiB 内存、32 进程，以及无限循环、输出洪泛、fork/内存耗尽和容器清理。

第二条启动临时 loopback 服务，为 20 个原型及 104 个正式 train/dev 任务分别运行缺陷与参考补丁 episode，再运行 4 个同题并发 episode。每条走 HTTP、容器和私有验收；客户端任务对象不含私有用例。报告为 `reports/service_verification.json`，轨迹在忽略提交的 `runs/docker-service-episodes/`。脚本用已知参考补丁，没有模型参与，不能作为模型修复率。冻结的最终 test 来源不会被加载。

第三条汇总前两份实测证据，并重跑全部自动测试（必须包含真实 Docker 用例，不能跳过）。报告为 `reports/day45_acceptance.json`。协议单元测试对已知 fixture 使用本地后端；真实隔离证据来自前两条命令和 Docker 集成用例。

## 手动启动服务

```bash
export CODE_REPAIR_SERVICE_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
python3 scripts/serve_evaluator.py --image "$CODE_REPAIR_DOCKER_IMAGE"
```

默认只加载正式 104 个任务，可用多个 `--dataset` 指定已校验的 train/dev 目录。服务仅监听 `127.0.0.1:8765`，最多 4 个并发执行，请求不超过 64KiB、源码不超过 16KiB，每次容器执行 5 秒。生产启动入口仅使用 Docker；缺失 Docker、镜像或引擎时启动失败，不回退到本地执行。按 Ctrl+C 停止。

全部请求需 `Authorization: Bearer <token>`。token 属于可信控制面，不得写入模型提示词、env_kwargs 或轨迹；后续适配器通过 worker 环境配置读取。远端运行用 SSH 转发服务端口，不对公网开放该服务。

| 接口 | 请求 | 返回 |
|---|---|---|
| GET /health | 无 body | 后端、镜像摘要、任务数量、数据清单 SHA256 |
| POST /v1/evaluate | task_id、source、mode（public/private） | status、tests、passed、failed、timed_out、elapsed_seconds |

公开结果额外提供失败用例 ID 与原因；私有结果只保留计数与状态。请求不能指定文件路径、命令、输入用例、期望结果、镜像或容器参数。无认证返回 401；超容量返回 503，客户端将其记为基础设施无效 episode。候选超时、输出超限和候选执行错误得 0；没有成功完成或零测试不能得 1。

客户端示例（与服务使用同一 token，但不要将 token 作为模型可见字段）：

```python
import os
from code_repair.tasks import load_task
from code_repair.evaluation import RemoteEvaluator
from code_repair.environment import RepairEnvironment

task = load_task('data/mbpp_repair/v0.1/dev/mbpp-526-m01', include_private=False)
client = RemoteEvaluator('http://127.0.0.1:8765', os.environ['CODE_REPAIR_SERVICE_TOKEN'], task.task_id)
with RepairEnvironment(task, evaluator=client) as env:
    result = env.step({'name': 'run_tests', 'arguments': {}})
    print(result.tool_response)  # 公开反馈；原始缺陷应触发失败
    terminal = env.step({'final': '结束'})
    print(terminal.reward)  # 未修复为 0
```

## 隔离与时间预算

每次执行无网络、无宿主挂载、只读根目录、UID/GID 65534、drop ALL capabilities、no-new-privileges；仅 `/tmp` 提供 16MiB 的 `nosuid,noexec` tmpfs。公开与私有执行各建新容器，进程、临时文件和工作区不会跨 episode 保留。宿主 Docker socket、服务 token、参考代码、私有期望值不传入候选容器。函数收到对应输入值，属于验收执行所需的可见信息。

行动时间预算 120 秒，最多 6 次决策；每次容器执行 5 秒，终局私有验收另有执行预算。Docker 清理最多另等 5 秒，HTTP 客户端最多等待执行预算加 15 秒的传输余量。因此 120 秒不是整个 HTTP 请求链路的绝对墙钟上限。后续模型 token/context 上限由 Agent-R1 适配器设置，本阶段没有验证模型 token 预算。

本服务提供项目受限任务的容器隔离，不是对互联网开放的通用代码平台。生产训练前仍需在目标主机验证 Docker 权限、平台镜像、并发资源及框架适配。第 4–5 天没有安装 Agent-R1/verl、没有加载模型或执行参数更新。
