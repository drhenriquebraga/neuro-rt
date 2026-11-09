"""Explicit revision paths shared by installation and existing model consumers.

Installed callers keep allow_legacy=False. Development entrypoints may explicitly
enable flat v1 folders; neither mode scans or chooses a latest revision.
"""
from pathlib import Path
import re

from .plugin_manifest import _relative_path


def resolve_model_folder(models_dir, model_id, revision, *, allow_legacy=False) -> Path:
    for value in (model_id, revision):
        if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', value):
            raise ValueError('ID e revisão exata do modelo são obrigatórios e relativos.')
    root = Path(models_dir).resolve()
    flat = _relative_path(root, model_id)
    versioned = _relative_path(flat, revision)
    if versioned.exists() or not allow_legacy:
        return versioned
    return flat if flat.is_dir() else versioned


def preflight_model_folders(models_dir, model, *, allow_legacy=False):
    """Validate the pinned legacy engine model and its Brain dependency, if used."""
    from .catalog import RELEASE, BRAIN, validate_model_folder, requires_brain
    folder = resolve_model_folder(models_dir, model['id'], model.get('revision', RELEASE),
                                  allow_legacy=allow_legacy)
    validate_model_folder(folder, model)
    brain_folder = None
    if requires_brain(folder):
        brain_folder = resolve_model_folder(models_dir, BRAIN['id'], BRAIN.get('revision', RELEASE),
                                            allow_legacy=allow_legacy)
        validate_model_folder(brain_folder, BRAIN)
    return folder, brain_folder


def shared_model_status(models_dir, *, allow_legacy=False):
    """Preserve the v1 status shape while using the same paths as preflight/worker."""
    import configparser
    from .catalog import MODELS, RELEASE
    status = []
    for model in MODELS:
        try:
            preflight_model_folders(models_dir, model, allow_legacy=allow_legacy)
            ready, reason = True, ''
        except (ValueError, OSError, configparser.Error) as error:
            ready, reason = False, str(error)
        status.append({**model, 'ready': ready, 'reason': reason,
                       'release': model.get('revision', RELEASE), 'license': 'BSD-2-Clause'})
    return status
