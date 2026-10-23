"use client";

import type { DragEvent, ChangeEvent } from "react";
import { useRef, useState } from "react";
import { CharacterArt, type CharacterVariant } from "@/components/character-art";
import { Icon } from "@/components/icons";

const samples: { id: CharacterVariant; title: string; detail: string; asset: string }[] = [
  { id: "cat", title: "小猫", detail: "一位毛茸茸的新朋友", asset: "/demo/cat.svg" },
  { id: "anime", title: "动漫角色", detail: "让最喜欢的角色来陪你", asset: "/demo/anime.svg" },
  { id: "person", title: "人物", detail: "把熟悉的面孔放进桌面", asset: "/demo/person.svg" },
  { id: "plush", title: "毛绒玩偶", detail: "让收藏品在桌边醒来", asset: "/demo/plush.svg" },
];

interface UploadStageProps {
  busy: boolean;
  error: string | null;
  onFile: (file: File) => void;
  onSample: (asset: string, name: string) => void;
}

export function UploadStage({ busy, error, onFile, onSample }: UploadStageProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  function accept(file?: File) {
    if (!file || busy) return;
    onFile(file);
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
        <div className="hero-kicker"><span className="kicker-orbit" /> 从一张照片开始</div>
        <h1 id="hero-title">让熟悉的模样，<br /><span>住进你的桌面。</span></h1>
        <p className="hero-subtitle">上传参考照片，或导入公开网页保存的参考文件。PetForge 在本机抠除背景、应用漫画滤镜，再预览和制作桌宠资源。</p>
        <p className="hero-english">One photo in. A little companion on your screen.</p>

        <div
          className={`dropzone${dragging ? " is-dragging" : ""}${busy ? " is-busy" : ""}`}
          aria-label="拖拽图片上传；也可以使用选择图片按钮"
          onClick={() => !busy && inputRef.current?.click()}
          onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
        >
          <input ref={inputRef} type="file" accept="image/png,image/jpeg,image/webp,.png,.jpg,.jpeg,.webp,.json" onChange={onInput} hidden />
          <div className="upload-icon"><Icon name={busy ? "spark" : "upload"} size={20} /></div>
          <div className="dropzone-content">
            <strong>{busy ? "正在准备你的桌宠…" : "拖一张图片到这里"}</strong>
            <span>{busy ? "请稍等片刻" : "或从电脑中选择图片"}</span>
          </div>
          <button type="button" className="button button-primary upload-cta" disabled={busy} onClick={(event) => { event.stopPropagation(); inputRef.current?.click(); }}>
            <Icon name="plus" size={16} /> 创建我的桌宠
          </button>
        </div>
        <div className="upload-footnote"><Icon name="image" size={15} /><span>PNG、JPG、WEBP 或 .petforge.json 参考文件</span><i /> <span>原图最大 10 MB</span></div>
        <p className="upload-privacy-note">仅上传你本人或已获授权的照片。图片会发送到当前 PetForge 服务进行处理。</p>
        {error && <div className="inline-alert" role="alert">{error}</div>}
      </div>

      <div className="creation-preview" aria-label="桌宠效果预览">
        <div className="preview-label"><span>桌面效果示意</span><span className="preview-live"><i /> 示例画面</span></div>
        <div className="mini-desktop">
          <div className="mini-desktop-shape" />
          <div className="mini-desktop-orbit orbit-one" />
          <div className="mini-desktop-orbit orbit-two" />
          <div className="desktop-shortcuts"><span><b /><small>周报.docx</small></span><span><b /><small>音乐</small></span><span><b /><small>设计素材</small></span></div>
          <div className="desktop-pet"><CharacterArt variant="cat" /></div>
          <div className="desktop-notice"><span className="notice-dot" /><div><b>你的新朋友</b><small>正在桌面上等你</small></div></div>
          <div className="mini-taskbar"><span className="windows-mark">◩</span><span className="task-search">搜索</span><span className="task-icons"><i /><i /><i /></span><span className="task-clock">9:41<br />10/07</span></div>
        </div>
        <div className="creation-steps" id="how-it-works" aria-label="从照片到桌宠的流程">
          <div className="creation-step"><span className="step-number">1</span><b>上传照片</b><small>一张清晰图片即可</small></div>
          <span className="step-connector" />
          <div className="creation-step"><span className="step-number">2</span><b>自动抠图</b><small>保留照片主体</small></div>
          <span className="step-connector" />
          <div className="creation-step"><span className="step-number">3</span><b>形象预览</b><small>对照原图检查透明角色</small></div>
          <span className="step-connector" />
          <div className="creation-step"><span className="step-number">4</span><b>导出资源</b><small>配合桌面运行程序使用</small></div>
        </div>
        <p className="creation-note">本机编辑器负责抠图、漫画滤镜和形象预览；常驻桌面需要 Godot 运行器。3D 建模是单独的可选实验。</p>
      </div>

      <div className="sample-shelf" id="examples">
        <div className="shelf-heading"><div><h2>先从喜欢的样子开始</h2><p>也可以上传自己的角色</p></div><span>试用示例</span></div>
        <div className="sample-grid">
          {samples.map((sample) => (
            <button key={sample.id} type="button" className="sample-card" onClick={() => onSample(sample.asset, sample.title)} disabled={busy}>
              <span className={`sample-art sample-${sample.id}`}><CharacterArt variant={sample.id} /></span>
              <span className="sample-copy"><b>{sample.title}</b><small>{sample.detail}</small></span>
              <span className="sample-open"><Icon name="arrow" size={15} /></span>
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
