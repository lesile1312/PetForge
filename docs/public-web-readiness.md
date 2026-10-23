# Public web readiness

## GitHub Pages reference handoff

The static showcase in `docs/index.html` can select and decode a local photo, display it without cropping, clear it, and save a `.petforge.json` reference file. No photo upload request is made. The downloaded file embeds the original photo and should be treated as private image data.

The local Next.js editor accepts that reference file through its upload picker, validates its envelope/type/size, and feeds the extracted original into the existing API flow. The editor displays original and processed images together. The public page links to the local editor only after explaining that it must first be installed and started. This handoff does not add cloud inference or generative cartoon redrawing; the current processing step remains segmentation plus a comic filter.

At the creator's explicit request, a web-sized copy of the original demonstration photograph is included at `docs/images/pet-demo/reference-photo.jpg`, beside the custom cartoon character. This fixed example is separate from visitor uploads. A visitor's selected image remains a temporary browser preview and is not persisted on the website.

The creator flow now talks to FastAPI through the Next.js `/api/*` proxy. The browser uses same-origin URLs, so a deployed site does not send visitors to their own `localhost`. Configure `PETFORGE_API_ORIGIN` in the Next.js server environment to the FastAPI origin.

## Desktop launch behavior

- Development mode defaults to `PETFORGE_RUNTIME_MODE=local`. Local portrait processing stops at the review screen; users explicitly launch Godot after checking the original and processed image. Optional 3D generation is requested separately.
- Production defaults to `PETFORGE_RUNTIME_MODE=package`. Visitors can download the generated image/model resource package; the website does not try to launch a process on the web server.
- The exported ZIP contains pet configuration, the comic sprite, its transparent cutout, and a GLB when 3D generation succeeds. It is not a standalone Windows installer. Visitors need a packaged PetForge desktop runtime before they can run the pet on their own desktop.

## Before opening the service to the public

The current API is a local-development service with SQLite and disk storage. A public deployment needs a persistent API host with enough CPU/GPU capacity for image segmentation and TripoSR, persistent storage, request limits and cleanup for abandoned uploads, and a user-facing deletion/retention policy. The API currently has no account system or per-user quota. Do not expose the development API as a public service until those operational controls and the photo-handling policy are in place.

Even with an online API, a single photograph only provides a front-facing view; hidden sides and geometry in the generated 3D model are inferred. The browser preview and the native desktop runtime are separate steps.
