"use client";

import { useEffect, useRef, useState } from "react";
import type { PetConfig } from "@petforge/pet-schema";
import { defaultPetConfig } from "@petforge/pet-schema";
import { api, imageUrl, type PetRecord } from "@/lib/api";
import { Icon } from "@/components/icons";
import { UploadStage } from "@/components/upload-stage";
import { DesktopPreview } from "@/components/desktop-preview";
import { SettingsPanel } from "@/components/settings-panel";
import { readReferenceFile } from "@/lib/reference";

type Stage = "upload" | "cutout" | "editor";
type ModelStatus = "idle" | "processing" | "ready" | "error";
const canLaunchLocalRuntime = process.env.NEXT_PUBLIC_PETFORGE_RUNTIME_MODE === "local";

export function Studio() {
  const [stage, setStage] = useState<Stage>("upload");
  const [activeStep, setActiveStep] = useState(1);
  const [pet, setPet] = useState<PetRecord | null>(null);
  const [config, setConfig] = useState<PetConfig | null>(null);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [previewOriginal, setPreviewOriginal] = useState(false);
  const [modelStatus, setModelStatus] = useState<ModelStatus>("idle");
  const [desktopStarted, setDesktopStarted] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const petId = new URLSearchParams(window.location.search).get("pet")
      ?? window.localStorage.getItem("petforge:lastPetId");
    if (!petId) return;
    window.localStorage.setItem("petforge:lastPetId", petId);
    let cancelled = false;
    void api.readPet(petId).then((savedPet) => {
      if (cancelled) return;
      setPet(savedPet);
      setConfig(savedPet.config);
      setStage(savedPet.processedImage ? "editor" : savedPet.originalImage ? "cutout" : "upload");
      setActiveStep(savedPet.modelUrl ? 4 : savedPet.processedImage ? 3 : savedPet.originalImage ? 2 : 1);
      setPreviewOriginal(!savedPet.processedImage);
      setModelStatus(savedPet.modelUrl ? "ready" : savedPet.processedImage ? "error" : "idle");
      setNotice(savedPet.modelUrl ? "已恢复上次项目，3D 模型已就绪。" : savedPet.processedImage ? "已恢复上次项目，可以重试 3D 建模。" : null);
    }).catch(() => {
      if (!cancelled) window.localStorage.removeItem("petforge:lastPetId");
    });
    return () => { cancelled = true; };
  }, []);

  async function handleFile(inputFile: File, nameHint?: string) {
    setError(null);
    setNotice(null);
    setWorking(true);
    let file: File;
    try {
      file = await readReferenceFile(inputFile);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "参考文件无法读取。");
      setWorking(false);
      return;
    }
    if (!new Set(["image/png", "image/jpeg", "image/webp"]).has(file.type)) {
      setError("请选择 PNG、JPG 或 WEBP 格式的图片。");
      setWorking(false);
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setError("图片不能超过 10 MB，请压缩后再试。");
      setWorking(false);
      return;
    }

    setWorking(true);
    try {
      let current = pet;
      if (!current) {
        current = await api.createPet(nameHint ?? "Momo");
        window.localStorage.setItem("petforge:lastPetId", current.id);
        setPet(current);
        setConfig(current.config);
      }
      const uploaded = await api.upload(current.id, file);
      setPet(uploaded);
      setConfig(uploaded.config);
      setStage("cutout");
      setActiveStep(2);
      setPreviewOriginal(true);
      setModelStatus("idle");
      setNotice("图片已上传，正在识别人物并抠除背景…");
      await processImage(uploaded);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "图片上传失败，请重试。");
    } finally {
      setWorking(false);
    }
  }

  async function handleSample(asset: string, name: string) {
    setWorking(true);
    setError(null);
    try {
      const response = await fetch(asset);
      if (!response.ok) throw new Error("示例图片暂时无法读取。");
      const sourceUrl = URL.createObjectURL(await response.blob());
      const image = new Image();
      image.src = sourceUrl;
      try {
        await image.decode();
      } catch {
        URL.revokeObjectURL(sourceUrl);
        throw new Error("示例图片无法解码，请重新选择或上传自己的图片。");
      }
      const canvas = document.createElement("canvas");
      canvas.width = image.naturalWidth;
      canvas.height = image.naturalHeight;
      const context = canvas.getContext("2d");
      if (!context) {
        URL.revokeObjectURL(sourceUrl);
        throw new Error("无法读取示例图片，请改为上传自己的图片。");
      }
      context.drawImage(image, 0, 0);
      URL.revokeObjectURL(sourceUrl);
      const png = await new Promise<Blob>((resolve, reject) => {
        canvas.toBlob((blob) => blob ? resolve(blob) : reject(new Error("示例图片转换失败。")), "image/png");
      });
      await handleFile(new File([png], `${name}.png`, { type: "image/png" }), name);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "示例图片无法加载。");
      setWorking(false);
    }
  }

  async function removeBackground() {
    if (!pet) return;
    setError(null);
    setNotice(null);
    setWorking(true);
    try {
      await processImage(pet);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "背景处理失败，请尝试简洁背景的图片。原图仍然保留。 ");
    } finally {
      setWorking(false);
    }
  }

  async function processImage(sourcePet: PetRecord) {
    setStage("cutout");
    setActiveStep(2);
    setModelStatus("idle");
    setPreviewOriginal(true);
    setNotice("正在使用 AI 识别并抠除人物…");
    const result = await api.removeBackground(sourcePet.id);
    if (result.status !== "processed") throw new Error("本地人物抠图没有生成透明 PNG，请检查 AI Provider 配置。");

    const cutoutPet: PetRecord = {
      ...sourcePet,
      processedImage: result.imageUrl,
      modelUrl: null,
      config: { ...sourcePet.config, appearance: { ...sourcePet.config.appearance, model: null } },
    };
    setPet(cutoutPet);
    setConfig(cutoutPet.config);
    setPreviewOriginal(false);
    setStage("editor");
    setActiveStep(3);
    setModelStatus("processing");
    setNotice(`漫画风格角色已生成 · ${result.width} × ${result.height}。正在重建 3D 模型…`);
    const localLaunch = canLaunchLocalRuntime
      ? api.launch(cutoutPet.id)
        .then(() => {
          setDesktopStarted(true);
          setNotice("卡通桌宠已显示在桌面，3D 参考模型继续生成…");
          return { started: true, message: "卡通桌宠已显示在桌面。" };
        })
        .catch((reason) => ({
          started: false,
          message: reason instanceof Error ? `桌面启动失败：${reason.message}` : "桌面启动失败，请检查 Godot Runtime。",
        }))
      : null;
    await generateModel(cutoutPet);
    if (localLaunch) {
      const launchResult = await localLaunch;
      setDesktopStarted(launchResult.started);
      if (!launchResult.started) setError(launchResult.message);
      setNotice((current) => `${current ?? "漫画风格角色已生成。"} ${launchResult.message}`);
    }
  }

  async function generateModel(sourcePet: PetRecord) {
    setModelStatus("processing");
    setError(null);
    setNotice("正在生成 3D 模型，首次运行可能需要下载模型权重并占用显卡显存…");
    try {
      const result = await api.generateModel(sourcePet.id);
      const nextPet: PetRecord = {
        ...sourcePet,
        modelUrl: result.modelUrl,
        config: { ...sourcePet.config, appearance: { ...sourcePet.config.appearance, model: "model.glb" } },
      };
      setPet(nextPet);
      setConfig(nextPet.config);
      setModelStatus("ready");
      setActiveStep(4);
      setNotice(`${result.provider} · 3D GLB 已生成。桌面宠物使用卡通角色和动作；3D 模型用于网页查看与下载。`);
    } catch (reason) {
      setModelStatus("error");
      setNotice("透明人物图已经保留；3D 模型生成失败，可以稍后重试或导出透明图。");
      setError(reason instanceof Error ? reason.message : "3D 模型生成失败，请稍后重试。");
    }
  }

  async function retryModelGeneration() {
    if (!pet?.processedImage) return;
    setWorking(true);
    await generateModel(pet);
    setWorking(false);
  }

  async function restoreOriginal() {
    if (!pet) return;
    setError(null);
    setWorking(true);
    try {
      await api.restoreOriginal(pet.id);
      const restoredPet = {
        ...pet,
        processedImage: null,
        modelUrl: null,
        config: { ...pet.config, appearance: { ...pet.config.appearance, model: null } },
      };
      setPet(restoredPet);
      setConfig(restoredPet.config);
      setModelStatus("idle");
      setPreviewOriginal(true);
      setStage("cutout");
      setActiveStep(2);
      setNotice("已恢复到原图。背景抠除尚未完成，你可以重新处理或替换图片。");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "恢复原图失败，请重试。");
    } finally {
      setWorking(false);
    }
  }

  async function saveConfig() {
    if (!pet || !config) return;
    setWorking(true);
    setError(null);
    try {
      const saved = await api.save(pet.id, config);
      setPet(saved);
      setConfig(saved.config);
      setNotice("设置已保存到 PetForge 项目。");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "保存失败，请重试。");
    } finally {
      setWorking(false);
    }
  }

  async function downloadPackage() {
    if (!pet || !config) return;
    setWorking(true);
    setError(null);
    try {
      const saved = await api.save(pet.id, config);
      setPet(saved);
      setConfig(saved.config);
      const blob = await api.export(pet.id);
      downloadBlob(blob, `${pet.id}.zip`);
      setNotice(saved.modelUrl
        ? "资源包已导出，包含透明 PNG 和 GLB 模型；需要配套的 Windows 桌面运行程序才能常驻桌面。"
        : "资源包已导出，包含透明 PNG；需要配套的 Windows 桌面运行程序才能常驻桌面。");
      setActiveStep(4);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "导出失败，请重试。");
    } finally {
      setWorking(false);
    }
  }

  async function launchPet() {
    if (!pet || !config) return;
    setWorking(true);
    setError(null);
    try {
      await api.save(pet.id, config);
      await api.launch(pet.id);
      setDesktopStarted(true);
      setActiveStep(5);
      setNotice("卡通桌宠已显示在桌面，可以关闭创建器了。");
    } catch (reason) {
      setDesktopStarted(false);
      const message = reason instanceof Error ? reason.message : "";
      setError(message.includes("Godot is not configured")
        ? "当前还没有配置 Godot Runtime。安装 Godot 4 后，在项目 .env 中填写 PETFORGE_GODOT_EXECUTABLE 即可启动桌宠。"
        : message || "启动失败，请确认 Godot 4 Runtime 已正确配置。");
    } finally {
      setWorking(false);
    }
  }

  async function downloadPng() {
    if (!pet?.processedImage) return;
    setError(null);
    const url = imageUrl(pet.processedImage);
    if (!url) return;
    try {
      const response = await fetch(url);
      if (!response.ok) throw new Error("透明 PNG 暂时无法下载，请检查 API 服务。");
      downloadBlob(await response.blob(), "character-cartoon.png");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "透明 PNG 下载失败。");
    }
  }

  async function downloadModel() {
    if (!pet?.modelUrl) return;
    setError(null);
    try {
      const response = await fetch(imageUrl(pet.modelUrl) ?? "");
      if (!response.ok) throw new Error("3D 模型暂时无法下载，请检查 PetForge 服务。");
      downloadBlob(await response.blob(), "model.glb");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "3D 模型下载失败。");
    }
  }

  function startAnother() {
    window.localStorage.removeItem("petforge:lastPetId");
    setPet(null);
    setConfig(null);
    setStage("upload");
    setActiveStep(1);
    setError(null);
    setNotice(null);
    setPreviewOriginal(false);
    setModelStatus("idle");
  }

  const image = pet ? imageUrl(previewOriginal ? pet.originalImage : pet.processedImage) : null;

  return (
    <main className="app-shell">
      <header className="topbar">
        <a href="#home" className="brand-lockup" aria-label="PetForge 首页" onClick={(event) => { if (stage !== "upload") { event.preventDefault(); startAnother(); } }}>
          <span className="brand-mark"><Icon name="mark" size={22} /></span>
          <span className="brand-word">PetForge</span>
          <span className="brand-version">BETA</span>
        </a>
        {stage === "upload" ? (
          <nav className="top-nav"><a href="#how-it-works">制作流程</a><a href="#examples">试试示例</a><span className="nav-divider" /><span className="local-badge"><i /> 单图创建</span></nav>
        ) : (
          <div className="editor-topbar-right"><span className="project-name"><Icon name="spark" size={15} /> {config?.name || "新桌宠"}</span><button className="button button-quiet new-pet-button" type="button" onClick={startAnother}>另建一个</button></div>
        )}
      </header>

      {stage === "upload" ? (
        <UploadStage busy={working} error={error} onFile={handleFile} onSample={handleSample} />
      ) : (
        <>
          <div className="workflow-bar" aria-label="创建步骤">
            <div className="workflow-project"><button type="button" onClick={startAnother} aria-label="返回创建页面"><Icon name="arrow" size={17} className="back-arrow" /></button><span className="workflow-project-name">{config?.name || "新桌宠"}</span><span className="workflow-unsaved"><i /> PetForge 项目</span></div>
            <ol className="workflow-steps">
              {(["上传照片", "自动抠图", "角色设置", "3D 预览", canLaunchLocalRuntime ? "启动桌宠" : "导出资源"] as const).map((label, index) => {
                const number = index + 1;
                return <li key={label} className={`${activeStep === number ? "is-current" : ""}${activeStep > number ? " is-complete" : ""}`}><span className="workflow-step-number">{activeStep > number ? <Icon name="check" size={13} /> : number}</span><span>{label}</span></li>;
              })}
            </ol>
            <div className="workflow-actions">
              <button type="button" className="button button-quiet save-button" onClick={saveConfig} disabled={working || !config}><Icon name="save" size={16} /> 保存</button>
              <button type="button" className={`button ${canLaunchLocalRuntime ? "button-export" : "button-primary"}`} onClick={downloadPackage} disabled={working || !pet?.processedImage}><Icon name="download" size={15} /> {canLaunchLocalRuntime ? "导出资源" : "下载资源包"}</button>
              {canLaunchLocalRuntime && <button type="button" className={`button button-primary launch-button${desktopStarted ? " is-running" : ""}`} onClick={launchPet} disabled={working || !pet?.processedImage}><Icon name="play" size={14} /> {desktopStarted ? "桌面已运行" : "启动桌宠"}</button>}
            </div>
          </div>

          {stage === "cutout" ? (
            <section className="cutout-stage">
              <div className="cutout-intro"><span className="section-eyebrow">第 2 步 · 角色制作</span><h1>让角色从背景里<br /><span>轻轻地走出来。</span></h1><p>本机自动抠图、做漫画风格角色，再重建可旋转的 3D 参考模型。原图和透明抠图都会保留。</p></div>
              <div className="cutout-card">
                {(error || notice) && <div className="editor-status" aria-live="polite">{error && <span className="editor-alert" role="alert">{error}</span>}{notice && !error && <span className="editor-notice"><Icon name="spark" size={14} /> {notice}</span>}</div>}
                <div className="cutout-card-top"><div><span className="cutout-card-kicker"><Icon name="image" size={15} /> 原始图片</span><b>{pet?.name}</b></div><button className="text-button" type="button" onClick={() => fileInputRef.current?.click()}><Icon name="undo" size={15} /> 换一张</button></div>
                <div className="cutout-image-preview"><div className="checkerboard" />{image ? <img src={image} alt="待处理的角色原图" /> : <span className="cutout-no-image">图片未能加载</span>}<span className="image-dimension-note">原图 · 背景保留</span></div>
                <input ref={fileInputRef} hidden type="file" accept="image/png,image/jpeg,image/webp" onChange={(event) => { const file = event.target.files?.[0]; if (file) void handleFile(file); event.target.value = ""; }} />
                <div className="cutout-card-bottom"><button type="button" className="button button-quiet" onClick={startAnother} disabled={working}>取消</button><button type="button" className="button button-primary cutout-action" onClick={removeBackground} disabled={working || !pet?.originalImage}><Icon name="spark" size={17} /> {working ? "AI 正在处理…" : "重新抠图并建模"}<Icon name="arrow" size={15} /></button></div>
              </div>
              <div className="cutout-assurance"><span className="assurance-icon"><Icon name="layers" size={17} /></span><p><b>原图会保留</b><small>不满意可以随时恢复，或换一张图片重试。</small></p></div>
            </section>
          ) : config && pet ? (
            <section className="editor-stage">
              <div className="editor-status" aria-live="polite">
                {error && <span className="editor-alert" role="alert">{error}</span>}
                {notice && !error && <span className="editor-notice"><Icon name="check" size={14} /> {notice}</span>}
              </div>
              <div className="editor-grid">
                <div className="editor-main-column">
                  <div className="editor-heading"><div><span className="section-eyebrow">桌面伙伴 · {pet.id.slice(0, 12)}</span><h1>给它一点个性。</h1><p>调好大小和行动习惯，预览会即时更新。</p></div><div className="editor-image-actions"><button type="button" className="text-button" onClick={restoreOriginal} disabled={working}><Icon name="undo" size={15} /> 恢复原图</button><button type="button" className="text-button" onClick={downloadPng} disabled={working || !pet.processedImage}><Icon name="download" size={15} /> 下载透明 PNG</button><button type="button" className="text-button" onClick={downloadModel} disabled={working || !pet.modelUrl}><Icon name="download" size={15} /> 下载 GLB</button></div></div>
                  <div className="reference-comparison">
                    <figure><figcaption>参考原图 · 保留在本机</figcaption>{pet.originalImage && <img src={imageUrl(pet.originalImage) ?? ""} alt="人物参考原图" />}</figure>
                    <figure><figcaption>当前处理结果 · 漫画滤镜</figcaption>{pet.processedImage && <img src={imageUrl(pet.processedImage) ?? ""} alt="处理后的卡通风格角色" />}</figure>
                  </div>
                  <DesktopPreview config={config} imageSrc={image} modelSrc={pet.modelUrl ? imageUrl(pet.modelUrl) : null} />
                  <div className={`model-status-card model-status-${modelStatus}`} aria-live="polite">
                    <span className="model-status-mark"><Icon name={modelStatus === "ready" ? "check" : modelStatus === "processing" ? "spark" : "layers"} size={15} /></span>
                    <div><b>{modelStatus === "ready" ? "3D 参考模型已生成" : modelStatus === "processing" ? "正在重建 3D 参考模型" : modelStatus === "error" ? "3D 模型尚未生成" : "上传后自动生成卡通角色与 3D 参考模型"}</b><small>{modelStatus === "ready" ? "可在网页单独查看；桌面运行的是带动作的卡通角色。" : modelStatus === "processing" ? "首次运行可能需要下载模型权重；卡通桌宠可以先运行。" : modelStatus === "error" ? "卡通桌宠和动作仍可使用，3D 下载稍后重试。" : "人物分割与单图重建都在本机完成。"}</small></div>
                    {modelStatus === "error" && <button type="button" className="text-button" onClick={retryModelGeneration} disabled={working}>重试 3D 建模</button>}
                  </div>
                  <div className="cutout-method"><span className="method-status"><i /> {pet.modelUrl ? "3D GLB 已生成" : pet.processedImage ? "透明 PNG 已生成" : "背景未移除"}</span><span>{pet.modelUrl ? "单图重建 · 背面与细节为 AI 推断" : pet.processedImage ? "AI 人物分割" : "先上传图片以运行 AI 抠图"}</span><button type="button" onClick={() => { setStage("cutout"); setActiveStep(2); setPreviewOriginal(true); setError(null); setNotice(null); }} disabled={working}>重新处理</button></div>
                </div>
                <SettingsPanel config={config} onChange={setConfig} />
              </div>
              <div className="editor-bottom-bar"><span><Icon name="clock" size={14} /> 设置保存在当前 PetForge 项目</span><span className="editor-bottom-actions"><button type="button" className="text-button" onClick={() => { setActiveStep(4); setNotice("桌面预览已更新，试着拖动角色看看。"); }}><Icon name="mouse" size={15} /> 预览互动</button><button type="button" className="button button-primary" onClick={saveConfig} disabled={working}><Icon name="save" size={15} /> {working ? "保存中…" : "保存设置"}</button></span></div>
            </section>
          ) : null}
        </>
      )}

      {stage === "upload" && <footer className="page-footer"><span>网页内创建并预览</span><span>照片由当前部署的 PetForge 服务处理</span><span>桌面常驻需要 Windows 运行程序</span></footer>}
    </main>
  );
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1200);
}
