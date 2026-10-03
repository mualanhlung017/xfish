import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('--engine',type=Path,required=True)
parser.add_argument('--network',type=Path,required=True)
parser.add_argument('--corpus',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--verifier',type=Path,required=True)
parser.add_argument('--reference',type=Path)
args=parser.parse_args()
spec=importlib.util.spec_from_file_location('eval_verifier',args.verifier)
module=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=module
spec.loader.exec_module(module)
rows=json.loads(args.corpus.read_text())
reference=json.loads(args.reference.read_text())['records'] if args.reference else None
session=module.EngineSession('net-compat',args.engine.resolve(),args.network.resolve(),16,60)
records=[]
mismatches=[]
try:
    for index,row in enumerate(rows):
        actual=session.evaluate(row['position'])
        records.append({'label':row['label'],'position':row['position'],'evaluation':actual})
        if reference:
            expected=reference[index]
            assert expected['position']==row['position']
            if actual!=expected['evaluation']:
                mismatches.append({'label':row['label'],'actual':actual,'expected':expected['evaluation']})
        if index%100==0:
            print(f'{index}/{len(rows)} mismatches={len(mismatches)}',flush=True)
finally:
    session.close()
def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            digest.update(block)
    return digest.hexdigest()
report={'passed':not mismatches,'positions':len(rows),'engine_sha256':sha(args.engine),
        'network_sha256':sha(args.network),'corpus_sha256':sha(args.corpus),
        'evaluated':sum(r['evaluation']['status']=='evaluated' for r in records),
        'in_check':sum(r['evaluation']['status']!='evaluated' for r in records),
        'mismatches':mismatches,'records':records}
args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:report[k] for k in ('passed','positions','evaluated','in_check')},indent=2))
if mismatches:
    print(json.dumps(mismatches[:8],indent=2))
    raise SystemExit(1)
