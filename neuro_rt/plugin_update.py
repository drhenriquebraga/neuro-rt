"""Standard-library release lookup and staged update; no payload code is executed."""
from dataclasses import asdict
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile

from . import install_state
from .plugin_manifest import _numeric_version

REPOSITORY = 'drhenriquebraga/neuro-rt'
MAX_SETUP_SIZE = 3 * 1024 * 1024
MIN_SETUP_HOST = '8.11'


class ReleaseUnavailable(ValueError):
    pass


def python_compatible(requirement, version=None):
    version = tuple(version or sys.version_info[:2])
    minimum = re.search(r'>=(\d+)\.(\d+)', requirement or '')
    maximum = re.search(r'<(\d+)\.(\d+)', requirement or '')
    return ((not minimum or version >= tuple(map(int, minimum.groups())))
            and (not maximum or version < tuple(map(int, maximum.groups()))))


class _HTTPSRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlsplit(newurl).scheme != 'https':
            raise ReleaseUnavailable('Redirecionamento sem HTTPS recusado.')
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        # GitHub asset redirects lead to storage hosts; credentials stay at api.github.com.
        if urllib.parse.urlsplit(newurl).netloc != urllib.parse.urlsplit(req.full_url).netloc:
            redirected.remove_header('Authorization')
        return redirected


def _open(url, *, binary=False):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname != 'api.github.com' or parsed.port not in (None, 443):
        raise ReleaseUnavailable('Origem de release não autorizada.')
    headers = {'Accept': 'application/octet-stream' if binary else 'application/vnd.github+json',
               'User-Agent': 'Local-Suite-NeuroRT', 'X-GitHub-Api-Version': '2022-11-28'}
    token = os.environ.get('GH_TOKEN')
    if token:
        headers['Authorization'] = 'Bearer ' + token
    try:
        return urllib.request.build_opener(_HTTPSRedirect()).open(
            urllib.request.Request(url, headers=headers), timeout=30)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            raise ReleaseUnavailable('GitHub 404: repositório privado sem acesso ou release ainda não publicada.') from None
        raise ReleaseUnavailable('GitHub indisponível (HTTP %s).' % error.code) from None
    except (OSError, urllib.error.URLError):
        raise ReleaseUnavailable('Não foi possível consultar a release. A versão instalada continua disponível.') from None


def _fetch_json(url):
    with _open(url) as stream:
        raw = stream.read(2 * 1024 * 1024 + 1)
    if len(raw) > 2 * 1024 * 1024:
        raise ReleaseUnavailable('Metadados de release excedem o limite.')
    return json.loads(raw)


def _fetch_asset_json(url):
    with _open(url, binary=True) as stream:
        raw = stream.read(install_state.MAX_MANIFEST + 1)
    if len(raw) > install_state.MAX_MANIFEST:
        raise ReleaseUnavailable('Manifesto externo excede o limite.')
    return json.loads(raw)


class ReleaseClient:
    def __init__(self, *, fetch_json=None, fetch_manifest=None, host_version=None, ttl=60):
        self._fetch = fetch_json or _fetch_json
        self._fetch_manifest = fetch_manifest or _fetch_asset_json
        self.host_version = host_version
        self._lock = threading.Lock()
        self._cached = None
        self._expires = 0
        self.ttl = ttl

    def refresh_plugin_release(self, plugin_id, installed_version):
        with self._lock:
            self._cached = None
            self._expires = 0
        return self.check_plugin_release(plugin_id, installed_version)

    def check_plugin_release(self, plugin_id, installed_version):
        if plugin_id != 'neuro-rt':
            raise ValueError('Plugin não autorizado.')
        with self._lock:
            if self._cached is None or time.monotonic() >= self._expires:
                try:
                    raw = self._fetch('https://api.github.com/repos/' + REPOSITORY + '/releases/latest')
                    version = raw['tag_name'].removeprefix('v')
                    _numeric_version(version)
                    if raw.get('draft') or raw.get('prerelease'):
                        raise ReleaseUnavailable('Release ainda não publicada como estável.')
                    name = 'NEURO_RT_SETUP_v' + version + '.zip'
                    assets = [a for a in raw['assets'] if a.get('name') == name]
                    if len(assets) != 1:
                        raise ReleaseUnavailable('Instalador versionado ausente na release.')
                    asset = assets[0]
                    digest = asset.get('digest', '')
                    if not isinstance(digest, str) or not re.fullmatch(r'sha256:[0-9a-f]{64}', digest):
                        raise ReleaseUnavailable('Asset sem SHA256 externo publicado; instalação indisponível.')
                    if (type(asset.get('size')) is not int or not 0 < asset['size'] <= MAX_SETUP_SIZE
                            or type(asset.get('id')) is not int or asset['id'] <= 0
                            or asset.get('url') != 'https://api.github.com/repos/' + REPOSITORY
                                + '/releases/assets/' + str(asset['id'])):
                        raise ReleaseUnavailable('Identidade ou tamanho do instalador inválido.')
                    self._cached = {'state': 'available', 'version': version,
                        'release_id': raw.get('id'), 'asset_id': asset['id'], 'name': name,
                        'url': asset['url'], 'sha256': digest[7:], 'size': asset['size'],
                        'package_kind': 'setup', 'reason': ''}
                    # Only release metadata is read before consent. The authenticated
                    # SETUP supplies its exact host requirement during preparation.
                    if self.host_version and _numeric_version(self.host_version) < _numeric_version(MIN_SETUP_HOST):
                        self._cached.update(state='incompatible', reason='Atualize o Local Suite para ' + MIN_SETUP_HOST + ' antes do NEURO RT.')
                except (OSError, ValueError, KeyError, TypeError):
                    import sys as _sys
                    error = _sys.exc_info()[1]
                    self._cached = {'state': 'unavailable', 'reason': str(error) if isinstance(error, ReleaseUnavailable)
                        else 'Não foi possível consultar a release. A versão instalada continua disponível.'}
                self._expires = time.monotonic() + self.ttl
            result = dict(self._cached, installed_version=installed_version)
        if result['state'] == 'available' and installed_version and (
                _numeric_version(installed_version) >= _numeric_version(result['version'])):
            result['state'] = 'current'
        return result

    def download(self, release, destination, progress=None):
        """Uses only the already selected immutable API asset, never looks up latest again."""
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_suffix('.part')
        size = 0
        digest = hashlib.sha256()
        created = False
        try:
            with _open(release['url'], binary=True) as source, partial.open('xb') as output:
                created = True
                for block in iter(lambda: source.read(1024 * 1024), b''):
                    size += len(block)
                    if size > release['size']:
                        raise ValueError('Download excede o tamanho fixado.')
                    digest.update(block)
                    output.write(block)
                    if progress:
                        progress(size, release['size'])
            if size != release['size'] or digest.hexdigest() != release['sha256']:
                raise ValueError('Download incompleto ou SHA256 externo divergente.')
            os.replace(partial, target)
        finally:
            if created:
                partial.unlink(missing_ok=True)
        return {'path': str(target), 'sha256': release['sha256']}


class UpdateCoordinator:
    def __init__(self, host_root, *, host_version, hold, busy, cancel, restart, client=None, package=None, host_python=None):
        self.host_root = Path(host_root)
        self.plugin_root = self.host_root / 'Plugins/NEURO RT'
        self.host_version = host_version
        self.host_python = host_python
        self.hold, self.busy, self.cancel, self.restart = hold, busy, cancel, restart
        self.client = client or ReleaseClient(host_version=host_version)
        self.offline_package = dict(package) if package is not None else None
        self._lock = threading.RLock()
        self._worker = None
        self._status = {'state': 'idle', 'reason': ''}
        self._selected = None
        self._transaction_id = None
        self._persisted_at = 0.0
        self._persisted_phase = None

    def _set_status(self, **values):
        with self._lock:
            self._status.update(values)
            snapshot = dict(self._status)
        phase = (snapshot.get('state'), snapshot.get('stage'), snapshot.get('error_code'))
        now = time.monotonic()
        if phase != self._persisted_phase or now - self._persisted_at >= .25:
            try:
                # Installer-only metadata: no exception text, patient or input paths.
                root = install_state._plugin(install_state.validate_host_root(self.host_root))
                install_state._atomic_json(install_state._path(root, 'update-status.json'), snapshot)
                self._persisted_at, self._persisted_phase = now, phase
            except (OSError, ValueError):
                return False
        return True

    def _release_hold(self):
        try:
            self.hold(False)
        except Exception:
            with self._lock:
                self._status['queue_release_failed'] = True

    def status(self):
        with self._lock:
            value = dict(self._status)
            transaction = self._transaction_id
        value['transaction_id'] = transaction
        if value.get('state') == 'preparing' and transaction:
            try:
                progress = install_state._read_json(install_state._path(self.plugin_root, 'install-status.json'))
                if progress.get('transaction_id') == transaction:
                    for key in ('stage', 'completed_files', 'total_files', 'processed_bytes',
                                'total_unpacked_bytes', 'error_code', 'error_stage', 'os_errno', 'winerror'):
                        if key in progress:
                            value[key] = progress[key]
            except (OSError, ValueError):
                pass
        return value

    def prepare(self, package, *, require_host=False, transaction_id=None):
        # Authenticate bytes before reading metadata, before invoking the installer.
        self._set_status(state='preparing', stage='host_validation', error_code='', error_stage='')
        install_state.validate_host_root(self.host_root)
        self._set_status(stage='verifying')
        if install_state._file_digest(package['path']) != package['sha256']:
            raise ValueError('SHA256 externo divergente.')
        with zipfile.ZipFile(package['path']) as archive:
            manifest, _, _, _ = install_state._inspect_zip(archive)
            module = json.loads(archive.read('code/module.json'))
        if (require_host or self._selected is not None) and module.get('execution_mode') != 'host':
            raise ValueError('O instalador remoto deve reutilizar o Python do Local Suite.')
        if self._selected is not None and self._selected.get('version') != module.get('version'):
            raise ValueError('A versão do SETUP difere da release selecionada.')
        self._set_status(version=module['version'])
        if _numeric_version(self.host_version) < _numeric_version(module['host_min_version']):
            raise install_state.InstallFailure('HOST_INCOMPATIBLE', 'Atualize o Local Suite antes de instalar esta release.')
        if not python_compatible(module.get('python')):
            raise install_state.InstallFailure('HOST_INCOMPATIBLE', 'O Python do Local Suite não atende esta release.')
        self._transaction_id = transaction_id or uuid.uuid4().hex
        receipt = install_state.begin_install(self.host_root, package, self._transaction_id,
                                             host_python=self.host_python)
        if receipt.following:
            raise install_state.InstallFailure('INSTALL_BUSY', 'Outra instalação possui a transação.')
        self._set_status(state='installed_pending_restart', stage='complete', version=receipt.version,
                         reason='Release verificada. Aguarda reinício do Local Suite.')
        return self.status()

    def finish_restart(self):
        self.hold(True)
        if self.busy():
            self._set_status(state='waiting', stage='waiting', reason='Aguardando a fila terminar para atualizar.')
            return self.status()
        state = install_state._read_json(install_state._path(self.plugin_root, 'installation.json'))
        version = state.get('pending_version')
        self._set_status(version=version or state.get('active_version'))
        if not callable(self.restart):
            self._release_hold()
            self._set_status(state='installed_pending_restart', stage='restart',
                error_code='RESTART_UNAVAILABLE', error_stage='restart',
                reason='O pacote está preparado. A reabertura controlada da suíte está indisponível.')
            return self.status()
        # Keep queue held until process exits; never mount new code in this process.
        activation_finished = False
        try:
            if version:
                self._set_status(state='activating', stage='validating',
                    reason='Conferindo os componentes antes da reabertura da suíte.')
                install_state.activate_release(self.plugin_root, version, host_python=self.host_python)
            activation_finished = True
            if not self._set_status(state='restarting', stage='restart', error_code='', error_stage='',
                    reason='Solicitando reabertura. Aguardando nova instância da suíte e ativação do plugin.'):
                raise OSError('restart status could not be persisted')
            result = self.restart()
            if (not isinstance(result, dict) or result.get('ok') is not True
                    or result.get('scheduled') is not True):
                raise ValueError('Reabertura não confirmada.')
        except BaseException as error:
            try:
                with install_state._installation_lock(self.plugin_root) as acquired:
                    if not acquired:
                        raise OSError('activation rollback lock unavailable')
                    current = install_state._read_json(self.plugin_root / 'installation.json')
                    if current != state:
                        if (current.get('transaction_id') != state.get('transaction_id')
                                or current.get('active_version') != (version or state.get('active_version'))):
                            raise OSError('activation changed concurrently')
                        install_state._atomic_json(self.plugin_root / 'installation.json', state)
            except (OSError, ValueError):
                self._set_status(state='failed', stage='restart', error_stage='restart',
                    error_code='ROLLBACK_INCOMPLETE', reason='A reabertura não foi confirmada; a fila permanece bloqueada para conferir a instalação.')
                return self.status()
            self._release_hold()
            if not activation_finished:
                self._set_status(state='installed_pending_restart', stage='activation',
                    **install_state.sanitize_install_error(error, 'activation'))
                return self.status()
            self._set_status(state='installed_pending_restart', stage='restart',
                error_code='RESTART_NOT_CONFIRMED', error_stage='restart',
                reason='O pacote está preparado. A suíte não confirmou a reabertura; tente novamente.')
            return self.status()
        self._set_status(state='restarting', stage='restart', error_code='', error_stage='',
                         reason='Reabertura solicitada. Aguardando nova instância da suíte e ativação do plugin.')
        return self.status()

    def _pending_host_setup(self, state):
        """Resume only the new shared-host contract, never an old bundle pending."""
        if state.get('pending_execution_mode') != 'host' or not state.get('pending_version'):
            return False
        try:
            version = state['pending_version']
            _numeric_version(version)
            code = install_state._path(self.plugin_root, 'versions/' + version)
            module = install_state._read_json(install_state._path(code, 'module.json'))
            inventory = install_state._read_json(install_state._path(code, 'release-manifest.json'))
            return (module.get('execution_mode') == inventory.get('execution_mode') == 'host'
                    and module.get('version') == inventory.get('version') == version
                    and module.get('runtime') == 'host-shared' and module.get('runtimes') == {}
                    and module.get('enabled_tools') == ['nidus'] and inventory.get('runtime') is None
                    and inventory.get('runtimes') == [] and inventory.get('models') == [])
        except (OSError, ValueError, TypeError, KeyError):
            return False

    def request_plugin_update(self, plugin_id, action):
        if plugin_id != 'neuro-rt' or action not in ('comecar', 'esperar', 'interromper'):
            raise ValueError('Ação de atualização inválida.')
        with self._lock:
            if self._worker and self._worker.is_alive():
                return self.status()
            if action == 'comecar' and self.busy():
                self._status.update(state='busy', reason='A atualização pode esperar terminar, ou interromper agora.')
                return self.status()
            self.hold(True)
            if action == 'interromper':
                self.cancel()
            self._set_status(state='waiting' if self.busy() else 'preparing',
                             stage='waiting' if self.busy() else 'checking', error_code='', error_stage='',
                             completed_files=0, total_files=0, processed_bytes=0, total_unpacked_bytes=0)
            offline_package = dict(self.offline_package) if self.offline_package is not None else None
            def work():
                try:
                    while self.busy():
                        time.sleep(.2)
                    state_path = self.plugin_root / 'installation.json'
                    state = install_state._read_json(install_state._path(self.plugin_root, 'installation.json')) if state_path.exists() else {}
                    if not self._pending_host_setup(state):
                        if offline_package is not None:
                            package = offline_package
                        else:
                            selected = self.client.check_plugin_release(plugin_id, state.get('active_version'))
                            if selected['state'] != 'available':
                                raise ReleaseUnavailable(selected.get('reason') or 'Não há versão nova disponível.')
                            self._selected = dict(selected)
                            plugin = install_state._plugin(install_state.validate_host_root(self.host_root))
                            destination = install_state._path(plugin, 'staging/downloads/' + uuid.uuid4().hex + '.zip')
                            self._set_status(state='downloading', stage='downloading', version=selected['version'], total_bytes=selected['size'], downloaded_bytes=0,
                                reason='Baixando a release verificada do NEURO RT.')
                            def progress(copied, total):
                                self._set_status(downloaded_bytes=copied, total_bytes=total)
                            package = self.client.download(self._selected, destination, progress=progress)
                        self._set_status(state='preparing', stage='checking', reason='Verificando e preparando os componentes da release.')
                        self.prepare(package)
                    self.finish_restart()
                except Exception as error:
                    stage = self.status().get('stage') or 'checking'
                    diagnostic = install_state.sanitize_install_error(error, stage)
                    self._release_hold()
                    self._set_status(state='failed', **diagnostic)
            self._worker = threading.Thread(target=work, name='neuro-update', daemon=True)
            self._worker.start()
            return self.status()


def inspect_local_source(folder):
    from .external_install import inspect_local_source as inspect
    return inspect(folder)


def prepare_external_plan(payload, *, source_folder=None):
    from .external_install import prepare_external_plan as prepare
    return prepare(payload, source_folder=source_folder)


def run_external(plan, progress, *, suite_root, host_python):
    from .external_install import run_external as run
    return run(plan, progress, suite_root=suite_root, host_python=host_python)


def _validate_external_plan(plan):
    from .external_install import _validate_plan
    _validate_plan(plan)


def main(argv=None):
    """Trusted lightweight setup prepares a release; the host owns activation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite-root', required=True)
    parser.add_argument('--host-version', required=True)
    parser.add_argument('--package-path')
    parser.add_argument('--package-sha256')
    parser.add_argument('--transaction-id')
    args = parser.parse_args(argv)
    try:
        from . import plugin_consent
        if not plugin_consent.accepted(plugin_consent.config_for_suite(args.suite_root), 'installation'):
            raise ValueError('Aceite do termo do plugin ausente.')
        coordinator = UpdateCoordinator(args.suite_root, host_version=args.host_version,
            hold=lambda _: None, busy=lambda: False, cancel=lambda: None, restart=None,
            host_python=sys.executable)
        if args.package_path:
            package = {'path': args.package_path, 'sha256': args.package_sha256}
        else:
            state_file = coordinator.plugin_root / 'installation.json'
            state = json.loads(state_file.read_text(encoding='utf-8')) if state_file.exists() else {}
            selected = coordinator.client.check_plugin_release('neuro-rt', state.get('active_version'))
            if selected['state'] != 'available':
                raise ReleaseUnavailable(selected.get('reason') or 'Não há release nova disponível.')
            coordinator._selected = dict(selected)
            destination = coordinator.plugin_root / 'staging/downloads' / (uuid.uuid4().hex + '.zip')
            package = coordinator.client.download(selected, destination)
        if install_state._file_digest(package['path']) != package['sha256']:
            raise ValueError('SHA256 externo divergente.')
        with zipfile.ZipFile(package['path']) as archive:
            install_state._inspect_zip(archive)
            module = json.loads(archive.read('code/module.json'))
        if not isinstance(module, dict):
            raise ValueError('Manifesto do plugin inválido.')
        parts = _numeric_version(module.get('version'))
        if parts + (0,) * max(0, 3 - len(parts)) >= (1, 1, 0):
            raise install_state.InstallFailure('EXTERNAL_MAINTENANCE_REQUIRED', 'A versão beta exige manutenção externa.')
        print(json.dumps(coordinator.prepare(package, require_host=True,
                                            transaction_id=args.transaction_id), ensure_ascii=True))
        return 0
    except (ValueError, OSError, zipfile.BadZipFile):
        error = sys.exc_info()[1]
        diagnostic = install_state.sanitize_install_error(error, 'preparing')
        if isinstance(error, ReleaseUnavailable):
            diagnostic['reason'] = str(error)
        print(json.dumps({'state': 'failed', **diagnostic}, ensure_ascii=True))
        return 1


if __name__ == '__main__':
    sys.exit(main())
