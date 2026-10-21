# zzh-agent-r1：面向 ZzhClaw 的代码修复 Agent 后训练

这是与 ZzhClaw 配套的 Agent-R1 训练项目。截至 2026-10-21，已完成三工具代码修复环境、隔离 Docker 验收服务、工具轨迹 SFT 和全参数 GRPO。正式训练执行到 74 步后触发学习信号保护停止，采用最近完整 checkpoint70；原 225 步目标尚未完成，checkpoint 不保存优化器动量。

冻结 dev 对照为 SFT-only 63/96、GRPO step70 72/96；独立最终 test 为 90/126 与 93/126（71.43% → 73.81%，+2.38 个百分点），配对改善 7 / 退化 4。test 覆盖 42 个原题来源，另有 8 个模型无关排除来源，三次 seeds 相关，未检验统计显著性。完整证据见 [最终对照](reports/final_test_eval_comparison.json) 和 [模型验收](reports/final_test_model_acceptance.json)。

第 13–14 天 ZzhClaw 受限 CLI 回接验收完成，15/15 项检查通过：新增 repair profile、模型 API 多轮工具调用与完整应用 dev 对照。相同 vLLM 应用环境下 SFT 69/96 → step70 75/96（+6.25 个百分点），配对改善 9 / 退化 3；这是 dev 迁移结果，原独立 test 结果保持不变。见 [迁移报告](docs/DAY13_14_MIGRATION_RESULTS.md)、[验收证据](reports/day14_acceptance.json) 和 [手动指南](docs/DAY13_14_ZZHCLAW_RUNBOOK.md)。通用 UI / 全工具集未迁移；模型留在 GPU 实例，Mac 无需下载大权重，当前完整权重备份未验收。

完整路线见 [执行方案](EXECUTION_PLAN.md)。

首次克隆请先看 [GitHub 发布与复现说明](docs/GITHUB_RELEASE.md)。配套应用的接入改动提供为 [ZzhClaw 补丁](integrations/zzhclaw/README.md)，第三方资产来源见 [来源说明](THIRD_PARTY_NOTICES.md)。

## 展示、简历与复算

[项目卡与架构](docs/PROJECT_CARD.md) · [简历三条描述与面试追问](docs/RESUME_AND_INTERVIEW.md) · [演示与复现](docs/DAY15_REPRODUCE.md) · [第 15 天交付与限制](docs/DAY15_RESULTS.md)。

第 15 天本机材料与离线证据验收已完成：三组结果复算、完整 SFT 曲线、保留缺口的 GRPO 诊断、正反案例及记录回放。完整 GRPO 逐步曲线仍缺 12–62 步本机日志；实时录屏、全新 GPU 重新训练、权重实例外备份与公开发布未包含在本次交付。

![相同环境内的 SFT / GRPO 对照](artifacts/day15/figures/evaluation_comparison.png)

无需 API key、GPU 或 Docker，即可回放已记录的 dev 工具轨迹：

```bash
python3 scripts/day15_demo.py --case improvement
python3 scripts/day15_demo.py --case regression
python3 scripts/check_day15.py
```

回放不执行候选代码，也不进行新模型推理。可分享的离线证据包位于 `artifacts/day15/zzh-repair-evidence.tar.gz`，不是权重备份或完整训练源码包。

学习复盘：[第 1–5 天](docs/DAYS_1_5_LEARNING_REVIEW.md)、[第 6 天](docs/DAY6_LEARNING_REVIEW.md)、[第 7–8 天](docs/DAYS_7_8_LEARNING_REVIEW.md)、[第 11–12 天](docs/DAYS_11_12_LEARNING_REVIEW.md)。

第九天：[数据卡](docs/DAY9_DATA_CARD.md)、[执行与存储说明](docs/DAY9_RUNBOOK.md)、[准备验收](reports/day9_local_acceptance.json)。准备验收通过不等同正式训练完成或能力提升。

自己动手执行：[迁移后手动训练指南](docs/MANUAL_TRAINING_GUIDE.md)，区分 Mac 与 GPU 终端，按检查、服务、配置、预检、启动的顺序操作，并说明 SwanLab 的用途和接入现状。

## 无依赖复现

需要 Python 3.10+，数据与本地 fixture 检查只用标准库，不需要 API key、联网或 GPU。从仓库根目录运行：

完整测试中的公开资源导出与固定 Agent-R1 接口需要先按 [克隆后准备](docs/GITHUB_RELEASE.md) 配置。只展示案例和核对现有结果时，使用上方第 15 天回放与检查命令即可。

```bash
python3 scripts/check_day1.py
python3 scripts/verify_episodes.py --backend trusted-local
python3 -m unittest discover -s tests -v
```

第一条命令检查第一天的 7 项标准，并重新执行数据验收：每题缺陷代码至少失败一条公开测试及一条私有测试，参考实现通过全部测试。结果写入 `reports/day1_acceptance.json` 和 `reports/prototype_verification.json`。Worker 异常、零测试和执行超时不会被当成有效的缺陷任务。

第二条命令用本仓库已知的原始代码与参考补丁驱动 40 次完整 episode，验证错误得 0、正确得 1、重复终止不重复计分及工作区清理。它不调用模型，不能作为模型成功率。结果写入 `reports/episode_verification.json`，逐步轨迹写入忽略提交的 `runs/prototype-episodes/`。

原型实测：第一天 7/7 项通过；20/20 任务的数据验收及 episode 验证通过。第 4–5 天完整自动测试 60/60 通过，包含真实 Docker 用例；未配置 Docker 时，该用例会跳过，因此普通离线测试不能代替容器验收。服务协议测试需要本机 loopback 权限。详见 [进度与验收](docs/PROGRESS.md)。

## 第 2–3 天：正式来源数据

首批 72 train / 32 dev 修复任务，分别来自 31 / 14 道不同 MBPP 原题；当时单独冻结 50 道 test 来源。每个入选 train/dev 任务含 2 条公开测试和 7 条私有用例，104/104 均参考通过、缺陷失败。题目及版本细节见 [MBPP 数据卡](docs/MBPP_DATA_CARD.md)。后续第九天 train 扩充至 300；最终 test 构建与执行状态以上方最新记录及 [test 数据卡](docs/FINAL_TEST_DATA_CARD.md) 为准。

已有官方快照后可完全离线复现：

```bash
python3 scripts/fetch_mbpp.py --check
python3 scripts/build_mbpp.py --check
python3 scripts/verify_mbpp.py
```

验收结果写入 `reports/mbpp_verification.json`。资源位于 `data/mbpp_repair/v0.1/`，其中 manifest 包含文件和转换代码校验和，selection_report 记录来源过滤、审查与缺陷筛选，test_sources.lock 冻结独立来源。已有文件不同会报错，不自动覆盖。

任务生成器 `scripts/build_prototype.py` 包含本仓库编写的 20 个原题及显式定位的缺陷注入规则。初次生成可不带 `--check`；已有文件有差异时会报告差异，不覆盖修改。后续变更任务时应显式更新数据版本、生成资源及校验和。

## 数据范围

| 缺陷类型 | train | dev | 总数 |
|---|---:|---:|---:|
| 边界判断 | 2 | 3 | 5 |
| 索引/切片 | 3 | 2 | 5 |
| 初始化 | 2 | 3 | 5 |
| 遗漏分支 | 3 | 2 | 5 |
| 合计 | 10 | 10 | 20 |

每题 2 条公开测试、至少 6 条私有验收用例，包含待修源码、参考实现、明确输入域和函数签名。公开与私有用例可共同包含关键边界，私有集合另外覆盖回归情况；这里的“私有”是后续运行时的可见性约定，不表示代码仓库中的用例保密。

20 道原题的 source_id 各不相同，没有跨 split 共享原题。题目简单，train/dev 也共享一些缺陷模式；它们用于协议与数据流程开发，不代表真实仓库能力，不能作为最终独立测试集。

```text
data/prototype/
  manifest.json                  # 文件校验和、版本、任务索引
  train/repair-001/
    task.json                    # 需求、签名、来源、缺陷类型
    starter/solution.py           # 缺陷代码
    reference/solution.py         # 参考修复；不暴露给 Agent
    public_tests.py               # 可见测试
    private_tests.json            # 独立验收输入与期望值；不暴露给 Agent
  dev/...
```

环境只将 starter/solution.py 和 public_tests.py 放入每次独立创建的 Agent 工作区。不能把包含参考答案和私有用例的整个仓库挂载给 Agent。

## 三个工具契约

`read_file(path)`、`write_file(path, content)`、`run_tests()` 的 schema、允许路径、源码限制和响应格式见 [工具契约](docs/TOOL_CONTRACT.md)。schema 位于 `code_repair/contracts.py`，调度与 episode 状态位于 `code_repair/environment.py`，执行后端位于 `code_repair/execution.py`。

当前最多 6 次决策，中间奖励为 0；最终回复或步数耗尽触发一次私有验收。错误参数消耗一步，非法写入保持原文件。基础设施故障单独标为无效 episode，不能算普通模型失败。本地环境提供 `astep()`；真实 Agent-R1 适配器位于 `code_repair/agent_r1_env.py`，多轮训练 Flow 与诊断共用 `agent_session.py`。

## 执行范围

离线 verifier 和显式选择的 `trusted-local` 后端仅用于本仓库已知、人工编写的 fixture。临时目录、独立子进程和超时不构成安全沙箱，不能用该后端执行模型生成代码或其他不可信代码。

Docker Desktop 已安装并通过本机 Linux VM 的真实隔离验收：固定镜像 digest、禁用网络、只读根文件系统、非 root、资源限制、不挂载宿主目录。候选 worker 只收到源码、函数名和输入，期望值由容器外的验收器比较。独立服务持有私有用例，客户端可只加载公开资源；服务不会读取参考实现。环境锁定见 `SANDBOX_LOCK.json`，操作说明见 [执行服务与容器验收](docs/EXECUTION_SERVICE.md)。当前 AutoDL 通过 SSH 隧道访问该 Mac 服务；如迁移执行服务到 Linux CPU 主机，需要在新主机重跑隔离验收。

本机打开 Docker Desktop 后，从仓库根目录运行：

```bash
export PATH="/Applications/Docker.app/Contents/Resources/bin:$PATH"
export CODE_REPAIR_DOCKER_IMAGE="$(python3 -c 'import json; print(json.load(open("SANDBOX_LOCK.json"))["image"])')"
python3 scripts/verify_sandbox.py
python3 scripts/verify_service.py
python3 scripts/check_day45.py
```

本机已拉取固定的官方 Python 镜像；执行器不会自动拉取。三条命令分别记录隔离证据、124 个任务的完整 HTTP/container episode 及当天总验收；报告位于 `reports/sandbox_verification.json`、`reports/service_verification.json` 和 `reports/day45_acceptance.json`。这些是已知补丁的环境测试，没有模型参与，也没有运行最终 test 来源。

`UPSTREAM_LOCK.json` 保留第一天的历史选择；当前源码、模型及实际依赖版本见 `TRAINING_SOURCE_LOCK.json`。第六天环境验收可复查：`python3 scripts/check_day6.py`；本机完整保留第八天产物时，可运行 `python3 scripts/check_day8.py` 复查基线与自建训练验收。正式规模数据、最终 test 用例及人工复核、GRPO 能力提升评测仍待完成；5-update smoke 不代表正式训练效果。
