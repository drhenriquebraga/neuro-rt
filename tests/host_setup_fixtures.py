"""Small invented host-shared SETUPs, with no Python, libraries or weights."""
import hashlib
import json
from pathlib import Path
import zipfile


def host_setup(root, version='1.0.2', mutate=None):
    module={'schema':'neuro-rt/plugin-manifest/1','id':'neuro-rt','version':version,
            'host_contract':'local-suite/plugins/1','host_min_version':'8.11',
            'entrypoint':'/neuro/','adapter':'integration/radai_neuro.py:montar',
            'catalog':'catalog/models.json','runtimes':{},'artifacts':[],
            'execution_mode':'host','runtime':'host-shared','enabled_tools':['nidus'],
            'python':'>=3.10'}
    candidate={'id':'future-model','catalog_state':'candidate','groups':['glioma'],
               'license':{'code':'MIT','weights':'MIT','sources':['https://example.org/license']},
               'channels':[{'role':'T1c'}],'classes':[]}
    files={'code/module.json':json.dumps(module).encode(),
           'code/catalog/models.json':json.dumps({'schema':'neuro-rt/catalog/1','models':[candidate]}).encode(),
           'code/integration/radai_neuro.py':b'def montar(): pass\n',
           'code/licenses/MIT.txt':b'Synthetic MIT license fixture'}
    manifest={'schema':'neuro-rt/release-package/1','plugin_id':'neuro-rt','version':version,
              'host_min_version':'8.11','python':'>=3.10','execution_mode':'host',
              'runtime':None,'runtimes':[],'models':[],'code_license_paths':['licenses/MIT.txt']}
    if mutate:
        mutate(manifest,files)
    manifest['files']=[{'path':name,'size':len(value),'sha256':hashlib.sha256(value).hexdigest()}
                       for name,value in files.items()]
    target=Path(root)/('NEURO_RT_SETUP_v'+version+'.zip')
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('release-manifest.json',json.dumps(manifest))
        for name,value in files.items():archive.writestr(name,value)
    return {'path':str(target),'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
