"""Audit the completed application migration without running any model or test cases."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from day13_prepare import PROTOCOL, build, digest
from code_repair.agent_protocol import parse_action
from code_repair.contracts import ContractError, validate_tool_call


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zzhclaw-repo',type=Path,default=Path('/Users/zzh/Documents/GitHub/zzhclaw'))
    args = parser.parse_args()
    checks = []
    metrics = {}
    def check(name, condition):
        checks.append({'name':name,'passed':bool(condition)})
        if not condition:
            raise ValueError(name)
    report = {'complete':False,'checked_at':datetime.now(timezone.utc).isoformat(),
        'scope':'restricted ZzhClaw CLI repair profile and paired application dev migration',
        'checks':checks,'metrics':metrics,'training_performed':False,'final_test_reexecuted':False,
        'formal_225_updates_complete':False,'model_weight_backup_complete':False,
        'statistical_significance_evaluated':False,
        'limitations':['32 dev variants from 14 original sources, with correlated repeated seeds',
            'vLLM backend/random stream differ from the earlier Transformers evaluation',
            'CLI-only restricted repair profile; general tools and UI were not evaluated',
            'Source FSDP weights were not rehashed or reloaded by this audit; merged-model identity uses recorded full hashes']}
    try:
        recipe = json.loads(PROTOCOL.read_text())
        check('current_application_and_evaluation_code_match_frozen_recipe',build(args.zzhclaw_repo.resolve())==recipe)
        protocol_sha = digest(PROTOCOL)
        report['protocol_sha256'] = protocol_sha
        check('original_final_test_protocol_unchanged',digest(ROOT/'training/final_test/evaluation_protocol.json')==
            '4b5fde7d02ac238d26fc4ed4cebcbb4d882ddfc0e85a530ab333cadc311742eb')
        local = json.loads((ROOT/'reports/day13_local_profile_acceptance.json').read_text())
        check('scripted_http_zzhclaw_and_real_docker_acceptance',local['complete'] and local['real_docker']
            and local['real_http_transport'] and local['profile_sha256']==recipe['app_files_sha256']['zzhclaw/agent/repair.py'])
        smoke_path = ROOT/'reports/day13_step70_smoke.json'
        smoke = json.loads(smoke_path.read_text())
        smoke_acceptance = json.loads((ROOT/'reports/day13_real_api_acceptance.json').read_text())
        check('real_model_api_smoke_complete',smoke_acceptance['complete']
            and smoke_acceptance['protocol_sha256']==protocol_sha
            and smoke_acceptance['source_report_sha256']==digest(smoke_path)
            and smoke['complete'] and len(smoke['episodes'])==2 and not smoke['scripted_fixture'])
        identities = {s:json.loads((ROOT/'runs/day13'/f'model-{s}.json').read_text()) for s in ('sft','step70')}
        check('recorded_merged_weight_hashes_and_server_version_match',all(i['stage']==stage
            and i['model_sha256']==recipe['model_sha256'][stage] and i['vllm_version']=='0.11.0'
            and i['helper_sha256']==recipe['local_files_sha256']['scripts/day13_serve_model.py']
            and i['core_files_sha256']==recipe['core_files_sha256'] for stage,i in identities.items()))
        ids = {row['task_id'] for row in recipe['tasks']}
        check('both_models_have_identical_frozen_initial_prompt_fingerprints',
            identities['sft']['initial_dev_prompts']==identities['step70']['initial_dev_prompts']
            and set(identities['sft']['initial_dev_prompts'])==ids)
        check('generation_defaults_equal_between_models',
            identities['sft']['generation_config']==identities['step70']['generation_config'])
        expected = {(row['task_id'],seed) for row in recipe['tasks'] for seed in recipe['seeds']}
        reports = {}
        tables = {}
        for stage in ('sft','step70'):
            path = ROOT/'reports'/f'day13_{stage}_dev.json'
            r = json.loads(path.read_text())
            reports[stage] = r
            es, inputs = r['episodes'],r['inputs']
            table = {(e['task_id'],e['seed']):e for e in es}
            check(stage+'_complete_unique_96_valid_episodes',r['complete'] and len(es)==len(table)==len(expected)==96
                and set(table)==expected and inputs['stage']==stage and inputs['scope']=='dev'
                and inputs['protocol_sha256']==protocol_sha and inputs['model_sha256']==recipe['model_sha256'][stage]
                and all(e['terminal']['valid_episode'] and e['reward'] in (0,1) and not e['final_test']
                    and e['profile']=='code-repair-v1' and e['model']=='zzh-repair-'+stage for e in es))
            check(stage+'_decision_and_token_budgets_preserved',all(1<=e['decisions']<=6
                and len(e['trace'])==len(e['prompt_tokens'])==len(e['response_tokens'])==e['decisions']
                and all(0<n<=4096 for n in e['prompt_tokens']) and all(0<n<=512 for n in e['response_tokens']) for e in es))
            for e in es:
                acceptance = e['terminal']['acceptance']
                correct = (acceptance is not None and acceptance['status']=='completed'
                    and acceptance['failed']==0 and acceptance['tests']>0
                    and e['terminal']['termination_reason']!='episode_timeout')
                if bool(e['reward'])!=correct:
                    raise ValueError('Reward does not match terminal acceptance')
                for t in e['trace']:
                    try:
                        action, parsed = parse_action(t['model_text']),True
                    except ValueError:
                        action, parsed = None,False
                    valid = parsed
                    if parsed and 'name' in action:
                        try:
                            validate_tool_call(action['name'],action['arguments'])
                        except ContractError:
                            valid = False
                    if action!=t['action'] or parsed!=t['parsed'] or valid!=t['contract_valid']:
                        raise ValueError('Raw model action differs from recorded protocol trace')
            check(stage+'_raw_action_contracts_and_terminal_rewards_recomputed',True)
            tables[stage] = table
            metrics[stage] = {'successes':sum(e['reward']==1 for e in es),'episodes':len(es),
                'invalid_attempts':len(r['invalid_attempts']),
                'invalid_model_actions':sum(not t['contract_valid'] for e in es for t in e['trace']),
                'decisions':sum(e['decisions'] for e in es),
                'prompt_tokens':sum(sum(e['prompt_tokens']) for e in es),
                'response_tokens':sum(sum(e['response_tokens']) for e in es),
                'episode_seconds':sum(e['elapsed_seconds'] for e in es),
                'termination_reasons':dict(Counter(e['terminal']['termination_reason'] for e in es)),
                'source_report_sha256':digest(path)}
        check('same_application_inference_and_evaluator_origins',all(reports['sft']['inputs'][k]==reports['step70']['inputs'][k]
            for k in ('inference_url','evaluator_url')))
        c = json.loads((ROOT/'reports/day14_application_comparison.json').read_text())
        improved = sum(tables['sft'][k]['reward']==0 and tables['step70'][k]['reward']==1 for k in expected)
        regressed = sum(tables['sft'][k]['reward']==1 and tables['step70'][k]['reward']==0 for k in expected)
        check('paired_summary_and_source_report_hashes_recomputed',c['complete'] and c['protocol_sha256']==protocol_sha
            and c['episodes_per_model']==96 and c['paired_improved']==improved and c['paired_regressed']==regressed
            and all(c[s+'_successes']==metrics[s]['successes']
                and c['source_reports_sha256'][s]==metrics[s]['source_report_sha256']
                and c['invalid_attempts'][s]==metrics[s]['invalid_attempts'] for s in reports)
            and c['delta_percentage_points']==100*(metrics['step70']['successes']-metrics['sft']['successes'])/96
            and all(c['by_seed'][str(seed)][s]==sum(e['reward'] for (task,sd),e in tables[s].items() if sd==seed)
                for s in reports for seed in recipe['seeds']))
        report.update(complete=True,paired_application_dev_complete=True,
            comparison_sha256=digest(ROOT/'reports/day14_application_comparison.json'),
            source_count=len({row['source_id'] for row in recipe['tasks']}),task_count=len(ids),
            valid_episodes=192,paired_improved=improved,paired_regressed=regressed,
            delta_percentage_points=c['delta_percentage_points'])
    except Exception as error:
        report['error'] = str(error)
    output = ROOT/'reports/day14_acceptance.json'
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if report['complete'] else 1


if __name__=='__main__':
    raise SystemExit(main())
