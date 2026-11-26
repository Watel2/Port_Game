import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from zipfile import ZipFile


GAME = "010062E01FE0C000"
VERSION = "1.2.1"
PACKAGE = "v196608"
COMMIT = "2f959ede5f1e08f10fe214e2e61933a051bdd515"
INPUT_SHA256 = "2cf4fa6cd8e6786302536f23b78f2581c1c69f45828c9e2390d3ed427cf5a4a4"


def read_inputs(archive, destination):
    with archive.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != INPUT_SHA256:
            raise ValueError("Build input archive does not match the expected SHA-256")
    with ZipFile(archive) as bundle:
        expected = {"title_id": GAME, "version": VERSION, "package": PACKAGE, "nxnative_commit": COMMIT}
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
        if any(name == app + "romfs.img" or name.startswith(app + "romfs/") for name in names):
            raise ValueError("The IPA unexpectedly contains the full game data")
        if not any(name.startswith(app + "msl/") and name.endswith(".metallib") for name in names):
            raise ValueError("The IPA contains no iOS shader libraries")
        bad = bundle.testzip()
        if bad:
            raise ValueError(f"Damaged IPA entry: {bad}")
    print("IPA verified: iOS executable, Metal libraries, and matching separate RomFS", flush=True)


def build(args):
    upstream, profile, game_dir, shaders, env = prepare(args)
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
    try:
        ios = upstream.build_shaders(
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
        DM_APP_VERSION=VERSION, DM_ENV_FILE=str(config), DM_SHADER_FILES="1",
        DM_PSO_GPUS="none", DM_LANG="en-US",
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["bash", str(pack), str(args.output)], env=env, check=True)
    verify_ipa(args.output, identity)


def main():
    parser = argparse.ArgumentParser()
    for name in ("repo", "archive", "work", "output"):
        parser.add_argument(name, type=lambda path: Path(path).resolve())
    parser.add_argument("--prepare-only", action="store_true")
    build(parser.parse_args())


if __name__ == "__main__":
    main()
