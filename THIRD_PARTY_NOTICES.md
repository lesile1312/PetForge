# Third-party notices

## Demonstration photograph

`docs/images/pet-demo/reference-photo.jpg` is a web-sized copy of the creator-provided personal reference photograph, displayed at the creator's request to demonstrate the custom character design. The source-code Apache-2.0 license does not grant rights to reuse this personal photograph. Contact the creator for permission to reuse it. The unchanged local source is retained outside the public website files.

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
| T2I-Adapter OpenPose SDXL (optional) | [TencentARC/t2i-adapter-openpose-sdxl-1.0](https://huggingface.co/TencentARC/t2i-adapter-openpose-sdxl-1.0/tree/f90998885600ed3627cedc305316edff47b8b03f) — model card reports Apache-2.0; pinned weights download locally and are not redistributed |

Model code, weight files, datasets, and generated images may have different terms. PetForge does not bundle large third-party weights in the source repository. Check each upstream license and model card before commercial use or redistribution. This notice is not legal advice.
