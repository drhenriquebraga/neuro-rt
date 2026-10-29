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
                    name = 'NEURO_RT_OFFLINE_v' + version + '.zip'
                    assets = [a for a in raw['assets'] if a.get('name') == name]
                    if len(assets) != 1:
                        raise ReleaseUnavailable('Payload offline completo ausente na release.')
                    asset = assets[0]
                    digest = asset.get('digest', '')
                    if not re.fullmatch(r'sha256:[0-9a-f]{64}', digest):
                        raise ReleaseUnavailable('Asset sem SHA256 externo publicado; instalação indisponível.')
                    self._cached = {'state': 'available', 'version': version,
                        'release_id': raw.get('id'), 'asset_id': asset['id'], 'name': name,
                        'url': asset['url'], 'sha256': digest[7:], 'size': asset['size'], 'reason': ''}
                    if self.host_version:
                        manifests = [a for a in raw['assets'] if a.get('name') == 'release-manifest.json']
                        if len(manifests) != 1:
                            raise ReleaseUnavailable('Manifesto de compatibilidade ausente na release.')
                        metadata = self._fetch_manifest(manifests[0]['url'])
                        if metadata.get('schema') != install_state.SCHEMA or metadata.get('version') != version:
                            raise ReleaseUnavailable('Manifesto externo não corresponde à release selecionada.')
                        minimum = metadata['host_min_version']
                        if _numeric_version(self.host_version) < _numeric_version(minimum):
                            self._cached.update(state='incompatible', reason='Atualize o Local Suite para ' + minimum + ' antes do NEURO RT.')
                        elif not python_compatible(metadata.get('python')):
                            self._cached.update(state='incompatible', reason='O Python desta versão do Local Suite não atende a release NEURO RT.')
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
    def __init__(self, host_root, *, host_version, hold, busy, cancel, restart, client=None, package=None):
        self.host_root = Path(host_root)
        self.plugin_root = self.host_root / 'Plugins/NEURO RT'
        self.host_version = host_version
        self.hold, self.busy, self.cancel, self.restart = hold, busy, cancel, restart
        self.client = client or ReleaseClient(host_version=host_version)
        self.offline_package = dict(package) if package is not None else None
        self._lock = threading.RLock()
        self._worker = None
        self._status = {'state': 'idle', 'reason': ''}
        self._selected = None

    def status(self):
        with self._lock:
            return dict(self._status)

    def prepare(self, package):
        # Authenticate bytes before reading metadata, before invoking the installer.
        if install_state._file_digest(package['path']) != package['sha256']:
            raise ValueError('SHA256 externo divergente.')
        with zipfile.ZipFile(package['path']) as archive:
            manifest, _, _, _ = install_state._inspect_zip(archive)
            module = json.loads(archive.read('code/module.json'))
        if _numeric_version(self.host_version) < _numeric_version(module['host_min_version']):
            raise ValueError('Atualize o Local Suite antes de instalar esta release.')
        if not python_compatible(module.get('python')):
            raise ValueError('O Python do Local Suite não atende esta release.')
        receipt = install_state.begin_install(self.host_root, package, uuid.uuid4().hex)
        with self._lock:
            self._status = {'state': 'installed_pending_restart', 'version': receipt.version,
                            'reason': 'Release verificada. Aguarda reinício do Local Suite.'}
        return self.status()

    def finish_restart(self):
        self.hold(True)
        if self.busy():
            with self._lock:
                self._status.update(state='waiting', reason='Aguardando a fila terminar para atualizar.')
            return self.status()
        if not callable(self.restart):
            self.hold(False)
            raise ValueError('Reinício controlado do Local Suite indisponível.')
        state = json.loads((self.plugin_root / 'installation.json').read_text(encoding='utf-8'))
        version = state.get('pending_version')
        if version:
            install_state.activate_release(self.plugin_root, version)
        # Keep queue held until process exits; never mount new code in this process.
        try:
            result = self.restart()
            if isinstance(result, dict) and (result.get('ok') is False or result.get('erro')):
                raise ValueError('O Local Suite não confirmou o reinício; release anterior preservada.')
        except BaseException:
            if state.get('active_version'):
                install_state.activate_release(self.plugin_root, state['active_version'])
            else:
                with install_state._installation_lock(self.plugin_root) as acquired:
                    if not acquired:
                        raise ValueError('Não foi possível restaurar a pendência; acompanhe a instalação.')
                    install_state._atomic_json(self.plugin_root / 'installation.json', state)
            self.hold(False)
            raise
        with self._lock:
            self._status.update(state='restarting', reason='Reabrindo o Local Suite para ativar a release.')
        return self.status()

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
            self._status.update(state='waiting' if self.busy() else 'preparing')
            offline_package = dict(self.offline_package) if self.offline_package is not None else None
            def work():
                try:
                    while self.busy():
                        time.sleep(.2)
                    state_path = self.plugin_root / 'installation.json'
                    state = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {}
                    if not state.get('pending_version'):
                        if offline_package is not None:
                            package = offline_package
                        else:
                            selected = self.client.check_plugin_release(plugin_id, state.get('active_version'))
                            if selected['state'] != 'available':
                                raise ReleaseUnavailable(selected.get('reason') or 'Não há versão nova disponível.')
                            self._selected = dict(selected)
                            plugin = install_state._plugin(install_state.validate_host_root(self.host_root))
                            destination = install_state._path(plugin, 'staging/downloads/' + uuid.uuid4().hex + '.zip')
                            with self._lock:
                                self._status.update(state='downloading', total_bytes=selected['size'], downloaded_bytes=0,
                                    reason='Baixando a release verificada do NEURO RT.')
                            def progress(copied, total):
                                with self._lock:
                                    self._status.update(downloaded_bytes=copied, total_bytes=total)
                            package = self.client.download(self._selected, destination, progress=progress)
                        with self._lock:
                            self._status.update(state='preparing', reason='Verificando e preparando os componentes da release.')
                        self.prepare(package)
                    self.finish_restart()
                except Exception as error:
                    self.hold(False)
                    with self._lock:
                        self._status.update(state='failed', reason=str(error) if isinstance(error, ReleaseUnavailable)
                            else 'Atualização interrompida; instalação e dados preservados.')
            self._worker = threading.Thread(target=work, name='neuro-update', daemon=True)
            self._worker.start()
            return self.status()


def main(argv=None):
    """Trusted lightweight setup prepares a release; the host owns activation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite-root', required=True)
    parser.add_argument('--host-version', required=True)
    parser.add_argument('--package-path')
    parser.add_argument('--package-sha256')
    args = parser.parse_args(argv)
    coordinator = UpdateCoordinator(args.suite_root, host_version=args.host_version,
        hold=lambda _: None, busy=lambda: False, cancel=lambda: None, restart=None)
    try:
        if args.package_path:
            package = {'path': args.package_path, 'sha256': args.package_sha256}
        else:
            state_file = coordinator.plugin_root / 'installation.json'
            state = json.loads(state_file.read_text(encoding='utf-8')) if state_file.exists() else {}
            selected = coordinator.client.check_plugin_release('neuro-rt', state.get('active_version'))
            if selected['state'] != 'available':
                raise ReleaseUnavailable(selected.get('reason') or 'Não há release nova disponível.')
            destination = coordinator.plugin_root / 'staging/downloads' / (uuid.uuid4().hex + '.zip')
            package = coordinator.client.download(selected, destination)
        print(json.dumps(coordinator.prepare(package), ensure_ascii=True))
        return 0
    except (ValueError, OSError, zipfile.BadZipFile):
        error = sys.exc_info()[1]
        print(json.dumps({'state': 'failed', 'reason': str(error) if isinstance(error, ReleaseUnavailable)
            else 'Instalação interrompida; versão ativa e dados preservados.'}, ensure_ascii=True))
        return 1


if __name__ == '__main__':
    sys.exit(main())
