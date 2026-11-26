import argparse
import hashlib
import io
import os
from pathlib import Path, PurePosixPath
import re
import tarfile
from urllib.request import Request, urlopen


class DriveParts(io.RawIOBase):
    def __init__(self, file_ids, token):
        super().__init__()
        self.file_ids = iter(file_ids)
        self.token = token
        self.current = None

    def readable(self):
        return True

    def readinto(self, buffer):
        while True:
            if self.current is None:
                file_id = next(self.file_ids, None)
                if file_id is None:
                    return 0
                request = Request(f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media")
                request.add_unredirected_header("Authorization", f"Bearer {self.token}")
                self.current = urlopen(request, timeout=90)
            count = self.current.readinto(buffer)
            if count:
                return count
            self.current.close()
            self.current = None

    def close(self):
        try:
            if self.current is not None:
                self.current.close()
        finally:
            super().close()


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

    file_ids = os.environ["DRIVE_FILE_IDS"].split(",")
    sha256 = os.environ["ARCHIVE_SHA256"]
    if not all(re.fullmatch(r"[A-Za-z0-9_-]+", value) for value in file_ids):
        parser.error("One or more comma-separated Drive file IDs are required")
    if not re.fullmatch(r"[A-Fa-f0-9]{64}", sha256):
        parser.error("A SHA-256 checksum is required")

    args.destination.mkdir(parents=True)
    parts = DriveParts(file_ids, os.environ["DRIVE_ACCESS_TOKEN"])
    with io.BufferedReader(parts, buffer_size=1024 * 1024) as source:
        extract_archive(source, args.destination, sha256)


if __name__ == "__main__":
    main()
