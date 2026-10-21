# 基于 Agent-R1 的 Python 代码修复 Agent 训练与评测：执行方案

编写日期：2026-10-12（Asia/Shanghai）。面向 Agent 应用开发实习；与 ZzhClaw 主项目配合。

2026-10-14 实施更新：第六天环境与诊断链路已通过 16/16 验收，完成两组各 2 次 GRPO 更新和 checkpoint 验证。三工具为引导式 JSON/Hermes 适配诊断；自建代码修复训练与能力提升尚未验证。最新事实见 [第六天实测结果](docs/DAY6_RESULTS.md)。下文“尚未安装/训练”等表述保留计划编写时点的状态。

本文是实施计划。尚未安装训练环境、租用 GPU、实现 recipe 或运行训练。硬件、参数、工期均为起始建议，不能视为已验证的运行配置或结果。

当前进度（2026-10-12）：第一天 7 项验收全部通过。第 2–3 天数据流程与首批数据验收已完成：固定 MBPP 来源，生成 72 train / 32 dev 任务（31 / 14 道原题），104/104 验收通过，50 道独立 test 来源已冻结。第 4–5 天已实现独立执行服务，并在本机 Docker Desktop 的 Linux VM 通过 22 项隔离检查、124 个任务共 252 次脚本 episode（含并发）及 60 项自动回归。正确补丁得 1、原始缺陷得 0，无重复奖励或串题；没有模型参与。完整规模数据扩充、最终 test 用例及人工复核、目标训练主机复验、Agent-R1 适配器和训练仍待完成。复现入口见 [README](README.md)，证据见 [进度与验收](docs/PROGRESS.md)，来源规则见 [MBPP 数据卡](docs/MBPP_DATA_CARD.md)。

## 1. 项目目标与边界

项目名称：**基于 Agent-R1 的 Python 代码修复 Agent 强化学习训练与评测**。

要验证的问题：在相同工具、提示词与执行预算下，GRPO 训练能否提高小模型利用公开测试反馈修复 Python 函数的成功率？

- ZzhClaw 负责 Coding Agent 系统、交互、会话与评测入口。
- 本项目负责数据、可执行训练环境、终局奖励、GRPO 实验、权重导出与回接验证。
- 第一版限制在一个小型 Python 源文件、一个明确缺陷、标准库任务。
- 第一版完成一个模型和一种 RL 算法。暂缓真实大型仓库修复、多个训练框架、复杂过程奖励与模型排行榜。
- 基线先用现有 Instruct 权重；仅在工具协议无法稳定执行时增加 SFT，并保留 SFT-only 对照。

最终交付：可复现的数据版本、训练配置、真实更新记录、可加载 checkpoint、独立测试报告、ZzhClaw 接入演示。测试集提升是待验证结论。

## 2. 起始技术选择

| 项目 | 首版选择 | 说明 |
|---|---|---|
| 模型 | Qwen/Qwen2.5-Coder-1.5B-Instruct | 小规模代码模型候选；先测工具协议和修复基线 |
| 算法 | GRPO | 每个任务采样多条轨迹，使用组内相对奖励；不开 critic |
| 框架 | Agent-R1 当前 main 的固定 commit | 不混用 legacy 教程 |
| 依赖 | 按官方安装说明建立 verl 兼容环境 | 官方说明要求 verl==0.7.0，但必须以 import 和最小训练验证兼容性 |
| 执行环境 | 独立的受限代码执行服务 | 候选代码与私有验收器隔离 |
| 推理与回接 | vLLM + OpenAI 兼容服务 | 使用 Hermes 工具协议，训练和部署验证一致性 |
| GPU 起点 | 1 张 80GB 显存 NVIDIA GPU | 是降低调试难度的资源假设，不是最低配置或运行保证 |

若 1.5B 在开发任务上几乎没有成功轨迹，先排除协议、工具与数据问题，再降低训练任务难度或做小规模 SFT。只有证据显示模型能力确实不足时，才换更大模型，并重新运行所有基线。

不要一开始选择 7B、多机或 QLoRA。首版采用全参数训练以减少适配分支；若显存不足，先降低并发和长度、启用 offload，再考虑 LoRA，并单独验证该版本对 rollout 权重同步与导出的支持。

## 3. 数据：先有 20 个原型任务，再扩充训练集

### 3.1 数据来源和划分

优先利用 ZzhClaw 已有题目调试环境，已有反复查看的题目不作为最终独立测试证据。

规模扩充可使用 Google Research 的 MBPP 原题与参考代码，转化为自建的缺陷修复任务。MBPP 原本是程序生成数据，不能直接称为现成的 Bug 修复 benchmark。

遵循原始来源划分：MBPP 训练来源 task_id 601–974；开发来源 511–600；测试来源 11–510。task_id 1–10 只用于示例。使用 sanitized 子集时同样继承来源划分；若过滤后数量不足，按同一来源集合补充经人工验收的原题。

先对原题与代码做去重，再注入缺陷。同一道原题、同一参考实现、近重复实现及其所有变体只能属于一个集合。

| 阶段 | 训练任务 | 开发任务 | 最终测试任务 | 作用 |
|---|---:|---:|---:|---|
| 原型 | 10 | 10 | 暂不运行 | 验证协议、工具、验收和轨迹 |
| 首版目标 | 约 300 | 约 60 | 约 150 | 小规模 RL 与独立对照 |

首版目标分别来自约 100 / 20 / 50 道不同原题，每道尽量保留 1–3 个有效缺陷。数量不足时补充不同原题，不能为了凑数复制近重复任务。报告同时列出原题数和变体数；150 个测试变体不等于 150 道独立原题。

公开原题可能进入过模型预训练数据；来源划分和新造缺陷不能证明彻底消除污染。实验结论限定在该修复任务分布。

### 3.2 缺陷类型和验收

首版四类：比较边界错误、索引或切片错误、累加/计数初始化错误、遗漏条件分支。每题只制造一个缺陷。

用 AST 或明确的源码定位实施 mutation，避免不受控的全局文本替换。每个候选任务通过以下检查才能入库：

1. 参考实现通过全部公开和私有测试。
2. 缺陷实现至少失败一个私有验收测试。
3. 为便于学习测试反馈，首批训练任务还应至少失败一个公开测试。
4. 需求、函数签名、合法输入和期望行为一致；没有未说明的特殊规则。
5. 不依赖第三方包、网络或外部文件；输入和输出可以被可靠验证。
6. 测试有实际断言且数量非零；异常退出不能算通过。

每题提供 1–2 个公开测试、至少 5 个独立的私有验收用例作为起点。根据任务补充正常值、边界值和回归用例；不存在合法空输入时，不强造空输入用例。原始 MBPP 测试数量较少，必须检查和扩充，不能仅靠三条断言声称充分验收。

自动生成的测试需检查与需求一致；参考代码输出可以帮助构建候选测试，但不能代替需求审查。人工审查所有最终测试原题与用例，训练集至少抽查 30 个任务，发现系统性问题则扩大审查。

### 3.3 每题目录与元数据

```text
tasks/<split>/<task_id>/
  task.json                 # task_id、source_id、split、缺陷类型、需求、签名
  starter/solution.py        # 给 Agent 的缺陷源码
  public_tests.py            # 给 Agent 的调试测试
  private_tests.json         # 私有输入及期望值，只由可信验收器读取
  reference/solution.py      # 只用于离线数据验证
```

这里是数据存储结构，不是模型工作区的挂载结构。模型只能访问 starter 与公开测试；不能把整个 tasks 目录挂载给候选代码。

冻结数据版本时记录源数据 commit/校验和、source_id、mutation 位置、split、测试校验和与转换代码版本。

## 4. 环境与工具：训练和 ZzhClaw 共用同一契约

### 4.1 三个工具

| 工具 | 接口 | 行为 |
|---|---|---|
| read_file | path | 只读取 solution.py 或 public_tests.py |
| write_file | path, content | 只替换 solution.py；长度和语法检查，保留函数签名 |
| run_tests | 无参数 | 在执行服务中运行固定公开测试，返回规范化失败摘要 |

工具名称、参数 schema、错误文本和返回格式同时用于 Agent-R1 与 ZzhClaw 的受限修复 profile。第一版整文件替换比复杂 patch 格式更容易验证。

不要在训练环境暴露通用 run_bash、任意命令参数、联网、全局文件读取或全局 skills。ZzhClaw 的主产品仍可有这些功能，但训练模型回接对照必须启用相同的受限工具集。

### 4.2 一条 episode 的规则

初始观察包含需求、可修改文件、工具 schema 和执行预算；先由模型读取源码，随后修改、运行公开测试、根据反馈再修改。模型以普通最终回复主动结束；无需增加一个会泄露私有结果的验收工具。

- 最多 6 次模型决策；每次最多 1 个工具调用，不执行并行工具调用。
- 每次生成上限 512 tokens；首版任务源码建议不超过 60 行。经开发集检查确有截断，再统一调整到 768 或 1024。
- 每步输入上限 4096 tokens；保留需求、工具 schema、最近候选代码和最近测试摘要，防止长日志塞满上下文。
- 单次公开测试最多 5 秒；行动时间预算首版 120 秒，终局私有验收另有最多 5 秒的执行预算，容器清理可能额外耗时。基于开发集测量调整并在对照前冻结。
- 输出限制 8KB，反馈只保留失败定位、异常类型和必要 traceback，避免堆栈无限增长。
- 达到步数上限时，验收当前候选代码并正常终止；格式错误消耗一步并提供固定反馈。
- 超时、上下文超限、worker 异常分别记录，不统称为模型修复错误。

6 次决策意味着一条常见路径是 read → write → test → write → test → final。成功不是必须调用完所有工具；主要奖励仍只看最终行为正确。

### 4.3 代码执行与私有验收

执行服务每个 episode 使用独立工作区；候选代码在无网络、非 root、限制 CPU/内存/时间的容器中执行，不挂载训练进程、凭证、私有测试和参考答案。原始缺陷源码每次恢复。

对于本项目选择的简单输入输出函数，可信验收器持有私有输入和期望值，通过受限 worker 执行候选函数并比较返回值；私有测试源码不放入候选可读目录。无法通过这种方式可靠验收的任务先排除。

单个临时目录或 subprocess timeout 不等于完整沙箱。若 AutoDL 实例无法使用所需隔离机制，先解决执行服务部署，或明确限制为受信任合成代码的实验；不能把目录副本描述成容器级隔离。

## 5. 奖励：先做终局二值奖励

```text
中间步骤：r = 0
episode 结束：
    候选代码有效、函数接口符合约定、全部私有验收通过：R = 1
    候选错误、超时、越界尝试或验收未通过：R = 0
```

终局奖励只加一次，挂在最后一个实际动作对应的 step。到达步数上限也必须验收，不能因为外层 loop 直接 break 丢掉最后奖励。

公开测试结果是观察反馈，不重复作为额外 reward。第一版不奖励格式、不奖励工具调用本身、不奖励少调用，也不做 LLM-as-a-judge。

基础设施异常必须标记为 invalid attempt，不能冒充普通模型失败。训练侧要对同一 task 重试补足 n=4 的完整有效分组；达到预设重试上限后整组作废并补充新组，保持每个更新的完整任务组数。若首版未实现分组恢复，停止该批并在恢复基础设施后重新收集，不能随意删除单条 rollout 破坏分组。对模型生成无限循环导致的执行超时则正常记 0。

GRPO 要记录同题多条轨迹的奖励：若某组全 0 或全 1，通常缺少组内相对学习信号。先在开发集探测奖励分布；成功率约 15%–65% 可作为工程参考区间，不是算法保证。若绝大多数组都无差异，先排查问题和任务难度，不盲目增加训练时长。

## 6. 接入 Agent-R1 的实施位置

在固定版本的 Agent-R1 上新增 recipe，保留核心 trainer：

```text
recipes/code_repair/
  __init__.py                # 导入注册项，导出 flow
  base.yaml                  # flow/env 配置
  code_repair_agent_flow.py   # 基于 AgentEnvLoop，处理终止、清理、轨迹
  env.py                     # AgentEnv.reset()/async step()
  tools.py                   # 固定工具 schema 与分派
  evaluator.py               # 与可信执行服务通信
  prompts.py                 # 固定系统提示词
  data_preprocess/process_code_repair.py
examples/code_repair/run_grpo.sh
scripts/verify_tasks.py
scripts/evaluate.py
scripts/export_checkpoint.sh
reports/
```

Agent-R1 当前 AgentEnv 接口为 reset 返回 Observation，async step 返回 `(Observation, reward, done, info)`；通用 loop 将环境 reward 写入 AgentFlowStep.reward_score。Observation.messages 必须包含完整的下一轮输入，而不只是新增工具输出。自定义 env 的注册模块必须在 worker 里导入，否则会出现找不到环境类型。

flow 配置草案：

```yaml
- name: code_repair
  _target_: recipes.code_repair.CodeRepairAgentFlow
  env_type: code_repair
```

这是待实现配置草案，CodeRepairAgentFlow 尚不存在。其运行逻辑以官方 AgentEnvLoop 为基础，并确保任何提前退出路径都处理终止与资源回收；episode 步数计数应由 env 和外层 loop 一致维护。当前通用 loop 不会自动将 env.step 的 info 保存到 step.extra_fields，薄封装需要显式保存验收结果、终止原因与工具耗时等诊断信息。

Parquet 行至少包括：prompt、agent_name、reward_model、env_kwargs，并按固定版本 loader 需要保留 data_source、extra_info 等字段。env_kwargs 只放 task_id/任务服务索引等数据，不把参考实现或私有测试插入模型观察。

当前源码仅在 step.reward_score 为 None 时调用外部评分，因此环境显式返回的 0.0 / 1.0 可以直接使用，首版将 custom_reward_function.path 设为 null。当前 GRPO 按 trajectory_uids 汇总整条轨迹的步骤奖励，再在同题的 n 条轨迹之间计算相对优势，并广播到该轨迹各步 action token；不能把终局 1 重复回填到每一步。

重要验证：手工脚本动作修复正确时，trainer 最终收到的 episode 奖励必须恰好为 1；错误修复为 0。用 reward 单元检查确认没有二次计分。不能直接复制问答任务的答案匹配奖励函数。

## 7. AutoDL 环境验证顺序

先在本地完成任务转换和离线验收，再租 GPU。

2026-10-13 实施补充：AutoDL 官方说明普通容器实例内不支持 Docker。先规划 GPU 实例运行训练、通过 SSH 反向隧道访问 Mac Docker 执行服务；连接和 worker 可达性必须实测。不假设普通实例能够安装并运行 Docker daemon。第六天状态与清单见 [DAY6_RUNBOOK.md](docs/DAY6_RUNBOOK.md)，目前只完成本地准备，尚无 GPU 实例或训练结果。

1. 选择 Linux NVIDIA CUDA 实例，起始按 1×80GB 规划；记录 CPU、RAM、磁盘、驱动、CUDA、GPU 型号。不要依赖未核对的镜像默认依赖。
2. 按 Agent-R1 官方安装说明建立 verl 兼容环境。verl v0.7.0 的安装源码要求 Python>=3.10、CUDA>=12.8，建议 Python 3.12；选择镜像前检查驱动与运行时兼容。固定 Agent-R1 与 verl 源码 revision、torch/vLLM/transformers 版本；保存 pip freeze 和镜像信息。
3. 验证 CUDA 可用、所有核心模块可 import、模型可以生成文本。
4. 验证 Hermes 工具解析：read_file、write_file、run_tests 各调用成功一次，完整经过一条多轮轨迹。
5. 用官方单步和工具示例做 1–2 次参数更新的环境检查，需按当前脚本调整 GPU 数、batch 和 logger；默认脚本不保证单卡可直接运行。
6. 在小开发样本上先测原模型的工具格式、终局奖励和组内奖励差异，再运行自建修复 recipe 的 5 次更新，导出 checkpoint 并重新加载。
7. 确认梯度、权重、奖励、checkpoint 都正常后，才进入正式训练。

官方 README 与安装说明提到 verl==0.7.0，同时 README 又要求含 AgentFlow/async rollout 支持的近期源码。以固定 revision 的真实 import 和 smoke 结果解决兼容性问题，不把单独 pip install verl==0.7.0 视为完成配置。

若环境排障超过首个短租窗口，先保存日志、停止闲置 GPU，再针对版本问题处理。训练进程之外的 vLLM 服务需要先关闭，避免占用同一张卡的显存。

## 8. GRPO 起始参数与分阶段运行

以下是拟采用参数，尚未在目标机器实测；需要结合固定版本的 Hydra 配置解析、batch 整除约束和显存调整。

| 参数 | 起点 | 解释 |
|---|---:|---|
| train_batch_size | 16 | 每次更新抽取 16 个不同任务 |
| rollout.n | 4 | 每题 4 条轨迹，形成约 64 个 episodes |
| max_steps | 6 | 每条轨迹最多 6 次模型决策 |
| max_prompt_length | 4096 | 每步输入预算，不是全轨迹总预算 |
| max_response_length | 512 | 每步输出预算 |
| learning rate | 1e-6 | 首轮固定，后续只在 dev 上调整 |
| PPO mini batch | 16 | 按实际框架对任务/步骤 batch 的语义核对 |
| micro batch per GPU | 1 | 降低峰值显存 |
| rollout / logprob micro batch | 1 | 首轮保守设置 |
| rollout workers | 1 | 验证稳定后再增加 |
| rollout 采样 | temperature=0.8，top_p=0.95 | 为同题采样不同轨迹；在版本配置中明确设置 |
| precision | BF16 | 以 GPU 与框架支持为前提 |
| gradient checkpointing | 开启 | 降低训练激活占用 |
| FSDP param/optimizer offload | 开启 | 减少显存，代价是 CPU 内存与速度 |
| critic.enable | False | GRPO 首版不训练价值模型 |
| KL | actor KL loss 开启，系数 0.001 起试 | 需要 reference；不再重复加入 reward KL |
| checkpoint/validation | 每约 10 updates | 小数据先频繁检查，正式参数以吞吐测量调整 |

算法相关键参考官方 GRPO launcher：algorithm.adv_estimator=grpo、actor_rollout_ref.rollout.n、critic.enable=False、actor_rollout_ref.rollout.agent.agent_flow_config_path、default_agent_flow。不能只改 estimator 便称完成多轮 GRPO。

完成 recipe 后，run_grpo.sh 应包含下面这类配置。该命令是开发目标，依赖尚未实现的文件和环境，不是现在即可执行的已验证脚本：

```bash
python3 -m agent_r1.trainer.main_agent_ppo \
  algorithm.adv_estimator=grpo \
  algorithm.norm_adv_by_std_in_grpo=True \
  algorithm.use_kl_in_reward=False \
  data.train_files=data/code_repair/train.parquet \
  data.val_files=data/code_repair/dev.parquet \
  data.train_batch_size=16 \
  data.max_prompt_length=4096 \
  data.max_response_length=512 \
  data.return_raw_chat=True \
  actor_rollout_ref.model.path=Qwen/Qwen2.5-Coder-1.5B-Instruct \
  actor_rollout_ref.model.enable_gradient_checkpointing=True \
  actor_rollout_ref.actor.optim.lr=1e-6 \
  actor_rollout_ref.actor.ppo_mini_batch_size=16 \
  actor_rollout_ref.actor.ppo_micro_batch_size_per_gpu=1 \
  actor_rollout_ref.actor.use_kl_loss=True \
  actor_rollout_ref.actor.kl_loss_coef=0.001 \
  actor_rollout_ref.actor.fsdp_config.param_offload=True \
  actor_rollout_ref.actor.fsdp_config.optimizer_offload=True \
  actor_rollout_ref.rollout.name=vllm \
  actor_rollout_ref.rollout.tensor_model_parallel_size=1 \
  actor_rollout_ref.rollout.gpu_memory_utilization=0.5 \
  actor_rollout_ref.rollout.n=4 \
  actor_rollout_ref.rollout.prompt_length=4096 \
  actor_rollout_ref.rollout.response_length=512 \
  actor_rollout_ref.rollout.log_prob_micro_batch_size_per_gpu=1 \
  actor_rollout_ref.rollout.agent.agent_flow_config_path=recipes/code_repair/base.yaml \
  actor_rollout_ref.rollout.agent.default_agent_flow=code_repair \
  actor_rollout_ref.rollout.agent.max_steps=6 \
  actor_rollout_ref.rollout.agent.num_workers=1 \
  actor_rollout_ref.ref.log_prob_micro_batch_size_per_gpu=1 \
  actor_rollout_ref.ref.fsdp_config.param_offload=True \
  critic.enable=False \
  reward_model.enable=False \
  custom_reward_function.path=null \
  trainer.n_gpus_per_node=1 \
  trainer.nnodes=1 \
  trainer.logger='["console"]' \
  trainer.save_freq=10 \
  trainer.test_freq=10 \
  trainer.total_epochs=3
```

smoke 用 trainer.total_training_steps=5 限制更新次数，并配置首尾保存/评测；先解析 Hydra 配置，确认相对路径、batch 语义与所有键存在。当前 trainer 的 mini batch 会结合 rollout.n 与轨迹边界处理，最多 64×6=384 个 step，不应把它误当成仅 16 个训练序列。

分三个运行阶段：

1. **smoke：5 个 updates。** 验证参数更新、奖励传递、并发隔离、checkpoint 导出，不判断泛化。
2. **首轮：约 300 个训练变体，先 3 epochs。** batch=16 时约为几十次更新，具体以 loader 与 drop_last 为准；开发集选 checkpoint。
3. **扩展：只有 dev 表现、奖励差异和预算支持才追加。** 优先改数据与真实失败，最多尝试一项配置变化，保留旧配置对照。dev 连续三个评测点没有改善可作为停止信号。

需记录 train reward、dev 完整修复成功率、组内不同奖励比例、有效梯度、KL、token、上下文截断率、工具格式错误、无效基础设施 attempts、GPU 峰值内存和秒/update。train reward 上升不能替代 dev/test 结果。

若连续批次全部奖励为 0：暂停扩大训练，检查验收、工具协议、任务难度和 rollout 采样。若只是协议能力不足，可做训练来源上的小规模成功轨迹 SFT；一旦加入 SFT，最终必须比较 Base / SFT-only / SFT+RL。

## 9. 必做评测与可选实验

### 9.1 主实验

| 组别 | 模型 | 工具、Prompt、反馈与预算 |
|---|---|---|
| Base | 原始 Instruct | 完全相同 |
| RL | dev 选出的 checkpoint | 完全相同 |
| SFT-only | 仅在使用 SFT 时增加 | 完全相同 |

先在同一个修复环境内做主对照，隔离权重变化的作用。之后在 ZzhClaw 受限 profile 再做 Base/RL 对照，观察迁移。不要用训练环境里的 RL 结果直接对比另一套工具和 Prompt 下的 ZzhClaw 原始结果。

最终 test 在配置冻结和 checkpoint 选定后运行。首版固定 temperature=0.6、top_p=0.95，分别以 seed 17 / 29 / 43 对每题运行 3 次，用于观察采样稳定性；Base/RL 的参数和种子相同。seed 不是跨硬件完全确定性的保证，需同时固定服务版本与批处理策略。均从原始缺陷开始；单次 episode 内允许多次修改，但不能跨 episode 拼接最佳补丁。主指标是所有有效单次 episodes 的成功率，不是三次中最好一次的 pass@3。

基础设施失败按原 seed 最多重试 2 次；仍无效则单独列出未完成任务、无效次数与有效覆盖率，不能静默排除后声称全量评测完成。

主报告列出：

- 独立原题数、缺陷变体数、attempts 数。
- 每次 episode 完整验收成功率及 Base/RL 配对胜负。
- 所有 attempts 的工具调用、生成 token、耗时；成功和失败分别补充统计。
- 终止原因、格式错误、无效写入和超时。
- 按缺陷类型拆分结果，但不根据 test 结果重新选择训练方案。
- 若计算 bootstrap 区间，按原始 source_id 聚类抽样，不能把同题变体和重复运行当成独立题。

最终测试失败可以做事后诊断；诊断后继续调参则这份 test 已成为开发证据，应另留新测试集或明确说明探索性质。

### 9.2 测试反馈消融（可选）

若要研究“训练是否更好地利用反馈”，采用 Base / RL × 有反馈 / 无反馈的 2×2。无反馈条件可以允许 run_tests 计入预算，但统一返回占位消息并隐藏 stdout/stderr/退出码；说明这种干预的限制。

仅测试“RL 后去掉反馈”只能说明反馈缺失影响 RL 模型，无法单独归因于强化学习。首版时间不足可不做消融，也不要在结论中声称已证明反馈利用机制。

## 10. 接回 ZzhClaw

1. 使用与固定训练版本匹配的官方 checkpoint 导出流程转换为 Hugging Face 权重；FSDP 分片目录不一定能直接被 vLLM 加载。verl v0.7.0 支持 `python -m verl.model_merger merge --backend fsdp --local_dir <checkpoint/global_step_N/actor> --target_dir <merged_hf>`；尖括号项需要替换成真实路径，不可直接复制。actor/huggingface 可能只有配置和 tokenizer，不能当成完整训练后权重。
2. 检查权重、tokenizer、chat template、特殊 token 配置完整；用同一组固定输入验证导出前后的模型行为。
3. 单独启动 vLLM 服务，先验证单工具和多轮调用。实际 step70 训练的是固定 JSON 动作，因此此次使用 tokenize / token completions / detokenize API，加共享解析器，保留训练协议；不启用原生 Hermes parser。若以后改用原生工具协议，应另建迁移实验。
4. 给 ZzhClaw 增加受限 code-repair profile，共享三个工具的 schema/实现、相同上下文策略和测试服务。
5. 增加可固定的 temperature、top_p、max_tokens/决策数等配置，保证 Base/RL 推理参数相同。现有 API 客户端若尚未暴露这些参数，需要补充。
6. 在 ZzhClaw 受限 profile 上适配冻结 benchmark，复用独立验收与报告，分别运行基线和 RL。2026-10-21 实际交付为 `CodeRepairAgent`、独立 `repair` CLI 和 `scripts/run_zzhclaw_repair.py` 批量入口，运行 SFT-only / step70 同环境 dev 对照；通用 ZzhClaw-Eval 任务类型和 UI 扩展不属于本轮交付。完整迁移结果见 [第 13–14 天报告](docs/DAY13_14_MIGRATION_RESULTS.md)。

当前 vLLM 服务在 AutoDL 的启动方式（先按操作指南上传小脚本）：

```bash
cd /root/autodl-tmp/agent-r1-day6
.venv/bin/python -u scripts/day13_serve_model.py --stage step70 --serve
```

Mac 上的受限 ZzhClaw profile 经 SSH 将 18000 转发到 GPU 的 8000，再运行：

```bash
cd /Users/zzh/Documents/ChatGPT/agent-r1
/Users/zzh/Documents/GitHub/zzhclaw/.venv/bin/python -u \
  scripts/run_zzhclaw_repair.py --stage step70 --scope dev --execute
```

本地电脑的 127.0.0.1 不指向 AutoDL；本地调用需要 SSH 隧道或经授权配置的服务地址。模型 API 兼容不代表工具语义自动兼容，必须完成前面的 profile 与多轮验证。

## 11. 参考排期：约 15 个工作日

时间按每天约 3–5 小时估计；框架版本排障和执行隔离可能延长，不保证两周完成。

| 工作日 | 任务 | 当天验收 |
|---|---|---|
| 1 | 固定任务、模型、工具契约；整理 20 个原型任务 | 每题参考通过、缺陷失败 |
| 2–3 | 实现任务转换、mutation、测试扩充与来源划分 | 数据验证报告；test 来源冻结 |
| 4–5 | 实现受限工具、执行服务、公开反馈和私有验收 | 脚本正确修复得 1，错误得 0；无串题 |
| 6 | AutoDL 环境与工具协议检查 | 固定依赖；官方最小更新成功 |
| 7 | 接入 recipe，先测小 dev 样本的原模型协议与奖励分布 | 工具可用；有可学习的组内奖励差异 |
| 8 | 完成完整原模型 dev 基线和自定义 5-update smoke | baseline-dev 报告；真实参数更新；checkpoint 可加载 |
| 9–10 | 扩充约 300 train；正式 GRPO 首轮 | 配置、日志、显存、吞吐、checkpoints |
| 11 | dev 选 checkpoint，必要时只改一个因素 | 选择依据及全部 dev 记录 |
| 12 | 冻结测试协议，运行 Base/RL 独立 test | 逐题配对结果和完整轨迹 |
| 13–14 | HF 导出、vLLM 服务、ZzhClaw profile 与回接对照 | API 工具调用通过；迁移报告 |
| 15 | 整理 README、训练曲线、案例与演示 | 他人可按文档复现；简历只写实测 |

若必须压缩工期，保留数据验证、真实参数更新和同环境 Base/RL 对照；减少模型数量、调参次数、可选消融与展示页面，不能用省略训练或独立验收来凑完成。

## 12. GPU 预算管理

预算按实际租价计算，不预设 AutoDL 当前价格或保证训练时长：

```text
费用 = 单卡每小时价格 × 卡数 × 实例运行小时数 + 存储等费用
预计训练时间 = 实测秒/update × 计划 updates + 验证/导出时间
GPU 小时 = 卡数 × 实例运行小时数
```

可先人为设置项目上限 24 GPU 小时，作为可调整的费用控制值，不是一定足够完成的承诺。环境检查短租 1–2 小时，正式运行前用 smoke 测吞吐并重新估算剩余预算。多卡时按卡数计入，不能把 2 卡运行 12 小时写成 12 GPU 小时。

数据与文档工作在本地完成；停机前把 checkpoint、manifest、日志与导出权重放到持久存储。OOM 优先检查多余服务占卡、降低 workers/micro batch、缩短长度并启用 offload，再决定是否扩卡。

## 13. 最终交付清单和面试材料

- README：具体问题、项目边界、架构、复现步骤、来源说明与已知限制。
- 数据卡与 manifest：来源、source_id 划分、mutation、公开/私有测试规则、数据版本。
- 训练卡：模型 revision、框架 commit、依赖、硬件、超参数、随机种子、实际 GPU 时长。
- 奖励验证记录：正确/错误补丁、步数耗尽、异常执行与基础设施故障的评分行为。
- 可加载 checkpoint 和导出校验记录。
- Base/RL 主实验报告，若有 SFT 则增加 SFT-only。
- ZzhClaw 回接报告，区分同环境训练收益与系统迁移收益。
- 至少 3 个改善案例、3 个持续失败或退化案例；没有该类样本时如实写数量。
- 约 3 分钟演示：任务 → 读代码 → 修改 → 公开测试反馈 → 再修复 → 独立验收 → 对照结果。

可用于简历的模板（完成后填写真实数字）：

> 基于 Agent-R1 构建 Python 代码修复训练环境，实现受限文件工具、测试反馈、执行预算与私有验收奖励；按原始题目划分训练/开发/测试并生成经验证的缺陷任务。
>
> 对 Qwen2.5-Coder-1.5B-Instruct 完成 GRPO 训练，记录奖励分布、策略变化与模型 checkpoint，在固定独立测试集上对比训练前后成功率、工具开销与失败类型。
>
> 导出模型并通过 vLLM 接入 ZzhClaw，在统一工具与预算下完成回接评测；成功率由 A% 到 B%，消耗 C GPU 小时。

只有测试结果支持时才写“提升”；开发集提升、测试集没有提升时，直接报告泛化不足及证据。面试要解释清楚自己新增的数据、环境、奖励、训练和评测，明确 trainer/GRPO 算法来自开源框架。

## 14. 第一批实际动作

按顺序做：

1. 在项目中固定 Agent-R1 上游 commit 并建立来源记录，不安装 Mac 本地 GPU 训练依赖。
2. 用 20 个原型任务明确 read_file/write_file/run_tests 契约。
3. 完成离线 verify：原始失败、参考通过、测试不可修改、私有资源不可读取。
4. 实现 CodeRepairEnv 与可脚本驱动的完整 episode，先不调用模型。
5. 再租 AutoDL 短时实例，验证工具协议、官方最小更新和自定义 5-update smoke。
6. smoke 通过后，按实测吞吐与 dev 基线决定正式训练预算。

## 15. 核对过的官方资料

- [Agent-R1 仓库与当前架构](https://github.com/AgentR1/Agent-R1)
- [Agent-R1 安装说明](https://agentr1.github.io/Agent-R1/getting-started/installation-guide/)
- [AgentEnv 接口源码](https://github.com/AgentR1/Agent-R1/blob/main/agent_r1/env/base.py)
- [AgentEnvLoop 源码](https://github.com/AgentR1/Agent-R1/blob/main/agent_r1/agent_flow/agent_env_loop.py)
- [官方 GRPO launcher](https://github.com/AgentR1/Agent-R1/blob/main/examples/hotpotqa/run_grpo.sh)
- [环境奖励的后处理入口](https://github.com/AgentR1/Agent-R1/blob/main/agent_r1/agent_flow/agent_flow.py)
- [步骤轨迹 GRPO 优势计算](https://github.com/AgentR1/Agent-R1/blob/main/agent_r1/trainer/ppo/core_algos.py)
- [官方工具数据转换示例](https://github.com/AgentR1/Agent-R1/blob/main/recipes/gsm8k/data_preprocess/process_gsm8k_tool.py)
- [verl v0.7.0 安装源码](https://github.com/verl-project/verl/blob/v0.7.0/docs/start/install.rst)
- [verl v0.7.0 checkpoint merger](https://github.com/verl-project/verl/blob/v0.7.0/verl/model_merger/__main__.py)
- [Qwen2.5-Coder-1.5B-Instruct 模型卡](https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct)
- [vLLM 工具调用说明](https://docs.vllm.ai/en/latest/features/tool_calling/)
- [MBPP 官方来源与原始划分](https://github.com/google-research/google-research/tree/master/mbpp)

以上资料核对日期为 2026-10-12，引用的是 main/当前文档页面；实际实施时必须固定版本并保存运行记录。本文未声称已验证目标 GPU 上的兼容性、吞吐或效果。
