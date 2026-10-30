(() => {
  const input = document.querySelector('#custom-png');
  const nameInput = document.querySelector('#custom-name');
  const button = document.querySelector('#custom-download');
  const status = document.querySelector('#custom-status');
  if (!input || !nameInput || !button || !status) return;
  let png = null;
  let selection = 0;
  const encoder = new TextEncoder();
  const crcTable = Array.from({length: 256}, (_, n) => {
    let c = n;
    for (let i = 0; i < 8; i++) c = (c & 1) ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    return c >>> 0;
  });
  function crc32(bytes) {
    let crc = 0xffffffff;
    for (const b of bytes) crc = crcTable[(crc ^ b) & 255] ^ (crc >>> 8);
    return (crc ^ 0xffffffff) >>> 0;
  }
  function header(size, values) {
    const b = new Uint8Array(size), v = new DataView(b.buffer);
    for (const [offset, value, width] of values) width === 2 ? v.setUint16(offset, value, true) : v.setUint32(offset, value, true);
    return b;
  }
  function zip(files) {
    const chunks = [], central = [];
    let offset = 0;
    for (const [path, bytes] of files) {
      const name = encoder.encode(path), crc = crc32(bytes), size = bytes.length;
      const local = header(30, [[0,0x04034b50,4],[4,20,2],[6,0x800,2],[14,crc,4],[18,size,4],[22,size,4],[26,name.length,2]]);
      const directory = header(46, [[0,0x02014b50,4],[4,20,2],[6,20,2],[8,0x800,2],[16,crc,4],[20,size,4],[24,size,4],[28,name.length,2],[42,offset,4]]);
      chunks.push(local, name, bytes); central.push(directory, name);
      offset += local.length + name.length + size;
    }
    const centralSize = central.reduce((n, part) => n + part.length, 0);
    const end = header(22, [[0,0x06054b50,4],[8,files.length,2],[10,files.length,2],[12,centralSize,4],[16,offset,4]]);
    return new Blob([...chunks, ...central, end], {type: 'application/zip'});
  }
  input.addEventListener('change', async () => {
    const current = ++selection, file = input.files[0];
    png = null; button.disabled = true;
    if (!file) { status.textContent = '先选择一张带透明背景的 PNG。'; return; }
    try {
      if (file.size > 10 * 1024 * 1024) throw new Error('图片超过 10 MB，请先缩小。');
      const bytes = new Uint8Array(await file.arrayBuffer());
      if (![137,80,78,71,13,10,26,10].every((v,i) => bytes[i] === v)) throw new Error('请选择 PNG 格式的角色图。');
      const bitmap = await createImageBitmap(file);
      if (bitmap.width > 8192 || bitmap.height > 8192 || bitmap.width * bitmap.height > 20000000) { bitmap.close(); throw new Error('图片尺寸过大，请缩小后重试。'); }
      const canvas = document.createElement('canvas'); canvas.width = bitmap.width; canvas.height = bitmap.height;
      const ctx = canvas.getContext('2d', {willReadFrequently:true}); ctx.drawImage(bitmap, 0, 0); bitmap.close();
      const pixels = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
      let transparent = false, visible = false;
      for (let i = 3; i < pixels.length; i += 4) { if (pixels[i] < 255) transparent = true; if (pixels[i] > 0) visible = true; if (transparent && visible) break; }
      if (!transparent || !visible) throw new Error('图片没有可用的透明背景，请先抠图并保存为透明 PNG。');
      if (current !== selection) return;
      png = bytes; button.disabled = false; status.textContent = '图片已准备好，可以下载桌宠文件。';
    } catch (error) { if (current === selection) status.textContent = error.message || '图片读取失败，请换一张 PNG。'; }
  });
  button.addEventListener('click', () => {
    if (!png) return;
    const id = 'pet_' + Array.from(crypto.getRandomValues(new Uint8Array(16)), b => b.toString(16).padStart(2, '0')).join('');
    const directory = `custom-pets/${id}`;
    const config = {version:'1.0', id, name:nameInput.value.trim().slice(0,40) || '我的桌宠', appearance:{sprite:'character.png',scale:1}, behavior:{moveSpeed:100,idleDuration:20,sleepDuration:120,randomWalk:true,randomJump:true,autoSleep:true,draggable:true,initialPosition:'right',randomWalkFrequency:'medium'}, window:{alwaysOnTop:true,mousePassthrough:true}};
    const bat = `@echo off\r\ncd /d "%~dp0"\r\nif not exist "%~dp0PetForge.exe" (echo Extract this ZIP into the PetForge Windows portable folder first. & pause & exit /b 1)\r\nstart "" "%~dp0PetForge.exe" --path "%~dp0PetForgeRuntime" -- --pet-project "%~dp0custom-pets\\${id}"\r\n`;
    const readme = '把本 ZIP 所有文件解压到 PetForge Windows 便携版文件夹（与 PetForge.exe 同一层），然后双击 Start-Custom-Pet.bat。\r\nExtract all files into the PetForge portable folder next to PetForge.exe, then run Start-Custom-Pet.bat.\r\n';
    const archive = zip([[`${directory}/character.png`, png], [`${directory}/pet.json`, encoder.encode(JSON.stringify(config,null,2))], ['Start-Custom-Pet.bat', encoder.encode(bat)], ['自定义桌宠说明.txt', encoder.encode(readme)]]);
    const url = URL.createObjectURL(archive), a = document.createElement('a'); a.href = url; a.download = `PetForge-${id}.zip`; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 60000);
    status.textContent = '桌宠文件已下载。请解压到 Windows 便携版文件夹，再双击 Start-Custom-Pet.bat。';
  });
})();
