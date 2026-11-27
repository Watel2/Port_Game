import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import sys
from zipfile import ZipFile


GAME = "010062E01FE0C000"
VERSION = "1.2.1"
PACKAGE = "v196608"
COMMIT = "2f959ede5f1e08f10fe214e2e61933a051bdd515"
INPUT_SHA256 = "af9e0ab168815a78eecb1bf518a5d4b36093046e5b3f8313d6e5f800aecac57f"
CONTROL_SHA256 = "67bda88953f6785248b17f04a56d94aea2d3f3882981b667f251ff273b4d0c9d"
SHADER_COUNT = 19_992
SHADER_IPA_SHA256 = "6e596f6a88edfddc2ffb9b6063670c2a734c30834197e402ef90e3488732953e"
CHEAT_BUILD_ID = "8567df0b7dc16822b015d604bbcc846d"
CHEAT_GATES = (
    (0x5329EC, 27, "b9405800", "Set wallet on its existing reader"),
    (0x5329AC, 28, "6b09011f", "Preserve raised wallet capacity on spending"),
    (0x51440, 29, "0b080128", "Scale the battle EXP reward before accumulation"),
)


def replace_once(path, marker, replacement):
    content = path.read_text(encoding="utf-8")
    if content.count(marker) != 1:
        raise ValueError(f"Unexpected source in {path}")
    path.write_text(content.replace(marker, replacement), encoding="utf-8")


def enable_cheat_menu(repo):
    source = Path(__file__).resolve().parents[2] / "Source"
    ios = repo / "dm/ios/Sources"
    for name in ("TimeStrangerCheatMenu.h", "TimeStrangerCheatMenu.m"):
        shutil.copyfile(source / name, ios / name)
    replace_once(repo / "dm/host/dm.h", "OBS_MAX = 27", "OBS_MAX = 30")
    replace_once(ios / "DmIOS-Bridging-Header.h", '#include "save_sync.h"',
                 '#include "save_sync.h"\n#import "TimeStrangerCheatMenu.h"')
    replace_once(ios / "GameMenu.swift", "    return items\n",
                 '    items.append(UIAction(title: "เงินเยนและ EXP") { _ in TimeStrangerShowCheatMenu() })\n    return items\n')
    profile = repo / "dm/games" / GAME / "patches.py"
    with profile.open("a", encoding="utf-8") as stream:
        stream.write(f"\nOBS = globals().get('OBS', {{}})\nOBS.setdefault({CHEAT_BUILD_ID!r}, []).extend({CHEAT_GATES!r})\n")


def read_inputs(archive, destination):
    with archive.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != INPUT_SHA256:
            raise ValueError("Build input archive does not match the expected SHA-256")
    with ZipFile(archive) as bundle:
        expected = {
            "title_id": GAME, "version": VERSION, "package": PACKAGE,
            "nxnative_commit": COMMIT, "shader_count": SHADER_COUNT,
        }
        if json.loads(bundle.read("build-inputs.json")) != expected:
            raise ValueError("Build input manifest does not match this workflow")
        bundle.extractall(destination)


def enable_external_romfs_identity(script):
    text = script.read_text()
    marker_check = (
        '"${DM_PYTHON:-python3}" "$DM/tools/romfs.py" "$ROMFS" "$MARKER"'
        ' || die "no RomFS at $ROMFS (missing $MARKER)"'
    )
    identity_branch = '  if [ -f "$ROMFS" ]; then\n    mkdir -p "$O"'
    if text.count(marker_check) != 1 or text.count(identity_branch) != 1:
        raise ValueError("The pinned nxnative packaging script has changed")
    text = text.replace(marker_check, '''if [ -n "${DM_EXTERNAL_ROMFS_ID:-}" ]; then
  [ "$PREPARE_XCODE" = NO ] && [ "${DM_COPY_ROMFS:-YES}" = NO ] && [ -s "$DM_EXTERNAL_ROMFS_ID" ] \
    || die "external RomFS identity requires a separate data IPA"
else
  ''' + marker_check + '\nfi')
    text = text.replace(identity_branch, '''  if [ -n "${DM_EXTERNAL_ROMFS_ID:-}" ]; then
    MAPS=("$P/romfs.id=$DM_EXTERNAL_ROMFS_ID")
    t "packing the verified external RomFS identity"
  elif [ -f "$ROMFS" ]; then
    mkdir -p "$O"''')
    script.write_text(text)


def prepare(args):
    sys.path[:0] = [str(args.repo / relative) for relative in ("scripts", "dm/games", "dm/tools")]
    upstream = importlib.import_module("build_ipa_from_nsp")
    upstream.pg = importlib.import_module("profile_guess")
    upstream.nacp = importlib.import_module("nacp")
    profiles = importlib.import_module("game")
    inputs = args.work / "input"
    read_inputs(args.archive, inputs)
    identity = upstream.romfs_image.parse_identity((inputs / "romfs.id").read_text().strip())
    if (
        identity.get("title") != GAME
        or identity.get("version") != VERSION
        or identity.get("build") != PACKAGE
        or not re.fullmatch(r"[0-9a-f]{16}", identity.get("index", ""))
        or identity.get("size", 0) <= 0
    ):
        raise ValueError("RomFS identity does not match this build")
    if upstream.pack_dump.program_id(inputs / "exefs/main.npdm") != int(GAME, 16):
        raise ValueError("ExeFS belongs to a different title")

    game_dir = args.work / "game"
    shutil.copytree(inputs / "exefs", game_dir / "ExeFS")
    control = args.control.read_bytes()
    if hashlib.sha256(control).hexdigest() != CONTROL_SHA256:
        raise ValueError("Control metadata does not match the 1.2.1 update")
    (game_dir / "control.nacp").write_bytes(control)
    profile = profiles.load(GAME)
    profiles_dir = args.work / "profiles"
    derived = profiles_dir / GAME
    upstream.derive_profile(profile, derived, PACKAGE, game_dir, profile.words("modules"), nup_label=VERSION)
    for table in (inputs / "tables").glob("*.tsv"):
        shutil.copyfile(table, derived / table.name)

    os.environ.update(DM_GAME=GAME, DM_GAMES_DIR=str(profiles_dir), DM_GAMES_FIRST="1")
    env = upstream.tool_env()
    env.update(DM_PYTHON=sys.executable, DM_REWRITE_J="1")
    profile = profiles.load(GAME)
    if profile.dir.resolve() != derived.resolve():
        raise ValueError("Failed to select the derived profile")
    shader_dir = args.work / "shader"
    shutil.copytree(inputs / "shader-package", shader_dir / "pkg")
    print(f"Verified build inputs and prepared the {VERSION} profile", flush=True)
    return upstream, profile, game_dir, shader_dir, env


def verify_ipa(output, identity_path):
    with ZipFile(output) as bundle:
        app = "Payload/DmIOS.app/"
        names = bundle.namelist()
        if app + "Info.plist" not in names or app + "DmIOS" not in names:
            raise ValueError("The IPA does not contain the iOS application")
        if bundle.read(app + "romfs.id").strip() != identity_path.read_bytes().strip():
            raise ValueError("The IPA contains a different RomFS identity")
        if hashlib.sha256(bundle.read(app + "dm/control.nacp")).hexdigest() != CONTROL_SHA256:
            raise ValueError("The IPA does not contain the expected control metadata")
        info = plistlib.loads(bundle.read(app + "Info.plist"))
        if app + "Assets.car" not in names or not info.get("CFBundleIcons", {}).get("CFBundlePrimaryIcon"):
            raise ValueError("The IPA does not contain the compiled app icon")
        if any(name == app + "romfs.img" or name.startswith(app + "romfs/") for name in names):
            raise ValueError("The IPA unexpectedly contains the full game data")
        shaders = sum(name.startswith(app + "msl/") and name.endswith("_b.metallib") for name in names)
        if shaders != SHADER_COUNT:
            raise ValueError(f"Expected {SHADER_COUNT} base and DLC shader libraries, found {shaders}")
        bad = bundle.testzip()
        if bad:
            raise ValueError(f"Damaged IPA entry: {bad}")
    print("IPA verified: iOS executable, Metal libraries, and matching separate RomFS", flush=True)


def reuse_ios_shaders(ipa, destination, profile_dir):
    with ipa.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != SHADER_IPA_SHA256:
            raise ValueError("Previous IPA hash does not match the shader build")
    prefix = "Payload/DmIOS.app/"
    with ZipFile(ipa) as bundle:
        for member in bundle.infolist():
            if not member.filename.startswith(prefix + "msl/") or member.is_dir():
                continue
            output = destination / member.filename.removeprefix(prefix + "msl/")
            output.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(member) as src, output.open("wb") as target:
                shutil.copyfileobj(src, target)
        for filename in ("c1_full.tsv", "cb_extent.tsv"):
            (profile_dir / filename).write_bytes(bundle.read(prefix + "dm/" + filename))
    print("Reused the verified 1.2.1 Metal libraries", flush=True)
    return destination


def build(args):
    upstream, profile, game_dir, shaders, env = prepare(args)
    if args.cheat_menu:
        enable_cheat_menu(args.repo)
    if args.prepare_only:
        return
    patched = args.work / "patched"
    patched.mkdir()
    logs = args.work / "logs"
    logs.mkdir()
    xlate = args.repo / "dm/gfx/tools/dmsh_xlate_bin/dmsh_xlate"
    upstream.check_prereqs(env, xlate)
    upstream.check_metal(sys.executable, args.repo, env)
    upstream.chain_header(sys.executable, args.repo, env, logs)

    def rewrite(module):
        print(f"Rewriting {module}", flush=True)
        with (logs / f"rewrite-{module}.log").open("w") as log:
            result = subprocess.run(
                [sys.executable, str(args.repo / "dm/tools/patch_nso.py"),
                 str(game_dir / "ExeFS" / module), str(patched), module],
                stdout=log, stderr=subprocess.STDOUT, env=env,
            )
        if result.returncode:
            print((logs / f"rewrite-{module}.log").read_text(errors="replace")[-6000:], flush=True)
            result.check_returncode()

    with ThreadPoolExecutor(max_workers=3) as workers:
        list(workers.map(rewrite, profile.modules_in(game_dir / "ExeFS")))
    if args.cheat_menu:
        obs = (patched / "main.obs.tsv").read_text(encoding="utf-8").splitlines()
        for address, gate, instruction, _ in CHEAT_GATES:
            if not any(line.startswith(f"{address:#x}\t{gate}\t{instruction}\t") for line in obs):
                raise ValueError(f"Missing cheat menu gate at {address:#x}")
    try:
        ios = reuse_ios_shaders(args.shader_ipa, shaders / "ios", profile.dir) if args.shader_ipa else upstream.build_shaders(
            sys.executable, args.repo, shaders, xlate, env, logs, profile,
            pull=profile.get("pso_mtl4", "off") == "on",
        )
    except upstream.BuildError:
        log = logs / "dmsh_build.log"
        if log.is_file():
            print(log.read_text(errors="replace")[-8000:], flush=True)
        raise

    pack = args.repo / "dm/ios/tools/build_ipa.sh"
    enable_external_romfs_identity(pack)
    identity = args.work / "input/romfs.id"
    config = args.work / "env.txt"
    config.write_text("DM_PREEMPT=1\n", encoding="ascii")
    env.update(
        GAME=GAME, W=str(args.work / "pack"), PATCHED=str(patched), MSL_IOS=str(ios),
        ROMFS=str(game_dir / "RomFS.img"), AOC="", GFXAPI="nvn", DM_COPY_ROMFS="NO",
        DM_EXTERNAL_ROMFS_ID=str(identity), DM_DISPLAY_NAME="Digimon Story Time Stranger",
        DM_ICON=str(args.work / "input/icon.jpg"),
        DM_APP_VERSION=VERSION, DM_ENV_FILE=str(config), DM_SHADER_FILES="1",
        DM_PSO_GPUS="none", DM_LANG="en-US",
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["bash", str(pack), str(args.output)], env=env, check=True)
    verify_ipa(args.output, identity)


def main():
    parser = argparse.ArgumentParser()
    for name in ("repo", "archive", "control", "work", "output"):
        parser.add_argument(name, type=lambda path: Path(path).resolve())
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--cheat-menu", action="store_true")
    parser.add_argument("--shader-ipa", type=lambda path: Path(path).resolve())
    build(parser.parse_args())


if __name__ == "__main__":
    main()
