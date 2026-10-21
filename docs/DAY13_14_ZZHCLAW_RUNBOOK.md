# 第 13–14 天：第 70 步模型回接 ZzhClaw

2026-10-21。本阶段只做应用接入，不继续 GRPO。模型留在 AutoDL；Mac 不需要下载 `model.safetensors`。

## 已完成和待完成

| 项目 | 当前状态 |
| --- | --- |
| HF 导出、独立 dev/test 对照 | 已完成，采用冻结的 step70 候选 |
| ZzhClaw 受限 `repair` 入口、会话与事件记录 | 已实现 |
| 新 profile 与通用 Agent 回归 | 51 项通过 |
| HTTP → ZzhClaw → 原修复环境 → 真实 Docker | 两个脚本诊断 episode 通过，错误 0 / 正确 1 |
| 真实模型经 vLLM API 驱动 ZzhClaw | 2026-10-21 两题 smoke 完成，1 成功 / 1 失败，均有效 |
| 应用内 SFT-only / step70 dev 对照 | 已完成：69/96 → 75/96，+6.25 pp；配对改善 9 / 退化 3 |
| 第 13–14 天整体验收 | 受限 CLI 回接范围内 15/15 通过，complete=true |

本地脚本验收只使用已知 dev 原始/参考代码驱动动作，不是模型自主修复成绩；随后已完成真实模型 smoke 和双模型 dev 对照。代码位于另一个仓库 `/Users/zzh/Documents/GitHub/zzhclaw`，新增 `zzhclaw/agent/repair.py`、`repair_cli.py`，命令为 `python -m zzhclaw repair`。普通 CLI / TUI / Web 的工具循环未切换到修复模式；本阶段交付独立命令行 profile。完整结果与边界见 [迁移报告](DAY13_14_MIGRATION_RESULTS.md)。以下保留用户实际执行的操作步骤。

真实模型 smoke 已在北京时间 13:59:40–13:59:51 完成，总计约 11.3 秒，无基础设施异常。两个 episode 均为 5 次合法决策，初始 token 指纹校验通过，prompt / response 均未超预算。`mbpp-526-m01` 只改成首字母大写，未实现尾字母大写，公开测试 0/2 后仍主动结束，私有验收 2/7，奖励 0；`mbpp-527-m01` 将错误的 `!=` 修正为 `==`，公开 2/2、私有 7/7，奖励 1。失败属于模型修复与停止决策问题，不是链路中断。本次两题不能代表完整能力，不据此修改冻结提示或测试；下一步运行完整应用 dev 对照。证据为 `reports/day13_step70_smoke.json` 与 `reports/day13_real_api_acceptance.json`。

## 为什么增加单独的 profile

模型训练的是 `read_file` / `write_file` / `run_tests` 三个 JSON 动作，不是通用 Shell Agent。直接挂上 ZzhClaw 的全部工具、技能和历史会话会改变任务分布。

现在直接复用 agent-r1 的冻结 `RepairSession` / `run_trajectory`：每次全新任务工作区，只允许 `solution.py` / `public_tests.py`，最多 6 次决策，prompt 4096、response 512 tokens，episode 240 秒，测试 10 秒。验收代码由 Mac Docker 执行，私有用例不进模型。ZzhClaw 负责受限 Agent 入口、会话持久化、工具事件和结果展示。

Mac 调用 vLLM `/tokenize` 获取真实 token IDs，再调用 `/v1/completions`，并由 `/detokenize` 解码返回的真实 IDs。不启用原生工具调用解析器。初始 prompt 必须与 GPU 上离线 HF tokenizer 的 token 指纹相同；使用不一致的模板会直接报错。

采样显式指定 BF16、temperature 0.6、top_p 0.95、top_k 20、repetition_penalty 1.1、512 response tokens；后两项来自原模型的 generation config。每个决策的 seed 为 episode seed 加决策下标。vLLM 与原 Transformers 的计算后端及随机流不同，因此是新的迁移 dev 实验，不能把两者当作逐字等价推理。SFT / step70 使用相同应用协议。

## 1. Mac：上传小脚本

保持 Docker Desktop、Mac 和 Codex 开启。不需要上传 ZzhClaw 或私有测试到 GPU。

```bash
cd /Users/zzh/Documents/ChatGPT/agent-r1
python3 scripts/day6_local_service.py status
python3 scripts/day13_prepare.py

scp -i runs/ssh/autodl_day6_ed25519 -P 37856 \
  scripts/day13_serve_model.py \
  root@connect.westc.seetacloud.com:/root/autodl-tmp/agent-r1-day6/scripts/day13_serve_model.py
```

服务状态应为 Docker、332 个 train/dev 任务。若 8765 服务未运行，执行 `python3 scripts/day6_local_service.py start --dataset data/mbpp_repair/v0.2`。不要在已有服务占用端口时再次启动。最终 test 服务 8766 不用于本次调试，不需要为本次迁移重开 test。

## 2. AutoDL：启动第 70 步模型服务

在你的 GPU SSH 终端中执行：

```bash
cd /root/autodl-tmp/agent-r1-day6
nvidia-smi
.venv/bin/python -u scripts/day13_serve_model.py --stage step70 --serve
```

脚本先重新计算完整导出权重 SHA256、核对冻结运行时、用本机 tokenizer 计算 32 个 dev prompt 指纹，再检查 GPU 空闲，最后前台启动 vLLM 0.11.0，仅监听 `127.0.0.1:8000`。它不会下载模型、启动训练或停止其他进程。看到 API server startup complete 后保持终端运行。

首次加载估计 2–5 分钟，取决于实例；这是估计，不是已经测出的启动耗时。若提示 GPU 被占用或报错，保留日志先排查，不要重复启动。仅做文件预检可去掉 `--serve`；文件预检通过不等于服务已启动。

## 3. Mac：模型 API 隧道

另开一个 Mac 终端，执行后保持打开：

```bash
cd /Users/zzh/Documents/ChatGPT/agent-r1
ssh -i runs/ssh/autodl_day6_ed25519 -p 37856 \
  -o IdentitiesOnly=yes -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=30 -o ServerAliveCountMax=3 \
  -N -L 18000:127.0.0.1:8000 \
  root@connect.westc.seetacloud.com
```

这个新隧道把 Mac 18000 转发到 GPU 8000。模型请求方向与之前 GPU 访问 Mac 的反向评价隧道不同；本次 Mac 自己访问 8765 Docker，不依赖 GPU 的 18765/18766 评价端口。现有其他隧道无需关闭。

## 4. Mac：同步小型身份报告并跑两题

再用一个 Mac 终端：

```bash
cd /Users/zzh/Documents/ChatGPT/agent-r1
mkdir -p runs/day13
scp -i runs/ssh/autodl_day6_ed25519 -P 37856 \
  root@connect.westc.seetacloud.com:/root/zzh-day13-model-step70.json \
  runs/day13/model-step70.json

/Users/zzh/Documents/GitHub/zzhclaw/.venv/bin/python \
  scripts/run_zzhclaw_repair.py --stage step70 --scope smoke

/Users/zzh/Documents/GitHub/zzhclaw/.venv/bin/python -u \
  scripts/run_zzhclaw_repair.py --stage step70 --scope smoke --execute
```

第一条 Python 命令只检查模型身份、API 和 Docker；第二条实际调用模型，经 ZzhClaw 修复两个不同来源的 dev 任务，seed17。预计数分钟，依任务而变，不预先承诺两题必须成功。即使修复失败，工具契约、轨迹和基础设施正确也可以证明链路正常；能力对照用完整 dev。

输出：`reports/day13_step70_smoke.json`；ZzhClaw 会话：`runs/day13/sessions/step70/smoke/`。发生基础设施或 API 异常会记入 `invalid_attempts` 并停止，不能当模型正常失败。原始模型非法动作会按冻结契约消耗决策，合法的修复失败记 0 分。

## 5. 两个模型的完整迁移 dev 对照

先保持 step70 服务，运行：

```bash
cd /Users/zzh/Documents/ChatGPT/agent-r1
/Users/zzh/Documents/GitHub/zzhclaw/.venv/bin/python -u \
  scripts/run_zzhclaw_repair.py --stage step70 --scope dev --execute
```

完成后在 **GPU 模型服务终端**按 Ctrl+C，确认该服务退出、GPU 空闲，再执行：

```bash
cd /root/autodl-tmp/agent-r1-day6
.venv/bin/python -u scripts/day13_serve_model.py --stage sft --serve
```

保持模型 API 隧道。Mac 同步 SFT 身份报告，再运行 SFT：

```bash
cd /Users/zzh/Documents/ChatGPT/agent-r1
scp -i runs/ssh/autodl_day6_ed25519 -P 37856 \
  root@connect.westc.seetacloud.com:/root/zzh-day13-model-sft.json \
  runs/day13/model-sft.json

/Users/zzh/Documents/GitHub/zzhclaw/.venv/bin/python -u \
  scripts/run_zzhclaw_repair.py --stage sft --scope dev --execute

python3 scripts/compare_zzhclaw_repair.py
```

每模型 32 题 × 3 seeds = 96 个单次 episode，总计 192。每个有效 episode 后落盘，相同输入可重跑命令续接缺失条目，不重复已完成项。新报告和原 dev/test 报告分开保存。完整对照的耗时需根据真实 API smoke 实测更新；原 Transformers dev 对照约 15 分钟只能作为历史参考，不能当新服务的计时结果。

### 2026-10-21 连接中断记录

step70 完整 dev 最初保存 55/96 条有效 episode，第 56 条 `mbpp-564-m01 / seed29` 在 `/detokenize` HTTP 请求时发生 `ConnectionResetError`，已单列到 `invalid_attempts`，未算作模型失败。只读排查确认 GPU API 进程 16534、引擎进程 16615 仍运行，远端 8000 `/v1/models` 返回正确 step70；Mac 18000 已无监听。恢复上面第 3 节的 SSH 隧道后，用户重跑同一条命令，跳过已保存的 55 条并完成剩余 41 条。无需重启 GPU 服务、改模型或重做已完成评估。诊断证据：`reports/day13_connection_diagnosis.json`。

北京时间 14:13:31，step70 应用 dev 全部完成：96 个唯一有效 task/seed 配对，75 成功、21 失败，成功率 78.125%；seed17 / 29 / 43 分别为 24/32、23/32、28/32。那次连接异常仍保留在无效尝试记录，重试结果计入有效覆盖。另有 `mbpp-577-m01 / seed29` 出现一次无法解析的模型动作，按原契约消耗决策，该 episode 最终失败，未被当作基础设施异常排除。有效 episode 实测耗时合计约 467.5 秒，开始至结束约 11 分钟（包含连接中断与人工恢复）。证据为 `reports/day13_step70_dev_acceptance.json`。这是 ZzhClaw / vLLM 后端上的 dev 结果，不能直接与原 Transformers 基线相减声称 GRPO 收益。

北京时间 14:25:50，SFT 应用 dev 96/96 完成，成功 69 条；无无效尝试与非法模型动作。生成 `reports/day14_application_comparison.json` 并运行 `python3 scripts/check_day14.py`，15/15 项检查通过。受限 CLI 回接的第 13–14 天验收完成；本次不包括通用 UI / 工具集的迁移，不代表原 225 步训练目标完成。

## 整体验收标准

1. 真实 step70 API 经 ZzhClaw 完成 smoke，token 模板一致，只有三个受限工具，无效基础设施单列。
2. 相同应用代码、环境和参数下，SFT / step70 各 96 个有效 dev episode，任务与 seeds 严格配对。
3. 生成 `reports/day14_application_comparison.json`，保留成功数、差异百分点、改善/退化、分 seed 结果及所有无效尝试；负向结果同样报告。
4. 保存可复现命令、版本、权重/脚本/协议指纹和原始轨迹。报告不包含 token。
5. 审查完成后才宣布第 13–14 天验收通过。没有预设“必须提升多少”才允许保留结果。

冻结协议位于 `training/integration/evaluation_protocol.json`，`day13_prepare.py` 不会覆盖已有实验协议。若要修改参数或代码，另建实验版本，不能悄悄改协议后覆盖成绩。

## 已有结果和边界

原冻结 dev：SFT 63/96（65.625%），step70 72/96（75%），+9.375 个百分点。独立最终 test：SFT 90/126（71.43%），step70 93/126（73.81%），+2.38 个百分点，配对改善 7 / 退化 4。test 来自 50 个冻结来源中的 42 个，另有 8 个按模型无关标准排除；3 seeds 相关，未做统计显著性检验。

GRPO 实际更新到 74 步，连续 5 个 batch 无组内奖励差异触发保护停止；候选来自最近完整 checkpoint70，第 71–74 步未保存。原 225 步训练目标没有完成。之后若继续训练到 225/255，属于新实验；已有 test 已被查看，不能用它反复选点再称为全新盲测。

GPU 上的完整权重没有完整备份到 Mac。API 回接不需要下载权重，但不能据此释放实例或删除原权重。相关小型报告已在 Mac，本说明不构成模型备份验收。
