"""Build a single Lunar IPA from three locally extracted update folders."""
import os
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
def replace_once(path, old, new):
    text = path.read_text(encoding='utf-8')
    if text.count(old) != 1:
        raise SystemExit(f'Unexpected upstream layout in {path}')
    path.write_text(text.replace(old, new, 1), encoding='utf-8')

if os.environ.get('LUNAR_SEPARATE_DATA') == 'true':
    replace_once(
        root / 'dm/ios/Sources/main.m',
        "    if (prog) {   // the program's files are in the app (Documents holds one image, one program's)",
        """    if (prog) {
        NSString *data = [doc stringByAppendingPathComponent:@"Data"];
        NSString *name = [[prog substringFromIndex:1] stringByAppendingPathExtension:@"img"];
        NSString *external = [data stringByAppendingPathComponent:name];
        if (romfs_image_complete(external)) {
            setenv("DM_ROMFS_PROGRAMS", data.fileSystemRepresentation, 0);
            return external;
        }
        if (![fm fileExistsAtPath:[NSBundle.mainBundle.resourcePath stringByAppendingPathComponent:prog]]) {
            fprintf(stderr, "boot: copy Data/%s into this app's Documents folder.\\n", name.UTF8String);
        }""",
    )
    replace_once(
        root / 'dm/ios/tools/build_ipa.sh',
        '    if [ -f "$ROMFS" ]; then MAPS+=("$P/p$PN/romfs.img=$ROMFS"); else MAPS+=("$P/p$PN/romfs=$ROMFS"); fi',
        '    # Lunar uses Documents/Data/<program index>.img for each program.',
    )
if os.environ.get('LUNAR_INTERIOR_TRIAL') == 'true':
    replace_once(
        root / 'dm/gfx/nvn/nvn_mtl.m',
        '    else if (g_dss_dirty || cur_ds_pass != g_pass.serial) { cur_ds = dss_get',
        """    // Lunar's Remastered map draws the captured 2D tiles and sprites on a
    // single plane. Replay those color draws in order if Metal's depth test
    // rejects the plane. Keep the recorded depth state for other geometry.
    else if (g_pass.hd && g_pass.tw == 2048 && g_pass.th == 1080 &&
             S.ds.dt && S.ds.dw && S.ds.df == NVN_DEPTH_FUNC_LEQUAL &&
             (S.chmask.mask & 0xfu) && dw && !dw->ind && dw->count > 0 &&
             dw->first >= 0 && pr->sh[0] && pr->sh[1] &&
             !strcmp(DM_GAME_ID, "0100DCD01E9EE001") &&
             !strcmp(pr->sh[0]->key, "ce0f7db020ac83e0_b") &&
             !strcmp(pr->sh[1]->key, "2cc22878585a151e_b")) {
        const char *enabled = getenv("DM_LUNAR_SCENE_DEPTH");
        int flat = (!enabled || strcmp(enabled, "0")) &&
            S.nattr >= 1 && S.attr[0].fmt == NVN_FORMAT_RGBA32F &&
            S.attr[0].stream == 0 && S.attr[0].offset == 0 &&
            S.stream[0].stride == 40 && S.stream[0].divisor == 0;
        if (flat) {
            uint64_t start = (uint64_t)dw->first * 40, count = (uint64_t)dw->count * 40;
            uint64_t addr = S.vbuf[0].address + start, offset;
            void *buffer;
            flat = S.vbuf[0].address && addr >= S.vbuf[0].address &&
                start <= S.vbuf[0].size && count <= S.vbuf[0].size - start &&
                !pend_hits(addr, count) && mtl_addr(addr, count, &buffer, &offset);
            const uint8_t *bytes = flat ? [(__bridge id<MTLBuffer>)buffer contents] : NULL;
            flat = bytes != NULL;
            for (uint64_t i = 0; flat && i < count; i += 40) {
                float z;
                memcpy(&z, bytes + offset + i + 8, sizeof z);
                flat = z == 1000.0f;
            }
        }
        if (flat) {
            static int logged;
            if (!logged) { MLOG("Lunar scene depth trial: replaying coplanar tiles and sprites in draw order"); logged = 1; }
            S.ds.df = NVN_DEPTH_FUNC_ALWAYS;
            cur_ds = dss_get(g_pass.hd, g_pass.hs);
            S.ds.df = NVN_DEPTH_FUNC_LEQUAL;
            g_dss_dirty = 1;
        } else if (g_dss_dirty || cur_ds_pass != g_pass.serial) {
            cur_ds = dss_get(g_pass.hd, g_pass.hs);
            g_dss_dirty = 0;
        }
        cur_ds_pass = g_pass.serial;
    }
    else if (g_dss_dirty || cur_ds_pass != g_pass.serial) { cur_ds = dss_get""",
    )
sys.path.insert(0, str(script.parent))
sys.argv = [str(script), str(inputs), '--package', 'v196608', '--romfs', 'bundle', *sys.argv[3:]]
exec(compile(source, str(script), 'exec'), {'__file__': str(script), '__name__': '__main__', 'LUNAR_TITLE': TITLE})
