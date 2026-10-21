"""All v0.2 known correct/defective fixtures through authenticated HTTP and real Docker."""
from concurrent.futures import ThreadPoolExecutor,as_completed
from collections import Counter
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from code_repair.dataset import sha256
from code_repair.evaluation import RemoteEvaluator
from code_repair.tasks import load_task


def main():
    dataset=ROOT/'data/mbpp_repair/v0.2'
    manifest=json.loads((dataset/'manifest.json').read_text())
    validation=json.loads((ROOT/'reports/day9_data_validation.json').read_text())
    if not validation['complete'] or validation['manifest_sha256']!=sha256((dataset/'manifest.json').read_bytes()):
        raise ValueError('Full static/local fixture validation required first')
    token=(ROOT/'runs/day6/evaluator_token').read_text().strip()
    def verify(item):
        directory=dataset/item['path'];task=load_task(directory,include_private=False)
        client=RemoteEvaluator('http://127.0.0.1:8765',token,task.task_id)
        correct=(directory/'reference/solution.py').read_text()
        results={}
        for name,source in [('reference',correct),('starter',task.starter_source)]:
            for mode in ('public','private'):
                result=client.check(source,mode,timeout=5)
                results[name+'/'+mode]=result
        valid=all(v['status']=='completed' and (v['failed']==0 if name.startswith('reference/') else v['failed']>0)
            for name,v in results.items())
        return {**{k:item[k] for k in ('task_id','source_id','split')},'valid':valid,'results':results}
    health=RemoteEvaluator('http://127.0.0.1:8765',token,manifest['tasks'][0]['task_id']).health()
    if health['backend']!='docker' or not health['container_isolation_configured'] or sha256((dataset/'manifest.json').read_bytes()) not in health['dataset_manifest_sha256']:
        raise ValueError('Expected actual Docker service for v0.2')
    rows=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(verify,item) for item in manifest['tasks']]
        for future in as_completed(futures):
            row=future.result();rows.append(row)
            if not row['valid']:print('FAILED',row['task_id'],flush=True)
            if len(rows)%25==0:print('Docker checked',len(rows),'/',len(manifest['tasks']),flush=True)
    rows.sort(key=lambda r:r['task_id'])
    report={'complete':len(rows)==332 and all(r['valid'] for r in rows),'scripted_known_fixtures':True,
        'model_involved':False,'backend':'docker','http_authenticated':True,
        'manifest_sha256':sha256((dataset/'manifest.json').read_bytes()),
        'tasks':rows,'counts':dict(Counter(r['split'] for r in rows)),
        'docker_executions':len(rows)*4,'test_sources_executed':False,'health':health}
    content=json.dumps(report,ensure_ascii=False,indent=2)+'\n'
    if token in content:raise ValueError('Credential in report')
    (ROOT/'reports/day9_docker_data_validation.json').write_text(content)
    print('Docker dataset validation',report['complete'],len(rows),'tasks')
    if not report['complete']:raise SystemExit(1)


if __name__=='__main__':main()
