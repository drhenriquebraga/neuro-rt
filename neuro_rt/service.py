import json
import os
import secrets
import subprocess
import sys
import threading
import time
import uuid
import re
from pathlib import Path

from . import __version__
from .catalog import get_model, model_status, validate_model_folder, requires_brain, BRAIN
from .contracts import validate_request


class Settings:
    def __init__(self, root):
        self.root = Path(root).resolve()
        config = self.root / 'neuro_rt.local.json'
        values = json.loads(config.read_text(encoding='utf-8')) if config.is_file() else {}
        def path(key, default):
            value = Path(values.get(key, default))
            return (self.root / value).resolve() if not value.is_absolute() else value.resolve()
        default_python = ('python/python.exe' if (self.root / 'python/python.exe').is_file()
                          else '.venv/Scripts/python.exe' if os.name == 'nt' else '.venv/bin/python')
        self.python = str(path('worker_python', default_python))
        if not Path(self.python).is_file() and 'worker_python' not in values:
            self.python = sys.executable
        self.models_dir = path('models_dir', 'models')
        self.data_dir = path('data_dir', 'runtime')
        self.host_app = path('host_app', 'host-app')
        self.host_python = str(path('host_python', 'host-python.exe'))
        self.processing_preference=values.get('processing_preference','auto')

    @property
    def export_available(self):
        return (self.host_app / 'engine.py').is_file() and Path(self.host_python).is_file()


class Service:
    def __init__(self, settings):
        self.settings = settings
        self.token = secrets.token_urlsafe(32)
        self._lock = threading.RLock()
        self._jobs = {}
        self._process = None
        self._thread = None
        self._closed = False
        self._demos = {}
        self._load_demos()

    def _load_demos(self):
        cache = self.settings.data_dir / 'demos.json'
        if not cache.is_file():
            return
        try:
            values = json.loads(cache.read_text(encoding='utf-8'))
            if values.get('schema') != 'neuro-rt/demos/1':
                return
            for item in values.get('demos', []):
                try:
                    self._load_demo_item(item)
                except (OSError, ValueError, KeyError, TypeError):
                    continue
        except (OSError, ValueError, KeyError, TypeError):
            return

    def _load_demo_item(self, item):
        job_id = item.get('job_id', '')
        if not re.fullmatch(r'[0-9a-f]{32}', job_id):
            return
        get_model(item['model'])
        job_dir = self.settings.data_dir / 'jobs' / job_id
        result = json.loads((job_dir / 'manifest.json').read_text(encoding='utf-8'))
        if (result.get('schema') != 'neuro-rt/result/1' or
            result.get('model_id') != item['model'] or
            result.get('status') not in ('completed', 'empty') or
            result.get('approval_status') != 'UNAPPROVED'):
            return
        public = {k: result[k] for k in ('model_id', 'backend_version', 'status', 'masks', 'approval_status')}
        if 'visualization' in result:
            public['visualization'] = result['visualization']
        self._jobs[job_id] = {'id': job_id, 'model': item['model'],
            'status': result['status'], 'result': public, 'demo': item,
            'message': 'Demonstração pública em cache; sugestão não aprovada.',
            'output_dir': str(job_dir), 'created_at': 0}
        self._demos[item['model']] = job_id

    def demo(self, model):
        get_model(model)
        if model not in self._demos:
            raise KeyError('Demo ainda não preparada.')
        return self.job(self._demos[model])

    def status(self):
        with self._lock:
            jobs = [dict(job) for job in self._jobs.values()]
        return {'module': 'neuro-rt', 'version': __version__, 'token': self.token,
                'export_available': self.settings.export_available,
                'processing_preference':self.settings.processing_preference,
                'shared_config_pending':True,
                'demos': [self._jobs[job_id]['demo'] for job_id in self._demos.values()],
                'models': model_status(self.settings.models_dir), 'jobs': jobs[-20:]}

    def preflight(self, request):
        model = get_model(request['model'])
        folder = self.settings.models_dir / model['id']
        validate_model_folder(folder, model)
        if requires_brain(folder):
            validate_model_folder(self.settings.models_dir / BRAIN['id'], BRAIN)
        if not Path(request['input_path']).exists():
            raise ValueError('Caminho da RM não encontrado.')
        if request['export_rtstruct']:
            if not Path(request['input_path']).is_dir():
                raise ValueError('RTSTRUCT requer a série DICOM MR original, não somente NIfTI.')
            if not self.settings.export_available:
                raise ValueError('Configure o Python e o gravador do Local Suite para exportar RTSTRUCT.')

    def submit(self, request):
        request = validate_request(request)
        self.preflight(request)
        with self._lock:
            if self._closed:
                raise RuntimeError('Serviço encerrado.')
            if any(job['status'] in ('running', 'visualizing', 'exporting') for job in self._jobs.values()):
                raise RuntimeError('Uma segmentação já está em execução; aguarde terminar.')
            job_id = uuid.uuid4().hex
            job_dir = self.settings.data_dir / 'jobs' / job_id
            job_dir.mkdir(parents=True)
            (job_dir / 'request.json').write_text(json.dumps(request), encoding='utf-8')
            job = {'id': job_id, 'model': request['model'], 'status': 'running',
                   'message': 'Conferindo a RM e executando o motor local.', 'created_at': time.time()}
            self._jobs[job_id] = job
            self._thread = threading.Thread(target=self._run, args=(request, job_dir, job_id), daemon=True)
            self._thread.start()
            return dict(job)

    def worker_command(self, request, job_dir):
        return [self.settings.python, '-u', '-m', 'neuro_rt.worker',
                '--request', str(job_dir / 'request.json'), '--job-dir', str(job_dir),
                '--models-dir', str(self.settings.models_dir)]

    def _execute(self, command, job_dir, logfile, cwd):
        env = dict(os.environ)
        env.update({'OMP_NUM_THREADS': '2', 'OPENBLAS_NUM_THREADS': '2', 'MKL_NUM_THREADS': '2',
                    'PYTHONUTF8': '1', 'ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS': '2',
                    'RADAI_TMP': str(job_dir / 'temp'), 'TEMP': str(job_dir / 'temp'),
                    'TMP': str(job_dir / 'temp')})
        (job_dir / 'temp').mkdir(exist_ok=True)
        flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        with logfile.open('wb') as log:
            with self._lock:
                if self._closed:
                    raise RuntimeError('Serviço encerrado.')
                process = subprocess.Popen(command, cwd=cwd, env=env, stdout=log,
                                           stderr=subprocess.STDOUT, creationflags=flags)
                self._process = process
            code = process.wait()
            with self._lock:
                self._process = None
            if code:
                raise RuntimeError('O subprocesso terminou com erro.')

    def _update(self, job_id, **values):
        with self._lock:
            self._jobs[job_id].update(values)

    def _run(self, request, job_dir, job_id):
        try:
            self._execute(self.worker_command(request, job_dir), job_dir,
                          job_dir / 'worker.log', self.settings.root)
            result = json.loads((job_dir / 'manifest.json').read_text(encoding='utf-8'))
            if result.get('schema') != 'neuro-rt/result/1':
                raise ValueError('Contrato de resultado inválido.')
            if self.settings.export_available:
                self._update(job_id,status='visualizing',message='Montando cortes e reconstruções.')
                self._execute([self.settings.host_python,str(self.settings.root/'neuro_rt/build_views.py'),
                    '--job-dir',str(job_dir),'--host-app',str(self.settings.host_app)],job_dir,
                    job_dir/'views.log',self.settings.host_app)
                result=json.loads((job_dir/'manifest.json').read_text(encoding='utf-8'))
            if request['export_rtstruct'] and result['status'] != 'empty':
                self._update(job_id, status='exporting', message='Gravando pelo motor do Local Suite.')
                self._execute([self.settings.host_python, str(self.settings.root / 'neuro_rt' / 'export.py'),
                               '--job-dir', str(job_dir), '--host-app', str(self.settings.host_app)],
                              job_dir, job_dir / 'export.log', self.settings.host_app)
                result = json.loads((job_dir / 'manifest.json').read_text(encoding='utf-8'))
            public = {k: result[k] for k in ('model_id', 'backend_version', 'status', 'masks', 'approval_status')}
            if 'rtstruct' in result:
                public['rtstruct'] = result['rtstruct']
            if 'visualization' in result:public['visualization']=result['visualization']
            self._update(job_id, status=result['status'], result=public,
                         message=('Nenhum voxel tumoral previsto; nenhuma ROI foi gravada.'
                                  if result['status'] == 'empty' else 'Resultado pronto para revisão.'),
                         output_dir=str(job_dir))
        except Exception:
            self._update(job_id, status='failed', message='Processamento falhou. Consulte o log privado na pasta do resultado.',
                         output_dir=str(job_dir))

    def job(self, job_id):
        with self._lock:
            if job_id not in self._jobs:
                raise KeyError('Job não encontrado.')
            return dict(self._jobs[job_id])

    def artifact(self, job_id, name):
        if name not in ('manifest.json', 'Tumor.nii.gz', 'RS_NeuroRT.dcm'):
            raise ValueError('Artefato não permitido.')
        self.job(job_id)
        job_dir = self.settings.data_dir / 'jobs' / job_id
        path = job_dir / 'masks' / name if name.endswith('.nii.gz') else job_dir / name
        if not path.is_file():
            raise FileNotFoundError('Artefato não encontrado.')
        return path

    def view_file(self,job_id,name):
        self.job(job_id)
        if not re.fullmatch(r'(?:view\.json|renderer\.js|(?:Tumor|Brain)\.stl|(?:axial|coronal|sagittal)_\d{3}\.png)',name):
            raise ValueError('Arquivo de visualização não permitido.')
        path=self.settings.data_dir/'jobs'/job_id/'views'/name
        if not path.is_file():raise FileNotFoundError('Visualização não encontrada.')
        return path

    def close(self):
        with self._lock:
            self._closed = True
            process, thread = self._process, self._thread
            if process and process.poll() is None:
                process.terminate()
        if thread:
            thread.join(timeout=5)
