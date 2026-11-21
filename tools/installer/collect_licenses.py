"""Retain dependency notices from this build environment without copying user data."""
from importlib.metadata import distributions
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'build/licenses'


def collect():
    OUT.mkdir(parents=True, exist_ok=True)
    inventory = []
    for dist in sorted(distributions(), key=lambda d: d.metadata.get('Name', '').lower()):
        name = dist.metadata.get('Name', 'unknown')
        inventory.append(f'{name}=={dist.version}')
        for file in dist.files or []:
            parts = Path(str(file)).parts
            if not parts or not parts[0].endswith('.dist-info'):
                continue
            if not any(word in str(file).lower() for word in ('license', 'copying', 'notice', 'authors')):
                continue
            source = Path(dist.locate_file(file))
            if source.is_file():
                target = OUT / name / Path(*parts[1:])
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
    python_license = Path(sys.base_prefix) / 'LICENSE.txt'
    if python_license.exists():
        shutil.copyfile(python_license, OUT / 'LICENSE-Python.txt')
    (OUT / 'BUILD-DEPENDENCIES.txt').write_text('\n'.join(inventory) + '\n', encoding='utf-8')
    shutil.copyfile(ROOT / 'tools/installer/LICENSE.windows-setup-shell', OUT / 'LICENSE.windows-setup-shell')
    (OUT / 'README.txt').write_text(
        'Dugout Atlas dependency notices\n'
        'Source: https://github.com/dhtjr1236-eng/dugout-atlas\n'
        'Exact application source should accompany each public release.\n'
        'PyQt6 is distributed under GPL v3 in this build; see its license.\n'
        'This inventory includes build dependencies as well as runtime packages.\n', encoding='utf-8')


if __name__ == '__main__':
    collect()
