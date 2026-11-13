"""NIDUS and host editor integration through real APIs and synthetic oblique DICOM."""
import os
from pathlib import Path
import socket, subprocess, sys, tempfile, threading, time, unittest
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]

class InlineEditorHost(unittest.TestCase):
    def test_nidus_inline_new_roi_and_draft_return(self):
        host=Path(os.environ.get('NEURO_HOST_ROOT',''))
        if not (host/'app/radai_menu.py').is_file():self.skipTest('Host path required')
        sys.path[:0]=[str(ROOT),str(ROOT/'app'),str(host/'app'),str(host/'tests')]
        for component in (host/'_montagem/componentes').iterdir():
            if (component/'app').is_dir():sys.path.append(str(component/'app'))
        from fastapi import FastAPI
        import uvicorn,radai_nidus_screen as screen,radai_contour_edit_api as api,radai_thumbnail,radai_archive
        import radai_contour_edit as core
        from test_contour_edit import make_series
        from unittest.mock import patch
        with tempfile.TemporaryDirectory(prefix='nidus-inline-') as temp:
            folder=Path(temp);uid,files=make_series(folder,shape=(21,64,72))
            ticket=radai_thumbnail.bilhete(str(folder),uid)
            app=FastAPI();screen.montar(app);api.montar(app)
            @app.get('/fixture')
            def fixture():return {'ticket':ticket}
            sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            server=uvicorn.Server(uvicorn.Config(app,log_level='error',access_log=False));thread=threading.Thread(target=lambda:server.run(sockets=[sock]),daemon=True)
            with patch.object(radai_archive,'ler_acervo',return_value=[]):
                thread.start()
                try:
                    until=time.monotonic()+20
                    while not server.started and time.monotonic()<until:time.sleep(.05)
                    self.assertTrue(server.started)
                    env=dict(os.environ,NEURO_INLINE_URL=f'http://127.0.0.1:{port}',PYTHONDONTWRITEBYTECODE='1')
                    result=subprocess.run(['node',str(ROOT/'tests/nidus_inline_browser.cjs')],env=env,capture_output=True,text=True,encoding='utf8',errors='replace',timeout=180)
                    self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                finally:
                    server.should_exit=True;thread.join(timeout=10)
                    for key in list(core._SESSIONS):core.close_session(key)

if __name__=='__main__':unittest.main()
