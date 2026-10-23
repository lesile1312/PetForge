(() => {
  const input = document.querySelector('#reference-file');
  const drop = document.querySelector('#reference-drop');
  const preview = document.querySelector('#reference-preview');
  const empty = document.querySelector('#reference-empty');
  const meta = document.querySelector('#reference-meta');
  const status = document.querySelector('#reference-status');
  const download = document.querySelector('#reference-download');
  const reset = document.querySelector('#reference-reset');
  let selection = null;
  let previewUrl = null;
  let revision = 0;

  async function select(file) {
    const current = ++revision;
    status.textContent = '';
    if (!file) return;
    let candidateUrl;
    try {
      if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) throw new Error('请选择 PNG、JPG 或 WEBP 图片。');
      if (!file.size || file.size > 10 * 1024 * 1024) throw new Error('请选择 10 MB 以内的图片。');
      candidateUrl = URL.createObjectURL(file);
      const image = new Image();
      image.src = candidateUrl;
      await image.decode();
      if (image.naturalWidth * image.naturalHeight > 24000000) throw new Error('图片分辨率较大，请缩小到 2400 万像素以内。');
      if (current !== revision) { URL.revokeObjectURL(candidateUrl); return; }
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      previewUrl = candidateUrl;
      selection = file;
      preview.src = previewUrl;
      preview.hidden = false;
      empty.hidden = true;
      meta.textContent = `参考原图 · ${file.name} · ${image.naturalWidth} × ${image.naturalHeight} · ${(file.size / 1048576).toFixed(2)} MB`;
      download.disabled = false;
      reset.hidden = false;
    } catch (error) {
      if (candidateUrl) URL.revokeObjectURL(candidateUrl);
      if (current === revision) status.textContent = error.message || '图片无法读取，请换一张试试。';
    }
  }
  input.addEventListener('change', () => { void select(input.files[0]); input.value = ''; });
  drop.addEventListener('dragover', (event) => { event.preventDefault(); drop.classList.add('dragging'); });
  drop.addEventListener('dragleave', () => drop.classList.remove('dragging'));
  drop.addEventListener('drop', (event) => { event.preventDefault(); drop.classList.remove('dragging'); void select(event.dataTransfer.files[0]); });
  reset.addEventListener('click', () => {
    revision++;
    selection = null;
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = null;
    preview.removeAttribute('src');
    preview.hidden = true;
    empty.hidden = false;
    reset.hidden = true;
    download.disabled = true;
    status.textContent = '';
    meta.textContent = '照片只在当前浏览器预览，刷新或清除后不保留。';
  });
  download.addEventListener('click', async () => {
    if (!selection) return;
    const file = selection;
    download.disabled = true;
    try {
      const dataUrl = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = () => reject(new Error('原图读取失败，请重试。'));
        reader.readAsDataURL(file);
      });
      const bundle = { format: 'petforge-reference', version: 1, image: { name: file.name, dataUrl } };
      const url = URL.createObjectURL(new Blob([JSON.stringify(bundle)], { type: 'application/json' }));
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `${file.name.replace(/\.[^.]+$/, '')}.petforge.json`;
      anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      status.textContent = '参考文件已准备下载。在本机创作器中选择此文件，即可继续处理原图。';
    } catch (error) { status.textContent = error.message || '参考文件保存失败。'; }
    finally { download.disabled = !selection; }
  });
})();
