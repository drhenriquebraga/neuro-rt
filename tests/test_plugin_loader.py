import hashlib
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

# Loader contracts run before scientific packages exist on a clean CI runner.
TEMP_ROOT = Path(__file__).resolve().parents[1] / '.research' / 'test_tmp'
TEMP_ROOT.mkdir(parents=True, exist_ok=True)


class PluginLoaderTests(unittest.TestCase):
    def fixture(self, base):
        root = base / 'Plugins/NEURO RT'
        code = root / 'versions/0.3.0'
        (code / 'integration').mkdir(parents=True)
        manifest = {'schema': 'neuro-rt/plugin-manifest/1', 'id': 'neuro-rt',
                    'version': '0.3.0', 'host_contract': 'local-suite/plugins/1',
                    'host_min_version': '8.10', 'entrypoint': '/neuro/',
                    'adapter': 'integration/adapter.py:montar'}
        (code / 'module.json').write_text(json.dumps(manifest), encoding='utf-8')
        (code / 'integration/adapter.py').write_text(
            'def montar(app, module_root, host_services=None):\n'
            '    app.calls += 1\n'
            '    return {"services": host_services, "root": str(module_root)}\n')
        files = [{'path': 'code/' + path.relative_to(code).as_posix(),
                  'size': path.stat().st_size,
                  'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                 for path in (code / 'module.json', code / 'integration/adapter.py')]
        (code / 'release-manifest.json').write_text(json.dumps({
            'schema': 'neuro-rt/release-package/1', 'plugin_id': 'neuro-rt',
            'version': '0.3.0', 'files': files}), encoding='utf-8')
        (root / 'installation.json').write_text(json.dumps({
            'schema': 'neuro-rt/installation/1', 'state': 'ready',
            'active_version': '0.3.0'}), encoding='utf-8')
        return root, code

    def test_absent_and_malformed_plugin_do_not_break_host(self):
        from integration.plugin_loader import discover_plugin
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            root = Path(tmp)
            self.assertEqual(discover_plugin(root)['state'], 'absent')
            plugin = root / 'Plugins/NEURO RT'
            plugin.mkdir(parents=True)
            (plugin / 'installation.json').write_text('{broken')
            self.assertEqual(discover_plugin(root)['state'], 'failed')

    def test_compatibility_and_code_integrity_before_mount(self):
        from integration.plugin_loader import discover_plugin
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            base = Path(tmp)
            _, code = self.fixture(base)
            old = {'contract': 'local-suite/plugins/1', 'version': '8.9'}
            self.assertEqual(discover_plugin(base, host_info=old)['state'], 'incompatible')
            host = {'contract': 'local-suite/plugins/1', 'version': '8.10'}
            self.assertEqual(discover_plugin(base, host_info=host)['state'], 'ready')
            (code / 'integration/adapter.py').write_text('raise RuntimeError("corrupt")')
            self.assertEqual(discover_plugin(base, host_info=host)['state'], 'failed')

    def test_uninventoried_bytecode_or_other_payload_never_reaches_mount(self):
        from integration.plugin_loader import discover_plugin
        for relative in ('integration/__pycache__/adapter.cpython-310.pyc',
                         'integration/adapter.pyc','integration/extra.pyd','web/extra.js'):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
                base = Path(tmp)
                _, code = self.fixture(base)
                path = code / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'unverified-payload')
                status = discover_plugin(base, host_info={
                    'contract':'local-suite/plugins/1','version':'8.10'})
                self.assertEqual(status['state'], 'failed')

    def test_redirected_empty_cache_directory_is_refused_before_import(self):
        from integration.plugin_loader import discover_plugin
        from unittest.mock import patch
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            base = Path(tmp)
            _, code = self.fixture(base)
            cache = code / 'integration/redirected-cache'
            cache.mkdir()
            original = Path.lstat
            def stat_with_reparse(path, *args, **kwargs):
                info = original(path, *args, **kwargs)
                if path == cache:
                    return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400)
                return info
            with patch.object(Path, 'lstat', stat_with_reparse):
                status = discover_plugin(base, host_info={
                    'contract':'local-suite/plugins/1','version':'8.10'})
            self.assertEqual(status['state'], 'failed')
            real_exists = Path.exists
            def exists_except_alias(path):
                return False if path == cache else real_exists(path)
            with patch.object(Path, 'lstat', stat_with_reparse), patch.object(Path, 'exists', exists_except_alias):
                status = discover_plugin(base, host_info={
                    'contract':'local-suite/plugins/1','version':'8.10'})
            self.assertEqual(status['state'], 'failed', 'A broken Windows junction must still be inspected with lstat')

    def test_mount_is_idempotent_and_carries_host_services(self):
        from integration.plugin_loader import discover_plugin, mount_plugin
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            base = Path(tmp)
            self.fixture(base)
            installation = discover_plugin(base, host_info={
                'contract': 'local-suite/plugins/1', 'version': '8.10'})
            app = SimpleNamespace(state=SimpleNamespace(), calls=0)
            services = object()
            first = mount_plugin(app, installation, services)
            second = mount_plugin(app, installation, services)
            self.assertIs(first, second)
            self.assertEqual(app.calls, 1)
            self.assertIs(first['service']['services'], services)

    def test_inventory_must_cover_adapter_and_never_escape(self):
        from integration.plugin_loader import discover_plugin
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            base = Path(tmp)
            _, code = self.fixture(base)
            inventory = code / 'release-manifest.json'
            values = json.loads(inventory.read_text())
            values['files'][1]['path'] = 'code/../escape.py'
            inventory.write_text(json.dumps(values))
            status = discover_plugin(base, host_info={
                'contract': 'local-suite/plugins/1', 'version': '8.10'})
            self.assertEqual(status['state'], 'failed')

    def test_concurrent_mount_keeps_one_instance(self):
        from integration.plugin_loader import discover_plugin, mount_plugin
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            base = Path(tmp)
            _, code = self.fixture(base)
            adapter = code / 'integration/adapter.py'
            adapter.write_text('import time\ndef montar(app, module_root, host_services=None):\n'
                               '    time.sleep(.03)\n    app.calls += 1\n    return object()\n')
            inventory = code / 'release-manifest.json'
            data = json.loads(inventory.read_text())
            entry = data['files'][1]
            entry.update(size=adapter.stat().st_size, sha256=hashlib.sha256(adapter.read_bytes()).hexdigest())
            inventory.write_text(json.dumps(data))
            installation = discover_plugin(base, host_info={
                'contract': 'local-suite/plugins/1', 'version': '8.10'})
            app = SimpleNamespace(state=SimpleNamespace(), calls=0)
            with ThreadPoolExecutor(max_workers=4) as pool:
                receipts = list(pool.map(lambda _: mount_plugin(app, installation, object()), range(4)))
            self.assertEqual(app.calls, 1)
            self.assertTrue(all(r is receipts[0] for r in receipts))
