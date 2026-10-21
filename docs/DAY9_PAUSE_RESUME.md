# 第九天暂停与续训

用户要求暂时关闭 Mac，之后再训练。暂停验收已完成：GPU driver 和流水线已停止，NVIDIA compute process 列表为空、显存约 1MiB；本机执行服务、SSH 隧道、同步监控和防休眠进程均已停止。日志与小状态已备份并核验，Mac 现在可以关机。AutoDL 实例未关机、未释放。

## 恢复点

- 最近完整 checkpoint：`/root/zzh-day9-checkpoints/global_step_11`。
- 下一次更新：第 12 次，累计目标仍为 225 次，不是额外 225 次。
- 第 12、13、14 次更新曾执行，但未到第 20 次定期保存点；这些更新的权重未保留，续训时重跑。
- 保存内容：model、scheduler / RNG 等 extra、`data.pt`；不含 optimizer。恢复后 Adam 动量重新初始化。
- 正式阶段原始日志和完整审计已归档到远端 `runs/day9/pauses/pause-20261015-step11/`。活动审计文件回退至第 11 步，与恢复权重一致；没有删除历史证据。
- 停止 driver 时返回码为 -6，分类为用户主动中断；没有将它标成正常完成或第九天通过。

原始状态见 [暂停报告](../reports/day9_pause_status.json)。最新权重备份是否完成，见 [备份报告](../reports/day9_weight_backup.json) 的 `complete` 与实际 SHA256 核验；仅有压缩包文件名不算备份成功。

本次为了尽快关闭 Mac，**完整权重未下载至 Mac**，大文件下载已中止并将不完整文件标为 `.partial`。AutoDL 保留原始 `global_step_11`，另在数据盘保存已校验压缩包 `runs/day9/pause_backup/global_step_11.tar.gz`，大小 5,766,732,836 字节，SHA256 为 `e52e4d7264fe13d0efee103d720cc5931c2fa091971555034e0ea60eea4b7eff`。压缩包和原始 checkpoint 位于不同挂载目录，但都属于当前实例，并不构成实例外权重备份。

Mac 保留日志、运行配置、轨迹、暂停历史以及 `runs/day9/pause_backup/small_states/` 下的 RNG / scheduler / 数据状态、实验身份和文件清单。小状态逐文件 SHA256 与远端备份清单核对；这个目录不含模型权重，不能单独恢复模型。保留当前 AutoDL 实例和两份权重文件，之后优先直接从远端原始 checkpoint 续跑。

## 下次继续

先打开 Mac 和 Docker Desktop，确认 AutoDL 实例可通过当前 SSH 连接访问。如实例换机或地址变化，先更新连接信息、检查文件和 GPU；不要删除旧实例中的唯一权重。

本机重启已验收的数据执行服务和隧道：

```bash
python3 scripts/day6_local_service.py start --dataset data/mbpp_repair/v0.2
python3 scripts/day6_tunnel.py start
```

远端检查原环境、权重、数据和空间后续跑：

```bash
cd /root/autodl-tmp/agent-r1-day6
export PYTHONPATH=/root/autodl-tmp/agent-r1-day6:/root/autodl-tmp/agent-r1-day6/runs/day6/Agent-R1
.venv/bin/python scripts/day9_preflight.py
.venv/bin/python scripts/day9_pipeline.py --continue-after-reload
```

后一命令前台运行；实际长跑应使用项目后台启动方式，并在 Mac 恢复日志同步与防休眠进程。它复核已经通过的第 10 → 11 步重载证据后，从最新完整 checkpoint 开始正式阶段，不重复 pilot。每次重新运行仍有 8 小时阶段上限；保留并核算各次运行耗时，不把暂停重新计时当作总耗时。

如需从 Mac 备份恢复，请先核验压缩包 SHA256，检查归档路径仅在 `global_step_11/` 内，再解包到训练主机的 checkpoint 根目录。保留该目录的完成标记和根目录实验身份文件，核对数据 / 代码 / SFT 清单指纹一致后再运行；不能只拷贝一个模型文件就声称数据进度已恢复。

Mac 关机后本次训练不会继续；这是有意暂停。下次训练期间仍须保持 Mac 联网、Docker 和隧道可用。
