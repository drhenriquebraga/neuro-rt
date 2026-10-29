"""Public entry point for the release builder contract."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.build_plugin_release import ReleaseArtifacts, build_release, verify_release, refresh_code_release, main

if __name__ == '__main__':
    main()
