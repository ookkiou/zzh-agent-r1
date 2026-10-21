"""Explicit test-only Docker service; the train/dev service remains unchanged."""
import argparse
import json
import os
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from code_repair.dataset import sha256
from code_repair.execution import DockerBackend
from code_repair.final_test import FinalTestRegistry
from code_repair.service import EvaluationServer


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8766)
    args=parser.parse_args()
    protocol_path=ROOT/'training/final_test/evaluation_protocol.json'
    protocol=json.loads(protocol_path.read_text())
    candidate=ROOT/'reports/day11_candidate_freeze.json'
    if protocol['status']!='sealed_before_first_model_test' or protocol['candidate_freeze_sha256']!=sha256(candidate.read_bytes()):
        raise ValueError('Frozen candidate and sealed held-out protocol required')
    if protocol['test_loader_sha256']!=sha256((ROOT/'code_repair/final_test.py').read_bytes()):
        raise ValueError('Test loader changed after sealing')
    token=os.environ.get('CODE_REPAIR_SERVICE_TOKEN','')
    if len(token)<32:
        raise ValueError('Set the existing private service token via environment; never print it')
    os.environ['PATH']='/Applications/Docker.app/Contents/Resources/bin:'+os.environ.get('PATH',os.defpath)
    image=json.loads((ROOT/'SANDBOX_LOCK.json').read_text())['image']
    registry=FinalTestRegistry(ROOT/'data/mbpp_repair/test-v0.1',protocol['dataset_manifest_sha256'],
        [r['task_id'] for r in protocol['tasks']])
    backend=DockerBackend(image)
    ready=backend.execute('def readiness(): return True','readiness',[[]],timeout=10)
    if ready.status!='completed' or ready.rows[0].get('value') is not True:
        raise ValueError('Docker readiness failed')
    with EvaluationServer(('127.0.0.1',args.port),registry,backend,token,test_timeout=10) as server:
        print('Test-only evaluator ready:',server.server_address,'tasks',len(registry.tasks),flush=True)
        server.serve_forever()


if __name__=='__main__':
    main()
