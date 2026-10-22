from __future__ import annotations

import os
import json
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageOps

from .background import ProviderUnavailableError
from ..configuration import ROOT


def _orient_triposr_glb_for_y_up(model: bytes) -> bytes:
    """Rotate TripoSR's Z-up mesh into the Y-up orientation expected by glTF viewers."""
    if len(model) < 20 or model[:4] != b"glTF":
        raise RuntimeError("TripoSR 返回的模型文件不是有效的 GLB。")

    magic, version, declared_length = struct.unpack_from("<4sII", model, 0)
    if magic != b"glTF" or version != 2 or declared_length != len(model):
        raise RuntimeError("TripoSR 返回的 GLB 文件头无效。")

    chunks: list[tuple[int, bytes]] = []
    offset = 12
    document: dict | None = None
    while offset < len(model):
        if offset + 8 > len(model):
            raise RuntimeError("TripoSR 返回的 GLB 数据不完整。")
        chunk_length, chunk_type = struct.unpack_from("<II", model, offset)
        offset += 8
        chunk_end = offset + chunk_length
        if chunk_end > len(model):
            raise RuntimeError("TripoSR 返回的 GLB 数据不完整。")
        chunk = model[offset:chunk_end]
        offset = chunk_end
        chunks.append((chunk_type, chunk))
        if chunk_type == 0x4E4F534A:
            try:
                document = json.loads(chunk.rstrip(b"\x00 \t\r\n").decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise RuntimeError("TripoSR 返回的 GLB 场景信息无法读取。") from error

    if document is None or not isinstance(document.get("nodes"), list):
        raise RuntimeError("TripoSR 返回的 GLB 缺少场景节点。")
    nodes = document["nodes"]
    if not any(node.get("name") == "PetForgeYUp" for node in nodes):
        for scene in document.get("scenes", []):
            roots = scene.get("nodes", [])
            if not roots:
                continue
            wrapper_index = len(nodes)
            nodes.append(
                {
                    "name": "PetForgeYUp",
                    "rotation": [-0.5, 0.5, 0.5, 0.5],
                    "children": roots,
                }
            )
            scene["nodes"] = [wrapper_index]

    materials = document.setdefault("materials", [])
    vertex_color_material_index = next(
        (index for index, material in enumerate(materials) if material.get("name") == "PetForgeVertexColors"),
        None,
    )
    for mesh in document.get("meshes", []):
        for primitive in mesh.get("primitives", []):
            if "COLOR_0" not in primitive.get("attributes", {}) or "material" in primitive:
                continue
            if vertex_color_material_index is None:
                vertex_color_material_index = len(materials)
                materials.append(
                    {
                        "name": "PetForgeVertexColors",
                        "doubleSided": True,
                        "pbrMetallicRoughness": {
                            "baseColorFactor": [1.0, 1.0, 1.0, 1.0],
                            "metallicFactor": 0.0,
                            "roughnessFactor": 0.92,
                        },
                    }
                )
            primitive["material"] = vertex_color_material_index

    rebuilt_chunks: list[bytes] = []
    for chunk_type, chunk in chunks:
        if chunk_type == 0x4E4F534A:
            chunk = json.dumps(document, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            chunk += b" " * (-len(chunk) % 4)
        rebuilt_chunks.append(struct.pack("<II", len(chunk), chunk_type) + chunk)

    total_length = 12 + sum(map(len, rebuilt_chunks))
    return struct.pack("<4sII", b"glTF", 2, total_length) + b"".join(rebuilt_chunks)


class TripoSRModelProvider:
    """Run the official TripoSR single-image reconstruction locally."""

    name = "triposr-local"
    MC_RESOLUTION = 192

    def __init__(self) -> None:
        repository = Path(os.getenv("PETFORGE_TRIPOSR_REPO") or ROOT / ".tools" / "TripoSR").expanduser()
        python = Path(os.getenv("PETFORGE_TRIPOSR_PYTHON") or sys.executable).expanduser()
        pretrained_model = os.getenv("PETFORGE_TRIPOSR_MODEL", "").strip()
        self.repository = (repository if repository.is_absolute() else ROOT / repository).resolve()
        self.python = (python if python.is_absolute() else ROOT / python).resolve()
        self.pretrained_model = (
            Path(pretrained_model).expanduser()
            if pretrained_model
            else None
        )
        if self.pretrained_model is not None and not self.pretrained_model.is_absolute():
            self.pretrained_model = (ROOT / self.pretrained_model).resolve()
        self.timeout = max(120, int(os.getenv("PETFORGE_TRIPOSR_TIMEOUT_SECONDS", "1200")))

    def availability_error(self) -> str | None:
        if not (self.repository / "run.py").is_file():
            return "本地 3D 生成环境尚未安装。请在项目目录运行 scripts/setup-ai.ps1。"
        if not self.python.is_file():
            return "找不到 TripoSR 的 Python 环境。请检查 .env 中的 PETFORGE_TRIPOSR_PYTHON。"
        if self.pretrained_model is not None and not all(
            (self.pretrained_model / filename).is_file()
            for filename in ("config.yaml", "model.ckpt")
        ):
            return "本地 TripoSR 权重尚未下载。请在项目目录运行 scripts/setup-ai.ps1。"
        return None

    def generate_model(self, cutout_path: Path, pet_directory: Path) -> bytes:
        problem = self.availability_error()
        if problem:
            raise ProviderUnavailableError(problem)
        if not cutout_path.is_file():
            raise FileNotFoundError("The transparent character image is missing.")

        with tempfile.TemporaryDirectory(prefix=".triposr-", dir=pet_directory) as temporary:
            work = Path(temporary)
            input_path = work / "input.png"
            output_directory = work / "output"
            (output_directory / "0").mkdir(parents=True, exist_ok=True)
            log_path = pet_directory / "triposr.log"
            with Image.open(cutout_path) as opened:
                cutout = ImageOps.exif_transpose(opened).convert("RGBA")
                matte_background = Image.new("RGBA", cutout.size, (127, 127, 127, 255))
                matte_background.alpha_composite(cutout)
                matte_background.convert("RGB").save(input_path, format="PNG")

            command = [
                str(self.python),
                str(self.repository / "run.py"),
                str(input_path),
                "--output-dir",
                str(output_directory),
                "--model-save-format",
                "glb",
                "--pretrained-model-name-or-path",
                str(self.pretrained_model or "stabilityai/TripoSR"),
                "--no-remove-bg",
                "--device",
                "cuda:0",
                "--mc-resolution",
                str(self.MC_RESOLUTION),
            ]
            environment = os.environ.copy()
            environment.setdefault("HF_HOME", str(Path.home() / ".cache" / "huggingface"))
            with log_path.open("wb") as log_file:
                try:
                    completed = subprocess.run(
                        command,
                        cwd=self.repository,
                        env=environment,
                        stdout=log_file,
                        stderr=subprocess.STDOUT,
                        timeout=self.timeout,
                        check=False,
                    )
                except subprocess.TimeoutExpired as error:
                    raise RuntimeError(
                        f"TripoSR 3D 生成超过 {self.timeout // 60} 分钟。检查显卡状态后可以重试。"
                    ) from error

            result_path = output_directory / "0" / "mesh.glb"
            if completed.returncode != 0 or not result_path.is_file():
                log_tail = log_path.read_text(encoding="utf-8", errors="replace")[-1600:]
                detail = "\n".join(line for line in log_tail.splitlines() if line.strip())
                raise RuntimeError(
                    "TripoSR 本地三维重建失败。请检查显卡显存与安装状态。"
                    + (f"\n{detail}" if detail else "")
                )

            model = result_path.read_bytes()
            if len(model) < 1024 or model[:4] != b"glTF":
                raise RuntimeError("TripoSR 返回的模型文件不是有效的 GLB。")
            return _orient_triposr_glb_for_y_up(model)
