from pathlib import Path

from .catalog import get_model


def validate_request(request):
    if not isinstance(request, dict) or request.get('explicit_request') is not True:
        raise ValueError('A segmentação de achado exige solicitação explícita.')
    get_model(request.get('model', ''))
    if not isinstance(request.get('input_path'), str) or not request['input_path'].strip():
        raise ValueError('Informe o caminho da RM NIfTI ou da pasta DICOM.')
    if request.get('device', 'auto') not in ('auto', 'cpu', 'cuda'):
        raise ValueError('Preferência de processamento inválida.')
    if not isinstance(request.get('export_rtstruct', False), bool):
        raise ValueError('Opção de RTSTRUCT inválida.')
    if not isinstance(request.get('series_uid', ''), str):
        raise ValueError('SeriesInstanceUID inválido.')
    return {**request, 'input_path': str(Path(request['input_path'].strip()).resolve()),
            'series_uid': request.get('series_uid', '').strip(),
            'device': request.get('device', 'auto'),
            'export_rtstruct': request.get('export_rtstruct', False)}
