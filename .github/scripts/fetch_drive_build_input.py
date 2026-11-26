import argparse
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import tarfile
from urllib.request import Request, urlopen


class HashingReader:
    def __init__(self, source):
        self.source = source
        self.digest = hashlib.sha256()

    def read(self, size):
        data = self.source.read(size)
        self.digest.update(data)
        return data


def extract_archive(source, destination, expected_sha256):
    reader = HashingReader(source)
    seen = set()
    with tarfile.open(fileobj=reader, mode="r|", bufsize=1024 * 1024) as archive:
        for member in archive:
            path = PurePosixPath(member.name)
            if (
                not member.isfile()
                or path.is_absolute()
                or path.parts[:2] != ("updates", "196608")
                or ".." in path.parts
                or path in seen
            ):
                raise ValueError("Unexpected member in the build archive")
            seen.add(path)
            archive.extract(member, path=destination, filter="data")

    while reader.read(1024 * 1024):
        pass
    if reader.digest.hexdigest() != expected_sha256.lower():
        raise ValueError("The build archive SHA-256 does not match")
    if PurePosixPath("updates/196608/exefs/main.npdm") not in seen:
        raise ValueError("The build archive does not contain the updated ExeFS")
    print(f"SHA-256 verified for {len(seen)} extracted files")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()

    file_id = os.environ["DRIVE_FILE_ID"]
    sha256 = os.environ["ARCHIVE_SHA256"]
    if not re.fullmatch(r"[A-Za-z0-9_-]+", file_id) or not re.fullmatch(r"[A-Fa-f0-9]{64}", sha256):
        parser.error("A Drive file ID and SHA-256 checksum are required")

    request = Request(
        f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media",
        headers={"Authorization": f"Bearer {os.environ['DRIVE_ACCESS_TOKEN']}"},
    )
    args.destination.mkdir(parents=True)
    with urlopen(request, timeout=90) as source:
        extract_archive(source, args.destination, sha256)


if __name__ == "__main__":
    main()
