"""Unicode-safe native file calls, enabled only inside owned scientific children."""
from contextlib import contextmanager
import os
from pathlib import Path
import threading

_private_worker = False


def enable_private_worker_io():
    global _private_worker
    _private_worker = True


@contextmanager
def native_file_path(path):
    path = Path(path).resolve()
    if os.name != 'nt' or str(path).isascii():
        yield str(path)
        return
    if not _private_worker or threading.current_thread() is not threading.main_thread():
        raise RuntimeError('I/O nativo Unicode exige o subprocesso científico privado.')
    if not path.name.isascii():
        raise ValueError('O nome do arquivo científico privado deve ser ASCII.')
    previous = Path.cwd()
    try:
        os.chdir(path.parent)
        yield path.name
    finally:
        os.chdir(previous)


def read_image(path, *args, **kwargs):
    import SimpleITK as sitk
    with native_file_path(path) as local:
        return sitk.ReadImage(local, *args, **kwargs)


def write_image(image, path, *args, **kwargs):
    import SimpleITK as sitk
    with native_file_path(path) as local:
        return sitk.WriteImage(image, local, *args, **kwargs)


def read_transform(path):
    import SimpleITK as sitk
    with native_file_path(path) as local:
        return sitk.ReadTransform(local)


def write_transform(transform, path):
    import SimpleITK as sitk
    with native_file_path(path) as local:
        return sitk.WriteTransform(transform, local)
