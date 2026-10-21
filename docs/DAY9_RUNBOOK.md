# 第九天：正式 GRPO 的数据、轻量 checkpoint 与试跑

本日数据目标为 300 train / 32 dev。当前训练起点仍是第七天 SFT-only 合并权重，不使用第八天 smoke 权重。数据详情见 [数据卡](DAY9_DATA_CARD.md)，运行参数以 [run_plan.json](../training/day9/run_plan.json) 为准。

## 用户选择的存储策略

用户指定“只保存权重和少量状态”。因此 checkpoint 保存 `model + extra` 和 trainer 的 `data.pt`，**不保存或加载 optimizer**。extra 包括 scheduler 与 RNG；恢复时加载权重和数据游标，Adam 动量重新建立。这是权重续跑，不等同完整优化器续训，也不承诺逐位复现。

第八天实测 FSDP 权重文件 7,108,515,723 字节，约 6.62GiB；extra 约 15KB、data 约 7KB。两份权重、一次 BF16 导出和余量按 22GiB 容量预算检查。原数据盘清理 wheel 后余 8.60GiB，系统盘约有 30GiB 可用，新的 checkpoint 默认位于 **`/root/zzh-day9-checkpoints`**，不写入旧 Day6–8 目录。

容量检查会把本次已完成且身份匹配的 checkpoint 计入预算，避免保存权重后错误地再次要求额外空出完整的 22GiB。每次写新 checkpoint 前只移除本次较旧的完整 checkpoint，至少保留最新完整一份；写入完成后最多保留两份。未完成、身份不符或被改动的文件会停止后续操作，供检查，不自动清除。

系统盘产物应单独备份，不能仅凭容器内已保存就当作异地备份；不要在唯一权重仍在实例中时释放或重建实例。日志、运行配置和小状态会同步到 Mac；完整权重是否备份须以实际传输和哈希核验为准。

## 固定参数与阶段

| 参数 | 值 |
|---|---|
| batch / 同题采样数 | 4 / 4 |
| PPO mini batch / micro batch | 4 / 1 |
| PPO epochs | 1 |
| LR / scheduler | 1e-6 / constant |
| temperature / top-p | 0.8 / 0.95 |
| 每条轨迹最大决策数 | 6 |
| prompt / response 上限 | 4096 / 512 |
| 正式总量 | 3 epochs，累计最多 225 updates |
| 保存频率 | 每 10 updates 及阶段终点 |
| 连续无组内奖励差异 | 5 个 batch 则停止并检查 |

顺序为 pilot 到累计 10 updates（最多 1 小时），重载探针到累计 11（最多 30 分钟），通过后正式阶段到累计 225（最多 8 小时）。后两阶段均为轻量权重续跑，分别重建优化器，不是额外再跑 11 或 225 步。pilot 后按实测吞吐复核剩余时间，时间上限不代表一定能完成 225 步。

每次真实优化之前继续检查多轮生成 mask、同题四条轨迹的 GRPO 优势、私有终局奖励只计一次，以及任务 ID 只能来自 train。基础设施错误中止 batch，不当作模型失败。连续无相对奖励差异的停止条件是训练健康检查，不是能力提升指标。

## 本机公开数据与服务

```bash
python3 scripts/day9_prepare.py
python3 scripts/build_day9_bundle.py
python3 scripts/day6_local_service.py start --dataset data/mbpp_repair/v0.2
python3 scripts/day6_tunnel.py start
```

已在运行时不要重复 start。GPU 推理和更新在 AutoDL；私有用例和 Docker 执行服务仍在 Mac，使用回环地址反向 SSH 隧道。训练期间 Mac 须保持唤醒、联网，Docker、执行服务和隧道保持可用；不能合盖后假设服务器训练仍能完成工具调用。

## 服务器检查与启动

当前远端项目根目录 `/root/autodl-tmp/agent-r1-day6`。增量包通过 SHA256、成员路径和逐文件字节检查后解包；不上传私有测试、参考源码或凭据。

```bash
cd /root/autodl-tmp/agent-r1-day6
export PYTHONPATH=/root/autodl-tmp/agent-r1-day6:/root/autodl-tmp/agent-r1-day6/runs/day6/Agent-R1
.venv/bin/python scripts/day9_prepare.py --parquet-only
.venv/bin/python scripts/day9_train.py resolve --phase pilot
.venv/bin/python scripts/day9_preflight.py
.venv/bin/python scripts/day9_control.py start --phase pilot
.venv/bin/python scripts/day9_control.py status
```

start 立即返回，后台 driver 自带该阶段时间上限，SSH 客户端断开不会单独终止 driver。执行前再次检查空间、运行身份、GPU 空闲和 Docker 服务数据版本；未满足则拒绝开训。正式配置解析不运行模型推理。

pilot 成功后：

```bash
.venv/bin/python scripts/day9_control.py start --phase reload_probe
# 等该阶段结束后验证真实重载，不要同时执行两个阶段。
.venv/bin/python scripts/day9_verify_reload.py
.venv/bin/python scripts/day9_control.py start --phase formal
```

重载验收要求 pilot/reload 两阶段退出码 0、完整轻量 checkpoint 10/11、scheduler 步数对应、实际 native model/extra 加载日志以及只执行第 11 次更新；optimizer 文件和加载日志均不得出现。脚本未实际通过前不能宣称重载已通过。

长跑前必须通过重载验收，并根据 pilot 的真实时间、奖励差异和显存情况决定是否需调整。运行身份包含数据、正式计划、SFT 权重清单和关键代码哈希；改变这些内容需要重新预检并使用合适的新 run 目录，不能混作同一实验。

## 效果评测与验收边界

训练自身不以 vLLM validation 结果替换第八天的 Transformers dev 基线。第十一天沿用冻结的 dev 协议评测候选权重，再决定保留哪个 checkpoint；保留窗口有限时需在轮换前导出、备份或先评测候选，不能恢复已删除的候选。第八天 SFT-only 的 63/96 是既有 dev 基线，不是正式 GRPO 结果。

本地数据完成、CPU 预检通过、GPU 训练已启动、阶段完成、权重重载通过及能力提升证明是不同状态；查看 [DAY9_RESULTS.md](DAY9_RESULTS.md) 和相应原始报告。正式 GRPO 尚未完成时，报告必须保持 `day9_complete=false`。冻结 test 来源未执行。
