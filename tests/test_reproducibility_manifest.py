import json
from pathlib import Path
from cymatic_engine.provenance_manifest import build_manifest

def _seed(root, statuses):
    (root/'results').mkdir()
    for name, st in statuses.items():
        (root/'results'/name).write_text(json.dumps({'status':st}), encoding='utf-8')

def test_blocks_when_mms_fa_missing(tmp_path):
    _seed(tmp_path, {
      'MMS_FA_STATUS.json':'BLOCKED','ALIGNMENT_VALIDATOR_STATUS.json':'IMPLEMENTED',
      'CANDIDATE_QC_STATUS.json':'IMPLEMENTED','DATASET_BUILDER_STATUS.json':'IMPLEMENTED',
      'CORPUS_BALANCE_QC_STATUS.json':'BLOCKED'})
    r=build_manifest(tmp_path)
    assert r['status']=='BLOCKED'
    assert 'mms_fa_not_executed_or_weights_unavailable' in r['failures']

def test_passes_only_all_upstream_pass(tmp_path):
    _seed(tmp_path, {k:'PASS' for k in [
      'MMS_FA_STATUS.json','ALIGNMENT_VALIDATOR_STATUS.json','CANDIDATE_QC_STATUS.json',
      'DATASET_BUILDER_STATUS.json','CORPUS_BALANCE_QC_STATUS.json']})
    r=build_manifest(tmp_path)
    assert r['status']=='PASS'
    assert len(r['chain_sha256'])==64
    assert r['reproducibility_policy']['content_addressed'] is True
