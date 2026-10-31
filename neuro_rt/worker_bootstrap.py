"""Explicit trusted CODE path and append-only, verified extras for one worker."""
import argparse
import json
from pathlib import Path
import runpy
import sys


def activate_resources(code_dir, plugin_root, descriptor):
    from .resource_paths import resolve_resources
    from .resource_preparation import verify_extra_resources
    from .install_state import _path
    checked, extras, _receipt = resolve_resources(plugin_root, code_dir, descriptor)
    if checked is None:
        return None
    recipe = json.loads(_path(code_dir, 'catalog/resource_recipe.json').read_text(encoding='utf-8'))
    verify_extra_resources(recipe, checked, extras)
    # Deliberately avoid site.addsitedir: no downloaded .pth hook is executed.
    # Libraries already owned by the Suite retain import priority.
    if str(extras) not in sys.path:
        sys.path.append(str(extras))
    return extras


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--module', choices=('study', 'legacy', 'export', 'views',
                                           'legacy-export', 'legacy-views'), required=True)
    parser.add_argument('--plugin-root')
    parser.add_argument('--resources')
    parser.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    code_dir = Path(__file__).resolve().parents[1]
    if args.resources is not None:
        if not args.plugin_root:
            raise ValueError('Raiz verificada dos recursos ausente.')
        activate_resources(code_dir, args.plugin_root, json.loads(args.resources))
    arguments = args.arguments[1:] if args.arguments[:1] == ['--'] else args.arguments
    module = {'study': 'neuro_rt.study_worker', 'legacy': 'neuro_rt.worker',
              'export': 'neuro_rt.export_study', 'views': 'neuro_rt.build_study_views',
              'legacy-export': 'neuro_rt.export', 'legacy-views': 'neuro_rt.build_views'}[args.module]
    sys.argv = [module, *arguments]
    runpy.run_module(module, run_name='__main__')


if __name__ == '__main__':
    main()
