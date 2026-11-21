# Windows 11 onedir build. Resource list is shared with build_windows.ps1.
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules
from PyInstaller.utils.win32.versioninfo import VSVersionInfo, FixedFileInfo, StringFileInfo, StringTable, StringStruct, VarFileInfo, VarStruct
import tomllib
import PyQt6

root = Path(SPECPATH).resolve().parents[1]
datas = [(str(root / name), str(Path(name).parent)) for name in (
    'config/translations.json', 'config/theme.qss', 'config/dark.qss',
    'config/brand_logo.png', 'config/player_names_seed.json', 'database/schema.sql',
    'docs/WINDOWS_PACKAGING_GUIDE_KO.md',
    'tools/installer/LICENSE.windows-setup-shell', 'tools/installer/UPSTREAM.md',
)]
datas += [(str(root / 'build/licenses'), 'licenses')]
binaries, hiddenimports = [], []
# PyQt6 uses PyInstaller's Qt hooks; do not collect competing Qt bindings.
datas += collect_data_files('pybaseball', excludes=['**/tests/**'])
hiddenimports += collect_submodules('pybaseball', filter=lambda name: '.tests' not in name)
hiddenimports += ['PyQt6.QtSvg', 'PyQt6.QtSvgWidgets', 'matplotlib.backends.backend_qtagg']
version = tomllib.loads((root / 'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
version_tuple = tuple(map(int, version.split('.'))) + (0,) * (4 - len(version.split('.')))
version_info = VSVersionInfo(ffi=FixedFileInfo(filevers=version_tuple, prodvers=version_tuple,
    mask=0x3f, flags=0, OS=0x40004, fileType=1, subtype=0, date=(0, 0)), kids=[
    StringFileInfo([StringTable('040904B0', [StringStruct(k, v) for k, v in {
        'CompanyName': 'dhtjr1236-eng', 'FileDescription': 'Dugout Atlas',
        'FileVersion': version, 'ProductName': 'Dugout Atlas', 'ProductVersion': version,
        'OriginalFilename': 'DugoutAtlas.exe'}.items()])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])])
a = Analysis([str(root / 'main.py')], pathex=[str(root)], binaries=binaries,
             datas=datas, hiddenimports=hiddenimports,
             excludes=['PySide2', 'PySide6', 'PyQt5', 'pytest', 'IPython', 'tkinter'], noarchive=False)
# Qt uses the Windows ICU API. Never bundle a third-party icuuc.dll from PATH
# (for example a PDF tool's version-suffixed ICU exports). Windows 10+ provides it.
a.binaries = [entry for entry in a.binaries if not (
    Path(entry[0]).name.lower().startswith(('api-ms-win-', 'icudt')) or
    Path(entry[0]).name.lower() in {'icuuc.dll', 'ucrtbase.dll'})]
# Python 3.13 can contribute an older MSVC runtime than Qt 6.11. Windows loads
# root-level DLLs first; use Qt's matching, backward-compatible runtime throughout.
qt_bin = Path(PyQt6.__file__).parent / 'Qt6/bin'
for index, (destination, source, kind) in enumerate(a.binaries):
    if Path(destination).name.lower() in {'vcruntime140.dll', 'vcruntime140_1.dll'}:
        runtime = qt_bin / Path(destination).name
        if runtime.is_file():
            a.binaries[index] = (destination, str(runtime), kind)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='DugoutAtlas',
          debug=False, strip=False, upx=False, console=False,
          icon=str(root / 'tools/installer/assets/app.ico'), version=version_info)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='DugoutAtlas')
