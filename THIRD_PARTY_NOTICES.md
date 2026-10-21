# 来源与第三方资产

本项目是围绕开源框架的受限代码修复训练与评估实现，不是 Agent-R1、verl 或 Qwen 的官方项目，也没有将上游算法实现宣称为从零原创。

| 组件 | 来源与用途 |
| --- | --- |
| Agent-R1 | https://github.com/AgentR1/Agent-R1 ，实际适配版本见 `TRAINING_SOURCE_LOCK.json` |
| verl | https://github.com/volcengine/verl ，固定训练源码与环境记录见 `TRAINING_SOURCE_LOCK.json` |
| Qwen2.5-Coder | https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct ，固定 revision 见模型与训练报告；权重不在本仓库 |
| MBPP | https://github.com/google-research/google-research/tree/master/mbpp ，上游快照与原始许可证位于 `data/sources/mbpp/` |
| ZzhClaw | https://github.com/ookkiou/Zzh-Claw ，受限接入补丁位于 `integrations/zzhclaw/` |

MBPP 任务在本项目中经过输入域审查、用例扩充和单位置缺陷注入；修改与选择过程在数据 manifest 和 selection report 中记录。`data/sources/mbpp/LICENSE` 保留原始 Apache-2.0 许可证。运行时“私有测试”是对模型的可见性边界，仓库中的测试资产用于审查与复现，不声称其内容属于保密服务。

未复制完整上游训练框架或大模型权重；它们由固定版本准备流程获取，并遵循各自来源的条款。本仓库目前没有另外授予统一的项目级开源许可证，第三方文件的许可证保留在原位置。
