export type CharacterVariant = "cat" | "anime" | "person" | "plush";

const palettes: Record<CharacterVariant, { body: string; shade: string; accent: string; skin: string }> = {
  cat: { body: "#e5a56d", shade: "#bf7643", accent: "#679d8c", skin: "#f8d5b2" },
  anime: { body: "#526f8e", shade: "#314b68", accent: "#a3d5c7", skin: "#f1c7a8" },
  person: { body: "#688f80", shade: "#456b5c", accent: "#edc568", skin: "#eec3a4" },
  plush: { body: "#c68bb0", shade: "#98648f", accent: "#f2c66d", skin: "#e7b89b" },
};

export function CharacterArt({ variant = "cat", className = "" }: { variant?: CharacterVariant; className?: string }) {
  const color = palettes[variant];
  if (variant === "anime") {
    return (
      <svg className={className} viewBox="0 0 180 230" fill="none" role="img" aria-label="Anime character illustration">
        <path d="M42 88c-9-44 18-75 48-75 35 0 56 27 51 73l-11 35H47L42 88Z" fill={color.shade} />
        <path d="M59 88c0-29 14-47 33-47 24 0 36 17 36 47v18c0 24-16 40-36 40S59 130 59 106V88Z" fill={color.skin} />
        <path d="M56 95c20-12 29-24 35-38 12 21 23 31 42 37V67c0-30-18-53-45-53-30 0-46 24-43 57l11 24Z" fill={color.shade} />
        <path d="M68 105c5-4 10-4 15 0M103 105c5-4 10-4 15 0" stroke="#423d44" strokeWidth="4" strokeLinecap="round" />
        <path d="M84 129c7 5 14 5 21 0" stroke="#ca7771" strokeWidth="3" strokeLinecap="round" />
        <path d="M45 216c3-40 17-62 46-62s45 22 48 62" fill={color.body} />
        <path d="m71 156 20 25 21-25" fill={color.accent} />
        <circle cx="50" cy="115" r="9" fill={color.skin} /><circle cx="138" cy="115" r="9" fill={color.skin} />
      </svg>
    );
  }
  if (variant === "person") {
    return (
      <svg className={className} viewBox="0 0 180 230" fill="none" role="img" aria-label="Person illustration">
        <path d="M54 79c0-36 15-59 37-59 25 0 39 23 39 59v11H54V79Z" fill="#4d584d" />
        <path d="M63 82c0-25 11-39 28-39s29 14 29 39v24c0 21-12 35-29 35s-28-14-28-35V82Z" fill={color.skin} />
        <path d="M41 220c3-48 18-76 50-76s48 28 50 76" fill={color.body} />
        <path d="m73 147 18 26 20-26" fill={color.accent} />
        <path d="M74 92c4-3 8-3 12 0m17 0c4-3 8-3 12 0" stroke="#44403a" strokeWidth="3.5" strokeLinecap="round" />
        <path d="M81 121c7 5 15 5 22 0" stroke="#bb7467" strokeWidth="3" strokeLinecap="round" />
        <path d="M53 73c6-28 22-45 42-45 22 0 34 16 37 43-12-4-22-13-29-23-9 12-25 20-50 25Z" fill="#4d584d" />
      </svg>
    );
  }
  if (variant === "plush") {
    return (
      <svg className={className} viewBox="0 0 180 230" fill="none" role="img" aria-label="Plush toy illustration">
        <path d="M45 61 30 24c-2-7 4-12 10-8l34 27m32 0 34-27c7-4 13 1 10 8l-15 37" fill={color.shade} />
        <path d="M42 103c0-33 19-55 48-55s48 22 48 55v43c0 38-20 64-48 64s-48-26-48-64v-43Z" fill={color.body} />
        <ellipse cx="64" cy="116" rx="6" ry="8" fill="#3d3c40" /><ellipse cx="116" cy="116" rx="6" ry="8" fill="#3d3c40" />
        <path d="M84 131c4-4 8-4 12 0l-6 7-6-7Z" fill="#ab716d" /><path d="M90 137v9m0 0c-7 7-14 5-18 0m18 0c7 7 14 5 18 0" stroke="#7d575c" strokeWidth="3" strokeLinecap="round" />
        <path d="M60 158c10-10 50-10 60 0-5 23-15 33-30 33s-25-10-30-33Z" fill={color.skin} />
        <path d="M79 88c6-9 16-9 22 0" stroke={color.accent} strokeWidth="8" strokeLinecap="round" />
      </svg>
    );
  }
  return (
    <svg className={className} viewBox="0 0 180 230" fill="none" role="img" aria-label="Cat illustration">
      <path d="m47 74-8-42c-2-9 7-13 14-7l37 32m48 17 8-42c2-9-7-13-14-7l-37 32" fill={color.body} stroke={color.shade} strokeWidth="5" strokeLinejoin="round" />
      <path d="M36 111c0-37 22-59 54-59s54 22 54 59v37c0 40-21 65-54 65s-54-25-54-65v-37Z" fill={color.body} />
      <path d="M48 114c5-5 11-5 16 0m37 0c5-5 11-5 16 0" stroke="#3f4241" strokeWidth="4" strokeLinecap="round" />
      <path d="m84 128 6 7 6-7" fill="#bd7771" />
      <path d="M90 135v9m0 0c-8 7-15 5-18 0m18 0c8 7 15 5 18 0" stroke="#765454" strokeWidth="3" strokeLinecap="round" />
      <path d="M57 134 26 128m31 18-32 2m98-14 31-6m-31 24 32 2" stroke="#f4e6d8" strokeWidth="2.5" strokeLinecap="round" />
      <path d="M59 172c8-9 54-9 62 0-5 22-16 32-31 32s-26-10-31-32Z" fill={color.skin} />
      <path d="M82 77c5-9 11-12 18-9" stroke={color.accent} strokeWidth="7" strokeLinecap="round" />
    </svg>
  );
}
