"""Wait for process-group ownership before importing a scientific worker."""
import runpy
import sys
from pathlib import Path


def main():
    args = sys.argv[1:]
    if args[:1] == ['--']: args = args[1:]
    if sys.stdin.buffer.readline() != b'NEURO_RT_READY\n':
        raise SystemExit(125)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from neuro_rt.scientific_io import enable_private_worker_io
    enable_private_worker_io()
    if len(args) >= 2 and args[0] == '-m':
        if args[1] not in ('neuro_rt.study_worker', 'neuro_rt.export_study',
                           'neuro_rt.build_study_views', 'neuro_rt.worker'):
            raise SystemExit('Worker fora da lista permitida.')
        sys.argv = args[1:]
        runpy.run_module(args[1], run_name='__main__')
    elif len(args) >= 2 and args[0] == '-c':
        # Internal process-control tests use the same handshake. No HTTP field
        # is ever accepted as command text by StudyService.
        sys.argv = ['-c', *args[2:]]
        exec(compile(args[1], '<managed-child>', 'exec'), {'__name__': '__main__'})
    else:
        raise SystemExit('Comando privado inválido.')


if __name__ == '__main__': main()
