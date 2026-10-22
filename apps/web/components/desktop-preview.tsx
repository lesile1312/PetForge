"use client";

import type { MouseEvent as ReactMouseEvent, PointerEvent as ReactPointerEvent } from "react";
import { createElement, useEffect, useRef, useState } from "react";
import type { PetConfig } from "@petforge/pet-schema";
import { CharacterArt } from "@/components/character-art";
import { Icon } from "@/components/icons";

interface DesktopPreviewProps {
  config: PetConfig;
  imageSrc: string | null;
  modelSrc: string | null;
}

export function DesktopPreview({ config, imageSrc, modelSrc }: DesktopPreviewProps) {
  const screenRef = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState({ x: 77, y: 55 });
  const [dragging, setDragging] = useState(false);
  const dragRef = useRef<{ pointerId: number } | null>(null);
  const modelViewerRef = useRef<HTMLElement | null>(null);
  const [modelViewerReady, setModelViewerReady] = useState(false);
  const [previewAction, setPreviewAction] = useState("idle");
  const [actionRun, setActionRun] = useState(0);
  const [showModel, setShowModel] = useState(false);
  const actionTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const show3d = showModel && Boolean(modelSrc);
  const size = Math.round(126 * config.appearance.scale);

  useEffect(() => {
    if (!show3d || !modelSrc || modelViewerReady) return;
    let active = true;
    void import("@google/model-viewer").then(() => {
      if (active) setModelViewerReady(true);
    });
    return () => { active = false; };
  }, [show3d, modelSrc, modelViewerReady]);

  useEffect(() => {
    const viewer = modelViewerRef.current;
    if (!viewer || !show3d || !modelSrc || !modelViewerReady) return;
    if (viewer.getAttribute("src") !== modelSrc) viewer.setAttribute("src", modelSrc);
    viewer.setAttribute("exposure", "1.35");
  }, [show3d, modelSrc, modelViewerReady]);

  useEffect(() => () => {
    if (actionTimer.current) clearTimeout(actionTimer.current);
  }, []);

  function triggerAction(action: string) {
    setShowModel(false);
    setPreviewAction(action);
    setActionRun((run) => run + 1);
    if (actionTimer.current) clearTimeout(actionTimer.current);
    if (action !== "idle") {
      actionTimer.current = setTimeout(() => setPreviewAction("idle"), action === "sleep" ? 4200 : 2500);
    }
  }

  function onPetContextMenu(event: ReactMouseEvent<HTMLDivElement>) {
    event.preventDefault();
    const actions = ["spin", "stretch", "dance"];
    const current = actions.indexOf(previewAction);
    triggerAction(actions[(current + 1) % actions.length]);
  }

  function onPointerDown(event: ReactPointerEvent<HTMLDivElement>) {
    if (event.button !== 0) return;
    if (show3d && event.target instanceof Element && event.target.closest("model-viewer")) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    dragRef.current = { pointerId: event.pointerId };
    setDragging(true);
  }

  function onPointerMove(event: ReactPointerEvent<HTMLDivElement>) {
    const screen = screenRef.current?.getBoundingClientRect();
    if (!dragRef.current || !screen) return;
    const x = ((event.clientX - screen.left) / screen.width) * 100;
    const y = ((event.clientY - screen.top) / screen.height) * 100;
    setPosition({ x: Math.min(94, Math.max(6, x)), y: Math.min(78, Math.max(14, y)) });
  }

  function onPointerUp(event: ReactPointerEvent<HTMLDivElement>) {
    if (!dragRef.current) return;
    dragRef.current = null;
    setDragging(false);
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
  }

  return (
    <section className="preview-card" aria-label="桌面预览">
      <div className="preview-card-heading"><div><span className="section-eyebrow">桌面预览</span><h2>看看它生活在这里</h2></div><span className="resolution-pill">Windows · 16:9</span></div>
      <div className="desktop-window" ref={screenRef}>
        <div className="wallpaper-glow" />
        <div className="wallpaper-ring wallpaper-ring-a" /><div className="wallpaper-ring wallpaper-ring-b" />
        <div className="wallpaper-line" />
        <div className="desktop-file desktop-file-one"><span className="file-icon file-folder"><Icon name="folder" size={18} /></span><small>我的文件</small></div>
        <div className="desktop-file desktop-file-two"><span className="file-icon file-notes"><Icon name="image" size={18} /></span><small>灵感参考</small></div>
        <div className="desktop-file desktop-file-three"><span className="file-icon file-cyan"><Icon name="layers" size={18} /></span><small>未命名.png</small></div>
        <div
          className={`preview-character${show3d ? " is-model" : ""}${dragging ? " is-dragging" : ""}`}
          data-action={previewAction}
          style={{ left: `${position.x}%`, top: `${position.y}%`, width: show3d ? 218 : size, height: show3d ? 258 : undefined }}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onLostPointerCapture={onPointerUp}
          onContextMenu={onPetContextMenu}
          role="img"
          aria-label={`${config.name}，当前动作：${actionLabels[previewAction] ?? "待机"}，可拖动；右键切换动作`}
        >
          <div key={actionRun} className={`preview-avatar-motion action-${previewAction}`}>
            {show3d && modelViewerReady && modelSrc
              ? createElement("model-viewer", { ref: modelViewerRef, src: modelSrc, alt: `${config.name} 的 3D 模型`, "camera-controls": "", "camera-orbit": "180deg 75deg 90%", "environment-image": "neutral", "shadow-intensity": "0.35", "interaction-prompt": "none", exposure: "1.35" })
              : imageSrc ? <img src={imageSrc} alt="" draggable={false} /> : <CharacterArt variant="cat" />}
          </div>
          {previewAction !== "idle" && <span className="preview-reaction" aria-hidden="true">{actionLabels[previewAction]}</span>}
          <span className="preview-name-tag">{config.name || "新伙伴"}</span>
        </div>
        <div className="preview-hint"><Icon name="mouse" size={14} /> 拖动它，或右键转圈、伸懒腰</div>
        <div className="windows-taskbar">
          <span className="taskbar-logo"><i /><i /><i /><i /></span>
          <span className="taskbar-searchbar"><Icon name="image" size={14} /><small>搜索</small></span>
          <span className="taskbar-apps"><b className="app-window" /><b className="app-mail" /><b className="app-folder" /><b className="app-browser" /></span>
          <span className="taskbar-tray"><i /><i /><i /></span>
          <span className="taskbar-time">09:41<br />2026/10/07</span>
        </div>
      </div>
      <div className="pet-action-panel">
        <div className="pet-action-heading">
          <span>{show3d ? "3D 单图模型" : "点动作，看看它怎么回应"}</span>
          {modelSrc && <div className="preview-mode-switch" role="group" aria-label="预览类型">
            <button type="button" className={!show3d ? "is-selected" : ""} aria-pressed={!show3d} onClick={() => { setShowModel(false); triggerAction("idle"); }}>卡通动作</button>
            <button type="button" className={show3d ? "is-selected" : ""} aria-pressed={show3d} onClick={() => setShowModel(true)}>3D 查看</button>
          </div>}
        </div>
        <div className="pet-action-list" role="group" aria-label="桌宠动作">
          {petActions.map((action) => <button key={action.id} type="button" className={previewAction === action.id && !show3d ? "is-active" : ""} aria-pressed={previewAction === action.id && !show3d} disabled={show3d} onClick={() => triggerAction(action.id)}>{action.label}</button>)}
        </div>
        {show3d && <p className="model-motion-note">单张照片生成的 3D 网格没有骨骼；桌面宠物使用卡通动作。</p>}
      </div>
      <div className="preview-caption"><span><i /> 角色大小 <b>{Math.round(config.appearance.scale * 100)}%</b></span><span><Icon name="speed" size={14} /> 行走速度 <b>{config.behavior.moveSpeed} px/s</b></span><span><Icon name="pin" size={14} /> 始终置顶</span></div>
    </section>
  );
}

const petActions = [
  { id: "idle", label: "待机" },
  { id: "walk", label: "散步" },
  { id: "wave", label: "挥手" },
  { id: "happy", label: "开心" },
  { id: "jump", label: "跳跃" },
  { id: "sleep", label: "睡觉" },
  { id: "spin", label: "转圈" },
  { id: "stretch", label: "伸懒腰" },
  { id: "dance", label: "跳舞" },
  { id: "angry", label: "生气" },
] as const;

const actionLabels: Record<string, string> = {
  wave: "嗨！", happy: "好开心", jump: "蹦！", sleep: "Z z z", spin: "转圈",
  stretch: "伸懒腰", dance: "♪", angry: "哼！", walk: "散步中",
};
