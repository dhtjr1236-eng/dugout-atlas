"""Archive the exact release source from an explicit allowlist, never user data."""
from pathlib import Path
import hashlib
import json
import platform
import sys
import tomllib
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[2]
CODE_DIRS = ('cache', 'charts', 'config', 'controllers', 'database', 'models', 'services', 'ui', 'workers', 'tests')
ROOT_FILES = ('main.py', 'requirements.txt', 'requirements-build.txt', 'constraints-release.txt',
              'pyproject.toml', '.gitignore', 'README.md', 'README.ko.md', 'ARCHITECTURE.md', 'CHANGELOG.md',
              'install.bat', 'run.bat', 'run_debug.bat', 'verify.bat', 'diagnose_sources.py', 'diagnose_sources.bat',
              'clear_cache.bat', 'open_bref_data.bat')
RESOURCES = ('config/translations.json', 'config/player_names_seed.json', 'config/brand_logo.png',
             'config/theme.qss', 'config/dark.qss', 'database/schema.sql')


def make_archive():
    version = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    selected = set(ROOT / name for name in (*ROOT_FILES, *RESOURCES))
    for name in CODE_DIRS:
        selected.update((ROOT / name).glob('*.py') if name == 'cache' else (ROOT / name).rglob('*.py'))
    selected.update((ROOT / 'tests/fixtures/season_race').glob('*.json'))
    selected.update((ROOT / 'tests/fixtures/pitch_analysis').glob('*.csv'))
    selected.update((ROOT / 'docs').glob('*.md'))
    selected.update((ROOT / 'docs/images').glob('*'))
    selected.update((ROOT / 'tools').glob('*.ps1'))
    selected.update((ROOT / 'tools/installer').glob('*.py'))
    selected.update((ROOT / 'tools/installer').glob('*.md'))
    selected.add(ROOT / 'tools/installer/LICENSE.windows-setup-shell')
    selected.add(ROOT / 'tools/installer/installer/dugout.iss')
    selected.add(ROOT / 'tools/installer/installer/setup.iss')
    selected.add(ROOT / 'tools/pyinstaller/DugoutAtlas.spec')
    selected.update((ROOT / '.github/workflows').glob('*.yml'))
    files = sorted(path for path in selected if path.is_file() and '__pycache__' not in path.parts)
    manifest = {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    info = {'version': version, 'python': sys.version, 'platform': platform.platform(),
            'source_files': len(files), 'source_sha256': manifest}
    release = ROOT / 'release'
    release.mkdir(exist_ok=True)
    (release / 'BUILD-INFO.json').write_text(json.dumps(info, indent=2), encoding='utf-8')
    with ZipFile(release / f'DugoutAtlas-v{version}-source.zip', 'w', ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(ROOT).as_posix())
        archive.writestr('SOURCE-MANIFEST.json', json.dumps(info, indent=2))
        archive.write(ROOT / 'build/licenses/BUILD-DEPENDENCIES.txt', 'BUILD-DEPENDENCIES.txt')


if __name__ == '__main__':
    make_archive()
