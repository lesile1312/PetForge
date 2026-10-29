"use client";

import type { DragEvent, ChangeEvent } from "react";
import { useRef, useState } from "react";
import { CharacterArt, type CharacterVariant } from "@/components/character-art";
import { Icon } from "@/components/icons";

const samples: { id: CharacterVariant; title: string; detail: string; asset: string }[] = [
  { id: "idle", title: "安静待机", detail: "我的卡通女孩桌宠", asset: "/demo/idle-portrait.png" },
  { id: "blink", title: "眨眼微笑", detail: "我的卡通女孩桌宠", asset: "/demo/blink-portrait.png" },
  { id: "run-left", title: "向左跑动", detail: "我的卡通女孩桌宠", asset: "/demo/run-left.png" },
  { id: "run-right", title: "向右跑动", detail: "我的卡通女孩桌宠", asset: "/demo/run-right.png" },
];

type SourceMode = "transparent" | "photo";

interface UploadStageProps {
  busy: boolean;
  error: string | null;
  onFile: (file: File, mode: SourceMode) => void;
  onSample: (asset: string, name: string) => void;
}

export function UploadStage({ busy, error, onFile, onSample }: UploadStageProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [sourceMode, setSourceMode] = useState<SourceMode>("transparent");

  function accept(file?: File) {
    if (!file || busy) return;
    onFile(file, sourceMode);
  }

  function onInput(event: ChangeEvent<HTMLInputElement>) {
    accept(event.target.files?.[0]);
    event.target.value = "";
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    accept(event.dataTransfer.files?.[0]);
  }

  return (
    <section className="upload-stage" aria-labelledby="hero-title">
      <div className="hero-copy">
        <div className="hero-kicker"><span className="kicker-orbit" /> 自己的角色，自己的桌宠</div>
        <h1 id="hero-title">把喜欢的角色，<br /><span>放到你的桌面。</span></h1>
        <p className="hero-subtitle">有透明 PNG 就直接开始；只有普通照片，也能先在本机抠除背景。接着调大小、走路速度和行动习惯，预览后再保存或启动。</p>
        <p className="hero-english">Your character, your little desktop companion.</p>

        <div className="source-mode-picker" role="group" aria-label="选择角色图片类型">
          <button type="button" className={`source-mode-option${sourceMode === "transparent" ? " is-selected" : ""}`} aria-pressed={sourceMode === "transparent"} onClick={() => setSourceMode("transparent")} disabled={busy}>
            <span className="source-mode-mark">PNG</span><span><b>我有透明角色图</b><small>直接导入，保留原画</small></span>
          </button>
          <button type="button" className={`source-mode-option${sourceMode === "photo" ? " is-selected" : ""}`} aria-pressed={sourceMode === "photo"} onClick={() => setSourceMode("photo")} disabled={busy}>
            <span className="source-mode-mark"><Icon name="image" size={16} /></span><span><b>我只有普通照片</b><small>本机抠除背景，效果看原图</small></span>
          </button>
        </div>

        <div
          className={`dropzone${dragging ? " is-dragging" : ""}${busy ? " is-busy" : ""}`}
          aria-label="拖拽图片上传；也可以使用选择图片按钮"
          onClick={() => !busy && inputRef.current?.click()}
          onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
        >
          <input ref={inputRef} type="file" accept={sourceMode === "transparent" ? "image/png,.png,.petforge.json" : "image/png,image/jpeg,image/webp,.png,.jpg,.jpeg,.webp,.petforge.json"} onChange={onInput} hidden />
          <div className="upload-icon"><Icon name={busy ? "spark" : "upload"} size={20} /></div>
          <div className="dropzone-content">
            <strong>{busy ? "正在准备你的桌宠…" : sourceMode === "transparent" ? "选择透明角色 PNG" : "选择普通人物照片"}</strong>
            <span>{busy ? "请稍等片刻" : "也可以把图片拖到这里"}</span>
          </div>
          <button type="button" className="button button-primary upload-cta" disabled={busy} onClick={(event) => { event.stopPropagation(); inputRef.current?.click(); }}>
            <Icon name="plus" size={16} /> {sourceMode === "transparent" ? "导入角色图" : "从照片开始"}
          </button>
        </div>
        <div className="upload-footnote"><Icon name="image" size={15} /><span>透明 PNG 可直接用；照片支持 PNG、JPG、WEBP</span><i /> <span>最大 10 MB</span></div>
        <p className="upload-privacy-note">照片只发送给当前 PetForge 服务。使用本机版本时，图片保存在本机；请勿把私人照片上传到不熟悉的网站。</p>
        {error && <div className="inline-alert" role="alert">{error}</div>}
      </div>

      <div className="creation-preview" aria-label="桌宠效果预览">
        <div className="preview-label"><span>桌面效果示意</span><span className="preview-live"><i /> 示例画面</span></div>
        <div className="mini-desktop">
          <div className="mini-desktop-shape" />
          <div className="mini-desktop-orbit orbit-one" />
          <div className="mini-desktop-orbit orbit-two" />
          <div className="desktop-shortcuts"><span><b /><small>周报.docx</small></span><span><b /><small>音乐</small></span><span><b /><small>设计素材</small></span></div>
          <div className="desktop-pet"><CharacterArt variant="idle" alt="我的卡通女孩桌宠，待机示意" /></div>
          <div className="desktop-notice"><span className="notice-dot" /><div><b>你的新朋友</b><small>正在桌面上等你</small></div></div>
          <div className="mini-taskbar"><span className="windows-mark">◩</span><span className="task-search">搜索</span><span className="task-icons"><i /><i /><i /></span><span className="task-clock">9:41<br />10/07</span></div>
        </div>
        <div className="creation-steps" id="how-it-works" aria-label="从角色图片到桌宠的流程">
          <div className="creation-step"><span className="step-number">1</span><b>导入角色</b><small>透明 PNG 最省事</small></div>
          <span className="step-connector" />
          <div className="creation-step"><span className="step-number">2</span><b>准备图片</b><small>透明图直用，照片可抠图</small></div>
          <span className="step-connector" />
          <div className="creation-step"><span className="step-number">3</span><b>设置与预览</b><small>调大小和行动习惯</small></div>
          <span className="step-connector" />
          <div className="creation-step"><span className="step-number">4</span><b>启动或导出</b><small>保存你调好的桌宠</small></div>
        </div>
        <p className="creation-note">运行器提供待机、走动、跳跃、睡觉和鼠标回应等通用动作。照片抠图不会自动画出新卡通，也不会生成专属动作。</p>
      </div>

      <div className="sample-shelf" id="examples">
        <div className="shelf-heading"><div><h2>我的卡通女孩桌宠</h2><p>同一角色的不同动作，点选即可试用</p></div><span>作者定制角色</span></div>
        <div className="sample-grid">
          {samples.map((sample) => (
            <button key={sample.id} type="button" className="sample-card" aria-label={`${sample.title}，用我的卡通女孩创建桌宠`} onClick={() => onSample(sample.asset, "我的卡通女孩")} disabled={busy}>
              <span className={`sample-art sample-${sample.id}`}><CharacterArt variant={sample.id} alt="" /></span>
              <span className="sample-copy"><b>{sample.title}</b><small>{sample.detail}</small></span>
              <span className="sample-open"><Icon name="arrow" size={15} /></span>
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
