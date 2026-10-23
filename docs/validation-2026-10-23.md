# Creation workflow validation / 桌宠制作流程核对

Date / 日期: 2026-10-23. Environment: existing Windows development checkout; Godot 4.7.2, local Python environment and cached BiRefNet portrait weights. This is not a clean-machine installer certification. / 使用已有依赖与模型缓存的 Windows 开发环境，不等于新电脑安装包认证。

| Check / 检查 | Observed result / 实测结果 |
| --- | --- |
| Direct PNG package creation / PNG 直建 | New private package directory, source PNG bytes unchanged / 新建独立目录，原图字节不变 |
| Existing directory protection / 防覆盖 | Existing output directory rejected / 拒绝覆盖已有目录 |
| Tracked-source snapshot / 受版本管理的源码副本 | API imports and Godot headless loading pass without copying the working tree's ignored storage modules or caches / 不复制本机忽略目录，API 导入及 Godot 无界面加载通过 |
| Native runtime package loading / Godot 加载 | Direct PNG and exported photo packages each loaded headlessly and exited with code 0 / 两种资源包无界面加载均以 0 退出 |
| Portrait upload / 照片导入 | Public reference JPEG accepted, original bytes preserved / 公开参考图上传后原始字节保留 |
| Segmentation + comic filter / 分割与滤镜 | Real `rembg:birefnet-portrait`, output 652 × 951, alpha range 0–255 / 使用真实模型生成带透明度的处理图 |
| Resource export / 导出 | ZIP includes `pet.json`, `character.png`, `cutout.png`, `README.txt` / 资源齐全 |
| Browser review / 网页检查 | Original/result images visible, manual launch enabled, 3D explicitly optional, actual export downloaded / 对照可见，可手动启动，可选 3D，实际下载成功 |
| Storage regression / 存储回归 | Two standard-library unit tests pass, including traversal/name rejection / 两项测试通过，保留路径与文件名校验 |
| Frontend / 前端 | Type checking and production compilation pass; build also reports a pre-existing Next.js security advisory / 类型检查和生产编译通过，构建另有现有 Next.js 安全更新提醒 |

The photo workflow initially failed because the storage allowlist omitted `cutout.png`. The fix permits only that intended derived file alongside the existing approved names. The tests retain rejection of traversal and arbitrary files. / 本轮发现并修复了白名单遗漏 `cutout.png` 导致照片处理返回 500 的故障，仍拒绝目录穿越与任意文件名。

The unanchored `storage/` ignore pattern also excluded API source files. It now ignores only root `/storage/`, and the API storage modules are included in the repository. / 原先 `storage/` 忽略规则同时排除了 API 存储源码；现改为仅忽略根目录 `/storage/`，补齐源码文件。

The pnpm 11.19.0 registry manifest requires Node >=22.13. The root engine declaration and both READMEs reflect that stricter requirement. / pnpm 11.19.0 的包声明要求 Node >=22.13，已同步修正根工程及中英文教程中的环境要求。

Reproduce the storage tests from `services/api/`: / 在 `services/api/` 运行存储测试：

```powershell
..\..\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Validation does not establish the quality of every portrait, automatically generated chibi art or character-specific animation, a signed Windows installer, fresh dependency downloads, multi-monitor/DPI behavior, or graphical desktop interactions on another machine. / 本次核对不保证所有照片的抠图质量、自动 Q 版重绘与专属动作，不涵盖签名安装包、新电脑依赖下载、多屏/DPI 或其他电脑上的桌面图形交互。

The public reference photo and custom cartoon are a design example. Current automatic photo processing is segmentation plus filtering. / 真人原图与定制卡通是设计对照；当前自动照片处理仍为人物分割加滤镜。
