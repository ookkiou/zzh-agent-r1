# 进度与验收

最新更新：2026-10-21。以下按日期保留历史记录；较早的“未执行 test / 暂停在 step11”不代表最新状态。

## 第 15 天：本机材料与离线证据交付完成

已新增项目卡、三条简历描述、一分钟介绍、14 个面试追问、复现指南及三分钟演示流程。基于原始报告生成三组评估图、完整 80 步 SFT 曲线、GRPO 观测切片，以及改善/退化/共同失败三个实际 dev 案例和补丁 diff；演示命令回放已记录轨迹，不启动模型或执行候选代码。

`python3 scripts/check_day15.py` 的本地材料验收 17/17 通过。离线证据包包含来源哈希、数字、图表、已记录轨迹、公开 starter 与复算脚本，不含大权重、SSH 私钥、评价 token 或私有测试输入；临时目录中以标准库环境完成数字重建、三类回放和包校验共 5 条命令，全部通过，未上传外部平台。

GRPO 本机逐 batch 指标仅有 1–11 和 63–74 步，12–62 的 51 个点留空；实例连接关闭，未为了整理材料开 GPU或编造数据。完整 GRPO 曲线、权重实例外备份、全新 GPU 环境复训、实时录屏、公开发布及原 225/255 步目标仍未完成，均与“本机材料交付完成”分开记录。见 [第 15 天结果](DAY15_RESULTS.md)、[验收报告](../reports/day15_acceptance.json)、[复算包隔离验证](../reports/day15_portability.json)。

## 当前：采用 step70，第 13–14 天受限 CLI 回接验收完成

正式 GRPO 实际到 74 步后触发连续 5 个 batch 无组内奖励差异的保护停止；最近完整 checkpoint 为 70，原 225 步目标未完成。冻结 dev 对照 SFT 63/96 → step70 72/96；最终独立 test 为 90/126 → 93/126（+2.38 个百分点），配对改善 7、退化 4。test 使用 42 个原题来源，另有 8 个模型无关排除来源；重复 seeds 相关，未做统计显著性检验。见 [最终模型验收](../reports/final_test_model_acceptance.json)。

用户选择先完成 step70 应用落地，不在当前阶段追加训练。已在 ZzhClaw 仓库实现独立 `repair` 命令：复用冻结三工具与 episode runner，并接入 ZzhClaw 会话、工具事件。51 项 profile / 通用 Agent 回归通过，4 项迁移结果计数与拒绝错误输入测试通过。已知 dev 原始代码和参考补丁通过真实 HTTP → ZzhClaw → Docker 验收，分别奖励 0 / 1；属于脚本诊断，没有模型自主推理。

用户手动启动 vLLM 服务并完成真实 API smoke、step70 和 SFT 各 96 条应用 dev 评估。全部 192 条有效，SFT 69/96（71.875%），step70 75/96（78.125%），+6.25 个百分点；配对改善 9、退化 3。三个 seed 成功数分别为 SFT 23/21/25、step70 24/23/28。step70 一次 SSH 隧道中断无效尝试保留，恢复后补齐覆盖；另一次非法模型动作按原契约正常消耗决策，最终失败。没有修改提示、补答案或排除失败来改善结果。

`python3 scripts/check_day14.py` 复算全部轨迹动作、终局奖励、任务/seed 覆盖及配对统计，检查模型/代码/协议指纹和 token 预算，15/15 通过，`complete=true`。受限 CLI profile 和独立批量评估入口属于本次交付；通用 ZzhClaw-Eval 任务适配、UI 和全工具集迁移未包含。新增 [迁移报告](DAY13_14_MIGRATION_RESULTS.md) 与 [最终验收](../reports/day14_acceptance.json)。原冻结 test 协议未变且未重跑，本助手未启动/停止 GPU 作业或下载大权重，模型完整备份未验收。现在可以进入第 15 天的 README、曲线、案例与演示整理。

## 第一天：完成

原计划当天验收为“每题参考通过、缺陷失败”，现在已实现可重复运行的验收命令：

```bash
python3 scripts/check_day1.py
```

| 标准 | 实际结果 |
|---|---|
| 固定任务范围 | 单文件 Python 函数修复，四类缺陷 |
| 固定模型和算法 | Qwen2.5-Coder-1.5B-Instruct / GRPO |
| 固定工具契约 | read_file / write_file / run_tests，路径和参数受限 |
| 20 个原型任务 | 10 train、10 dev，20 个不同 source_id |
| 缺陷实现失败 | 20/20 每题至少一个公开和私有用例失败 |
| 参考实现通过 | 20/20 全通过，共 40 个公开、121 个私有用例 |
| 来源与版本记录 | 数据及契约 SHA256；Agent-R1 commit b124aa46534cbf2fb8bc8af11405774984c42ac7 |

机器验收报告：[day1_acceptance.json](../reports/day1_acceptance.json)，其中 `complete=true`，7 项机器检查全部通过。逐题数据结果见 [prototype_verification.json](../reports/prototype_verification.json)。版本记录见 [UPSTREAM_LOCK.json](../UPSTREAM_LOCK.json)：上游未克隆安装，模型权重未下载，权重 revision 在下载前另行固定。

## 原型环境：本地 fixture 验证已完成

已实现三个工具、每次独立工作区、reset 恢复、最多 6 步、超时、终局私有验收、一次性奖励、基础设施故障分类及逐步轨迹。参考补丁只由验证脚本读取，环境不读取参考实现。

```bash
python3 scripts/verify_episodes.py --backend trusted-local
python3 -m unittest discover -s tests -v
```

实测 20/20 任务通过，共 40 次完整脚本 episode：原始代码均得 0，参考补丁均得 1，重复终止得 0，工作区全部清理。详见 [episode_verification.json](../reports/episode_verification.json)。脚本使用已知参考补丁，没有模型参与，因此不能将结果写成模型 100% 修复成功率。

该阶段自动测试共 34 项：33 项通过，1 项真实 Docker 集成用例跳过。已覆盖签名/路径限制、非法写入、仅记住公开答案无法得分、预算耗尽、无重复奖励、工作区独立、私有信息不进入观察、无限循环超时、输出洪泛及缺失 Docker 的故障分类。

该阶段尚未安装 Docker，本地执行只用于已知 fixture。后续第 4–5 天已安装并通过真实容器验收，见下文。

## 第 2–3 天：数据流程与首批数据验收完成

官方 MBPP 快照固定为 `f46ca8374b4cddef97ca4208ad986049d74d296a`，原始数据、sanitized 数据、README、LICENSE 均保留 SHA256。转换器从 974 道原题中做静态筛选，只执行已明确审查的 train/dev 来源及受控变体。

已实现继承官方划分、参考源码去重、输入域约定、字面量断言转换、独立回归用例、单点 AST 缺陷注入、逐题判定和来源冻结。

| 当天验收 | 实际结果 |
|---|---|
| 数据验证报告 | 104/104 通过；每题参考全过、缺陷触发公开及私有失败 |
| 首批 train/dev | 72 / 32 个任务，来自 31 / 14 道不同原题 |
| 测试扩充 | 每题 2 个公开 + 7 个私有用例，公开/私有输入不重叠 |
| 来源与缺陷可追踪 | 原题 ID、固定 commit、AST 变更位置、文件及转换器 SHA256 |
| 跨集合去重 | 变量重命名/常量抽象 AST 与近似过滤，包含原型来源 |
| test 来源冻结 | 50 道原题，未执行参考或模型评测；后续另行构建验收用例 |
| 离线重建 | fetch 校验通过；build --check 全部资源逐字一致 |

```bash
python3 scripts/fetch_mbpp.py --check
python3 scripts/build_mbpp.py --check
python3 scripts/verify_mbpp.py
```

结果见 [mbpp_verification.json](../reports/mbpp_verification.json)，具体来源、排除理由、审查限制和后续测试规则见 [MBPP 数据卡](MBPP_DATA_CARD.md)。该阶段加入数据测试后的自动测试总计 48 项，47 项通过、1 项 Docker 集成测试跳过。

此处完成的是首批数据与转换流程，约 300 train / 60 dev / 150 test 尚未达到。助手已审查入选契约，但用户对训练来源的抽查、最终测试的人工复核还未完成。

## 第 4–5 天：完成，本机真实容器验收通过

按用户选择在 Mac 安装 Docker Desktop，使用其 Linux VM 完成 CPU 容器验收。Docker Desktop 4.93.0 / Engine 29.8.1，官方 Python 3.12.15 镜像按 digest 固定，详见 [SANDBOX_LOCK.json](../SANDBOX_LOCK.json)。没有租用 GPU，也没有下载模型或训练。

新增独立执行服务、鉴权客户端与公开资源加载模式。服务校验 train/dev 资源哈希并持有私有用例；不读取参考实现。客户端工作区只有待修文件和公开测试，候选执行容器不含参考答案、私有期望值、服务 token 或宿主挂载。缺失 Docker 时生产服务启动失败，不使用本地执行兜底。

| 当天验收 | 实际结果 |
|---|---|
| 真实隔离探针 | 22/22：禁网、只读、非 root、无 capabilities、禁止提权、无宿主挂载、资源上限及异常清理 |
| 正确补丁得 1 | 20 原型 + 104 正式任务全部通过，HTTP → Docker → 私有验收 |
| 错误补丁得 0 | 同一批 124 个原始缺陷全部为 0 |
| 不重复计分与清理 | 重复结束为 0；独立工作区全部清理 |
| 并发无串题 | 同题 4 个并发 episode，正确/错误交错，反馈和奖励独立 |
| 私有材料边界 | 客户端不加载私有用例；私有 HTTP 返回仅摘要，模型消息和轨迹不含 token/私有用例 |
| 真实完整流程 | 共 252 个 scripted episodes，无模型参与，不是模型成功率 |
| 自动回归 | 60/60 通过，真实 Docker 用例运行，无跳过 |
| 前期数据冻结 | 官方快照校验、build --check 再次通过，冻结 test 来源未执行 |

实测报告：[sandbox_verification.json](../reports/sandbox_verification.json)、[service_verification.json](../reports/service_verification.json)，总验收：[day45_acceptance.json](../reports/day45_acceptance.json)。操作说明、启动命令、接口与时间预算见 [EXECUTION_SERVICE.md](EXECUTION_SERVICE.md)。

```bash
export PATH="/Applications/Docker.app/Contents/Resources/bin:$PATH"
export CODE_REPAIR_DOCKER_IMAGE="$(python3 -c 'import json; print(json.load(open("SANDBOX_LOCK.json"))["image"])')"
python3 scripts/verify_sandbox.py
python3 scripts/verify_service.py
python3 scripts/check_day45.py
```

本次结果适用于该 Mac 的 Docker Linux VM；最终训练主机的 Linux/amd64、Docker 权限及并发资源需再验证。模型 token/context 限制、Agent-R1/verl 适配及真实参数更新尚未实施。

## 仍待完成

1. 扩充正式数据到目标规模，基于冻结来源构建最终 test 用例，完成人工复核。20 道原型与首批正式数据都不作为已完成训练的证据。
2. 若后续把执行服务迁到独立 Linux CPU 主机，需要在该主机重跑容器验收。当前 AutoDL 通过 SSH 隧道访问已验收的 Mac Docker 服务。
3. 扩大 train 后配置正式 GRPO、完整优化器续训状态与存储预算；自建 recipe 的真实 vLLM 多轮优化已于第八天通过 5-update smoke。
4. 正式 SFT+GRPO dev 选模、独立测试与 ZzhClaw 回接；完整 Base/SFT-only dev 基线已于第八天完成。

## 第 6 天：环境与诊断验收完成；以下保留准备过程记录

2026-10-13 第六天开始时用户尚未创建 AutoDL 实例，后续已选择配置但尚未提供开机连接信息。已取回固定 commit 的 Agent-R1 官方源码归档并核对训练入口和官方 GSM8K 示例，记录重点文件 SHA256；仅查询官方模型元数据，固定 Qwen 权重 revision，未下载权重。新记录见 [TRAINING_SOURCE_LOCK.json](../TRAINING_SOURCE_LOCK.json)。verl v0.7.0 已通过官方源码归档解析固定 commit，入口 37 条顶层导入的静态模块检查无缺失；见 [day6_static_compatibility.json](../reports/day6_static_compatibility.json)。运行环境安装、完整依赖锁定和 GPU 兼容性仍待实测。

新增 [day6_preflight.py](../scripts/day6_preflight.py) 和 [第六天执行清单](DAY6_RUNBOOK.md)。Mac 体检结果见 [day6_local_preflight.json](../reports/day6_local_preflight.json)，训练前置检查 1/8，`preflight_complete=false`、`day6_complete=false`；本机不是 Linux NVIDIA 训练主机，当前结果符合预期。

核对 AutoDL 官方说明后，普通容器实例内不支持 Docker。候选部署调整为 GPU 实例运行训练、通过 SSH 反向隧道访问 Mac 上已验收的 Docker 执行服务；该隧道与 Ray worker 访问仍需服务器实测。不能将本机隔离验收当作 AutoDL 宿主隔离已经通过。

下一步需要创建实例、提供非敏感连接信息，然后体检硬件、建立兼容依赖、验证模型和工具协议、运行官方最小参数更新。第六天尚未通过验收，没有 GPU 租用或训练结果。

2026-10-14 用户准备租用 GPU。新增 `scripts/build_day6_bundle.py`，将按归档 SHA256 与 commit 校验的 Agent-R1/verl 源码、版本记录和体检脚本打包为 `runs/day6/day6-bootstrap.tar.gz`（约 4.3MB）。已校验全部打包字节，并在全新临时目录解包运行体检，源码重点文件校验通过；本机无 NVIDIA GPU，体检仍正确保持未就绪。报告见 [day6_bootstrap.json](../reports/day6_bootstrap.json)。上传包不含模型权重或本项目私有修复用例；没有安装依赖、连接服务器或运行训练。GPU 模式、SSH 认证与镜像实际版本待用户提供后验证。

### 2026-10-14：AutoDL 已连接，安装进行中

用户已完成专用 SSH 公钥配置。已实际连接并记录硬件：[day6_server_inventory.json](../reports/day6_server_inventory.json)。实例为 RTX 4080 SUPER 32GB，Python 3.12.3、PyTorch 2.8.0+cu128，CUDA 12.8；实际 CUDA 张量运算及 BF16 支持检查通过。训练采用独立 venv，复用基础镜像的 PyTorch。

固定 revision 的 Qwen2.5-Coder-1.5B-Instruct 已下载到实例，全部 9 个必需文件通过 SHA256/Git blob 校验，见 [day6_model_download_status.json](../reports/day6_model_download_status.json)。此结果仅证明权重完整，尚不能证明推理或训练成功。

已启动 Mac Docker 验证服务和回环地址 SSH 反向隧道；远端模型三工具往返尚待验证。仅上传一个原型任务的公开资源，不上传私有用例或参考实现。官方 GSM8K 诊断数据已固定来源并上传，与冻结的代码修复 test 来源无关。

依赖安装仍在进行。已处理 FlashInfer 隔离构建尝试下载其他 PyTorch、OpenCV/CuPy 新版与 NumPy 1.26 的解析冲突，缓存已下载 wheel，并选取与基础 PyTorch ABI 匹配的 FlashAttention wheel。完整 pip check、GPU 推理、FlashAttention 运算、Hydra 配置解析、最小参数更新及 checkpoint 重载均未验收。第六天仍未完成。

### 2026-10-14：最终环境与诊断验收完成

`python3 scripts/check_day6.py` 实测 **16/16 通过，complete=true**，见 [day6_acceptance.json](../reports/day6_acceptance.json)。依赖安装、pip check、8/8 体检、BF16 FlashAttention 运算、模型推理、实际服务器及 Ray worker 访问 Mac Docker、真实不可达服务的无效 episode 分类均通过。

官方单步与工具配置分别从原始权重完成 2 次 GRPO 更新，损失有限、梯度非零；分别有 261/338 和 258/338 个张量发生变化，checkpoint 合并并在 GPU 重载生成文本成功。不是同一个模型连续训练四步。完整日志、配置、rollout 和 Linux 依赖记录已备份到本机；模型 checkpoint 权重仍在远端数据盘。

三工具是引导式诊断，模型输出 JSON 代码块，通过严格适配及官方 Hermes 解析检查后完成往返，最终修复奖励 **0**。官方 GSM8K 工具配置日志全部只有一轮生成，没有证明真实多轮工具调用参与训练。此次没有自建修复 recipe 训练、完整 dev 基线或效果提升结论，冻结 repair test 来源未运行。完整说明见 [DAY6_RESULTS.md](DAY6_RESULTS.md)。

下一步进入第七天：接入自建 AgentEnv/flow，统一格式、观察编码与生成 token mask，测少量 train/dev 的合法动作、有效 episode 和组内奖励差异，按实测决定是否加格式 SFT。

## 第 7 天：验收完成；以下保留本地准备过程

2026-10-15 已实现真实 `CodeRepairAgentEnv`、自定义 Flow、共享自主交互 runner、严格动作解析和公开资源加载。基础设施错误直接终止 rollout/batch；原始生成 token 与观察分离，每轮工具结果进入下一轮 prompt。上游真实张量后处理的远端检查脚本已准备，尚未执行。

固定导出 104 个 train/dev 任务的公开资源，选择 4 train + 4 dev 的不同来源作为小诊断，每题 n=4，共 32 episodes。参考源码和私有用例不进入上传包；冻结 test 来源未执行。适配器测试 13/13，无跳过；真实 AgentEnv → HTTP → Mac Docker 的 16 次已知原始/正确补丁 episode 均得到预期 0/1，并完成清理。没有模型参与这些检查。

`python3 scripts/check_day7_local.py` 本地验收 **8/8 通过**，`local_preparation_complete=true`，但 `day7_complete=false`。证据见 [day7_local_acceptance.json](../reports/day7_local_acceptance.json)、[day7_docker_adapter.json](../reports/day7_docker_adapter.json)。增量上传包已逐字节核验，不含凭据或私有/参考资源。

旧 SSH 地址连接被拒绝；用户询问是否需要开机，已说明先完成本地准备以避免付费空等。当前准备已完成，待实例开机及当前 SSH/GPU 信息后运行远端 preflight、真实 tensor/mask 检查和原始模型自主诊断。尚无第七天模型成功率、组内奖励差异或 SFT 决策，不能标记整天验收完成。操作与限制见 [DAY7_RUNBOOK.md](DAY7_RUNBOOK.md)。

### 2026-10-15：AutoDL 实测与 SFT 备选路线完成

已连接用户开机后的原 32GB 实例，GPU 依赖体检、公开数据 parquet 与实际 Agent-R1 张量检查通过。原模型 32/32 自主轨迹有效，但 train/dev 各 0/16 成功，4 个 train 同题分组都没有奖励差异。原始阶段验收保持 `complete=false`，没有把“运行完成”算作学习信号通过。

依据执行计划，在 63 个 train 任务上构建 315 个监督样本；全部 8 个诊断来源排除，未使用 dev/test 标签。80 步 LoRA SFT 完成，28 个 q_proj 张量变化，合并 checkpoint GPU 重载成功。以完全相同诊断协议复测：train/dev 各 12/16 成功，train 2/4 组出现奖励差异。最终 [day7_sft_acceptance.json](../reports/day7_sft_acceptance.json) 执行检查 10/10，`complete=true`、`ready_for_grpo_smoke=true`。

这些是小样本 SFT-only 结果，未进行代码修复 GRPO；真实 vLLM 多轮轨迹参与参数更新、完整 dev 基线与独立测试仍待第八天及后续验证。私有测试留在 Mac，冻结 test 来源未执行，6 个冻结数据构建文件未变。详情见 [DAY7_RESULTS.md](DAY7_RESULTS.md)。本日 GPU 作业已退出，Mac 服务与隧道已停止；实例未关机或释放，模型备份状态另见报告。

## 第 8 天：验收完成；以下保留准备过程

已连接原 AutoDL 32GB 实例，启动 Mac Docker 验收服务和反向隧道。冻结完整 dev 评测协议：32 个缺陷任务、14 个来源，每模型每题 3 seeds，Base / SFT-only 总计 192 条单次 episode。只评测 dev，未执行最终 test。

自建 5-update GRPO 配置、vLLM 轨迹记录与更新前 batch 检查已编写。真实上游 GRPO 的合成信用分配探针通过，Hydra 配置解析通过；当前完整模型评测仍在运行，不能据此宣称训练通过。操作与标准见 [DAY8_RUNBOOK.md](DAY8_RUNBOOK.md)。

### 2026-10-15：完整基线与真实自建训练验收通过

完整 dev 基线覆盖 32 个任务、14 个来源，两种模型各 3 seeds，共 192 条有效轨迹，无基础设施失败。Base 2/96 成功（2.08%），SFT-only 63/96（65.63%）；配对有 62 条 SFT 改善、1 条退化，保留全部原始轨迹。此对照不是 GRPO 收益或最终独立测试。

从 SFT 合并权重开始完成恰好 5 次全参数 GRPO 更新；80 条实际 vLLM 多轮轨迹进入优化器，20 个同题分组中 6 个有奖励差异。实际 trainer batch 的分组、终局奖励只计一次、生成 mask、组内轨迹优势均验证通过。第五次全 1、策略优势为零，仍有 KL 梯度，不能据此宣称有效相对学习。

相对 SFT-only 起点，338 个检查张量中 282 个、69350135 个元素变化；全部数值有限，导出 checkpoint GPU 重载通过，BF16 重载后的差异仍保留。`python3 scripts/check_day8.py` 最终 **14/14 通过，complete=true**。报告、配置和轨迹均已备份本机；完整权重在远端数据盘，smoke 未保存 optimizer 状态，不支持精确优化器续训。

GPU 作业退出，Mac 服务与隧道已停止；实例未停机或释放，冻结 test 未执行。完整结果与限制见 [DAY8_RESULTS.md](DAY8_RESULTS.md)、[day8_acceptance.json](../reports/day8_acceptance.json)。下一阶段才进行数据扩充和正式 GRPO，不把此次 5-update smoke 当作正式效果。

## 第 9 天：数据与配置准备完成，GPU 试跑进行中

2026-10-15 已建立独立 v0.2 数据版本：300 train / 32 dev，分别来自 74 / 14 道原题。104 个原有任务逐字节保留，dev 模型输入不变，50 个 test 来源冻结文件不变且未执行。独立复验 332/332、真实 HTTP → Docker 验证 332/332（1328 次执行）、离线重建及 14 项定向测试通过。人工签字复核尚未完成，审查归属明确记录为代理审查。

公开导出 997 文件，上传包不含参考源码、私有用例和 mutation 元数据。实际服务器 CPU 预检 39/39、本地准备验收 14/14 通过。清理 419 个 wheel 下载缓存释放 4.296GiB，数据盘余 8.60GiB，旧模型与 checkpoint 保留。

用户选择只保存权重和少量状态；因此正式配置保存 model/extra/data、不保存 optimizer，利用系统盘 `/root/zzh-day9-checkpoints` 的约 30GiB 空间通过 22GiB 预算门槛，无需此次扩容。权重续跑会重建 Adam 动量，不能宣称完整优化器恢复。初次启动的 Ray 环境变量类型错误已修正并保留失败记录，修正后的真实 vLLM 多轮 GRPO 已进入更新。

后台按 10-update pilot → 第 11 次更新重载探针 → 验收 → 累计最多 225 次更新顺序运行，阶段上限 1 小时 / 30 分钟 / 8 小时。每阶段失败则停止检查；Mac 同步进程记录状态，并在流水线结束后尝试核验权重备份，不自动关闭或释放实例。当前 `day9_complete=false`，尚无正式 GRPO dev/test 收益。结果与实时报告入口见 [DAY9_RESULTS.md](DAY9_RESULTS.md)，操作见 [DAY9_RUNBOOK.md](DAY9_RUNBOOK.md)。

### 第九天：权重重载验收通过，用户要求暂停

原始 Ray worker 日志补齐了主进程未转发的第 11 步更新及模型 / scheduler / RNG 加载记录；SHA256 与来源 PID 证据保留，重载验收通过，训练算法未变。正式阶段曾完成第 12–14 次更新，随后按用户要求停止，GPU compute process 列表为空。最近完整 checkpoint 为第 11 步，下次从第 12 步重跑；已归档完整中断审计，活动审计恢复到与保存状态一致。训练未完成、test 未执行、AutoDL 实例未关闭或释放。备份与操作状态见 [暂停与续训记录](DAY9_PAUSE_RESUME.md) 和 `reports/day9_pause_status.json`。
