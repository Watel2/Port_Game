"""Build a single Lunar IPA from three locally extracted update folders."""
import sys
from pathlib import Path

TITLE = 0x0100DCD01E9EE000
root = Path(sys.argv[1]).resolve()
inputs = Path(sys.argv[2]).resolve()
script = root / 'scripts/build_ipa_from_nsp.py'
source = script.read_text(encoding='utf-8')
edits = [
    ("    if not nsp_dir.exists():", "    nsp_dir = nsp_dir / f'{LUNAR_TITLE + PROGRAM_INDEX:016X}'\n    if not nsp_dir.exists():"),
    (r"    if PROGRAM_INDEX and dump == 'folder': raise BuildError('--program / PROGRAM_INDEX picks a program from a multi-program application\'s NSPs or NUP; a dump folder is read as one program\'s files')" + "\n", ""),
    ("        app, fam = scan_dump(nsp_dir, int(want, 16) if want else None)", "        app = LUNAR_TITLE + PROGRAM_INDEX\n        update = nsp_dir / 'updates/196608'\n        if not pack_dump.is_version(update) or pack_dump.program_id(update / 'exefs/main.npdm') != app:\n            raise BuildError(f'{update}: invalid Lunar program files')\n        fam = {'base': None, 'updates': [(196608, update)], 'dlc': [], 'dump': True}"),
    ("        discovered = discover_sibling_programs(fam, app, b, u, nx, keys, logs / f'programs_list_{pkg_ver}.log', env)", "        discovered = {i: {'tid': LUNAR_TITLE + i, 'in_base': False, 'in_update': True} for i in (1, 2)}"),
]
for old, new in edits:
    if source.count(old) != 1:
        raise SystemExit('Unexpected upstream build script version')
    source = source.replace(old, new, 1)
sys.path.insert(0, str(script.parent))
sys.argv = [str(script), str(inputs), '--package', 'v196608', '--romfs', 'bundle', *sys.argv[3:]]
exec(compile(source, str(script), 'exec'), {'__file__': str(script), '__name__': '__main__', 'LUNAR_TITLE': TITLE})
