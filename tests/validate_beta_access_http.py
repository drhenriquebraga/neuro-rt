"""Real loopback HTTP gate on the unchanged portable Python; no httpx/PHI/models."""
import argparse
import hashlib
import http.client
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

def child(port, work):
    from unittest.mock import patch
    from types import SimpleNamespace
    from fastapi import FastAPI, HTTPException, Request
    import uvicorn
    from integration.radai_neuro import montar
    calls=[]
    service=SimpleNamespace(token='synthetic-310-only',close=lambda:None,
        studies=SimpleNamespace(catalog={'g':{'groups':['glioma']}},
            selection=lambda *a: calls.append('selection') or {'selected':True},
            submit=lambda *a: calls.append('submit') or {'submitted':True}),
        status=lambda:{'token':'synthetic-310-only','calls':list(calls),
                       'python':sys.version.split()[0],'interpreter':sys.executable,'pid':os.getpid()})
    settings=SimpleNamespace(data_dir=Path(work))
    app=FastAPI()
    for tool in ('nidus','glioma','metastasis','meningioma','anatomia'):
        app.add_api_route('/neuro/'+tool,lambda:{'tool':True})
    app.add_api_route('/api/nidus/tubos',lambda:{'manual':True},methods=['POST'])
    with patch('neuro_rt.service.Service',return_value=service),patch('neuro_rt.service.Settings',return_value=settings):
        montar(app,ROOT)
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,log_level='error',access_log=False))

    @app.post('/__test_shutdown')
    async def shutdown(request: Request):
        if request.headers.get('x-neuro-token') != service.token:
            raise HTTPException(403)
        server.should_exit = True

    server.run()

def run(python):
    base=ROOT/'.research/test_plugin_tmp';base.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='beta-http310-',dir=base) as tmp:
        work=Path(tmp)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        log=(work/'server.log').open('wb')
        origin='http://127.0.0.1:'+str(port)
        def request(path,body=None,protected=True,request_origin=origin):
            headers={'Origin':request_origin}
            if protected:headers['X-Neuro-Token']='synthetic-310-only'
            if body is not None:headers['Content-Type']='application/json'
            connection=http.client.HTTPConnection('127.0.0.1',port,timeout=20)
            try:
                connection.request('POST' if body is not None else 'GET',path,
                    json.dumps(body).encode() if body is not None else None,headers)
                response=connection.getresponse();raw=response.read()
                values=dict(response.getheaders())
                content=json.loads(raw) if 'application/json' in values.get('content-type','') else raw.decode('utf-8')
                return response.status,content,values
            finally:connection.close()
        def wait_until_ready(process):
            deadline=time.monotonic()+30
            while True:
                try:
                    status,content,_=request('/neuro/api/status')
                    assert status==200
                    return content['pid']
                except (OSError,http.client.HTTPException):
                    if process.poll() is not None or time.monotonic()>deadline:raise RuntimeError('Synthetic server did not start')
                    time.sleep(.1)
        def start():
            return subprocess.Popen([python,'-I','-B',str(Path(__file__).resolve()),'--child','--port',str(port),'--work',str(work)],
                stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0)
        def stop(process):
            if process.poll() is not None:
                return
            try:
                request('/__test_shutdown', {})
                process.wait(timeout=10)
            except (OSError, http.client.HTTPException, subprocess.TimeoutExpired):
                process.terminate()
                process.wait(timeout=10)
        process=start()
        try:
            pid=wait_until_ready(process)
            assert request('/neuro/glioma')[0]==303
            assert request('/neuro/api/selection',{'category':'glioma','tickets':[]})[0]==428
            policy=request('/neuro/api/consent')[1]['policy']
            payload=dict(accepted=True,version=policy['version'],digest=policy['digest'])
            assert request('/neuro/api/consent',payload,False)[0]==403
            assert request('/neuro/api/consent',payload)[0]==200
            assert request('/neuro/api/studies',{'studies':[{'model_ids':['g']}]})[0]==428
            for tool in ('nidus','glioma','metastasis','meningioma','anatomia'):
                assert request('/neuro/'+tool)[0]==303
                assert request('/neuro/testing/'+tool)[0]==200
                policy=request('/neuro/api/testing/'+tool)[1]['policy']
                payload=dict(accepted=True,version=policy['version'],digest=policy['digest'])
                assert request('/neuro/api/testing/'+tool,dict(payload,accepted=False))[0]==400
                assert request('/neuro/api/testing/'+tool,payload,request_origin='https://untrusted.example')[0]==403
                assert request('/neuro/'+tool)[0]==303
                status,_,headers=request('/neuro/api/testing/'+tool,payload)
                assert status==200 and 'set-cookie' not in headers, 'Consent must not depend on a browser cookie'
                status,_,headers=request('/neuro/testing/'+tool)
                assert status==303 and headers['location']=='/neuro/'+tool
                assert request('/neuro/'+tool)[0]==200
            assert request('/api/nidus/tubos',{})[0]==200
            assert request('/api/nidus/tubos',{},request_origin='https://untrusted.example')[0]==403
            assert request('/neuro/api/selection',{'category':'glioma','tickets':[]})[0]==200
            assert request('/neuro/api/studies',{'studies':[{'model_ids':['g']}]})[0]==202
            status = request('/neuro/api/status')[1]
            assert status['calls']==['selection','submit']
            assert Path(status['interpreter']).resolve()==Path(python).resolve()
            stop(process)
            process=start()
            assert wait_until_ready(process)!=pid
            assert request('/neuro/onboarding')[0]==303
            assert request('/neuro/testing/nidus')[0]==303
            assert request('/api/nidus/tubos',{})[0]==200
            assert request('/neuro/api/selection',{'category':'glioma','tickets':[]})[0]==200
            files=['integration/plugin_access.py','integration/testing_access.py','integration/radai_neuro.py','neuro_rt/plugin_consent.py']
            return {'schema':'neuro-rt/beta-http-validation/1','python':status['python'],
                'shared_interpreter':True,'first_use':True,'five_tool_acknowledgements':True,
                'protected_post':True,'persisted_after_process_restart':True,
                'no_clinical_data':True,'models_or_dicom_processed':False,
                'tool_pages_synthetic':True,'harness_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'httpx_installed_or_used':False,'sources':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}}
        finally:
            stop(process)
            log.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--child',action='store_true');parser.add_argument('--port',type=int);parser.add_argument('--work');parser.add_argument('--python',default=sys.executable);parser.add_argument('--output')
    args=parser.parse_args()
    if args.child:child(args.port,args.work)
    else:
        result=run(args.python)
        if args.output:Path(args.output).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(result,indent=2))
