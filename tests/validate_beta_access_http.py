"""Real loopback HTTP gate on the unchanged portable Python; no httpx/PHI/models."""
import argparse
import hashlib
import http.client
import json
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
    from fastapi import FastAPI
    import uvicorn
    from integration.radai_neuro import montar
    calls=[]
    service=SimpleNamespace(token='synthetic-310-only',close=lambda:None,
        studies=SimpleNamespace(catalog={'g':{'groups':['glioma']}},
            selection=lambda *a: calls.append('selection') or {'selected':True},
            submit=lambda *a: calls.append('submit') or {'submitted':True}),
        status=lambda:{'token':'synthetic-310-only','calls':list(calls),
                       'python':sys.version.split()[0],'interpreter':sys.executable})
    settings=SimpleNamespace(data_dir=Path(work))
    app=FastAPI()
    for tool in ('nidus','glioma','metastasis','meningioma','anatomia'):
        app.add_api_route('/neuro/'+tool,lambda:{'tool':True})
    app.add_api_route('/api/nidus/tubos',lambda:{'manual':True},methods=['POST'])
    with patch('neuro_rt.service.Service',return_value=service),patch('neuro_rt.service.Settings',return_value=settings):
        montar(app,ROOT)
    uvicorn.run(app,host='127.0.0.1',port=port,log_level='error',access_log=False)

def run(python):
    base=ROOT/'.research/test_plugin_tmp';base.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='beta-http310-',dir=base) as tmp:
        work=Path(tmp)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        log=(work/'server.log').open('wb')
        process=subprocess.Popen([python,'-I','-B',str(Path(__file__).resolve()),'--child','--port',str(port),'--work',str(work)],stdout=log,stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0)
        cookies={}
        origin='http://127.0.0.1:'+str(port)
        def request(path,body=None,protected=True):
            headers={'Origin':origin}
            if protected:headers['X-Neuro-Token']='synthetic-310-only'
            if cookies:headers['Cookie']='; '.join(k+'='+v for k,v in cookies.items())
            if body is not None:headers['Content-Type']='application/json'
            connection=http.client.HTTPConnection('127.0.0.1',port,timeout=20)
            try:
                connection.request('POST' if body is not None else 'GET',path,
                    json.dumps(body).encode() if body is not None else None,headers)
                response=connection.getresponse();raw=response.read()
                values=dict(response.getheaders())
                for key,value in response.getheaders():
                    if key.lower()=='set-cookie':
                        name,content=value.split(';',1)[0].split('=',1);cookies[name]=content
                content=json.loads(raw) if 'application/json' in values.get('content-type','') else raw.decode('utf-8')
                return response.status,content,values
            finally:connection.close()
        try:
            deadline=time.monotonic()+30
            while True:
                try:
                    assert request('/neuro/api/status')[0]==200;break
                except (OSError,http.client.HTTPException):
                    if process.poll() is not None or time.monotonic()>deadline:raise RuntimeError('Synthetic server did not start')
                    time.sleep(.1)
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
                status,_,headers=request('/neuro/api/testing/'+tool,payload)
                assert status==200 and 'HttpOnly' in headers['set-cookie']
                assert request('/neuro/'+tool)[0]==200
            assert request('/api/nidus/tubos',{})[0]==200
            assert request('/neuro/api/selection',{'category':'glioma','tickets':[]})[0]==200
            assert request('/neuro/api/studies',{'studies':[{'model_ids':['g']}]})[0]==202
            status = request('/neuro/api/status')[1]
            assert status['calls']==['selection','submit']
            assert Path(status['interpreter']).resolve()==Path(python).resolve()
            files=['integration/plugin_access.py','integration/testing_access.py','integration/radai_neuro.py','neuro_rt/plugin_consent.py']
            return {'schema':'neuro-rt/beta-http-validation/1','python':status['python'],
                'shared_interpreter':True,'first_use':True,'five_tool_acknowledgements':True,
                'protected_post':True,'no_clinical_data':True,'models_or_dicom_processed':False,
                'tool_pages_synthetic':True,'harness_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'httpx_installed_or_used':False,'sources':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}}
        finally:
            process.terminate()
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=10)
            log.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--child',action='store_true');parser.add_argument('--port',type=int);parser.add_argument('--work');parser.add_argument('--python',default=sys.executable);parser.add_argument('--output')
    args=parser.parse_args()
    if args.child:child(args.port,args.work)
    else:
        result=run(args.python)
        if args.output:Path(args.output).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(result,indent=2))
