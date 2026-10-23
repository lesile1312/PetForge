from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class StorageProvider(ABC):
    @abstractmethod
    def pet_directory(self, pet_id: str) -> Path: ...

    @abstractmethod
    def save(self, pet_id: str, file_name: str, content: bytes) -> Path: ...

    @abstractmethod
    def delete_pet(self, pet_id: str) -> None: ...
