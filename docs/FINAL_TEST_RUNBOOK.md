# 最终 test：用户手动执行指南

本机数据构建和168次Docker夹具验收已通过。以下命令才会启动最终模型test；本指南生成时尚未执行。测试使用42个原题、种子17/29/43，每个模型126次，共252次。SFT-only与step70权重从AutoDL本地加载。

## 0. Mac权重下载可以暂停

SCP到Mac只是独立备份，不是推理依赖。在正在下载model.safetensors的那个终端按Ctrl+C可以停止复制，远端文件仍保留。Mac的部分文件不能作为模型使用。当前不要释放或删除存有唯一完整模型的实例；后续可另选备份方式。

## 1. Mac：启动单独的test评价服务并上传小包

Docker Desktop需运行。

~~~bash
cd /Users/zzh/Documents/ChatGPT/agent-r1
python3 scripts/final_test_local_service.py start
~~~

健康状态应含backend=docker、task_count=42、数据指纹46de09ae5b37c40a2a06f2a40ddf455b9195628ae96e0840a31955de8a7ea109。若8766已占用，先运行status子命令核对，不重复启动。

~~~bash
scp -i /Users/zzh/Documents/ChatGPT/agent-r1/runs/ssh/autodl_day6_ed25519   -P 37856   /Users/zzh/Documents/ChatGPT/agent-r1/runs/final_test/final-test-public.tar.gz   root@connect.westc.seetacloud.com:/root/autodl-tmp/agent-r1-day6/runs/final-test-public.tar.gz
~~~

包约32KB，132个文件，包含公开任务、只读加载器、冻结协议和GPU评估入口，不含私有用例、参考代码或完整模型权重。SSH地址适用于当前实例，迁移后须先更新连接信息。

## 2. Mac：另开终端，保持test反向隧道

~~~bash
caffeinate -i -s ssh -p 37856   -N -T   -o ExitOnForwardFailure=yes   -o ServerAliveInterval=30   -o ServerAliveCountMax=3   -R 127.0.0.1:18766:127.0.0.1:8766   root@connect.westc.seetacloud.com
~~~

需要密码时只在自己终端输入。连接成功通常没有输出。训练阶段的18765隧道不是本轮18766隧道。Mac需接电、开盖、联网，Docker与该隧道持续可用。

## 3. AutoDL：解包，校验，通过后后台启动

~~~bash
cd /root/autodl-tmp/agent-r1-day6
tar -xzf runs/final-test-public.tar.gz

if .venv/bin/python scripts/evaluate_final_test.py --check-only; then
  nohup .venv/bin/python -u scripts/evaluate_final_test.py     > reports/final_test_eval.log 2>&1 < /dev/null &
  echo $! > runs/final_test/evaluation.pid
  cat runs/final_test/evaluation.pid
fi
~~~

只执行一次。校验包括两个模型哈希、封存协议、42道公开任务、tokenizer和生成默认值、冻结核心代码及Docker服务身份。失败会在启动推理前停止；不要通过改协议哈希、任务或私有用例来绕过校验。

本程序只做推理和代码验收，没有参数更新，也不会恢复GRPO训练。

## 4. AutoDL：查看进度

等待约一分钟：

~~~bash
tail -n 15 reports/final_test_eval.log
~~~

先出现stage=sft、total=126，随后stage=step70。进度报告为reports/final_test_eval_sft.json及final_test_eval_step70.json。完成后将出现PAIRED FINAL TEST COMPARISON，对照文件为reports/final_test_eval_comparison.json。

将启动进程号与日志发给助手以核验，并切换每10分钟汇报到最终test。旧的训练/dev监控当前暂停，不把其状态当作本轮test状态。

## 5. 结果使用

完整覆盖两组126个有效episode后，报告总体成功率、百分点差异、成对改善/退化、各种子表现及8个来源排除原因。单模型126次是42个原题的重复采样，不是126个独立原题。

独立test结果如实保留，不以它反复调整模型、任务、提示词再宣称同一结果为未见测试。原225步计划未完成的事实继续记录。
