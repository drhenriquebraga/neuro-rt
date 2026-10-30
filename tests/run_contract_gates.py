"""Run the existing CI suite list and save an auditable local result."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--extra',action='append',default=[])
    args=parser.parse_args()
    workflow=ROOT/'.github/workflows/verify.yml'
    match=re.search(r'\$suites = @\(([^)]*)\)',workflow.read_text(encoding='utf-8'))
    if match is None:raise ValueError('CI suite list is absent')
    suites=list(dict.fromkeys(re.findall(r"'([^']+)'",match.group(1))+args.extra))
    if any(not re.fullmatch('test_[a-z0-9_]+',name) for name in suites):raise ValueError('Invalid suite name')
    rows=[]
    for name in suites:
        started=time.monotonic()
        result=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromName(name))
        row={'suite':name,'tests':result.testsRun,'skipped':len(result.skipped),
             'failures':len(result.failures),'errors':len(result.errors),'seconds':round(time.monotonic()-started,3)}
        rows.append(row);print(json.dumps(row),flush=True)
        if not result.wasSuccessful():break
    receipt={'schema':'neuro-rt/contract-gates/1','python':sys.version.split()[0],
        'workflow_sha256':hashlib.sha256(workflow.read_bytes()).hexdigest(),
        'success':len(rows)==len(suites) and all(not (r['failures'] or r['errors']) for r in rows),
        'tests':sum(r['tests'] for r in rows),'skipped':sum(r['skipped'] for r in rows),'suites':rows}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    return 0 if receipt['success'] else 1

if __name__=='__main__':raise SystemExit(main())
