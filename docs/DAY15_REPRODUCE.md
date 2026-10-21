# 第 15 天：演示、复算与复现

本页区分三件事：已记录结果的离线复算、真实模型重新推理、从头重新训练。当前实测的是第一种，以及此前已经完成的模型评估；第 15 天不自动启动 GPU、训练、Docker 作业或外部发布。

## 1. 零 GPU 的展示与证据复算

在项目根目录执行，Python 3.10+，回放和数字复算仅用标准库：

```bash
python3 scripts/build_day15_delivery.py --skip-plots
python3 scripts/day15_demo.py --case improvement
python3 scripts/day15_demo.py --case regression
python3 scripts/day15_demo.py --case shared-failure
python3 scripts/check_day15.py
```

脚本从完整报告重新配对，重算三组成功数和改善/退化。回放显示两个模型的每次工具动作、公开测试汇总及终局汇总；不执行候选补丁、不读私有测试输入、不调用模型。加 `--delay 0.5` 可以慢速讲解，但“回放”标签必须保留。可以用系统录屏录制这个过程，不把它称为实时推理。

画图另需 Matplotlib / NumPy；使用已有本机 Python 环境运行：

```bash
python3 scripts/build_day15_delivery.py
```

输出目录 `artifacts/day15/`：

| 文件 | 用途 |
| --- | --- |
| `metrics.json` | 来源哈希、完整效果数字及曲线缺口 |
| `evaluation_summary.csv` | 三组同环境评估的导出数字 |
| `sft_updates.csv` | 80 次实际 SFT loss / gradient |
| `training_observations.csv` | 74 步索引；缺失指标留空，不插值 |
| `figures/*.png`、`*.pdf` | SFT、GRPO 诊断与评估对照图 |
| `cases/*.json`、`*.md` | 三类记录案例、逐步轨迹和实际补丁差异 |

GRPO 的 1–11 步来自本机原始 batch 审计；63–74 步来自已保存的只读诊断摘要，12–62 步的 batch 指标不在本机。早期 loss / gradient 只使用确认保留的 1–11 步，旧暂停过程中随后废弃的 12–14 步不接入候选训练曲线。第 15 天请求远端补充日志时 SSH 连接关闭，因此没有宣称已获得完整 GRPO 日志或要求为整理材料开 GPU。

## 2. 三分钟讲解顺序

1. 30 秒：打开 `PROJECT_CARD.md`，说明训练模型、Agent 工具环境和独立执行服务如何形成闭环。
2. 45 秒：展示三组评估图，先报独立 test 的 +2.38 pp，再解释应用 dev 的 +6.25 pp，不混用后端。
3. 45 秒：运行 improvement 回放，比较 LIS 边界修复的实际补丁和执行结果。
4. 30 秒：运行 regression 或 shared-failure，说明退化和公开测试失败后仍停止的局限。
5. 30 秒：展示训练诊断图，解释同题组全对也可能没有相对学习信号，以及为什么保留 step70。

这是一份演示流程与可执行回放；本次没有录制视频，也没有声称实时 GPU 演示通过。

## 3. 真实模型演示（用户手动，另行选择）

前提：完整 step70 导出仍在实例上；AutoDL vLLM 服务已启动，别名 `zzh-repair-step70`；Mac 18000 API 隧道和 Docker 8765 评价服务正常。此前最后运行的是 SFT 服务，因此不能只把模型名改成 step70 就假定服务已经切换。按 [回接指南](DAY13_14_ZZHCLAW_RUNBOOK.md) 手动切换和检查。

```bash
cd /Users/zzh/Documents/ChatGPT/agent-r1

PYTHONPATH=/Users/zzh/Documents/GitHub/zzhclaw:/Users/zzh/Documents/ChatGPT/agent-r1 \
  /Users/zzh/Documents/GitHub/zzhclaw/.venv/bin/python -m zzhclaw repair \
  --public-data runs/day9/public_data --task mbpp-527-m01 \
  --model zzh-repair-step70 --seed 17 \
  --token-file runs/day6/evaluator_token \
  --output runs/day15/live-527-seed17.json
```

这是会调用 GPU 的新 episode，本次未运行。不保证修复成功；已有输出会被拒绝覆盖，重复演示请改用新的输出文件名，保留失败和成功。只用 dev，不拿最终 test 反复调演示。

## 4. 从新环境复现完整链路

需要训练仓库与 ZzhClaw 仓库两个代码树、完整 train/dev 与冻结 test 构建输入、固定模型 revision、依赖锁、Linux GPU、Docker 评价主机及凭据配置。这里没有替他人从全新机器重新完成一次全链路训练。

| 环节 | 固定入口 / 证据 |
| --- | --- |
| MBPP 来源、构建与来源隔离 | `docs/MBPP_DATA_CARD.md`、`DAY9_DATA_CARD.md`、`scripts/build_mbpp.py` |
| 执行隔离与真实 Docker 验收 | `docs/EXECUTION_SERVICE.md`、`SANDBOX_LOCK.json` |
| 基础模型与环境 | Qwen2.5-Coder-1.5B-Instruct revision `2e1fd397ee46e1388853d2af2c993145b0f1098a`；`training/day6/requirements.linux.lock.txt` |
| LoRA SFT | `training/day7/sft_warmup.json`、`reports/day7_sft_warmup.json`、`docs/DAY7_RUNBOOK.md` |
| 多轮 GRPO | `training/code_repair/day9.yaml`、`training/day9/run_plan.json`、`docs/DAY9_RUNBOOK.md` |
| 人工执行与 SSH | `docs/MANUAL_TRAINING_GUIDE.md`；新实例端口需重新确认，不照搬旧 37105 |
| checkpoint 导出与独立 test | `docs/FINAL_TEST_RUNBOOK.md`；协议已冻结且既有 test 已被查看 |
| ZzhClaw API 与同环境迁移 | `docs/DAY13_14_ZZHCLAW_RUNBOOK.md`、`scripts/check_day14.py` |

Agent-R1 commit `b124aa46534cbf2fb8bc8af11405774984c42ac7`，verl v0.7 固定源码版本详见环境记录。实际 GPU 为报告中的 32GB 实例，不能将 `nvidia-smi` 的驱动最高 CUDA 版本当 PyTorch 编译 CUDA 版本；实测 PyTorch 2.8.0+cu128、Transformers 4.57.1、vLLM 0.11.0、Ray 2.48.0。

当前仅保留权重与部分状态，不保存 Adam 动量；重新训练或续训与原过程不逐位等价。公开数据和环境准备脚本不能替代真实 GPU 更新、独立 test 或新机器复现验收。

## 5. 可分享的离线证据包

```bash
python3 scripts/package_day15.py
```

生成 `artifacts/day15/zzh-repair-evidence.tar.gz`。这是结果复算与回放包，不是完整训练源码或权重备份。只包含明确列出的证据报告、绘图/回放/检查脚本、文档和三题公开 starter；不含 `.env`、SSH 私钥、评价 token、完整模型、私有测试输入、参考实现或原始服务日志。没有上传到任何外部平台。

把压缩包放到任意工作目录，解包后可以这样验证（保留原包供校验）：

```bash
tar -xzf zzh-repair-evidence.tar.gz
cd zzh-repair-evidence
python3 scripts/build_day15_delivery.py --skip-plots
python3 scripts/day15_demo.py --case improvement
python3 scripts/check_day15.py --archive ../zzh-repair-evidence.tar.gz
```

重新绘图需要 Matplotlib / NumPy，但已有 PNG / PDF 可直接查看。包校验报告记录文件 SHA256；本项目的完整训练源代码仍需使用原仓库。
