import type { ReactNode } from "react";

type IconName = "mark" | "upload" | "image" | "spark" | "arrow" | "check" | "download" | "play" | "undo" | "plus" | "close" | "save" | "moon" | "mouse" | "pin" | "speed" | "layers" | "folder" | "clock" | "sun";

const paths: Record<IconName, ReactNode> = {
  mark: <><path d="M12 3.5 20.5 8v8L12 20.5 3.5 16V8L12 3.5Z" /><path d="m8.5 10.5 3.5-2 3.5 2v4L12 16.5l-3.5-2v-4Z" /></>,
  upload: <><path d="M12 16V4m0 0L7.5 8.5M12 4l4.5 4.5" /><path d="M4 15.5v3A1.5 1.5 0 0 0 5.5 20h13a1.5 1.5 0 0 0 1.5-1.5v-3" /></>,
  image: <><rect x="3.5" y="4" width="17" height="16" rx="2.5" /><circle cx="9" cy="9.5" r="1.5" /><path d="m5 17 5-4 3 2 3-3 4 4" /></>,
  spark: <><path d="m12 3 1.8 6.2L20 11l-6.2 1.8L12 19l-1.8-6.2L4 11l6.2-1.8L12 3Z" /><path d="m19 15 .8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8L19 15Z" /></>,
  arrow: <><path d="M5 12h14M13 6l6 6-6 6" /></>,
  check: <path d="m5 12 4.5 4.5L19 7" />,
  download: <><path d="M12 4v11m0 0 4-4m-4 4-4-4" /><path d="M4 18v2h16v-2" /></>,
  play: <path d="m9 6 10 6-10 6V6Z" />,
  undo: <><path d="M9 14 4 9l5-5" /><path d="M4 9h9a6 6 0 0 1 0 12h-2" /></>,
  plus: <path d="M12 5v14M5 12h14" />,
  close: <path d="m6 6 12 12M18 6 6 18" />,
  save: <><path d="M5 4h12l3 3v13H4V4h1Z" /><path d="M8 4v6h8V4m-8 16v-6h8v6" /></>,
  moon: <path d="M19 14.5A7.5 7.5 0 0 1 9.5 5 8 8 0 1 0 19 14.5Z" />,
  mouse: <><rect x="6" y="3" width="12" height="18" rx="6" /><path d="M12 3v6m-6 0h12" /></>,
  pin: <><path d="m16 4 4 4-3 1-4 4v5l-2 2-2-6-6-2 2-2h5l4-4 2-2Z" /><path d="m5 19 4-4" /></>,
  speed: <><path d="M4 17a8 8 0 1 1 16 0" /><path d="m12 13 4-4m-9 9h10" /></>,
  layers: <><path d="m12 3 9 5-9 5-9-5 9-5Z" /><path d="m3 12 9 5 9-5M3 16l9 5 9-5" /></>,
  folder: <><path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z" /></>,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  sun: <><circle cx="12" cy="12" r="4" /><path d="M12 2v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></>,
};

export function Icon({ name, size = 18, className }: { name: IconName; size?: number; className?: string }) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {paths[name]}
    </svg>
  );
}
