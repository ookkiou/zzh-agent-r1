"""Replay recorded dev tool traces. No live model, candidate execution or network."""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=('improvement','regression','shared-failure'),default='improvement')
    parser.add_argument('--stage',choices=('sft','step70','both'),default='both')
    parser.add_argument('--delay',type=float,default=0,help='Presentation delay between decisions; default zero')
    args=parser.parse_args()
    if not 0<=args.delay<=2:
        parser.error('Use delay between 0 and 2 seconds')
    r=json.loads((ROOT/'artifacts/day15/cases'/f'{args.case}.json').read_text())
    print('RECORDED DEV REPLAY — no model inference; no candidate code execution')
    print(f"{r['task_id']} | seed {r['seed']} | {r['title']}")
    stages=('sft','step70') if args.stage=='both' else (args.stage,)
    for stage in stages:
        e=r['episodes'][stage]
        print(f'\n[{stage}]')
        for i,t in enumerate(e['trace'],1):
            a=t['action'] or {}
            name=a.get('name','final' if 'final' in a else 'invalid_action')
            response=t['tool_response']
            suffix=''
            if name=='run_tests' and response and isinstance(response.get('output'),dict):
                out=response['output'];suffix=f" public={out['passed']}/{out['tests']}"
            elif response and not response['ok']:
                suffix=' rejected'
            print(f'  {i}. {name}{suffix}')
            if args.delay:
                time.sleep(args.delay)
        acc=e['terminal']['acceptance']
        print(f"  terminal: private aggregate={acc['passed']}/{acc['tests']}; reward={e['reward']}")
    print('\nRecorded patches: artifacts/day15/cases/'+args.case+'.md')
    return 0


if __name__=='__main__':
    sys.exit(main())
