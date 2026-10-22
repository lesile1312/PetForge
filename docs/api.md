# API

All JSON responses use `{ "data": ..., "error": null }`. Errors use `{ "data": null, "error": { "code": ..., "message": ... } }`.

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/api/pets` | List projects |
| POST | `/api/pets` | Create project |
| GET | `/api/pets/{id}` | Read project and config |
| PATCH | `/api/pets/{id}` | Update supported config fields |
| POST | `/api/pets/{id}/image` | Upload PNG/JPEG/WEBP (10 MB max) |
| POST | `/api/pets/{id}/remove-background` | Process source into cropped RGBA PNG |
| POST | `/api/pets/{id}/restore-original` | Clear the processed cutout and return to the source image |
| POST | `/api/pets/{id}/export` | Download ZIP package |
| POST | `/api/pets/{id}/launch` | Start local Godot runtime when configured |
| DELETE | `/api/pets/{id}` | Remove project and files |

`/health` reports service readiness. Open `/docs` for interactive OpenAPI documentation during development. AI animation generation is an explicit provider stub returning `not_generated`.
