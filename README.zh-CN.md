# 自定义桌宠petforge

**把你自己的角色图片，做成住在电脑桌面上的小伙伴。**

**中文** · [English](README.md) · [真人原图与桌宠演示](https://lesile1312.github.io/PetForge/#example) · [参考图入口](https://lesile1312.github.io/PetForge/#create)

自定义桌宠petforge 是面向 Windows 的开源桌宠项目，使用 Next.js、FastAPI 和 Godot。项目目标是让用户在本机上传照片，选择要处理的人物，保留可见特征并标记 AI 推测补全的身体部分，生成卡通形象与动作，预览确认后打包成可在整个电脑桌面运行的宠物。人物识别只检测照片中的人物，不识别真人身份。

## 第一次使用？从这里开始

先选符合你现在情况的路线：

| 你的目标 | 适合的路线 | 需要准备 |
| --- | --- | --- |
| 我已经有透明角色 PNG，想把它放到桌面 | [快速启动 PNG 桌宠](#路线一直接用自己的透明-png制作桌宠)（[下载源码 ZIP](https://github.com/lesile1312/PetForge/archive/refs/heads/main.zip)） | Windows、Godot 4、自定义桌宠petforge 源码 |
| 我想从人物照片开始 | [安装本机照片编辑器](#路线二从真人照片开始使用本机编辑器) | Windows、Node.js、pnpm、Python、Godot 4；首次处理还需联网下载模型 |
| 我只想先看看效果 | [打开演示网页](https://lesile1312.github.io/PetForge/#example) | 浏览器；演示网页不会在电脑上启动桌宠 |

**当前进度：** GitHub Pages 是静态演示和参考图入口，不是云端生成服务。现有本机编辑器仍以抠图和漫画滤镜为主。仓库新增了实验性的本地 Python P0 流程：人物预检/选择、抠图、参考图卡通生成和五种代表动作预览；pose-v2 为待机、招手、蹲下玩手机加入明确的骨架条件图，中间文件保留在本机。它还没有接入网页编辑器。pose-v2 新模型的真实照片复跑未完成，动作与画质验收门仍未通过，因此不能当成普通用户可用的完整功能；网页展示的 18 个专属动作也不会自动套用到任意上传照片。仓库目前提供源码，还没有一键安装包。想立即制作桌宠，请使用完整、透明背景的卡通 PNG。本项目是独立社区项目，与 OpenAI 或 Codex 无隶属关系。

## 真人照片与卡通桌宠对照

<p align="center">
  <img src="docs/images/pet-demo/reference-photo.jpg" height="340" alt="最初的真人参考照片" />
  <img src="docs/images/pet-demo/idle-portrait.png" height="300" alt="参照真人照片制作的卡通桌宠" />
</p>

左右图展示同一位作者自有角色：本人提供的参考照片，以及参照人物特征人工设计并多轮调整的卡通女孩。网站展示、动作预览与桌面运行器内置示例复用这套素材。**这只是定制案例；上传任意照片不会自动生成同等精细的卡通立绘和动作绑定。**

<p align="center"><img src="docs/images/pet-demo/action-gallery.png" width="760" alt="定制角色的待机、眨眼和左右跑动作" /></p>

[查看网页对照](https://lesile1312.github.io/PetForge/#example) · [查看跑步帧组](docs/images/pet-demo/run-cycle.png)

## 定制角色的 18 种动作

[查看完整动作图册和动画预览](https://lesile1312.github.io/PetForge/#actions)。网页展示 18 张角色动作图，并提供 3 段由 Godot 桌面运行器以 60 FPS 原速渲染的动画，其中包含完整 16 秒的玩手机动作。

- **日常状态（4）**：安静呼吸待机、等待输入、眨眼微笑、睡觉。
- **移动（2）**：向左跑动、向右跑动。
- **问候与手势（11）**：招手微笑、开心微笑、点头致意、整理头发、照镜子、托腮思考、左右张望、害羞摸脸、抬手舒展、捂嘴轻笑、送出小爱心。
- **手机互动（1）**：蹲下看屏幕、点按、滑动。

这些是展示角色专用的动作素材。新上传的图片不会自动获得这些姿势、动画帧或角色专属绑定。

## 当前能做什么

| 功能 | 当前状态 |
| --- | --- |
| 用自己的 PNG 制作桌宠 | 可创建资源包并运行通用 Godot 桌宠，无需 AI 模型 |
| 处理人物照片 | 本机人物抠图与漫画滤镜，保留原图并展示前后对照 |
| 显示在整个桌面 | 独立透明无边框窗口，可拖动、置顶，独立于浏览器 |
| 行为互动 | 展示角色有 18 种专属动作图；通用运行器提供待机、移动、睡眠、跳跃和点击反馈。其他图片不会自动继承该角色的细致手势 |
| 导出资源 | `pet.json`、`character.png`，以及可选抠图和静态 GLB |
| 公开网页 | 本地选图预览和保存 `.petforge.json` 参考文件，不提供云端图片生成 |
| 照片识别、卡通重绘与动作适配 | 本地 P0 实验分支已有技术验证代码；未接入网页，真实照片画质/动作与 Godot 集成尚未验收。见[技术设计](docs/photo-to-pet-technical-design.zh-CN.md)和[P0 记录](docs/superpowers/plans/2026-10-28-photo-to-18-actions-p0.md) |

当前可以用透明 PNG 创建桌宠；本机编辑器上传照片后仍得到抠图与滤镜结果。实验 worker 正在验证“照片识别 → 卡通化 → 动作预览 → 桌面宠物”链路，但尚未成为可从网页启动的完整流程。需要马上运行时，请准备卡通 PNG；新图片不会自动获得示例角色的跑步帧或专属动作。

## 路线一：直接用自己的透明 PNG，制作桌宠

需要 Windows 10/11 x64、PowerShell、项目源码与 Godot 4。**这条路线无需 Node.js、Python、CUDA 或 AI 账号。**

1. 下载并解压仓库 ZIP，或克隆项目：

```powershell
git clone https://github.com/lesile1312/PetForge.git
cd PetForge
```

2. 准备透明 PNG：人物完整，头发、手脚四周留出透明边距。如果原图有不透明背景，桌宠也会带着该背景显示。
3. 将命令中的两个路径换成你自己的图片路径和 Godot 可执行文件路径：

```powershell
.\scripts\create-pet.ps1 -ImagePath 'C:\Pictures\my-character.png' -Name '我的桌宠' -GodotExecutable 'C:\Tools\Godot\Godot.exe'
```

脚本会显示生成目录并启动宠物。每次新建一个 `storage/custom-pets/` 子文件夹，保留原始图片，不覆盖已有资源包。只制作文件、暂不启动时使用：

```powershell
.\scripts\create-pet.ps1 -ImagePath 'C:\Pictures\my-character.png' -Name '我的桌宠' -NoLaunch
```

鼠标左键拖动，右键切换互动；让宠物获得焦点后按 Esc 退出。宠物显示在独立桌面窗口中。单张平面 PNG 的动作表现取决于图片及现有绑定，不能直接获得示例的全部精细动作。

## 路线二：从真人照片开始，使用本机编辑器

### 准备环境

- Windows 10/11 x64；Git 或下载解压后的仓库。
- Node.js 22.13 以上、pnpm 11.19.0（与项目 `package.json` 一致；pnpm 需要此 Node 版本）。
- Python 3.12，确保 `py` 启动器或 `python.exe` 可用。
- Godot 4，项目当前开发使用 Godot 4.7.2，请选择兼容的 Godot 4 版本。
- 安装依赖和首次下载抠图模型时需要联网。2D 人物抠图可用 CPU；CUDA 显卡只属于可选的 TripoSR 实验要求。

### 安装与启动

在项目根目录执行：

```powershell
npm install --global pnpm@11.19.0
.\scripts\setup.ps1
```

安装脚本会在 `.env` 不存在时创建它。编辑其中这一行，填写你电脑上的实际路径：

```dotenv
PETFORGE_GODOT_EXECUTABLE=C:/Tools/Godot/Godot.exe
```

然后启动网页和 API：

```powershell
pnpm dev
```

保持终端打开，访问 <http://127.0.0.1:3000/>。API 健康检查地址为 <http://127.0.0.1:8000/health>。公开 GitHub Pages 网页不会自动启动你电脑上的服务。

### 从照片到桌宠的具体操作

1. 选择 PNG/JPG/WEBP 照片，最大 10 MB；也可以选择公开网页保存的 `.petforge.json` 参考文件。
2. 等待本机人物分割与漫画滤镜处理。首次加载可能下载模型；头发遮挡、复杂背景的效果需要检查。
3. 对照参考原图与透明处理结果，调整大小和行为设置。当前不会自动补全身体或 AI 重绘成新卡通人物。
4. 满意后点击 **启动桌宠**。`.env` 中需要配置 Godot；修改环境配置后要重新启动 `pnpm dev`。桌宠使用独立原生窗口显示。
5. 点击 **导出资源**，保存你自己的桌宠 ZIP。这个 ZIP 是资源包，不是 Windows 安装程序。

**2D 制作不会自动运行 3D 建模。** 只有你主动选择可选的 3D 实验时，才需要单独运行 `scripts/setup-ai.ps1` 配置 TripoSR。它会下载较大的模型与运行环境，需要兼容的 CUDA 显卡。

### 再次启动或分享导出的宠物

把 ZIP 解压到独立目录，保留 `pet.json`、`character.png` 和它引用的素材。在项目根目录执行：

```powershell
& 'C:\Tools\Godot\Godot.exe' --path '.\apps\desktop' -- --pet-project 'C:\MyPets\MyCompanion'
```

替换为你的实际路径。桌宠可以独立于网页运行；让宠物获得焦点后按 Esc 退出。发给别人试用时，对方也需要本项目与 Godot，或兼容的自定义桌宠petforge 桌面运行器；单发资源 ZIP 不会自动为对方安装运行程序。

## 常见问题

| 问题 | 处理办法 |
| --- | --- |
| 打不开 `127.0.0.1:3000` | 先在这台电脑启动 `pnpm dev`，保持终端运行。公网演示页不等于本机编辑器。 |
| 提示未配置 Godot | 填好 `.env` 的实际可执行文件路径并重启服务；直启脚本使用 `-GodotExecutable`。 |
| PowerShell 禁止运行脚本 | 阅读脚本后，可用 `powershell -NoProfile -ExecutionPolicy Bypass` 新开仅当前进程放行的终端再执行，无需修改整机策略。 |
| 安装失败 | 核对 Node、pnpm、Python 版本，按终端报错修复后重跑 `scripts/setup.ps1`。 |
| 抠图很慢或失败 | 首次可能下载模型；检查 API 终端、网络和磁盘空间。也可以先用透明 PNG 路线。 |
| 看起来只是照片滤镜 | 当前就是抠图加漫画滤镜。希望使用 Q 版角色时，请先提供画好的透明卡通 PNG。 |
| 头发或脚被裁掉 | 检查原图与抠图边缘，保留透明边距；运行器无法恢复原图已经缺失的部分。 |
| 自己的图片没有演示人物的动作 | 演示角色使用定制素材，新 PNG 只获得通用行为，不会自动生成同样的肢体绑定与新动画帧。 |
| 3D 模型失败 | 继续使用 2D 桌宠。3D 是单独实验，需要额外环境。 |

## 隐私、开源许可与贡献

公开网页选图只在当前浏览器预览，除非用户主动下载或分享参考文件。本机编辑器把照片发送到同一台电脑的 FastAPI；原图、生成图和数据库默认保存在 `storage/`。可以通过 `PETFORGE_STORAGE_ROOT` 和 `PETFORGE_DATABASE_PATH` 修改位置。直启脚本不上传图片。请勿提交 `.env`、个人项目和模型缓存。

演示真人照片是按创作者要求公开展示的素材，不随源代码许可授予再利用权，见[第三方与素材说明](THIRD_PARTY_NOTICES.md)。源代码采用 [Apache-2.0](LICENSE)，模型权重与素材遵循各自条款。

API 当前面向本地开发；公开托管前需要补齐访问控制、配额、存储和照片保留策略。依赖需要持续安全更新，开发构建通过不等于完成安全审计。

欢迎贡献安装包、通用角色绑定、自然动作和编辑体验改进。提交 Issue 时附复现步骤、系统与版本，避免附带私人照片和密钥。

## 工程结构与技术资料

[制作流程核对记录](docs/validation-2026-10-23.md)列出了本机已检查的环节，以及尚未覆盖的验证范围。

```text
apps/web/              Next.js 本机编辑器
apps/desktop/          Godot 透明桌宠运行器
services/api/          FastAPI 与本机图片处理
packages/pet-schema/   共享宠物配置格式
scripts/create-pet.ps1 自有 PNG 直启入口
storage/               本地私人项目，Git 忽略
docs/                  公开网页与技术文档
```

[架构](docs/architecture.md) · [照片到桌宠技术设计](docs/photo-to-pet-technical-design.zh-CN.md) · [资源包格式](docs/pet-format.md) · [开发说明](docs/development.md) · [项目状态](docs/project-status.md)
