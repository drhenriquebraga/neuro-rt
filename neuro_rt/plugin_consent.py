"""Versioned plugin acknowledgement shared by trusted installer and onboarding.

No patient/operator identity is stored. This acknowledgement neither approves
results nor replaces any bundled component licence or the Local Suite terms.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile

VERSION = '1.1'
STAGES = ('installation', 'first_use')
CLAUSES = (
    ('scope', 'NEURO RT é um plugin de estudo e pesquisa da Local Suite. Nesta entrega, '
     'Nidus, Glioma, Metastasis, Meningioma e Anatomia estão em fase de testes. '
     'As ferramentas ainda estão sendo moldadas; a participação é voluntária e '
     'cada entrada solicita a confirmação desta fase.'),
    ('nidus', 'Nidus RT realiza construção geométrica a partir das entradas escolhidas '
     'pelo usuário. Não detecta lesões. O consenso ajustável entre união e interseção '
     'das projeções é uma sugestão geométrica; sua exportação para RTSTRUCT exige '
     'ação explícita, permanece UNAPPROVED e não cria CTV.'),
    ('clinical', 'Não é software médico registrado e não substitui o fluxo clínico do '
     'serviço. Resultados são sugestões não aprovadas (UNAPPROVED). Nenhuma tela '
     'aprova contornos. Revisão e aprovação para tratamento são atos do profissional '
     'responsável no TPS.'),
    ('licenses', 'A integração NEURO RT é MIT; o Nidus e o núcleo compartilhado mantêm '
     'Apache-2.0. Componentes, modelos, pesos e atlas preservam suas licenças próprias, '
     'avisos e atribuições distribuídos em LICENSE, NOTICE, licenses e catalog. Este '
     'aceite não concede uma licença geral aos pesos nem altera licenças originais.'),
    ('local', 'O processamento usa arquivos e recursos locais escolhidos pelo usuário. '
     'Instalação e atualização consultam o GitHub e baixam componentes autorizados. '
     'Essas rotinas não enviam exames. O usuário deve respeitar as permissões de '
     'acesso às pastas e proteger seus dados.'),
    ('suite', 'Este documento complementa os Termos, a Política e os Créditos da '
     'Local Suite. O aceite permite instalar e conhecer a ferramenta; não constitui '
     'validação clínica nem aprovação de qualquer resultado.'),
)


def policy():
    value = {'schema': 'neuro-rt/consent-policy/1', 'plugin_id': 'neuro-rt',
             'version': VERSION, 'language': 'pt-BR', 'title': 'Termo do plugin NEURO RT',
             'clauses': [{'id': key, 'text': text} for key, text in CLAUSES]}
    raw = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':')).encode()
    return dict(value, digest=hashlib.sha256(raw).hexdigest())


def config_for_suite(suite_root):
    return Path(suite_root).absolute() / 'Plugins' / 'NEURO RT' / 'config'


def _path(config_dir, stage, create=False):
    if stage not in STAGES:
        raise ValueError('Etapa de aceite desconhecida.')
    config_dir = Path(config_dir).absolute()
    # Do not follow redirected folders when writing a local acknowledgement.
    for current in reversed((config_dir, *config_dir.parents)):
        if current.exists() or current.is_symlink():
            info = current.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise ValueError('Pasta de aceite não pode ser link ou reparse point.')
    if create:
        config_dir.mkdir(parents=True, exist_ok=True)
    path = config_dir / ('consent-' + stage + '.json')
    if path.is_symlink() or (path.exists() and getattr(path.lstat(), 'st_file_attributes', 0) & 0x400):
        raise ValueError('Registro de aceite não pode ser redirecionado.')
    return path


def accepted(config_dir, stage):
    try:
        path = _path(config_dir, stage)
        if path.stat().st_size > 8192:
            return False
        value = json.loads(path.read_text(encoding='utf-8'))
        current = policy()
        return (isinstance(value, dict) and value.get('schema') == 'neuro-rt/consent-receipt/1'
                and value.get('accepted') is True and value.get('stage') == stage
                and value.get('version') == current['version'] and value.get('digest') == current['digest']
                and isinstance(value.get('accepted_at'), str) and bool(value['accepted_at']))
    except (OSError, ValueError, UnicodeError):
        return False


def accept(config_dir, stage, payload):
    current = policy()
    if (not isinstance(payload, dict) or payload.get('accepted') is not True
            or payload.get('version') != current['version'] or payload.get('digest') != current['digest']):
        raise ValueError('Leia e aceite a versão atual do termo do plugin.')
    path = _path(config_dir, stage, create=True)
    value = {'schema': 'neuro-rt/consent-receipt/1', 'plugin_id': 'neuro-rt', 'stage': stage,
             'accepted': True, 'version': current['version'], 'digest': current['digest'],
             'accepted_at': datetime.now(timezone.utc).isoformat()}
    descriptor, tmp = tempfile.mkstemp(prefix='.consent-', dir=str(path.parent))
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite-root', required=True)
    parser.add_argument('--accept-terms', action='store_true',
                        help='Only after showing the current terms and obtaining explicit agreement.')
    args = parser.parse_args(argv)
    config = config_for_suite(args.suite_root)
    if accepted(config, 'installation'):
        return 0
    current = policy()
    print(current['title'] + ' — versão ' + current['version'])
    for clause in current['clauses']:
        print('\n' + clause['text'])
    print('\nSHA-256: ' + current['digest'])
    try:
        explicit = args.accept_terms or input('\nDigite ACEITO para instalar: ').strip() == 'ACEITO'
        if not explicit:
            return 2
        accept(config, 'installation', dict(accepted=True, version=current['version'], digest=current['digest']))
    except (OSError, ValueError, EOFError):
        print('Instalação não autorizada: aceite explícito ausente ou não pôde ser gravado.')
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
