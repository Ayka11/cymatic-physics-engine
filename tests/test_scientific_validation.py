from cymatic_engine.scientific_validation import validate_science

def base():
    phones=['æ','ɑ','ɛ','ɪ','i','ʌ','ə','u','ʊ','ɔ','oʊ','aɪ','eɪ','p','b','t','d','k','g','f','v','s','z','ʃ','ʒ','θ','ð','h','m','n','l','r','w','j']
    rec=[]
    for pi,p in enumerate(phones):
        for i in range(20):
            rec.append({'phone_normalized':p,'confidence':.9,'start_sample':i*1000,'end_sample':i*1000+500,'speaker_id':f's{i%5}'})
    return {'records':rec,'dataset_sha256':'x','real_mms_fa_execution_performed':True},{'status':'PASS'},{'status':'PASS','manifest_hash':'m'},{'status':'PASS','dataset_sha256':'x'}

def test_review_without_reference():
    d,q,m,b=base(); r=validate_science(d,q,m,b,rerun_hash='x'); assert r['status']=='PASS_WITH_REVIEW'; assert 'independent_reference_alignment' in r['review_items']

def test_pass_with_reference():
    d,q,m,b=base(); r=validate_science(d,q,m,b,independent_reference_present=True,rerun_hash='x'); assert r['status']=='PASS'; assert r['release_freeze']['frozen']

def test_block_hash():
    d,q,m,b=base(); r=validate_science(d,q,m,b,independent_reference_present=True,rerun_hash='bad'); assert r['status']=='BLOCKED'
