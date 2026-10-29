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

`character.png` is the transparent sprite shown by the web preview. The desktop runtime uses the file named by `appearance.sprite`, which can be a padded canvas that keeps full action frames inside the transparent window. `cutout.png` is optional and preserves the unfiltered transparent segmentation for 3D reconstruction. `model.glb`, when present, is a separate static 3D preview.

Optional `animations` maps action names to PNG frame paths inside the package. Each action has an explicit frame rate and loop setting. Paths must stay inside the package.

```json
"animations": {
  "wave": {
    "frames": ["animations/wave/wave_000.png", "animations/wave/wave_001.png"],
    "fps": 60,
    "loop": false
  }
}
```

The runtime plays these frames for matching actions. It uses the built-in procedural pose when a package does not provide frames for an action.

`packages/pet-schema/schemas/pet.schema.json` is the JSON Schema contract. The API additionally validates with Pydantic. Runtime and animation fields have explicit version-compatible defaults.
