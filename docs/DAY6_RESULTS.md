# 第六天实测结果：环境、工具通道与最小训练更新

日期：2026-10-14。第六天机器验收入口为 `python3 scripts/check_day6.py`，报告见 [day6_acceptance.json](../reports/day6_acceptance.json)。本次验收针对训练环境与诊断链路，不能当作代码修复能力提升结果。

## 实际完成了什么

| 项目 | 实测结果 |
|---|---|
| 训练主机 | AutoDL，RTX 4080 SUPER 32760 MiB，16 核 CPU 配额、约 62 GiB 内存配额 |
| 基础环境 | Ubuntu 22.04、Python 3.12.3、PyTorch 2.8.0+cu128；CUDA tensor 和 BF16 检查通过 |
| 训练依赖 | vLLM 0.11.0、固定 tag 源码的 verl 0.7.0.dev0、Ray 2.48.0、Transformers 4.57.1；全部核心模块导入及 pip check 通过 |
| FlashAttention | 2.8.1，选择 C++ ABI TRUE wheel，SHA256 校验及 BF16 GPU 运算对照通过 |
| 模型 | Qwen2.5-Coder-1.5B-Instruct，固定 revision，全部 9 个必需文件校验通过，实际 GPU 推理成功 |
| 执行服务 | GPU → SSH 回环隧道 → Mac Docker；服务器及真实 Ray worker 的鉴权健康检查通过 |
| 三工具诊断 | 原始模型生成 read_file / write_file / run_tests 请求，实际完成一条四步 episode；公开测试和私有终局在 Mac Docker 执行 |
| 故障分类 | 真实连接拒绝触发 infrastructure_error，episode 标记无效，不混为正常失败样本 |
| 官方单步诊断 | GSM8K，GRPO，2 次更新，有限损失和非零梯度；checkpoint 保存、权重变化与 GPU 重载通过 |
| 官方工具配置诊断 | GSM8K AgentEnvLoop 配置，另一次从原始模型开始的 GRPO，2 次更新；checkpoint 检查通过，但没有观察到真实多轮工具调用 |

两次诊断各自从原始模型开始，合计运行四次 update，不能描述成同一个模型连续训练四步。每次配置为 batch=4、n=2、micro-batch=1、单 GPU、prompt 1536 / response 256、CPU offload。只保存模型及 extra state，并保留最后一个 checkpoint；没有验证 optimizer state 断点续训。

## 参数更新的直接证据

| 诊断 | 两步梯度范数 | 权重变化 | 重载结果 |
|---|---|---|---|
| single | 0.9635 / 1.3813 | 检查 338 个张量，261 个发生变化；29,771,678 个元素不同 | GPU 加载后生成 `7` |
| tool 配置 | 1.5621 / 0.9600 | 检查 338 个张量，258 个发生变化；30,592,289 个元素不同 | GPU 加载后生成 `7` |

所有检查到的 checkpoint 权重均有限。比较时发现合并文件额外保存了 `lm_head.weight`，已验证模型配置启用了共享词嵌入，并检查它与 `model.embed_tokens.weight` 完全相等，再按同一组权重名比较。

详见 [single checkpoint 报告](../reports/day6_single_checkpoint_verification.json)、[tool checkpoint 报告](../reports/day6_tool_checkpoint_verification.json)。训练奖励来自不同 batch，没有用它们计算“提升了多少”。

## 工具验证的范围与限制

三工具运行是**引导式协议诊断**：控制器指定工具顺序，提供工具格式说明，最后由控制器终止。没有读取参考补丁或私有用例，没有把服务 token 放进模型消息。模型没有修好缺陷：公开测试通过 1/2，私有终局通过 2/6，最终奖励为 **0**。因此它证明工具通道、反馈和打分可以工作，不证明模型已经具备稳定修复能力。

原始模型输出的是完整 JSON 代码块，并非原生 Hermes 标签。本次增加严格的完整消息适配器：只接受一个 Hermes 或 JSON 代码块请求，校验 name/arguments，再交给固定工具契约。还将真实模型输出规范化为 Hermes，使用固定 Agent-R1 官方解析器做语义一致性检查和真实 Docker 回放。回放报告会明确标记 `is_replay=true`，没有冒充一次新的模型生成。详见 [真实模型轨迹](../reports/day6_model_protocol.json)、[Hermes 适配验证](../reports/day6_hermes_adapter.json)。

官方 GSM8K 工具配置的两步日志中 `num_steps/max=1`。这证明该配置可以进行训练计算，但没有证明数学工具被模型实际调用，更没有证明多轮工具观察参与训练的闭环已经完成。后续修复 recipe 必须把解析器、聊天模板、观察编码和训练 token mask 一起验证；不能直接宣布 Agent 训练全部接通。

本次 GSM8K 来自固定官方数据快照，只选择 32 条 train 和 8 条 test 做运行诊断。它们不是项目的代码修复最终测试集；冻结的 MBPP test 来源未展开、未评测。原有数据转换器和资源哈希仍保持一致。

## 遇到的问题与解决方式

1. **远端非交互 SSH 找不到 Python**：使用明确的 conda/venv Python 路径，保留本机私钥及远端专用公钥。
2. **依赖下载慢、解析器反复下载大包**：缓存完成的 wheel；明确固定 OpenCV、CuPy、NumPy 及相关 SDK 版本，解析成功后再安装，避免重复下载。
3. **可选 FlashInfer 的隔离构建尝试拉取其他 PyTorch**：停止该构建，保留基础 PyTorch 2.8.0，诊断使用明确的 FlashAttention 后端；没有把其他版本装进基础环境。
4. **FlashAttention 二进制 ABI 需要匹配**：检查基础 torch 的 C++ ABI，选用 TRUE wheel，核对官方文件哈希，再实际比较 GPU 运算结果。
5. **verl 版本字符串不等于 tag 名**：官方归档版本文件为 `0.7.0.dev`，安装规范化为 `0.7.0.dev0`。校验源码版本文件哈希与 editable 路径，未更换 commit。
6. **模型输出格式、源码与工具结果混淆**：保留失败记录，加入严格 JSON 适配及公开源码展示；语法错误和伪造结果仍被拒绝。后续需要真实基线和必要的格式 SFT，不能用提示词调试结果代替评测。
7. **checkpoint 权重名称差异**：显式验证 tied weights 后比较，再进行 GPU 重载；不是仅检查文件存在。

## 证据和复现入口

- [总体验收](../reports/day6_acceptance.json)：16 项检查及证据 SHA256。
- [环境体检](../reports/day6_preflight.json)、[完整依赖记录](../training/day6/requirements.linux.lock.txt)、[环境版本 JSON](../reports/day6_environment.lock.json)。依赖文件是该 Linux 实例的实际快照，包含基础镜像包和主机路径，不能原样安装到 Mac。
- [单步训练日志](../reports/day6_single_smoke.log)、[工具配置训练日志](../reports/day6_tool_smoke.log)。实际启动参数和 rollout 备份在忽略提交的 `runs/day6-smoke/`。
- [源码与模型版本](../TRAINING_SOURCE_LOCK.json)、[原始模型文件元数据](../reports/day6_model_files.lock.json)。

远端项目目录为 `/root/autodl-tmp/agent-r1-day6`。两个可加载导出分别在：

```text
runs/day6-smoke/single/merged-step2
runs/day6-smoke/tool/merged-step2
```

checkpoint 权重保存在远端数据盘；本机备份的是诊断日志、配置和验收报告，并未下载整套权重。后续复用单步脚本时，`resume_mode=disable` 会从原始权重重新开始，不能当作恢复已有训练。

## 下一步

第七天开始接入自建代码修复 recipe：实现 Agent-R1 AgentEnv/flow 适配，统一生成格式和观察编码，核对只训练模型生成 token，先在少量 train/dev 任务检查原模型的合法动作率、有效 episode、终局奖励和 GRPO 组内奖励差异。依据实际失败决定是否做格式 SFT，并保留 SFT-only 对照。随后第八天完成正式 dev 基线和自建 5-update smoke，第九至十天再进行正式 GRPO。
