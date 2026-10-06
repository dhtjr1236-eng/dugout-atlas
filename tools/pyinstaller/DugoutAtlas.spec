# Windows 11 onedir build. Resource list is shared with build_windows.ps1.
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

root = Path(SPECPATH).resolve().parents[1]
datas = [(str(root / name), str(Path(name).parent)) for name in (
    'config/translations.json', 'config/theme.qss', 'config/dark.qss',
    'config/player_names_seed.json', 'config/theme_tokens.py', 'database/schema.sql',
    'docs/WINDOWS_PACKAGING_GUIDE_KO.md',
)]
binaries, hiddenimports = [], []
# PyQt6 uses PyInstaller's Qt hooks; do not collect competing Qt bindings.
for package in ('matplotlib', 'seaborn', 'pybaseball'):
    package_datas, package_binaries, package_imports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_imports
hiddenimports += ['PyQt6.QtSvg', 'PyQt6.QtSvgWidgets', 'matplotlib.backends.backend_qtagg']
a = Analysis([str(root / 'main.py')], pathex=[str(root)], binaries=binaries,
             datas=datas, hiddenimports=hiddenimports,
             excludes=['PySide2', 'PySide6', 'PyQt5'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='DugoutAtlas',
          debug=False, strip=False, upx=False, console=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='DugoutAtlas')
