export type CharacterVariant = "idle" | "blink" | "run-left" | "run-right";

const characterArt: Record<CharacterVariant, { src: string; label: string; width: number; height: number }> = {
  idle: { src: "/demo/idle-portrait.png", label: "安静待机", width: 160, height: 300 },
  blink: { src: "/demo/blink-portrait.png", label: "眨眼", width: 160, height: 300 },
  "run-left": { src: "/demo/run-left.png", label: "向左跑动", width: 256, height: 244 },
  "run-right": { src: "/demo/run-right.png", label: "向右跑动", width: 256, height: 244 },
};

export function CharacterArt({
  variant = "idle",
  className = "",
  alt,
}: {
  variant?: CharacterVariant;
  className?: string;
  alt?: string;
}) {
  const art = characterArt[variant];

  return (
    <img
      className={className}
      src={art.src}
      alt={alt ?? `自定义桌宠petforge卡通女孩：${art.label}`}
      width={art.width}
      height={art.height}
      draggable={false}
    />
  );
}
