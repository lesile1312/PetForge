# Third-party notices

PetForge depends on third-party code and may download separate model weights. Each dependency and model keeps its own license and usage terms. This inventory is a starting point; packaged distributions must ship the exact notices and license texts for their pinned versions.

| Component | Project / license |
| --- | --- |
| Godot Engine | [godotengine.org/license](https://godotengine.org/license/) — MIT |
| Next.js / React | [Next.js](https://github.com/vercel/next.js) — MIT; [React](https://github.com/facebook/react) — MIT |
| FastAPI / Pydantic | [FastAPI](https://github.com/fastapi/fastapi) — MIT; [Pydantic](https://github.com/pydantic/pydantic) — MIT |
| rembg | [danielgatis/rembg](https://github.com/danielgatis/rembg) — MIT |
| BiRefNet portrait weights | [ZhengPeng7/BiRefNet-portrait](https://huggingface.co/ZhengPeng7/BiRefNet-portrait) — model card reports MIT; verify the exact ONNX conversion and revision before redistribution |
| TripoSR (optional) | [VAST-AI-Research/TripoSR](https://github.com/VAST-AI-Research/TripoSR) — MIT source; the model weights and any fetched files require separate review |
| Diffusers (optional) | [huggingface/diffusers](https://github.com/huggingface/diffusers) — Apache-2.0 |
| SDXL (optional) | [stabilityai/stable-diffusion-xl-base-1.0](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0) — CreativeML Open RAIL++-M; not bundled |
| IP-Adapter (optional) | [tencent-ailab/IP-Adapter](https://github.com/tencent-ailab/IP-Adapter) — Apache-2.0; model variants have their own model cards |

Model code, weight files, datasets, and generated images may have different terms. PetForge does not bundle large third-party weights in the source repository. Check each upstream license and model card before commercial use or redistribution. This notice is not legal advice.
