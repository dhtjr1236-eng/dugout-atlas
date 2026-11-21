# Windows Setup Shell attribution

The installer is adapted from https://github.com/MrUmid2oo4/windows-setup-shell
at commit `d1e0c642c50fcce1e04a2ea3dccd697f46184518` (MIT).
The original license is retained in `LICENSE.windows-setup-shell` and bundled
with the application. `installer/setup.iss` is an unmodified reference;
`installer/dugout.iss` is the Dugout Atlas adaptation used by the build.

Retains the custom Inno Setup split-panel options / progress / finished design.
Changes: Korean/English, product artwork, keyboard-accessible native buttons,
per-user installation, no automatic previous-product uninstall, no duplicate
post-install launch, no language registry overwrite, no downloaded UI fonts.
Inno Setup retains responsibility for validation, rollback, shortcuts, upgrades
and uninstall. There are no user-data deletion instructions.
