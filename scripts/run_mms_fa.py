#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
from cymatic_engine.alignment.mms_fa_runtime import MMSFARuntime, phone_projection_gate

p=argparse.ArgumentParser()
p.add_argument('--audio', required=True)
p.add_argument('--text', required=True)
p.add_argument('--out', required=True)
p.add_argument('--device', default='auto')
a=p.parse_args()
rt=MMSFARuntime(device=a.device).load()
result=rt.align(a.audio,a.text)
result['phone_projection']=phone_projection_gate(result,None)
Path(a.out).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'status':result['status'],'records':len(result['records']),'phone_projection':result['phone_projection']},ensure_ascii=False))
