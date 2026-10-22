from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AppearanceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sprite: str = Field(default="character.png", pattern=r"^[A-Za-z0-9._/-]+\.png$")
    model: str | None = Field(default=None, pattern=r"^model\.glb$")
    scale: float = Field(default=1.0, ge=0.5, le=2.0)


class BehaviorConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    moveSpeed: int = Field(default=100, ge=20, le=300)
    idleDuration: int = Field(default=20, ge=10, le=120)
    sleepDuration: int = Field(default=120, ge=30, le=600)
    randomWalk: bool = True
    randomJump: bool = True
    autoSleep: bool = True
    draggable: bool = True
    initialPosition: Literal["left", "right", "random"] = "right"
    randomWalkFrequency: Literal["low", "medium", "high"] = "medium"


class WindowConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    alwaysOnTop: bool = True
    mousePassthrough: bool = True


class PetConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal["1.0"] = "1.0"
    id: str = Field(pattern=r"^pet_[a-f0-9]{32}$")
    name: str = Field(min_length=1, max_length=40)
    appearance: AppearanceConfig = Field(default_factory=AppearanceConfig)
    behavior: BehaviorConfig = Field(default_factory=BehaviorConfig)
    window: WindowConfig = Field(default_factory=WindowConfig)
    animations: dict[str, dict[str, object]] | None = None
    personality: dict[str, object] | None = None
    voice: dict[str, object] | None = None
    skills: list[str] | None = None
    agent: dict[str, object] | None = None


class PetCreate(BaseModel):
    name: str = Field(default="Momo", min_length=1, max_length=40)


class PetPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=40)
    appearance: AppearanceConfig | None = None
    behavior: BehaviorConfig | None = None
    window: WindowConfig | None = None


class PetRecord(BaseModel):
    id: str
    name: str
    config: PetConfig
    originalImage: str | None = None
    processedImage: str | None = None
    modelUrl: str | None = None
    createdAt: str
    updatedAt: str


class BackgroundRemovalResult(BaseModel):
    status: Literal["processed", "not_generated"]
    provider: str
    imageUrl: str
    width: int
    height: int
    note: str


class ModelGenerationResult(BaseModel):
    status: Literal["generated"]
    provider: str
    modelUrl: str
    note: str
