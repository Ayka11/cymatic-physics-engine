import argparse,json
from cymatic_engine.scientific_validation import validate_science

def load(p):
    with open(p,encoding='utf-8') as f:return json.load(f)

ap=argparse.ArgumentParser(); ap.add_argument('--dataset',required=True); ap.add_argument('--qc',required=True); ap.add_argument('--manifest',required=True); ap.add_argument('--benchmark',required=True); ap.add_argument('--rerun-hash'); ap.add_argument('--reference',action='store_true'); ap.add_argument('--output',required=True); a=ap.parse_args()
r=validate_science(load(a.dataset),load(a.qc),load(a.manifest),load(a.benchmark),independent_reference_present=a.reference,rerun_hash=a.rerun_hash)
with open(a.output,'w',encoding='utf-8') as f: json.dump(r,f,ensure_ascii=False,indent=2)
print(r['status'])
