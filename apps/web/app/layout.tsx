import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "PetForge — 把一张照片变成桌面伙伴",
  description: "上传一张照片，本机抠图并转成漫画风格，试动作后启动桌面宠物。",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
