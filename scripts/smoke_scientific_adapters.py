"""Opt-in real full adapter inference on synthetic inputs; never clinical data."""
import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'tests'))
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'runtime/mplconfig'))
os.environ.setdefault('ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS','2')
from scientific_adapter_fixtures import context_for
from neuro_rt.adapter_registry import ADAPTER_FACTORIES
from neuro_rt.geometry_pipeline import verify_reference_geometry


def peak_memory_mb():
    class Counters(ctypes.Structure):
        _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD)]+[(x,ctypes.c_size_t) for x in
            ('PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage',
             'QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]
    c=Counters(); c.cb=ctypes.sizeof(c)
    current=ctypes.windll.kernel32.GetCurrentProcess
    current.restype=wintypes.HANDLE
    memory=ctypes.windll.psapi.GetProcessMemoryInfo
    memory.argtypes=[wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD]
    if not memory(current(),ctypes.byref(c),c.cb):raise ctypes.WinError()
    return c.PeakWorkingSetSize/1024**2


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--model',required=True)
    parser.add_argument('--output',required=True,type=Path); args=parser.parse_args()
    import numpy as np
    try:
        import torch
        torch.set_num_threads(2)
    except ImportError:pass
    args.output.mkdir(parents=True,exist_ok=False)
    ctx=context_for(args.output,args.model,ROOT/'models')
    adapter=ADAPTER_FACTORIES[ctx.model_spec['adapter_id']]()
    start=time.perf_counter()
    try:
        with patch('socket.socket.connect',side_effect=AssertionError('Inferencia deve permanecer offline')):
            prepared=adapter.prepare(ctx); raw=adapter.predict(prepared,ctx)
            result=adapter.normalize_result(raw,ctx)
        restored=list(Path(prepared.output_dir).glob('class_*.nii.gz'))
        valid=(len(restored)==len(raw.masks) and all(
            verify_reference_geometry(path,ctx.reference).valid for path in restored))
        if not valid:raise ValueError('Geometria final invalida')
        report={'model_id':args.model,'status':result.status,'geometry_valid':valid,
                'elapsed_seconds':time.perf_counter()-start,'peak_working_set_mb':peak_memory_mb(),
                'mask_count':len(result.masks),'restored_class_count':len(restored),'result':result.to_dict(),
                'validation_scope':'full published inference on synthetic data; not clinical validation'}
        (args.output/'evidence.json').write_text(json.dumps(report,indent=2),encoding='utf8')
        print(json.dumps({k:v for k,v in report.items() if k!='result'}),flush=True)
    except Exception as error:
        (args.output/'failure.json').write_text(json.dumps({'error':repr(error),'elapsed_seconds':time.perf_counter()-start}),encoding='utf8')
        raise


if __name__=='__main__':main()
