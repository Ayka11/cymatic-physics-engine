#!/usr/bin/env python3
import argparse, json
from cymatic_engine.corpus.real_corpus_runner import run_corpus
p=argparse.ArgumentParser(); p.add_argument('--manifest',required=True); p.add_argument('--output-dir',required=True); p.add_argument('--device',default='auto')
a=p.parse_args(); r=run_corpus(a.manifest,a.output_dir,a.device); print(json.dumps(r,ensure_ascii=False,indent=2)); raise SystemExit(0 if r['status'].startswith('PASS') else 2)
