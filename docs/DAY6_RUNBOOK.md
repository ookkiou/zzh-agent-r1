# 第六天：AutoDL 训练环境准备与最小更新验收

更新：2026-10-14。当前状态：**第六天环境与诊断链路验收完成，16/16 检查通过；自建代码修复训练尚未开始。**

实际实例为 RTX 4080 SUPER 32GB / Python 3.12.3 / PyTorch 2.8.0+cu128。GPU 推理、引导式三工具往返、真实 Ray worker 服务访问、两组各 2 次 GRPO 更新、权重变化与 checkpoint GPU 重载均通过。工具请求采用严格 JSON 到 Hermes 适配；引导修复奖励为 0，官方工具配置没有观察到多轮调用。完整证据与限制见 [第六天实测结果](DAY6_RESULTS.md)。下文第 3–6 节保留准备阶段的建议与当时状态；以本段、最终清单和实测报告为当前状态。

## 1. 第六天是干什么的

前五天已经解决“任务是什么、代码如何执行、修复如何打分”。第六天要解决“模型能否在目标 GPU 上运行，训练框架能否真正更新权重”。

这一天主要是兼容性与运行链路检查，不研究最终修复成功率，也不做长时间正式训练。它连接两部分：

```text
已有：任务 + 工具 + Docker 执行服务 + 0/1 奖励
                   ↓
第六天：GPU/驱动/依赖 + 模型推理 + 工具协议 + 官方最小训练更新
                   ↓
后续：自建 recipe 接入 + 原模型基线 + 5-update smoke + 正式 GRPO
```

关键区别：能 import 不等于能训练，能生成文本不等于会调用工具，训练进程启动不等于完成了参数更新。

## 2. 当天要完成的四件事

| 工作 | 为什么做 | 验收证据 |
|---|---|---|
| 记录 GPU/CPU/RAM/磁盘、驱动、Python 与 CUDA | 排除硬件和运行时不匹配 | 服务器体检 JSON、nvidia-smi、CUDA tensor 实际运算 |
| 建立可追溯依赖环境 | 防止 torch/vLLM/verl 接口与二进制冲突 | 源码 revision、实际安装版本、核心模块 import、依赖锁定 |
| 验证模型推理与工具协议 | 排除聊天模板、函数调用解析和服务连接问题 | 文本生成、三个工具调用、完整多轮轨迹、执行服务健康检查 |
| 用官方示例完成最小训练更新 | 确认 rollout、奖励、反向传播和优化器链路可用 | 1–2 次实际 update、有限梯度/损失记录、参数变化或 checkpoint 证据 |

第六天不是完成自建 code-repair recipe 的日子。官方 GSM8K 小样例用于训练栈诊断；自建修复环境进入 trainer 的适配、基线及 5-update smoke 按后续阶段推进。

## 3. 重要部署调整：普通 AutoDL 实例不能直接照搬 Docker

AutoDL [普通容器实例说明](https://api.autodl.com/docs/env/)明确写明容器实例内不支持使用 Docker。不能因为实例里是 root，就假设能启动 Docker daemon；目前也不能声称目标 GPU 主机已通过容器验收。

本项目先采用下面的候选部署方式，待实例创建后实测：

```text
Mac                                   AutoDL 普通 GPU 实例
Docker Desktop                        Python / CUDA / 模型 / Agent-R1
独立执行服务 127.0.0.1:8765   ←SSH反向隧道← 127.0.0.1:18765
候选代码仍在 Mac 的受限容器运行          训练进程仅发送评测请求
```

SSH 由 Mac 发起，使用反向转发把 AutoDL 的 loopback 端口转到 Mac 服务。机制参考 [AutoDL SSH 隧道文档](https://api.autodl.com/docs/ssh_proxy/)。这是基于平台说明与现有 RemoteEvaluator 的部署方案，**隧道和 Ray worker 可达性尚未实测**。

需要在服务器验证 SSH 允许反向转发、远端监听仅为 loopback、服务 token 可用、worker 能访问同一服务地址、断连能正确归为基础设施故障。Mac 需保持运行、网络与 Docker 可用；往返延迟及四并发容量需要实际测量。

若此方案不满足稳定性或吞吐，再将执行服务迁移到有 Docker 权限的独立 Linux CPU 主机，不在普通 GPU 实例内用未隔离本地执行代替它。

## 4. 用户尚未创建实例：先确定这些配置

下列是本项目降低首次排障难度的资源起点，不是最低配置保证，也没有测得吞吐或费用。

| 项目 | 起始考虑 |
|---|---|
| GPU | 先按单张 80GB NVIDIA GPU 规划；具体型号、价格和可用性以控制台为准，较小显存需另做参数与显存验证 |
| CPU/RAM | 优先较充足配置，起始考虑至少 8 vCPU、64GB RAM；开启 offload 或编译依赖可能需要更多 |
| 磁盘 | 预留模型、依赖缓存、数据、checkpoint 空间，起始考虑至少 100GB 可用数据盘，再按实际大小核算 |
| 系统 | Linux x86_64；建议 Python 3.12 环境 |
| CUDA | 以 verl v0.7.0 文档的 CUDA >=12.8 为起点，之后核对驱动、torch 和 vLLM 的实际组合 |
| 执行服务 | 起步保留 Mac Docker 服务，GPU 实例通过 SSH 反向隧道访问 |
| 使用方式 | 先短时环境验证，不直接运行多 epoch；保存日志和失败原因，避免 GPU 空闲等待排障 |

CUDA 起点来自 [verl v0.7.0 安装文档](https://github.com/verl-project/verl/blob/v0.7.0/docs/start/install.rst)。这些建议尚未在目标实例验证；实例镜像目录、GPU 库存与实时租价本次没有获取，不能将本表当作已经验证的购买清单。

不要仅凭 nvidia-smi 显示的 CUDA 字样判断环境兼容：它反映驱动支持范围；`torch.version.cuda` 反映 torch 构建运行时；`nvcc --version` 反映本地编译工具链。需要以实际 import、GPU 运算及训练验证它们的组合。

创建后需要提供 GPU 型号/显存、镜像信息、SSH 连接命令或别名。密码和私钥保留在本机，不发到聊天中。

### 2026-10-13 补充：4090 与具体镜像候选

用户提出使用 4090。普通 RTX 4090 为 24GB 显存，可作为本项目 1.5B 模型推理、工具协议与小规模训练可行性验证的起点；本项目尚未在该卡完成训练，不能承诺原计划 batch=16、n=4、4096 上下文的完整多轮 GRPO 配置能装入。原建议 80GB 是减少首次显存排障的资源余量，不是最低要求。若平台提供 48GB 版本，可以比较实际价格后考虑，但不假设它与普通 24GB 卡配置相同。

预算优先时，先用 1 张 4090 24GB 做短时验证，保留较充足 CPU 内存；训练阶段从较小 batch、n=2、micro-batch=1、较短上下文及 offload 起步，逐项测量显存。必要时调整卡型，不能将待验证的内存估算写成已跑通结论。

**具体镜像候选：AutoDL 官方 PyTorch 2.8.0 / Python 3.12 / CUDA 12.8。** AutoDL [官方镜像表](https://www.autodl.com/docs/base_config/)列出了这一组合；vLLM 0.11.0 的 [官方 CUDA 依赖](https://github.com/vllm-project/vllm/blob/v0.11.0/requirements/cuda.txt)也指定 torch 2.8.0，与当前核对的 verl 安装脚本方向一致。系统优先 Ubuntu 22.04，候选镜像的 OS、glibc、驱动与 FlashAttention ABI 仍需登录体检确认。这里是选择基础镜像，不代表它预装了 Agent-R1/verl，或已经完成依赖兼容验收。

这次核对的是官方文档中的组合，尚未读取用户控制台的实时库存、镜像选项或价格；如果没有完全一致的选项，应先看实际列表再决定替代组合，不直接选一个旧版镜像开始长时训练。

### 2026-10-14 补充：4090 无库存时的 vGPU-32GB 候选

用户表示 4090 无库存，询问 vGPU-32GB。AutoDL [官方首页](https://www.autodl.com/)将 vGPU-32G 标注为 RTX 4080S 32G，可作为本项目单卡 1.5B 模型推理和小规模训练验证的替代候选；镜像仍优先 PyTorch 2.8.0 / Python 3.12 / CUDA 12.8。32GB 比原候选 24GB 提供更多显存容量，但不据此推断训练速度或承诺完整多轮 GRPO 配置能直接运行。登录后需核对实际设备、显存、驱动与 CUDA 运算，随后按小 batch 和 offload 实测。尚未收到实例连接信息，不将候选建议记作硬件已验收。

## 5. 历史记录：2026-10-13 的本地准备

1. 下载已固定 commit `b124aa46534cbf2fb8bc8af11405774984c42ac7` 的官方 Agent-R1 源码归档，保留 LICENSE，检查训练入口、配置及官方 GSM8K 脚本。没有执行上游代码或安装训练依赖。
2. 将源码归档与重点文件的 SHA256 记录到 `TRAINING_SOURCE_LOCK.json`。源码在忽略提交的 `runs/day6/Agent-R1/`，不把大量上游文件当作本项目原创代码提交。
3. 从官方 Hugging Face 元数据固定模型 revision：`2e1fd397ee46e1388853d2af2c993145b0f1098a`；只查元数据，**没有下载模型权重**。
4. 新增 `scripts/day6_preflight.py`，采集目标主机信息、包版本、源码重点文件完整性；在显式选项下检查训练模块 import 和 CUDA tensor 运算。
5. 在 Mac 跑体检生成 `reports/day6_local_preflight.json`。它显示不是 Linux NVIDIA 训练主机，因此未通过训练前置条件，属于预期结果，不是项目回归失败。

旧的 `UPSTREAM_LOCK.json` 保留第 1 天选择时的历史快照；第六天新增的版本解析以 `TRAINING_SOURCE_LOCK.json` 为准。

verl 的目标仍为官方要求的 0.7.0。最初遇到 GitHub API 限流及 git 传输失败，随后通过官方 tag 源码归档的 Git PAX comment 解析出 commit `f9c855f7cf04d603c9546bc01776c74806a879c1`，已记录归档 SHA256。对四个入口模块的 37 条顶层 verl 导入做了静态检查，模块均存在；检查中未直接识别的三个符号可在星号重导出的子模块中找到定义。报告为 `reports/day6_static_compatibility.json`。这是源码检查，不证明 GPU 运行或全部嵌套路径兼容。torch/vLLM 等实际安装版本仍未锁定，不能把本地准备写成“依赖已安装并验收”。

### 开机前的就绪范围与时间估计

现有材料足以在 SSH 登录权限可用后开始服务器体检；尚未完成单卡 launcher 的配置解析、安装依赖的运行验收和模型工具驱动验证，不能承诺开机即训练。首次登录可能需要用户在本机终端输入密码，或配置公钥登录；只提供连接命令并不等于已有认证权限。

以下按任务量估计，不是本项目实测耗时：

| 阶段 | 顺利情况下的时间估计 |
|---|---|
| SSH、文件传输、服务器基础体检 | 10–20 分钟 |
| 安装依赖与下载模型 | 30–90 分钟，取决于网络与是否需要编译 |
| 模型推理、服务隧道、工具协议验证 | 20–40 分钟 |
| 配置解析与官方最小更新排障 | 30–90 分钟 |

建议为第六天预留约 2–4 小时工作窗口；依赖冲突、编译或显存调整可能延长到半天或更久。首次有卡窗口先以体检、推理和最小更新可行性为目标，不预先承诺整天验收完成。

AutoDL [官方无卡模式说明](https://www.autodl.com/docs/save_money/)列出 0.5 核 CPU、2GB 内存的轻量配置，可以先用于 SSH、文件传输和部分下载准备；不承诺在这类资源下完成 torch/FlashAttention 等重依赖编译。无卡模式会释放 GPU，之后正常开机可能受库存影响。是否使用以用户控制台实际选项与计费为准。

## 6. 实例创建后的执行顺序

### A. 先体检，再安装

将本项目和固定 Agent-R1 源码传到服务器，激活拟使用的 Python 环境，在本项目根目录运行：

```bash
python3 scripts/day6_preflight.py \
  --upstream-dir /实际路径/Agent-R1 \
  --output reports/day6_server_preflight.json
```

该命令不会安装依赖、下载权重或训练。退出码 1 表示前置条件未齐，具体看 JSON；不要忽略失败直接开始训练。路径需替换，不能照抄占位符。

### B. 解决依赖与源码兼容性

依照 [Agent-R1 安装说明](https://agentr1.github.io/Agent-R1/getting-started/installation-guide/)与固定 verl 版本文档，在单独 Python 环境安装。首先核对实例已安装的 torch/vLLM，避免随意安装一个包替换另一个包的二进制依赖。

Agent-R1 README 同时提到 verl 0.7.0 和近期 AgentFlow/async rollout 接口。本次以真实 import 和最小更新判定兼容；需要改 revision 时应记录明确原因和新 commit，不能悄悄用 latest。

另已核对 [verl v0.7.0 安装脚本](https://github.com/verl-project/verl/blob/v0.7.0/scripts/install_vllm_sglang_mcore.sh)：其中使用 vLLM 0.11.0，并指定了 Python 3.12 / torch 2.8 对应的 FlashAttention wheel。这些用于筛选候选镜像和核对 ABI，不表示已经验证了服务器组合；脚本还有可选框架安装项，不能在未知环境中不加检查地整段运行。

依赖就绪后运行：

```bash
python3 scripts/day6_preflight.py \
  --upstream-dir /实际路径/Agent-R1 \
  --probe-training-stack \
  --output reports/day6_server_preflight.json
```

GPU 运算及核心模块 import 使用有超时的子进程。该体检即使全过，也只证明部分前置条件；它始终将 `day6_complete` 保留为 false，因为没有验证推理、隧道或参数更新。

### C. 建立执行服务隧道

先在 Mac 按 `docs/EXECUTION_SERVICE.md` 启动带 token 的 Docker 执行服务。再从 Mac 建立 SSH 反向转发，示意命令：

```bash
ssh -N -T \
  -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -R 127.0.0.1:18765:127.0.0.1:8765 \
  -p 实际端口 用户@实际主机
```

这条命令尚未执行，端口、用户、主机需替换。服务 token 通过可信环境配置传给调用端，不放到模型观察或数据行中。先从服务器访问服务健康接口，再验证公开反馈、私有终局与断连分类；后续 Ray worker 也需要单独验证可达性。

### D. 下载固定模型，检查推理和工具协议

先完成版本与存储核对，再按 lock 中 revision 下载模型，记录实际路径。验证文本生成、Hermes 工具解析以及 read_file/write_file/run_tests 的一次完整多轮交互。当前尚未实现独立模型驱动验收器，这部分需在实例可用后完成，不能拿已有脚本补丁轨迹替代模型调用证据。

### E. 官方小样例做最小更新

以固定源码的 GSM8K 单步和工具示例作为诊断基础，分别控制为很少的更新，不使用本项目冻结 test 来源。按目标 GPU 调整模型、batch、长度和 logger，先解析 Hydra 配置，再实际运行。

本次源码核对发现：

- `examples/gsm8k/run_steppo.sh` 与工具版本默认两张 GPU、较大的 batch，算法为 gae 并配置 critic；不是单卡 GRPO smoke 配置。
- 正确 GPU 数配置键为 `trainer.n_gpus_per_node`。
- 原脚本会重设 CUDA_VISIBLE_DEVICES；仅在命令前 export 一个值，不能保证其内部不覆盖。
- 官方脚本默认不保存 checkpoint，最小验收需调整保存设置并收集更新证据。

因此目前没有把原脚本原样包装成“一键保证能跑”的单卡命令。服务器环境确定后再生成并验证具体 launcher。

## 7. 第六天最终验收清单

以下按实际证据更新，组合项目必须全部满足才勾选。

- [x] 目标 Linux GPU 主机的硬件、驱动和 Python 环境记录完整（day6_server_inventory.json）。
- [x] verl 精确源码 revision 与实际 torch/vLLM/transformers 等版本锁定，核心模块可 import。
- [x] CUDA tensor 运算和模型文本推理实际成功。
- [x] 执行服务隧道可用，控制面与候选代码隔离保持，真实连接拒绝分类为无效 episode；未主动切断运行中的隧道。
- [x] 引导式模型协议完成三个工具及终局；原生输出为 JSON 代码块，经过显式适配验证官方 Hermes 解析，非自主修复能力验收。
- [x] 官方单步和工具配置各完成 2 次更新，有有限损失、非零梯度、权重变化和 GPU 重载证据；工具配置的轨迹仍为单轮。
- [x] 保存当天日志、实际配置、依赖记录与总体验收报告，限制见 DAY6_RESULTS.md。

下一步：第七天接入自建代码修复 recipe，核对格式、观察编码和生成 token mask，先做少量 train/dev 奖励与格式分布诊断。当前尚无代码修复训练或能力提升结论。
