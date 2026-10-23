from __future__ import annotations

import re
import shutil
from pathlib import Path

from .provider import StorageProvider

PET_ID_PATTERN = re.compile(r"^pet_[a-f0-9]{32}$")
SAFE_FILE_PATTERN = re.compile(r"^[a-f0-9]{32}\.(?:png|jpe?g|webp)$|^(?:character|cutout)\.png$|^model\.glb$|^original\.(?:png|jpe?g|webp)$")


class LocalStorageProvider(StorageProvider):
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def pet_directory(self, pet_id: str) -> Path:
        if not PET_ID_PATTERN.fullmatch(pet_id):
            raise ValueError("Invalid pet id")
        path = (self.root / "pets" / pet_id).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("Resolved path escaped storage root")
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save(self, pet_id: str, file_name: str, content: bytes) -> Path:
        if not SAFE_FILE_PATTERN.fullmatch(file_name):
            raise ValueError("Invalid storage file name")
        target = (self.pet_directory(pet_id) / file_name).resolve()
        if not target.is_relative_to(self.root):
            raise ValueError("Resolved path escaped storage root")
        target.write_bytes(content)
        return target

    def delete_pet(self, pet_id: str) -> None:
        path = self.pet_directory(pet_id)
        shutil.rmtree(path, ignore_errors=True)
