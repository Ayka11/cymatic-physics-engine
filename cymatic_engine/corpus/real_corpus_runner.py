from __future__ import annotations
import json, hashlib
from pathlib import Path
from typing import Any

from ..alignment.mms_fa_runtime import MMSFARuntime
from ..alignment.phone_projection import project_phone_spans

SCHEMA = 'CPE_REAL_CORPUS_RUN_v713'

def canonical_json(x: Any) -> str:
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':'))

def sha256_text(x: str) -> str:
    return hashlib.sha256(x.encode('utf-8')).hexdigest()

def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows=[]
    with open(path, encoding='utf-8') as f:
        for line_no,line in enumerate(f,1):
            if not line.strip(): continue
            try: rows.append(json.loads(line))
            except json.JSONDecodeError as e: raise ValueError(f'{path}:{line_no}: invalid JSON: {e}')
    return rows

def run_corpus(manifest_path: str | Path, output_dir: str | Path, device: str='auto') -> dict[str, Any]:
    manifest_path=Path(manifest_path); output_dir=Path(output_dir); output_dir.mkdir(parents=True, exist_ok=True)
    items=load_jsonl(manifest_path)
    if not items:
        return {'schema':SCHEMA,'status':'BLOCKED','reason':'EMPTY_MANIFEST','items':0}
    runtime=MMSFARuntime(device=device, with_star=False)
    results=[]; blocked=[]
    for idx,item in enumerate(items):
        uid=str(item.get('utterance_id','')).strip(); speaker=str(item.get('speaker_id','')).strip()
        audio=item.get('audio_file'); transcript=item.get('transcript')
        if not uid or not speaker or not audio or transcript is None:
            blocked.append({'index':idx,'utterance_id':uid,'reason':'MANIFEST_SCHEMA'})
            continue
        try:
            map_path=item.get('phone_map_file')
            if not map_path:
                blocked.append({'index':idx,'utterance_id':uid,'reason':'PHONE_MAP_REQUIRED'}); continue
            maps=load_jsonl(map_path)
            alignment=runtime.align(audio, transcript)
            proj=project_phone_spans(
                utterance_id=uid, speaker_id=speaker, audio_file=str(audio),
                word=str(item.get('word','')).strip() or str(item.get('normalized_word','')).strip(),
                normalized_word=str(item.get('normalized_word','')).strip() or str(item.get('word','')).strip(),
                char_spans=[{'char_start':r['char_start'],'char_end':r['char_end'],'start_sample':r['start_sample'],'end_sample':r['end_sample'],'confidence':r['confidence']} for r in alignment['records']],
                phone_map=maps,
                source_alignment=alignment,
            )
            if proj.get('status')!='PASS':
                blocked.append({'index':idx,'utterance_id':uid,'reason':proj.get('reason','PHONE_PROJECTION_BLOCKED'),'detail':proj.get('errors',[])})
                continue
            results.extend(proj['phones'])
        except Exception as e:
            blocked.append({'index':idx,'utterance_id':uid,'reason':'RUNTIME_ERROR','detail':str(e)})
    out_jsonl=output_dir/'projected_phones.jsonl'
    with open(out_jsonl,'w',encoding='utf-8') as f:
        for row in results: f.write(canonical_json(row)+'\n')
    digest=hashlib.sha256(out_jsonl.read_bytes()).hexdigest()
    status='PASS' if results and not blocked else ('PASS_WITH_BLOCKED_ITEMS' if results else 'BLOCKED')
    report={'schema':SCHEMA,'status':status,'manifest_sha256':sha256_text(manifest_path.read_text(encoding='utf-8')),
            'items_total':len(items),'items_projected':len({r['utterance_id'] for r in results}),'phone_rows':len(results),
            'blocked_items':blocked,'projected_jsonl':str(out_jsonl),'projected_jsonl_sha256':digest,
            'model_id':'torchaudio.pipelines.MMS_FA','fail_closed':True}
    (output_dir/'REAL_CORPUS_RUN_v713.json').write_text(canonical_json(report),encoding='utf-8')
    return report
