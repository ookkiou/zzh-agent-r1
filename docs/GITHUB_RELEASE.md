# GitHub 首次发布说明

目标：`ookkiou/zzh-agent-r1`，公开仓库。发布训练代码、任务数据、脱离凭据的实验报告、图表和复算材料；不发布模型权重或运行凭据。

## 克隆后先运行什么

```bash
git clone https://github.com/ookkiou/zzh-agent-r1.git
cd zzh-agent-r1
python3 scripts/day15_demo.py --case improvement
python3 scripts/day15_demo.py --case regression
python3 scripts/check_day15.py
```

以上是已记录结果的回放和离线证据核验，不需要 GPU、Docker、外部 ZzhClaw 安装或 API key，也不进行新的模型推理。需要重算图表数字时：

```bash
python3 scripts/build_day15_delivery.py --skip-plots
```

完整重新画图还需要 Matplotlib / NumPy。证据包在最初的第 15 天之后会随发布文档和公开审计副本更新而重新打包；以本次包的 `.sha256` 和 manifest 为准，模型、test 协议、原始评估结果不因此改变。

## 数据与完整测试的前提

`runs/` 是运行目录，包含模型、凭据和缓存，整体不上传。需要公开模型输入的测试，可以从已提交的数据重建，不执行模型或候选代码：

```bash
python3 scripts/prepare_public_exports.py
```

部分接口测试还需要固定的 Agent-R1 源码位于 `runs/day6/Agent-R1`，并安装对应接口依赖；GPU 训练依赖更完整的锁定环境。不要把离线证据检查通过误写成全新 GPU 训练已复现。原始数据和镜像也有独立复验入口，见 `DAY15_REPRODUCE.md`。

ZzhClaw 代码在另一个仓库，应用 profile 的可复现补丁和基线 commit 已放在 `integrations/zzhclaw/`，无需依赖作者尚未提交的本机改动。

## 发布边界

- `.gitignore` 排除 `runs/`、`.env`、私钥、权重、缓存、原始日志与不完整下载。
- 用于结果曲线的 1–11 步原始审计另有公开副本 `reports/day9_training_batch_audit_1_11.jsonl`，其字节与本机原始审计一致，不包含评价 token。
- `reports/` 中早期的暂停与未完成状态是历史快照；当前状态以最终 test、day14 和 day15 报告为准。
- 历史操作文档含原运行路径和端口示例；不是面向读者可直接复用的有效登录配置，不提供私钥或令牌。
- 首次提交使用 GitHub noreply 邮箱，避免把本机私人邮箱写入新的公开 Git 历史。
- 目前不随仓库提供完整权重，原 225/255 步目标与实例外权重备份仍未验收。
