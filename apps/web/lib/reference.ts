/** A portable local handoff from the public showcase; never executes imported code. */
export async function readReferenceFile(file: File): Promise<File> {
  if (!file.name.toLowerCase().endsWith(".petforge.json")) return file;
  if (file.size > 15 * 1024 * 1024) throw new Error("参考文件过大，请重新选择不超过 10 MB 的原图。");
  const source = JSON.parse(await file.text());
  if (source?.format !== "petforge-reference" || source?.version !== 1) {
    throw new Error("这不是支持的 PetForge 参考文件。");
  }
  const image = source.image;
  if (typeof image?.name !== "string" || typeof image?.dataUrl !== "string") {
    throw new Error("参考文件缺少图片。");
  }
  const match = /^data:(image\/(?:png|jpeg|webp));base64,([A-Za-z0-9+/]*={0,2})$/.exec(image.dataUrl);
  if (!match || match[2].length > 14 * 1024 * 1024) throw new Error("参考图片格式不支持或图片过大。");
  const bytes = Uint8Array.from(atob(match[2]), (character) => character.charCodeAt(0));
  if (!bytes.length || bytes.length > 10 * 1024 * 1024) throw new Error("参考图片必须在 10 MB 以内。");
  return new File([bytes], image.name.replace(/[\\/]/g, "_"), { type: match[1] });
}
