from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel

PetAction = Literal["idle", "walk", "sleep", "jump", "wave", "happy", "angry"]


class AnimationGenerationResult(BaseModel):
    status: Literal["not_generated", "generated"]
    action: PetAction
    provider: str
    message: str


class AnimationGenerationProvider(ABC):
    @abstractmethod
    def generate_animation(self, reference_image: bytes, action: PetAction, prompt: str = "") -> AnimationGenerationResult: ...


class MockAnimationProvider(AnimationGenerationProvider):
    def generate_animation(self, reference_image: bytes, action: PetAction, prompt: str = "") -> AnimationGenerationResult:
        return AnimationGenerationResult(
            status="not_generated",
            action=action,
            provider="mock",
            message="Animation generation is not available in V0.1.",
        )
