"""Formal-run observer and bounded retention; delegate GRPO to the Day8-verified path."""
import json
import os
from pathlib import Path

from code_repair.checkpoint_retention import ensure_run_root,mark_checkpoint_complete,prepare_checkpoint_save
from code_repair.day8_audit import AuditedRayAgentTrainer,audit_batch


class FormalRepairTrainer(AuditedRayAgentTrainer):
    def _update_actor(self,batch):
        allowed=json.loads(Path(os.environ['CODE_REPAIR_RUN_INPUTS']).read_text())
        table={r['task_id'] for r in allowed['tasks'] if r['split']=='train'}
        if not set(map(str,batch.non_tensor_batch['repair_task_id'])).issubset(table):
            raise ValueError('Non-train task entered formal optimizer batch')
        signal=audit_batch(batch,self.config.actor_rollout_ref.rollout.n)
        zeros=getattr(self,'_zero_signal_batches',0)+1 if signal['mixed_reward_groups']==0 else 0
        self._zero_signal_batches=zeros
        if zeros>=int(os.environ['CODE_REPAIR_ZERO_SIGNAL_LIMIT']):
            raise RuntimeError('Repeated batches lack relative reward signal; stop and inspect, keep latest completed checkpoint')
        return super()._update_actor(batch)

    def _save_checkpoint(self):
        root=Path(self.config.trainer.default_local_dir)
        fingerprint=os.environ['CODE_REPAIR_RUN_FINGERPRINT']
        ensure_run_root(root,fingerprint)
        removed=prepare_checkpoint_save(root,fingerprint,self.global_steps)
        super()._save_checkpoint()
        info=mark_checkpoint_complete(root,fingerprint,self.global_steps)
        log=root/'checkpoint_events.jsonl'
        with log.open('a') as stream:
            stream.write(json.dumps({'global_step':self.global_steps,'removed_older_owned_steps':removed,
                'saved_bytes':sum(info['files'].values()),'model_extra_and_data_saved':True,
                'optimizer_state_saved':False})+'\n')
