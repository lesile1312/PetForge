export type InitialPosition = "left" | "right" | "random";
export type WalkFrequency = "low" | "medium" | "high";
export type PetAction = "idle" | "walk" | "sleep" | "jump" | "wave" | "happy" | "angry";

export interface PetConfig {
  version: "1.0";
  id: string;
  name: string;
  appearance: { sprite: string; model?: string | null; scale: number };
  behavior: {
    moveSpeed: number;
    idleDuration: number;
    sleepDuration: number;
    randomWalk: boolean;
    randomJump: boolean;
    autoSleep: boolean;
    draggable: boolean;
    initialPosition: InitialPosition;
    randomWalkFrequency: WalkFrequency;
  };
  window: { alwaysOnTop: boolean; mousePassthrough: boolean };
  animations?: Record<string, { file: string; fps: number; loop: boolean }>;
  personality?: Record<string, unknown>;
  voice?: Record<string, unknown>;
  skills?: string[];
  agent?: Record<string, unknown>;
}

export const defaultPetConfig = (id: string, name = "Momo"): PetConfig => ({
  version: "1.0",
  id,
  name,
  appearance: { sprite: "character.png", model: null, scale: 1 },
  behavior: {
    moveSpeed: 100,
    idleDuration: 20,
    sleepDuration: 120,
    randomWalk: true,
    randomJump: true,
    autoSleep: true,
    draggable: true,
    initialPosition: "right",
    randomWalkFrequency: "medium",
  },
  window: { alwaysOnTop: true, mousePassthrough: true },
});
