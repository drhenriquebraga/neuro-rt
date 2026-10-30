"""Online delivery selects a small SETUP and never a runtime/model bundle."""
import io
import importlib.metadata
from contextlib import redirect_stdout
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from neuro_rt import install_state, plugin_update as update
from host_setup_fixtures import host_setup
from test_plugin_install import fixture_package


def release(version='1.0.2',size=1024,digest='a'*64):
    return {'id':23,'tag_name':'v'+version,'assets':[
        {'id':7,'name':'NEURO_RT_SETUP_v'+version+'.zip','size':size,
         'digest':'sha256:'+digest,
         'url':'https://api.github.com/repos/drhenriquebraga/neuro-rt/releases/assets/7'},
        {'id':8,'name':'NEURO_RT_SETUP_LATEST.zip','size':size,'digest':'sha256:'+'b'*64,
         'url':'https://api.github.com/repos/drhenriquebraga/neuro-rt/releases/assets/8'},
        {'id':9,'name':'NEURO_RT_OFFLINE_v'+version+'.zip','size':1_200_000_000,
         'digest':'sha256:'+'c'*64,'url':'https://api.github.com/repos/drhenriquebraga/neuro-rt/releases/assets/9'}]}


class SetupReleaseTests(unittest.TestCase):
    def test_selects_only_versioned_setup_without_external_inventory(self):
        client=update.ReleaseClient(fetch_json=lambda _:release(),host_version='8.11',
            fetch_manifest=lambda _:self.fail('No inventory asset may be fetched'))
        value=client.check_plugin_release('neuro-rt',None)
        self.assertEqual(value['state'],'available')
        self.assertEqual(value['name'],'NEURO_RT_SETUP_v1.0.2.zip')
        self.assertEqual(value['asset_id'],7)
        self.assertEqual(value['sha256'],'a'*64)
        self.assertEqual(value['package_kind'],'setup')

    def test_missing_setup_never_falls_back_to_offline_or_alias(self):
        raw=release();raw['assets']=raw['assets'][1:]
        value=update.ReleaseClient(fetch_json=lambda _:raw).check_plugin_release('neuro-rt',None)
        self.assertEqual(value['state'],'unavailable')

    def test_digest_size_and_owned_asset_endpoint_are_required(self):
        for field,value in [('digest',None),('size',1_200_000_000),('size',True),
                            ('url','https://api.github.com/repos/other/project/releases/assets/7')]:
            with self.subTest(field=field,value=value):
                raw=release();raw['assets'][0][field]=value
                result=update.ReleaseClient(fetch_json=lambda _:raw).check_plugin_release('neuro-rt',None)
                self.assertEqual(result['state'],'unavailable')

    def test_old_host_is_incompatible_without_downloading_components(self):
        client=update.ReleaseClient(fetch_json=lambda _:release(),host_version='8.10',
            fetch_manifest=lambda _:self.fail('No component download before consent'))
        self.assertEqual(client.check_plugin_release('neuro-rt',None)['state'],'incompatible')


class SetupMigrationTests(unittest.TestCase):
    def setUp(self):
        base=Path(__file__).resolve().parents[1]/'runtime/test-tmp';base.mkdir(parents=True,exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=base);self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.host=self.root/'suite';self.host.mkdir()
        for name in ('radai_panel.py','radai_ui.py','entrega.txt'):(self.host/name).write_text('synthetic')
        self.plugin=self.host/'Plugins/NEURO RT'

    def coordinator(self,client=None):
        return update.UpdateCoordinator(self.host,host_version='8.11',host_python=sys.executable,
            hold=lambda _:None,busy=lambda:False,cancel=lambda:None,
            restart=lambda:{'ok':True,'scheduled':True},client=client)

    def test_pending_old_bundle_gets_light_setup_preserving_existing_data(self):
        old=fixture_package(self.root,'1.0.1')
        install_state.begin_install(self.host,old,'old')
        (self.plugin/'data/keep.txt').write_text('keep')
        current=host_setup(self.root)
        data=Path(current['path']).read_bytes();calls=[]
        client=update.ReleaseClient(fetch_json=lambda url:(calls.append(url) or release(size=len(data),digest=current['sha256'])),host_version='8.11')
        coordinator=self.coordinator(client)
        with patch.object(update,'_open',return_value=io.BytesIO(data)), \
                patch.object(install_state,'validate_host_runtime',return_value=Path(sys.executable)):
            coordinator.request_plugin_update('neuro-rt','esperar')
            coordinator._worker.join(30)
        self.assertFalse(coordinator._worker.is_alive())
        self.assertEqual(coordinator.status()['state'],'restarting')
        self.assertEqual(coordinator.status()['version'],'1.0.2')
        state=json.loads((self.plugin/'installation.json').read_text())
        self.assertEqual(state['execution_mode'],'host')
        self.assertIsNone(state['runtime'])
        self.assertEqual((self.plugin/'data/keep.txt').read_text(),'keep')
        self.assertEqual(len(calls),1)

    def test_pending_host_setup_resumes_without_any_download(self):
        current=host_setup(self.root)
        with patch.object(install_state,'validate_host_runtime',return_value=Path(sys.executable)):
            install_state.begin_install(self.host,current,'new',host_python=sys.executable)
            coordinator=self.coordinator()
            with patch.object(coordinator.client,'check_plugin_release',side_effect=AssertionError('No redownload')):
                coordinator.request_plugin_update('neuro-rt','esperar');coordinator._worker.join(30)
        self.assertEqual(coordinator.status()['state'],'restarting')
        self.assertEqual(coordinator.status()['version'],'1.0.2')

    def test_remote_descriptor_cannot_install_a_renamed_legacy_bundle(self):
        coordinator=self.coordinator()
        coordinator._selected={'package_kind':'setup'}
        with self.assertRaises(ValueError):coordinator.prepare(fixture_package(self.root))
        self.assertFalse((self.plugin/'installation.json').exists())

    def test_selected_release_version_must_equal_authenticated_setup_version(self):
        coordinator=self.coordinator()
        coordinator._selected={'package_kind':'setup','version':'9.9.9'}
        with patch.object(install_state,'begin_install',side_effect=AssertionError('Must reject before installation')):
            with self.assertRaises(ValueError):coordinator.prepare(host_setup(self.root))
        self.assertFalse((self.plugin/'installation.json').exists())

    def test_missing_base_dependency_is_reported_without_installing_packages(self):
        coordinator=self.coordinator();coordinator.offline_package=host_setup(self.root)
        with patch('importlib.metadata.version',side_effect=importlib.metadata.PackageNotFoundError('numpy')):
            coordinator.request_plugin_update('neuro-rt','comecar');coordinator._worker.join(30)
        self.assertEqual(coordinator.status()['state'],'failed')
        self.assertEqual(coordinator.status()['error_code'],'HOST_INCOMPATIBLE')
        self.assertFalse((self.plugin/'installation.json').exists())
        self.assertFalse((self.plugin/'runtimes').exists())

    def test_online_cli_pins_selected_version_before_preparing(self):
        setup=host_setup(self.root)
        client=SimpleNamespace(check_plugin_release=lambda *_:{'state':'available','version':'9.9.9'},
                               download=lambda *_:setup)
        with patch.object(update,'ReleaseClient',return_value=client), \
                patch('neuro_rt.plugin_consent.accepted',return_value=True), \
                patch.object(install_state,'begin_install',side_effect=AssertionError('Must not install mismatched version')), \
                redirect_stdout(io.StringIO()):
            result=update.main(['--suite-root',str(self.host),'--host-version','8.11'])
        self.assertEqual(result,1)
