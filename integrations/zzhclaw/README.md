# ZzhClaw 受限 repair profile 补丁

本目录把另一个本机仓库中已经验证的接入改动一并发布，避免训练仓库引用未公开的本地代码。不是完整 ZzhClaw 源码副本；原始应用与其许可证见 [Zzh-Claw](https://github.com/ookkiou/Zzh-Claw)。

固定基线 commit：`a6831bcfa6c2cc0fade3c10da52e9203904d1cda`。补丁包含 README、显式 CLI 路由、`CodeRepairAgent`、vLLM token transport 与相关测试；普通 Agent 工具循环保持原样。`manifest.json` 记录基线与补丁 SHA256。

从新目录准备应用（路径可自行选择）：

```bash
git clone https://github.com/ookkiou/Zzh-Claw.git zzhclaw-repair
cd zzhclaw-repair
git checkout --detach a6831bcfa6c2cc0fade3c10da52e9203904d1cda
git apply --check ../zzh-agent-r1/integrations/zzhclaw/repair-profile.patch
git apply ../zzh-agent-r1/integrations/zzhclaw/repair-profile.patch
```

安装应用依赖后，把训练仓库加入 `PYTHONPATH`。受限 profile 的运行命令与评价服务前提见训练仓库的 `docs/DAY13_14_ZZHCLAW_RUNBOOK.md`；将示例中的本机绝对路径替换为自己的路径。模型权重与 SSH 凭据不随补丁提供。

这是 CLI 修复 profile 的集成，不代表所有 UI 或通用工具都经过模型迁移验收。
