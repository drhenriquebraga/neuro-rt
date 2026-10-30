import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from neuro_rt import plugin_update as update
from test_plugin_install import fixture_package


class UpdateDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        base = Path(__file__).resolve().parents[1] / 'runtime/test-tmp'
        base.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.host = self.root / 'host'
        self.host.mkdir()
        for name in ('radai_panel.py','radai_ui.py','entrega.txt'):
            (self.host/name).write_text('synthetic')
        self.plugin = self.host/'Plugins/NEURO RT'
        self.events = []
        self.coordinator = update.UpdateCoordinator(self.host, host_version='8.10',
            hold=lambda value: self.events.append(('hold',value)), busy=lambda:False,
            cancel=lambda:None, restart=None, package=fixture_package(self.root))

    def test_missing_restart_is_pending_and_never_claims_install_failed(self):
        self.coordinator.request_plugin_update('neuro-rt','comecar')
        self.coordinator._worker.join(30)
        value = self.coordinator.status()
        self.assertEqual(value['state'],'installed_pending_restart')
        self.assertEqual(value['error_code'],'RESTART_UNAVAILABLE')
        state=json.loads((self.plugin/'installation.json').read_text())
        self.assertEqual(state['pending_version'],'1.0.0')
        self.assertIsNone(state['active_version'])
        self.assertEqual(self.events[-1],('hold',False))

    def test_configuration_reload_receipt_is_not_real_restart_confirmation(self):
        self.coordinator.prepare(self.coordinator.offline_package)
        self.coordinator.restart=lambda:{'agendada':True,'recarga':1}
        value=self.coordinator.finish_restart()
        self.assertEqual(value['state'],'installed_pending_restart')
        self.assertEqual(value['error_code'],'RESTART_NOT_CONFIRMED')
        state=json.loads((self.plugin/'installation.json').read_text())
        self.assertIsNone(state['active_version'])
        self.assertEqual(state['pending_version'],'1.0.0')

    def test_restart_acceptance_is_scheduled_not_mounted_success(self):
        self.coordinator.prepare(self.coordinator.offline_package)
        self.coordinator.restart=lambda:{'ok':True,'scheduled':True}
        value=self.coordinator.finish_restart()
        self.assertEqual(value['state'],'restarting')
        self.assertNotIn('mounted',value)

    def test_restart_status_is_durable_before_callback_can_close_process(self):
        self.coordinator.prepare(self.coordinator.offline_package)
        observed=[]
        def restart():
            value=json.loads((self.plugin/'update-status.json').read_text(encoding='utf-8'))
            observed.append(value['state'])
            return {'ok':True,'scheduled':True}
        self.coordinator.restart=restart
        self.coordinator.finish_restart()
        self.assertEqual(observed,['restarting'])

    def test_activation_is_busy_and_not_a_second_restart_action(self):
        self.coordinator.prepare(self.coordinator.offline_package)
        self.coordinator.restart=lambda:{'ok':True,'scheduled':True}
        original=update.install_state.activate_release
        observed=[]
        def activate(*args,**kwargs):
            value=self.coordinator.status()
            observed.append((value['state'],value['stage']))
            return original(*args,**kwargs)
        with patch.object(update.install_state,'activate_release',side_effect=activate):
            self.coordinator.finish_restart()
        self.assertEqual(observed,[('activating','validating')])

    def test_worker_failure_has_safe_durable_stage_and_code(self):
        with patch.object(self.coordinator,'prepare',side_effect=PermissionError(13,'Patient Alice / private path')):
            self.coordinator.request_plugin_update('neuro-rt','comecar')
            self.coordinator._worker.join(30)
        value=self.coordinator.status()
        self.assertEqual(value['state'],'failed')
        self.assertEqual(value['error_code'],'PERMISSION_DENIED')
        self.assertTrue(value['error_stage'])
        self.assertNotIn('Alice',json.dumps(value))
        receipt=json.loads((self.plugin/'update-status.json').read_text(encoding='utf-8'))
        self.assertEqual(receipt['error_code'],'PERMISSION_DENIED')
        self.assertNotIn('private path',json.dumps(receipt))

    def test_status_exposes_only_current_transaction_progress_without_rehash(self):
        self.plugin.mkdir(parents=True,exist_ok=True)
        self.coordinator._transaction_id='current'
        self.coordinator._status={'state':'preparing','reason':''}
        (self.plugin/'install-status.json').write_text(json.dumps({'transaction_id':'current',
            'state':'installing','stage':'extracting','completed_files':15,'total_files':100,
            'processed_bytes':500,'total_unpacked_bytes':2000}),encoding='utf-8')
        with patch.object(update.install_state,'read_install_status',side_effect=AssertionError('Do not rehash packages during polling')):
            value=self.coordinator.status()
        self.assertEqual(value['stage'],'extracting')
        self.assertEqual(value['completed_files'],15)
        self.assertEqual(value['processed_bytes'],500)

    def test_foreign_installer_lock_never_leads_to_activation_or_restart(self):
        called=[]
        self.coordinator.restart=lambda:(called.append(True) or {'ok':True,'scheduled':True})
        self.plugin.mkdir(parents=True)
        with update.install_state._installation_lock(self.plugin) as acquired:
            self.assertTrue(acquired)
            with patch.object(update.install_state,'begin_install',return_value=update.install_state.InstallReceipt('foreign',None,(),False,True)):
                self.coordinator.request_plugin_update('neuro-rt','comecar')
                self.coordinator._worker.join(30)
        self.assertEqual(called,[])
        self.assertEqual(self.coordinator.status()['error_code'],'INSTALL_BUSY')

    def test_fresh_coordinator_resumes_actual_pending_version_without_latest_download(self):
        self.coordinator.prepare(self.coordinator.offline_package)
        resumed=update.UpdateCoordinator(self.host,host_version='8.11',hold=lambda _:None,
            busy=lambda:False,cancel=lambda:None,restart=lambda:{'ok':True,'scheduled':True})
        with patch.object(resumed.client,'check_plugin_release',side_effect=AssertionError('Pending payload must be reused')):
            resumed.request_plugin_update('neuro-rt','esperar')
            resumed._worker.join(30)
        self.assertEqual(resumed.status()['state'],'restarting')
        self.assertEqual(resumed.status()['version'],'1.0.0')

    def test_activation_failure_after_pointer_write_restores_pending_before_release(self):
        self.coordinator.prepare(self.coordinator.offline_package)
        before=(self.plugin/'installation.json').read_bytes()
        called=[]
        self.coordinator.restart=lambda:(called.append(True) or {'ok':True,'scheduled':True})
        original=update.install_state._status
        def fail_ready(*args,**kwargs):
            if len(args)>2 and args[2]=='ready':
                raise PermissionError(13,'Synthetic private path')
            return original(*args,**kwargs)
        with patch.object(update.install_state,'_status',side_effect=fail_ready):
            value=self.coordinator.finish_restart()
        self.assertEqual((self.plugin/'installation.json').read_bytes(),before)
        self.assertEqual(value['state'],'installed_pending_restart')
        self.assertEqual(called,[])


if __name__=='__main__':
    unittest.main()
