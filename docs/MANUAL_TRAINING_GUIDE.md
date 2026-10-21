# 自己执行：迁移后恢复第九天训练

本轮由你复制命令、实际执行；助手解释命令、检查输出并排查错误。当前训练保持暂停，本指南不表示已经在新实例开训。

目标：确认迁移完整后加载第 11 步权重，从第 12 次更新继续，累计最多 225 次。第 12–14 步在上次暂停前执行过，但没有保存，因此会重跑。模型、scheduler / RNG、数据进度恢复，Adam 优化器重新初始化。

## 1. 本轮先做：新实例只读检查

在 **新 AutoDL 实例的终端** 执行。可以使用 AutoDL 的 JupyterLab Terminal，或你自己 SSH 登录后的终端。这些命令不启动训练、不修改模型。

```bash
nvidia-smi
df -h /root /root/autodl-tmp
ls -ld /root/autodl-tmp/agent-r1-day6
ls -lh /root/zzh-day9-checkpoints/global_step_11/actor/
```

每条命令分别回答：

| 命令 | 要确认什么 |
|---|---|
| `nvidia-smi` | 实际 GPU 名称、显存，以及是否有其他进程占用 |
| `df -h` | 系统盘与数据盘容量、可用空间 |
| 项目目录 `ls` | 代码、数据、模型、虚拟环境所在的项目目录是否迁移 |
| checkpoint 目录 `ls` | 系统盘上的最新 checkpoint 是否一起迁移 |

将输出发给助手，检查后再进入下一节。若提示目录不存在，先定位迁移文件；这不代表需要重新训练。数据盘中另有 `runs/day9/pause_backup/global_step_11.tar.gz`，可经哈希核验后恢复 checkpoint。原始 checkpoint 及根目录 `zzh_run_identity.json` 都需要保留。

## 2. 理解三个终端的位置

| 终端 | 用途 | 所在机器 |
|---|---|---|
| Mac 终端 A | 启动 Docker 评价服务、执行 Mac 命令 | Mac |
| Mac 终端 B | 保持 SSH 反向隧道 | Mac |
| GPU 终端 | 环境检查、查看配置、启动训练 | 新 AutoDL 实例 |

Python 模型推理与参数更新发生在 AutoDL；模型写出的代码通过隧道交给 Mac Docker 执行。Mac 在训练期间需要开机、联网，Docker 与隧道持续可用。

## 3. 环境、数据与权重验收

在 GPU 终端进入原路径并确认 Python 版本：

```bash
cd /root/autodl-tmp/agent-r1-day6
.venv/bin/python --version
.venv/bin/python -m pip check
```

期望迁移原 Python 3.12 环境；`pip check` 没有依赖冲突。之后核对公开数据、SFT 参考权重、checkpoint 第 11 步及实验指纹；完成哈希验证才能把“文件复制完成”算作“可恢复训练”。这些检查尚未在你的新实例执行，不能提前标记通过。

若镜像没有迁移完整，不要随意升级 PyTorch / vLLM / FlashAttention；使用项目固定依赖记录修复。新 VGPU32GB 的实际硬件仍需体检，显存相同不保证软件兼容性或速度相同。

## 4. 启动 Mac 评价服务与新地址隧道

打开 Docker Desktop 并等待 engine 就绪。在 Mac 终端 A：

```bash
cd /Users/zzh/Documents/ChatGPT/agent-r1
python3 scripts/day6_local_service.py start --dataset data/mbpp_repair/v0.2
```

返回健康状态中应有 `backend: docker`、`task_count: 332`。如果提示端口已占用，先用 `status` 核对已有服务，不重复启动。

Mac 终端 B 的隧道命令需要使用 **新实例** 的 SSH 主机、端口和已授权的公钥。待你提供新 SSH 登录命令后，助手会填好可复制命令。不要直接使用当前 `day6_tunnel.py` 默认地址：它仍指向旧实例。SSH 密码、私钥、SwanLab API Key 都由你在自己的终端输入，不发到聊天中。

## 5. 先看配置，再运行预检

下面的 `preview` 只查看正式阶段的配置，不进行训练。

```bash
cd /root/autodl-tmp/agent-r1-day6
export PYTHONPATH=/root/autodl-tmp/agent-r1-day6:/root/autodl-tmp/agent-r1-day6/runs/day6/Agent-R1
.venv/bin/python scripts/day9_train.py preview --phase formal
.venv/bin/python scripts/day9_preflight.py
```

检查 `trainer.resume_from_path` 指向第 11 步、累计步数为 225、保存和加载内容为 `model/extra`，以及 `cpu_preparation_complete`、`storage_ready`、`ready_for_gpu_pilot` 为 true。最后一个是脚本沿用的就绪字段名，恢复正式阶段同样使用它，不是要求再跑 pilot。

当前存储预算是两份权重、导出及余量共 22GiB；脚本会把本次已有完整 checkpoint 的大小计入容量预算，不能只凭当前 `df` 空间小于 22GiB 就判断失败。

还要确认远端通过反向隧道访问的 Mac 服务健康、版本正确。预检脚本本身不证明完整工具链已在新主机验收，正式启动入口还会检查服务。

## 6. 验收后，由你启动训练

在确认前面各项输出后，GPU 终端运行以下命令。它真正启动训练，当前文档生成过程没有执行它。

```bash
.venv/bin/python scripts/day9_control.py start --phase formal
.venv/bin/python scripts/day9_control.py status
```

第一条后台启动一个阶段，SSH 普通终端断开不会单独终止它；仍需 Mac 的 Docker 与隧道在线。不要重复启动，也不使用 `pilot` 阶段覆盖已有进度。累计目标为 225，单次正式阶段上限 8 小时，连续 5 个 batch 无组内奖励差异会停止检查。

直接用这个控制入口不会自动创建新的全流程监督器、Mac 同步、防休眠或备份任务；后续按实际需要单独准备。迁移前的 Mac 同步脚本仍含旧 SSH 地址，更新前不启动它。

这个入口启动单个正式阶段，不更新旧监督器的状态文件。因此 `status` 中的 `pipeline paused_by_user` 可能是上次的历史状态；本次是否正在运行，以 `formal running`、本次 attempt 和新日志为准。阶段完成后还需收集原始 worker 日志并做完整验收，不把后台进程退出直接当作整天验收通过。

先用预览输出确认新 attempt 的日志位置；运行后可查看：

```bash
.venv/bin/python scripts/day9_control.py status
tail -n 30 reports/day9_formal_controller.log
```

controller 日志会在阶段结束时给出具体训练日志路径；实际训练过程中从 `runs/day9/launch/` 的新 attempt 记录取得 attempt ID，再查看对应 `reports/day9_formal_execute_<attempt>.log`。如需实时查看，助手按你本次实际输出填好 `tail -f` 命令，避免读到上次暂停的日志。

## 7. SwanLab：训练曲线与实验记录

如果你说的“图像”是 loss / reward 等训练曲线，SwanLab 适合做这件事。它还支持展示图像、文本等媒体，但本项目是代码修复 Agent，不需要图片数据预处理。

当前真实训练脚本只配置 `trainer.logger=['console']`，原冻结 Linux 依赖清单没有 SwanLab。现有日志足以运行和验收；SwanLab 是可选的实验记录方式，尚未接入或验证。官方 verl 支持 SwanLab logger，但本项目外层脚本不直接接受任意 Hydra 参数，不能在 `day9_train.py` 命令后随意加 `trainer.logger=...`。

准备接入时，再选择记录进程读取现有指标，或在明确记录配置变更后启用原生 logger；保留原始日志与恢复指纹。不要把示例中的随机 loss 当作真实训练数据，也不要把 SwanLab 的“实验续接”当成模型 checkpoint 恢复。

| 想看什么 | 当前证据来源 | 含义 |
|---|---|---|
| 策略 loss / KL | `actor/pg_loss`、`actor/kl_loss` | 优化过程，RL 中不要求每一步单调下降 |
| 整条轨迹成功率 | `critic/score/trajectory/mean`，或真实轨迹审计 | 训练题上的表现，不是 dev/test 能力 |
| 组内奖励差异 | 审计 JSON 中的 `mixed_reward_groups`，需要额外接入 | 是否有相对优势信号 |
| 梯度与耗时 | `actor/grad_norm`、`timing_s/step` | 数值与吞吐健康情况 |
| GPU 占用 | NVML 采样 | 与训练库自身的 allocator 指标分开理解 |

不要把 `critic/score/mean` 直接称为轨迹成功率：我们多轮 Agent 的这个数是 step 层面的均值。图表可帮助观察训练，但不能代替冻结 dev 上的 SFT-only / SFT+GRPO 对照。

官方资料：[SwanLab 实验记录](https://docs.swanlab.cn/guide_cloud/experiment_track/what-is-experiment-track.html)、[verl 集成](https://docs.swanlab.cn/guide_cloud/integration/integration-verl.html)。

## 8. 暂停与继续

希望结束时先通知助手一起确认最近完整 checkpoint，并停止本次 driver 和监督任务，再关闭 Mac。当前训练脚本没有安全的 `stop` 子命令，不用 `killall python` 或直接关 Mac 代替保存。停止后可能从最近一次定期 checkpoint 重跑若干步。

本次已知恢复点为第 11 步；后续以实际完成标记、保存日志和哈希核验为准。完整模型仍在 AutoDL，Mac 只有日志、小状态和不完整下载；迁移验收前保留旧实例。
