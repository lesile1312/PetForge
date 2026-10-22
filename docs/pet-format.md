# Pet Package Format

A package contains `pet.json` and the image paths it references. `version` is mandatory. Unknown future extension objects (`animations`, `personality`, `voice`, `skills`, `agent`) may be added without changing the identity and appearance fields.

```json
{
  "version": "1.0",
  "id": "pet_0123456789abcdef0123456789abcdef",
  "name": "Momo",
  "appearance": { "sprite": "character.png", "scale": 1.0 },
  "behavior": {
    "moveSpeed": 100,
    "idleDuration": 20,
    "sleepDuration": 120,
    "randomWalk": true,
    "randomJump": true,
    "autoSleep": true,
    "draggable": true,
    "initialPosition": "right",
    "randomWalkFrequency": "medium"
  },
  "window": { "alwaysOnTop": true, "mousePassthrough": true }
}
```

`character.png` is the transparent comic-style sprite that the web preview and 2D desktop runtime use. `cutout.png` is optional and preserves the unfiltered transparent segmentation for 3D reconstruction. The desktop actions are built into the runtime, so a package does not need generated animation sheets. `model.glb`, when present, is a separate static 3D preview.

`packages/pet-schema/schemas/pet.schema.json` is the JSON Schema contract. The API additionally validates with Pydantic. Runtime and animation fields have explicit version-compatible defaults.
