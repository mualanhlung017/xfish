import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('--engine',type=Path,required=True)
parser.add_argument('--old',type=Path,required=True)
parser.add_argument('--new',type=Path,required=True)
parser.add_argument('--verifier',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
spec=importlib.util.spec_from_file_location('loader_verifier',args.verifier)
module=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=module
spec.loader.exec_module(module)
root=args.output.resolve().parent/'loader-artifacts'
root.mkdir(exist_ok=True)
session=module.EngineSession('loader',args.engine.resolve(),args.old.resolve(),16,60)
records=[]
expected={}
try:
    for label,net in [('old',args.old),('new',args.new),('old',args.old),('new',args.new),('old',args.old)]:
        session.send(f'setoption name EvalFile value {net.resolve()}')
        session.ready()
        evaluation=session.evaluate('position startpos')
        if label in expected:
            assert evaluation==expected[label]
        else: expected[label]=evaluation
        records.append({'switch':label,'evaluation':evaluation})
    for label,net in [('old',args.old),('new',args.new)]:
        session.send(f'setoption name EvalFile value {net.resolve()}')
        session.ready()
        export=root/f'{label}-export.nnue'
        session.send(f'export_net {export}')
        result=session.ready()
        assert any('saved successfully' in line for line in result),result
        session.send(f'setoption name EvalFile value {export}')
        session.ready()
        evaluation=session.evaluate('position startpos')
        assert evaluation==expected[label]
        # Force real accumulator updates and return to the same cold root.
        result=session.search('position startpos',8)
        assert result['bestmove'] not in ('0000','(none)')
        assert session.evaluate('position startpos')==expected[label]
        records.append({'roundtrip':label,'evaluation':evaluation,'search':result,'export_size':export.stat().st_size})
finally: session.close()

exports={label:(root/f'{label}-export.nnue').read_bytes() for label in ('old','new')}
bad={
 'empty':b'',
 'compressed-truncated':args.new.read_bytes()[:1024],
 'compressed-missing-end':args.new.read_bytes()[:-1],
 'legacy-truncated':exports['old'][:128],
 'v17-truncated':exports['new'][:128],
 'v17-extra-byte':exports['new']+b'\x01',
 'legacy-extra-byte':exports['old']+b'\x01',
 'wrong-version':b'BAD!'+exports['new'][4:],
 'wrong-architecture-hash':exports['new'][:4]+b'BAD!'+exports['new'][8:],
 'oversized-description':exports['new'][:8]+b'\xff\xff\xff\xff'+exports['new'][12:128],
}
bad_results=[]
for label,data in bad.items():
    path=root/f'{label}.nnue'
    path.write_bytes(data)
    commands=f'uci\nsetoption name EvalFile value {path}\nisready\nposition startpos\neval\nquit\n'
    result=subprocess.run([str(args.engine.resolve())],input=commands,text=True,encoding='utf-8',errors='replace',capture_output=True,timeout=30)
    assert result.returncode==1 and 'not loaded successfully' in result.stdout,(label,result.returncode,result.stdout[-1000:],result.stderr)
    bad_results.append({'case':label,'exit_code':result.returncode,'clean_rejection':True})
report={'passed':True,'switches':records,'malformed':bad_results,'old_eval':expected['old'],'new_eval':expected['new']}
args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'passed':True,'switches':5,'roundtrips':2,'malformed_rejected':len(bad_results),'new_eval':expected['new']},indent=2))
