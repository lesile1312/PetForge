from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable
from pathlib import Path

from PIL import Image, ImageDraw

from ..device import DeviceProfile
from .base import CancelToken, GenerationCancelled, PortraitCandidate, PortraitRequest, ProviderError


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _build_portrait_prompts(request: PortraitRequest) -> tuple[str, str, str, str]:
    style = {
        "warm_chibi": "2D hand-drawn kawaii chibi, large head, small body, warm pastels, clean line art",
        "lively_chibi": (
            "2D hand-drawn kawaii chibi, large head, small body, bright pastels, lively eyes, clean line art"
        ),
    }.get(request.style_preset, "2D hand-drawn kawaii chibi cartoon, warm pastels, clean line art")
    clothing = f", keep outfit colors and details: {request.clothing_description}" if request.clothing_description else ""
    prompt = (
        f"cute 2D chibi of same person; keep face, hair, skin and outfit colors; {style}{clothing}"
    )
    pose = request.pose_description or "front-facing neutral upright standing pose, arms at sides, legs straight"
    prompt_2 = f"{style}, full body, {pose}, hands and feet visible, centered with margin, cream background"
    negative = "photorealistic, photograph, realistic skin, adult proportions, 3D, text, watermark"
    negative_2 = (
        "photorealistic, photograph, realistic skin, cropped, close-up, out of frame, multiple people, "
        "extra limbs, fused hands, missing feet, blur"
    )
    if request.pose_description is None or "idle" in request.pose_description.casefold():
        negative_2 += ", raised leg, crossed legs, kneeling, sitting, reaching, dancing"
    return prompt, prompt_2, negative, negative_2


class DeterministicFakePortraitGenerator:
    model_id = "fake-portrait-v1"

    def __init__(self, seed: int = 17):
        self.seed = seed

    def generate(
        self, request: PortraitRequest, device: DeviceProfile, output_dir: Path, cancel: CancelToken | None = None
    ) -> PortraitCandidate:
        del device
        if cancel:
            cancel.check()
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        with Image.open(request.source_path) as source_file:
            source = source_file.convert("RGBA")
        source.thumbnail((384, 512), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (384, 512), (0, 0, 0, 0))
        x = (canvas.width - source.width) // 2
        y = (canvas.height - source.height) // 2
        canvas.alpha_composite(source, (x, y))
        # Add a small reproducible shape only so tests can prove deterministic output.
        ImageDraw.Draw(canvas).ellipse((8, 8, 16, 16), fill=(self.seed % 255, 120, 180, 255))
        source.close()
        image_path, mask_path = output / "candidate.png", output / "mask.png"
        canvas.save(image_path, format="PNG", optimize=False)
        canvas.getchannel("A").save(mask_path, format="PNG", optimize=False)
        provenance = {
            "generator_kind": "deterministic_fake",
            "model_id": self.model_id,
            "seed": self.seed,
            "source_reference_sha256": _sha256(request.source_path),
            "inferred_regions": list(request.inferred_regions),
            "style_preset": request.style_preset,
        }
        (output / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
        canvas.close()
        return PortraitCandidate(image_path, mask_path, request.inferred_regions, provenance)


class LocalSDXLPortraitGenerator:
    """Reference-conditioned SDXL portrait generator with local-only model loading."""

    model_id = "sdxl-base-ipadapter-t2i-openpose-birefnet-p0"
    model_evidence = {
        "model_revision": "p0-2026-10-29-pose-v2",
        "licenses": [
            {
                "component_id": "sdxl-base-1.0",
                "license_name": "CreativeML Open RAIL++-M",
                "terms_url": "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/blob/bf714989e22c57ddc1c453bf74dab4521acb81d8/LICENSE.md",
                "weights_redistributable": False,
            },
            {
                "component_id": "ip-adapter-plus-sdxl-vit-h",
                "license_name": "Apache-2.0",
                "terms_url": "https://github.com/tencent-ailab/IP-Adapter/blob/main/LICENSE",
                "weights_redistributable": True,
            },
            {
                "component_id": "t2i-adapter-openpose-sdxl-1.0",
                "license_name": "Apache-2.0",
                "terms_url": "https://huggingface.co/TencentARC/t2i-adapter-openpose-sdxl-1.0",
                "weights_redistributable": True,
            },
            {
                "component_id": "birefnet-portrait-cutout",
                "license_name": "MIT",
                "terms_url": "https://huggingface.co/ZhengPeng7/BiRefNet-portrait/blob/main/LICENSE",
                "weights_redistributable": True,
            },
            {
                "component_id": "mediapipe-pose-full",
                "license_name": "Apache-2.0",
                "terms_url": "https://github.com/google-ai-edge/mediapipe/blob/master/LICENSE",
                "weights_redistributable": True,
            },
        ],
    }

    def __init__(
        self,
        model_root: Path,
        output_masker: Callable[[Image.Image], Image.Image],
        *,
        device_mode: str = "auto",
        steps: int = 24,
        width: int = 768,
        height: int = 1024,
        ip_adapter_scale: float = 0.30,
    ):
        if device_mode not in {"auto", "cpu", "cuda"}:
            raise ValueError("invalid_device_mode")
        if steps < 1 or width < 256 or height < 256:
            raise ValueError("invalid_generation_settings")
        self.model_root = Path(model_root)
        self.output_masker = output_masker
        self.device_mode = device_mode
        self.steps = steps
        self.width = width
        self.height = height
        self.ip_adapter_scale = ip_adapter_scale
        self._pipeline = None
        self.peak_gpu_memory_bytes = 0

    def _load(self, device: DeviceProfile):
        if self._pipeline is not None:
            return self._pipeline

        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
        os.environ["DIFFUSERS_VERBOSITY"] = "error"
        checkpoint = self.model_root / "sdxl" / "sd_xl_base_1.0.safetensors"
        config_dir = self.model_root / "sdxl-config"
        adapter_root = self.model_root / "ip-adapter"
        encoder_dir = adapter_root / "models" / "image_encoder"
        adapter_file = adapter_root / "sdxl_models" / "ip-adapter-plus_sdxl_vit-h.safetensors"
        pose_adapter_root = self.model_root / "t2i-adapter" / "openpose"
        required = (
            checkpoint,
            config_dir / "model_index.json",
            encoder_dir / "config.json",
            encoder_dir / "model.safetensors",
            adapter_file,
            pose_adapter_root / "config.json",
            pose_adapter_root / "diffusion_pytorch_model.safetensors",
        )
        if any(not path.is_file() for path in required):
            raise ProviderError("portrait_model_files_missing")

        import torch
        from diffusers import StableDiffusionXLAdapterPipeline, T2IAdapter
        from transformers import CLIPVisionModelWithProjection

        use_cuda = self.device_mode == "cuda" or (
            self.device_mode == "auto" and device.gpu_name is not None and torch.cuda.is_available()
        )
        if self.device_mode == "cuda" and not torch.cuda.is_available():
            raise ProviderError("cuda_runtime_unavailable")
        runtime_device = "cuda" if use_cuda else "cpu"
        dtype = torch.float16 if use_cuda else torch.float32

        try:
            pose_adapter = T2IAdapter.from_pretrained(
                str(pose_adapter_root), torch_dtype=dtype, local_files_only=True
            )
            image_encoder = CLIPVisionModelWithProjection.from_pretrained(
                str(encoder_dir), torch_dtype=dtype, local_files_only=True
            )
            pipeline = StableDiffusionXLAdapterPipeline.from_single_file(
                str(checkpoint),
                config=str(config_dir),
                torch_dtype=dtype,
                use_safetensors=True,
                local_files_only=True,
                adapter=pose_adapter,
                image_encoder=image_encoder,
                add_watermarker=False,
            )
            pipeline.load_ip_adapter(
                str(adapter_root),
                subfolder="sdxl_models",
                image_encoder_folder=None,
                weight_name=adapter_file.name,
                local_files_only=True,
            )
            pipeline.set_ip_adapter_scale(self.ip_adapter_scale)
            if use_cuda:
                pipeline.enable_model_cpu_offload()
                pipeline.adapter.to("cuda")
            else:
                pipeline.to("cpu")
            pipeline.enable_vae_slicing()
            pipeline.enable_vae_tiling()
        except ProviderError:
            raise
        except Exception as error:
            raise ProviderError("portrait_model_load_failed") from error
        self._pipeline = pipeline
        self._runtime_device = runtime_device
        self._dtype = str(dtype).replace("torch.", "")
        return pipeline

    def generate(
        self, request: PortraitRequest, device: DeviceProfile, output_dir: Path, cancel: CancelToken | None = None
    ) -> PortraitCandidate:
        if request.pose_control_image is not None and not Path(request.pose_control_image).is_file():
            raise ProviderError("pose_control_image_missing")
        pipeline = self._load(device)
        import torch
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        with Image.open(request.source_path) as source_file:
            source_rgba = source_file.convert("RGBA")
            background = Image.new("RGBA", source_rgba.size, (255, 249, 244, 255))
            background.alpha_composite(source_rgba)
            reference = background.convert("RGB")
            background.close()
            source_rgba.close()
        if request.pose_control_image is not None:
            with Image.open(request.pose_control_image) as control_file:
                pose_control = control_file.convert("RGB")
            pose_conditioning_scale = 1.0
        else:
            pose_control = Image.new("RGB", (self.width, self.height), (0, 0, 0))
            pose_conditioning_scale = 0.0

        prompt, prompt_2, negative, negative_2 = _build_portrait_prompts(request)
        for text, tokenizer in (
            (prompt, pipeline.tokenizer),
            (prompt_2, pipeline.tokenizer_2),
            (negative, pipeline.tokenizer),
            (negative_2, pipeline.tokenizer_2),
        ):
            if len(tokenizer.encode(text, add_special_tokens=True)) > tokenizer.model_max_length:
                raise ProviderError("portrait_prompt_too_long")
        generator_device = self._runtime_device
        random = torch.Generator(device=generator_device).manual_seed(int(request.seed))
        if self._runtime_device == "cuda":
            torch.cuda.reset_peak_memory_stats()

        def check_cancel(_step, _timestep, _latents):
            if cancel:
                cancel.check()

        try:
            result = pipeline(
                prompt=prompt,
                prompt_2=prompt_2,
                negative_prompt=negative,
                negative_prompt_2=negative_2,
                image=pose_control,
                ip_adapter_image=reference,
                width=self.width,
                height=self.height,
                num_inference_steps=self.steps,
                guidance_scale=7.0,
                adapter_conditioning_scale=pose_conditioning_scale,
                generator=random,
                callback=check_cancel if cancel else None,
                callback_steps=1,
            )
            if self._runtime_device == "cuda":
                self.peak_gpu_memory_bytes = int(torch.cuda.max_memory_reserved())
            generated = result.images[0].convert("RGB")
            alpha = self.output_masker(generated).convert("L")
            if alpha.size != generated.size or alpha.getbbox() is None:
                raise ProviderError("generated_cutout_invalid")
            candidate_image = generated.convert("RGBA")
            candidate_image.putalpha(alpha)
            image_path, mask_path = output / "candidate.png", output / "mask.png"
            candidate_image.save(image_path, format="PNG", optimize=False)
            alpha.save(mask_path, format="PNG", optimize=False)
            provenance = {
                "generator_kind": "local_sdxl_ip_adapter",
                "model_id": self.model_id,
                "seed": int(request.seed),
                "base_revision": "bf714989e22c57ddc1c453bf74dab4521acb81d8",
                "adapter_revision": "9bf28b38530e55ffa91c6d82e5161a982c22f284",
                "pose_adapter_revision": "f90998885600ed3627cedc305316edff47b8b03f",
                "runtime_device": self._runtime_device,
                "runtime_dtype": self._dtype,
                "inference_steps": self.steps,
                "canvas_size": [self.width, self.height],
                "ip_adapter_scale": self.ip_adapter_scale,
                "pose_conditioning_scale": pose_conditioning_scale,
                "pose_control_sha256": _sha256(request.pose_control_image) if request.pose_control_image else None,
                "source_reference_sha256": _sha256(request.source_path),
                "inferred_regions": list(request.inferred_regions),
                "style_preset": request.style_preset,
            }
            (output / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
            return PortraitCandidate(image_path, mask_path, request.inferred_regions, provenance)
        except ProviderError:
            raise
        except Exception as error:
            raise ProviderError("portrait_generation_failed") from error
        finally:
            pose_control.close()
            reference.close()
            try:
                generated.close()
            except UnboundLocalError:
                pass
            try:
                alpha.close()
            except UnboundLocalError:
                pass
            try:
                candidate_image.close()
            except UnboundLocalError:
                pass
