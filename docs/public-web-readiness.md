# Public web readiness

The creator flow now talks to FastAPI through the Next.js `/api/*` proxy. The browser uses same-origin URLs, so a deployed site does not send visitors to their own `localhost`. Configure `PETFORGE_API_ORIGIN` in the Next.js server environment to the FastAPI origin.

## Desktop launch behavior

- Development mode defaults to `PETFORGE_RUNTIME_MODE=local`, auto-launches Godot after local portrait processing, and keeps a manual launch button in the editor.
- Production defaults to `PETFORGE_RUNTIME_MODE=package`. Visitors can download the generated image/model resource package; the website does not try to launch a process on the web server.
- The exported ZIP contains pet configuration, the comic sprite, its transparent cutout, and a GLB when 3D generation succeeds. It is not a standalone Windows installer. Visitors need a packaged PetForge desktop runtime before they can run the pet on their own desktop.

## Before opening the service to the public

The current API is a local-development service with SQLite and disk storage. A public deployment needs a persistent API host with enough CPU/GPU capacity for image segmentation and TripoSR, persistent storage, request limits and cleanup for abandoned uploads, and a user-facing deletion/retention policy. The API currently has no account system or per-user quota. Do not expose the development API as a public service until those operational controls and the photo-handling policy are in place.

Even with an online API, a single photograph only provides a front-facing view; hidden sides and geometry in the generated 3D model are inferred. The browser preview and the native desktop runtime are separate steps.
