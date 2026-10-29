from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import re
import secrets
import subprocess
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from PIL import Image, UnidentifiedImageError
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

from .configuration import ALLOWED_FORMATS, DATABASE_PATH, MAX_UPLOAD_BYTES, ROOT, STORAGE_ROOT, from_project_root
from .database import PetRepository
from .models import (
    BackgroundRemovalResult,
    ModelGenerationResult,
    PetConfig,
    PetCreate,
    PetPatch,
    PetRecord,
)
from .providers.animation import MockAnimationProvider
from .providers.background import (
    EdgeMatteProvider,
    MockBackgroundRemovalProvider,
    ProviderUnavailableError,
    RembgBackgroundRemovalProvider,
)
from .providers.cartoon import cartoonize_png
from .providers.model import TripoSRModelProvider
from .storage.local import LocalStorageProvider

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("petforge.api")
repository = PetRepository(DATABASE_PATH)
storage = LocalStorageProvider(STORAGE_ROOT)
background_provider_name = os.getenv("BACKGROUND_REMOVAL_PROVIDER", "rembg").strip().lower()
background_provider = {
    "mock": MockBackgroundRemovalProvider,
    "edge-matte": EdgeMatteProvider,
    "rembg": RembgBackgroundRemovalProvider,
}.get(background_provider_name, RembgBackgroundRemovalProvider)()
model_provider_name = os.getenv("PETFORGE_3D_PROVIDER", "triposr").strip().lower()
model_provider = TripoSRModelProvider() if model_provider_name == "triposr" else None
animation_provider = MockAnimationProvider()
PET_ID_PATTERN = re.compile(r"^pet_[a-f0-9]{32}$")
RANDOM_IMAGE_PATTERN = re.compile(r"^[a-f0-9]{32}\.(?:png|jpe?g|webp)$")


def success(data: Any, status_code: int = 200) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"data": data, "error": None})


def fail(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"data": None, "error": {"code": code, "message": message}})


def serialize_pet(row: dict[str, Any]) -> dict[str, Any]:
    model_file = row["config"].get("appearance", {}).get("model")
    model_path = (STORAGE_ROOT / "pets" / row["id"] / "model.glb").resolve()
    model_url = (
        f"/api/pets/{row['id']}/model"
        if model_file == "model.glb" and model_path.is_relative_to(STORAGE_ROOT) and model_path.is_file()
        else None
    )
    return PetRecord(
        id=row["id"],
        name=row["name"],
        config=row["config"],
        originalImage=f"/api/pets/{row['id']}/image?kind=original" if row.get("original_image") else None,
        processedImage=f"/api/pets/{row['id']}/image?kind=processed" if row.get("processed_image") else None,
        modelUrl=model_url,
        createdAt=row["created_at"],
        updatedAt=row["updated_at"],
    ).model_dump()


def get_pet_or_404(pet_id: str) -> dict[str, Any]:
    if not PET_ID_PATTERN.fullmatch(pet_id):
        raise HTTPException(HTTP_404_NOT_FOUND, "Pet not found")
    pet = repository.get(pet_id)
    if pet is None:
        raise HTTPException(HTTP_404_NOT_FOUND, "Pet not found")
    return pet


def persist_pet(pet: dict[str, Any]) -> None:
    """Keep the independent runtime package config in sync with SQLite."""
    package_directory = storage.pet_directory(pet["id"])
    config_path = package_directory / "pet.json"
    temporary_path = package_directory / "pet.json.tmp"
    temporary_path.write_text(json.dumps(pet["config"], ensure_ascii=False, indent=2), encoding="utf-8")
    temporary_path.replace(config_path)
    repository.save(pet)


def remove_derived_file(pet_id: str, file_name: str) -> None:
    path = (storage.pet_directory(pet_id) / file_name).resolve()
    if path.is_relative_to(storage.root) and path.is_file():
        path.unlink()


@asynccontextmanager
async def lifespan(_: FastAPI):
    repository.initialize()
    logger.info("PetForge API ready; storage=%s", STORAGE_ROOT)
    yield


app = FastAPI(title="PetForge API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def reject_untrusted_browser_origins(request: Request, call_next: Any):
	origin = request.headers.get("origin")
	allowed_origins = {"http://localhost:3000", "http://127.0.0.1:3000"}
	if request.url.path.startswith("/api/") and request.method != "OPTIONS" and origin and origin not in allowed_origins:
		return fail("origin_not_allowed", "PetForge API only accepts requests from its local Web editor.", 403)
	return await call_next(request)


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(_: Request, error: StarletteHTTPException) -> JSONResponse:
    code = {404: "not_found", 409: "conflict", 413: "file_too_large", 415: "unsupported_media_type", 422: "invalid_input", 503: "runtime_unavailable"}.get(error.status_code, "request_failed")
    return fail(code, str(error.detail), error.status_code)


@app.exception_handler(ValidationError)
async def validation_error_handler(_: Request, error: ValidationError) -> JSONResponse:
    return fail("invalid_input", error.errors(include_url=False).__str__(), 422)


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(_: Request, error: RequestValidationError) -> JSONResponse:
    return fail("invalid_input", str(error.errors()), 422)


@app.exception_handler(Exception)
async def unexpected_error_handler(_: Request, error: Exception) -> JSONResponse:
    logger.exception("Unhandled API error", exc_info=error)
    return fail("internal_error", "The request could not be completed.", 500)


@app.get("/health")
def health() -> dict[str, Any]:
    return {"data": {"status": "ok", "version": "0.1.0"}, "error": None}


@app.get("/api/pets")
def list_pets() -> dict[str, Any]:
    return {"data": [serialize_pet(pet) for pet in repository.list()], "error": None}


@app.post("/api/pets", status_code=201)
def create_pet(payload: PetCreate) -> JSONResponse:
    pet_id = f"pet_{secrets.token_hex(16)}"
    now = repository.now()
    config = PetConfig(id=pet_id, name=payload.name).model_dump(exclude_none=True)
    pet = {
        "id": pet_id,
        "name": payload.name,
        "config": config,
        "original_image": None,
        "processed_image": None,
        "created_at": now,
        "updated_at": now,
    }
    persist_pet(pet)
    return success(serialize_pet(pet), 201)


@app.get("/api/pets/{pet_id}")
def read_pet(pet_id: str) -> dict[str, Any]:
    return {"data": serialize_pet(get_pet_or_404(pet_id)), "error": None}


@app.patch("/api/pets/{pet_id}")
def update_pet(pet_id: str, patch: PetPatch) -> dict[str, Any]:
    pet = get_pet_or_404(pet_id)
    changes = patch.model_dump(exclude_unset=True, exclude_none=True)
    config = dict(pet["config"])
    if "name" in changes:
        pet["name"] = changes.pop("name")
        config["name"] = pet["name"]
    for section in ("appearance", "behavior", "window"):
        if section in changes:
            config[section] = changes[section]
    pet["config"] = PetConfig.model_validate(config).model_dump(exclude_none=True)
    pet["updated_at"] = repository.now()
    persist_pet(pet)
    return {"data": serialize_pet(pet), "error": None}


async def read_upload(upload: UploadFile) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while chunk := await upload.read(1024 * 1024):
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "Image must be 10 MB or smaller")
        chunks.append(chunk)
    if total == 0:
        raise HTTPException(400, "The uploaded image is empty")
    return b"".join(chunks)


@app.post("/api/pets/{pet_id}/image")
async def upload_image(pet_id: str, file: UploadFile = File(...)) -> JSONResponse:
    pet = get_pet_or_404(pet_id)
    content = await read_upload(file)
    declared_type = (file.content_type or "").lower().split(";")[0].strip()
    if declared_type not in ALLOWED_FORMATS.values():
        raise HTTPException(415, "Upload a PNG, JPEG, or WEBP image")
    suffix_format = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".webp": "WEBP"}.get(Path(file.filename or "").suffix.lower())
    if suffix_format is None:
        raise HTTPException(415, "Use a .png, .jpg, .jpeg, or .webp file")
    try:
        with Image.open(io.BytesIO(content)) as image:
            image_format = image.format
            width, height = image.size
            image.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise HTTPException(400, "The uploaded file is not a readable image") from error
    if image_format not in ALLOWED_FORMATS or declared_type != ALLOWED_FORMATS[image_format] or image_format != suffix_format:
        raise HTTPException(415, "The file contents do not match its PNG, JPEG, or WEBP media type")
    if width * height > 40_000_000:
        raise HTTPException(400, "Image dimensions are too large (maximum 40 megapixels)")

    suffix = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}[image_format]
    file_name = f"{secrets.token_hex(16)}{suffix}"
    storage.save(pet_id, file_name, content)
    remove_derived_file(pet_id, "character.png")
    remove_derived_file(pet_id, "cutout.png")
    remove_derived_file(pet_id, "model.glb")
    remove_derived_file(pet_id, "triposr.log")
    pet["original_image"] = file_name
    pet["processed_image"] = None
    pet["config"]["appearance"]["model"] = None
    pet["updated_at"] = repository.now()
    persist_pet(pet)
    logger.info("Image uploaded for %s (%s bytes, %sx%s)", pet_id, len(content), width, height)
    return success(serialize_pet(pet))


@app.post("/api/pets/{pet_id}/use-original")
def use_original_as_character(pet_id: str) -> JSONResponse:
    pet = get_pet_or_404(pet_id)
    file_name = pet.get("original_image")
    if not file_name or not RANDOM_IMAGE_PATTERN.fullmatch(file_name):
        raise HTTPException(409, "请先上传透明背景 PNG，再将它作为桌宠角色图。")
    if not file_name.lower().endswith(".png"):
        raise HTTPException(415, "直接导入只支持透明背景 PNG。普通照片请切换到“我只有普通照片”。")

    original_path = (storage.pet_directory(pet_id) / file_name).resolve()
    if not original_path.is_relative_to(storage.root) or not original_path.is_file():
        raise HTTPException(404, "Original image not found")
    try:
        with Image.open(original_path) as opened:
            if opened.format != "PNG":
                raise HTTPException(415, "直接导入只支持透明背景 PNG。普通照片请切换到“我只有普通照片”。")
            character = opened.convert("RGBA")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise HTTPException(400, "无法读取这张 PNG，请重新导出后再试。") from error

    alpha = character.getchannel("A")
    histogram = alpha.histogram()
    transparent_ratio = sum(histogram[:250]) / (character.width * character.height)
    if alpha.getextrema()[0] == 255 or transparent_ratio < 0.005:
        raise HTTPException(400, "这张 PNG 没有可用的透明背景。请切换到“我只有普通照片”，或先准备透明 PNG。")

    bounds = alpha.point(lambda value: 255 if value > 8 else 0).getbbox()
    if bounds is None:
        raise HTTPException(400, "这张 PNG 里没有检测到可见角色。")
    left, top, right, bottom = bounds
    padding_x = max(2, round((right - left) * 0.03))
    padding_y = max(2, round((bottom - top) * 0.03))
    character = character.crop((
        max(0, left - padding_x),
        max(0, top - padding_y),
        min(character.width, right + padding_x),
        min(character.height, bottom + padding_y),
    ))
    output = io.BytesIO()
    character.save(output, format="PNG", optimize=True)
    storage.save(pet_id, "character.png", output.getvalue())
    remove_derived_file(pet_id, "cutout.png")
    remove_derived_file(pet_id, "model.glb")
    remove_derived_file(pet_id, "triposr.log")
    pet["processed_image"] = "character.png"
    pet["config"]["appearance"]["sprite"] = "character.png"
    pet["config"]["appearance"]["model"] = None
    pet["updated_at"] = repository.now()
    persist_pet(pet)
    logger.info("Transparent character image selected for %s (%sx%s)", pet_id, character.width, character.height)
    return success(serialize_pet(pet))


@app.post("/api/pets/{pet_id}/remove-background")
def remove_background(pet_id: str) -> JSONResponse:
    pet = get_pet_or_404(pet_id)
    file_name = pet.get("original_image")
    if not file_name or not RANDOM_IMAGE_PATTERN.fullmatch(file_name):
        raise HTTPException(409, "Upload an image before removing its background")
    original_path = (storage.pet_directory(pet_id) / file_name).resolve()
    if not original_path.is_relative_to(storage.root) or not original_path.is_file():
        raise HTTPException(404, "Original image not found")
    try:
        source = original_path.read_bytes()
        provider = background_provider
        processed, width, height = provider.remove_background(source)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    except ProviderUnavailableError as error:
        logger.warning("Background provider is unavailable: %s", error)
        raise HTTPException(503, str(error)) from error
    except Exception as error:
        logger.exception("Background removal provider failed for %s", pet_id)
        raise HTTPException(503, "Background removal failed. Try a simpler background or keep the original image.") from error
    generated = provider.name != "mock"
    if generated:
        cartoon_sprite = cartoonize_png(processed)
        storage.save(pet_id, "cutout.png", processed)
        storage.save(pet_id, "character.png", cartoon_sprite)
        pet["processed_image"] = "character.png"
    else:
        pet["processed_image"] = None
    pet["config"]["appearance"]["sprite"] = "character.png"
    pet["config"]["appearance"]["model"] = None
    remove_derived_file(pet_id, "model.glb")
    pet["updated_at"] = repository.now()
    persist_pet(pet)
    result = BackgroundRemovalResult(
        status="processed" if generated else "not_generated",
        provider=provider.name,
        imageUrl=f"/api/pets/{pet_id}/image?kind={'processed' if generated else 'original'}",
        width=width,
        height=height,
        note=("本地人物分割与漫画风格处理已完成，原图和透明抠图均已保留，图片未发送到云端。" if generated else "当前使用 Mock Provider，未执行真实背景移除。"),
    )
    return success(result.model_dump())


@app.post("/api/pets/{pet_id}/restore-original")
def restore_original(pet_id: str) -> dict[str, Any]:
    pet = get_pet_or_404(pet_id)
    file_name = pet.get("original_image")
    if not file_name or not RANDOM_IMAGE_PATTERN.fullmatch(file_name):
        raise HTTPException(409, "No original image is available")
    original = (storage.pet_directory(pet_id) / file_name).resolve()
    if not original.is_relative_to(storage.root) or not original.is_file():
        raise HTTPException(404, "Original image not found")
    pet["processed_image"] = None
    pet["config"]["appearance"]["sprite"] = "character.png"
    pet["config"]["appearance"]["model"] = None
    pet["updated_at"] = repository.now()
    persist_pet(pet)
    processed_path = (storage.pet_directory(pet_id) / "character.png").resolve()
    if processed_path.is_relative_to(storage.root) and processed_path.exists():
        processed_path.unlink()
    cutout_path = (storage.pet_directory(pet_id) / "cutout.png").resolve()
    if cutout_path.is_relative_to(storage.root) and cutout_path.exists():
        cutout_path.unlink()
    remove_derived_file(pet_id, "model.glb")
    return {"data": {"restored": True}, "error": None}


@app.get("/api/pets/{pet_id}/image")
def get_image(pet_id: str, kind: Literal["original", "processed"] = "processed") -> FileResponse:
    pet = get_pet_or_404(pet_id)
    file_name = pet["processed_image"] if kind == "processed" else pet["original_image"]
    if not file_name:
        raise HTTPException(404, "Image not found")
    valid_name = file_name == "character.png" if kind == "processed" else bool(RANDOM_IMAGE_PATTERN.fullmatch(file_name))
    if not valid_name:
        raise HTTPException(404, "Image not found")
    path = (storage.pet_directory(pet_id) / file_name).resolve()
    if not path.is_relative_to(storage.root) or not path.is_file():
        raise HTTPException(404, "Image not found")
    media_type = "image/png" if kind == "processed" else ALLOWED_FORMATS.get({".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".webp": "WEBP"}.get(path.suffix.lower(), ""), "application/octet-stream")
    return FileResponse(path, media_type=media_type, filename=file_name, content_disposition_type="inline")


@app.post("/api/pets/{pet_id}/generate-model")
def generate_model(pet_id: str) -> JSONResponse:
    pet = get_pet_or_404(pet_id)
    if not pet.get("processed_image"):
        raise HTTPException(409, "Run AI background removal before generating a 3D model")
    if model_provider is None:
        raise HTTPException(503, "本地 3D 生成已关闭，请将 PETFORGE_3D_PROVIDER 设为 triposr。")

    pet_directory = storage.pet_directory(pet_id)
    cutout_path = (pet_directory / "cutout.png").resolve()
    if not cutout_path.is_file():
        cutout_path = (pet_directory / "character.png").resolve()
    if not cutout_path.is_relative_to(storage.root) or not cutout_path.is_file():
        raise HTTPException(404, "Processed character image not found")
    try:
        generated_model = model_provider.generate_model(cutout_path, pet_directory)
    except ProviderUnavailableError as error:
        logger.warning("3D model provider is unavailable: %s", error)
        raise HTTPException(503, str(error)) from error
    except Exception as error:
        logger.exception("3D model generation failed for %s", pet_id)
        raise HTTPException(503, str(error) or "本地 3D 重建失败，请检查 TripoSR 日志后重试。") from error

    storage.save(pet_id, "model.glb", generated_model)
    pet["config"]["appearance"]["model"] = "model.glb"
    pet["updated_at"] = repository.now()
    persist_pet(pet)
    return success(
        ModelGenerationResult(
            status="generated",
            provider=model_provider.name,
            modelUrl=f"/api/pets/{pet_id}/model",
            note="GLB 已在本机生成。单张图片看不到的背面和细节由模型推断。",
        ).model_dump()
    )


@app.get("/api/pets/{pet_id}/model")
def get_model(pet_id: str) -> FileResponse:
    pet = get_pet_or_404(pet_id)
    if pet["config"].get("appearance", {}).get("model") != "model.glb":
        raise HTTPException(404, "3D model has not been generated")
    path = (storage.pet_directory(pet_id) / "model.glb").resolve()
    if not path.is_relative_to(storage.root) or not path.is_file():
        raise HTTPException(404, "3D model file not found")
    return FileResponse(
        path,
        media_type="model/gltf-binary",
        filename="model.glb",
        content_disposition_type="inline",
        headers={"Cache-Control": "no-store"},
    )


@app.post("/api/pets/{pet_id}/export")
def export_pet(pet_id: str) -> StreamingResponse:
    pet = get_pet_or_404(pet_id)
    if not pet.get("processed_image"):
        raise HTTPException(409, "Remove the image background before exporting")
    package_directory = storage.pet_directory(pet_id).resolve()
    sprite_relative = pet["config"].get("appearance", {}).get("sprite", "character.png")
    sprite = (package_directory / sprite_relative).resolve()
    original_sprite = package_directory / "character.png"
    if not sprite.is_relative_to(package_directory) or not sprite.is_file() or not original_sprite.is_file():
        raise HTTPException(404, "Processed character image not found")
    config = PetConfig.model_validate(pet["config"]).model_dump(exclude_none=True)
    package = io.BytesIO()
    with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("pet.json", json.dumps(config, ensure_ascii=False, indent=2))
        archive.write(original_sprite, "character.png")
        if sprite != original_sprite:
            archive.write(sprite, sprite_relative)
        for animation in config.get("animations", {}).values():
            for relative_frame in animation["frames"]:
                frame_path = (package_directory / relative_frame).resolve()
                if not frame_path.is_relative_to(package_directory) or not frame_path.is_file():
                    raise HTTPException(409, "An animation frame is missing from this pet package")
                archive.write(frame_path, relative_frame)
        cutout_path = (package_directory / "cutout.png").resolve()
        if cutout_path.is_relative_to(storage.root) and cutout_path.is_file():
            archive.write(cutout_path, "cutout.png")
        model_path = (package_directory / "model.glb").resolve()
        has_model = config["appearance"].get("model") == "model.glb" and model_path.is_relative_to(storage.root) and model_path.is_file()
        if has_model:
            archive.write(model_path, "model.glb")
        readme = "PetForge package 1.0\nOpen this folder in the PetForge Godot runtime.\n"
        animation_count = len(config.get("animations", {}))
        if animation_count:
            readme += f"Includes a comic-styled character sprite and {animation_count} packaged frame animations.\n"
        else:
            readme += "Includes a comic-styled character sprite and built-in desktop actions.\n"
        readme += "Includes a locally generated 3D model (model.glb).\n" if has_model else "Includes a transparent 2D character image (character.png).\n"
        archive.writestr("README.txt", readme)
    package.seek(0)
    return StreamingResponse(
        package,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{pet_id}.zip"'},
    )


@app.post("/api/pets/{pet_id}/launch")
def launch_pet(pet_id: str) -> JSONResponse:
    pet = get_pet_or_404(pet_id)
    if not pet.get("processed_image"):
        raise HTTPException(409, "Process a character image before launching")
    standalone_executable = os.getenv("PETFORGE_RUNTIME_EXECUTABLE", "").strip().strip('"')
    godot_executable = os.getenv("PETFORGE_GODOT_EXECUTABLE", "").strip().strip('"')
    runtime_project = from_project_root(os.getenv("PETFORGE_RUNTIME_PROJECT", "apps/desktop"))
    if standalone_executable and Path(standalone_executable).is_file():
        command = [standalone_executable, "--pet-project", str(storage.pet_directory(pet_id))]
        working_directory = Path(standalone_executable).parent
    elif godot_executable and Path(godot_executable).is_file() and runtime_project.is_dir():
        command = [godot_executable, "--path", str(runtime_project), "--", "--pet-project", str(storage.pet_directory(pet_id))]
        working_directory = runtime_project
    else:
        raise HTTPException(503, "Godot is not configured. Set PETFORGE_GODOT_EXECUTABLE to your Godot 4 executable.")
    try:
        creation_flags = 0
        if os.name == "nt":
            creation_flags = (
                subprocess.DETACHED_PROCESS
                | subprocess.CREATE_NEW_PROCESS_GROUP
            )
        runtime_log = storage.pet_directory(pet_id) / "runtime.log"
        with runtime_log.open("ab") as log_file:
            process = subprocess.Popen(
                command,
                cwd=working_directory,
                stdin=subprocess.DEVNULL,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                close_fds=True,
                creationflags=creation_flags,
            )
        try:
            process.wait(timeout=2.5)
        except subprocess.TimeoutExpired:
            logger.info("Started Godot runtime for %s (pid=%s)", pet_id, process.pid)
            return success({"started": True, "petId": pet_id, "processId": process.pid}, 202)
        log_tail = runtime_log.read_text(encoding="utf-8", errors="replace")[-1200:]
        logger.error("Godot exited during startup for %s with code %s", pet_id, process.returncode)
        detail = "桌宠程序启动后立即退出。"
        if log_tail.strip():
            detail += f"\n运行日志：{log_tail.strip()}"
        raise HTTPException(503, detail)
    except OSError as error:
        logger.exception("Could not start Godot for %s", pet_id)
        raise HTTPException(503, "Godot could not be started. Check PETFORGE_GODOT_EXECUTABLE or PETFORGE_RUNTIME_EXECUTABLE.") from error
    logger.info("Started Godot runtime for %s", pet_id)
    return success({"started": True, "petId": pet_id}, 202)


@app.delete("/api/pets/{pet_id}")
def delete_pet(pet_id: str) -> JSONResponse:
    get_pet_or_404(pet_id)
    repository.delete(pet_id)
    storage.delete_pet(pet_id)
    return success({"deleted": True, "petId": pet_id})
