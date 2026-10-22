# PetForge 当前工程审计

日期：2026-10-22。方式：读取源码、配置、现有产物与历史验证记录。没有在本轮启动模型、重跑网页端到端流程、修改桌宠功能或发布 GitHub。

建议先阅读 [下一阶段技术设计](photo-to-pet-technical-design.zh-CN.md)。本文区分当前代码具有什么、已有证据是什么，以及下一阶段还缺什么。

## 1. 实际工程组成

| 部分 | 当前事实与定位 |
| --- | --- |
| 根工作区 | pnpm monorepo，包版本 0.1.0；根脚本支持 Web/API 开发和类型检查/构建 |
| Web | package.json 声明 Next.js `^16.4.0`、React `^19.3.0`、TypeScript、Tailwind 3；具体安装版本由 lockfile/安装环境确定 |
| API | FastAPI + Pydantic 2 + SQLite + 本地文件；有上传、抠图、滤镜、3D、导出和本机启动接口 |
| 本地抠图 | 默认 `RembgBackgroundRemovalProvider`，使用 `birefnet-portrait`；另有 edge-matte 和 mock |
| 卡通化 | Pillow 调色、降色、轮廓与贴纸描边；不是基于照片生成新的卡通立绘 |
| AI 动画接口 | `MockAnimationProvider` 返回 `not_generated`；不能理解为已经能生成动作素材 |
| 3D | 独立 TripoSR 子进程生成静态 GLB；当前命令明确指定 `cuda:0`，不具备通用 CPU 生成后端 |
| 桌面 | Godot 4 工程，透明、无边框、置顶、拖动、状态机和程序化/帧动画 |
| 定制成品 | `deliverables/CodexDesktopPet` 保存特定人物版本、素材、脚本快照和预览；当前活动包文件夹仍叫 `godot_package_v21`，最近动作修订为 v38 |
| Git | PetForge 目录存在 `.git`；本轮只读查询确认分支尚无提交，没有 remote 输出。未进行提交、配置修改或推送 |

Git 只读查询使用单次命令的 `safe.directory` 参数处理旧沙箱文件所有者差异，没有改全局 Git 信任设置。

## 2. 当前网页生成流程

源码中的流程是：创建项目 → 上传图片 → rembg 抠图 → Pillow 漫画滤镜 → 编辑器 → 可选本机 Godot 启动 + TripoSR 静态 3D 重建。

重点文件：

- [Web 流程](../apps/web/components/studio.tsx)：`processImage()` 调用抠图，随后尝试启动本地桌宠并运行 3D 生成。
- [浏览器 API 封装](../apps/web/lib/api.ts)：使用同源 `/api`。
- [Next.js 代理](../apps/web/next.config.ts)：将 `/api/*` 转给 FastAPI；开发和生产的 Runtime 模式不同。
- [API 主入口](../services/api/app/main.py)：REST 路由、上传限制、项目保存、导出与进程启动。
- [抠图 Provider](../services/api/app/providers/background.py)：真实 rembg 和有限制的边缘颜色算法。
- [滤镜](../services/api/app/providers/cartoon.py)：确定性图像处理。
- [动画接口](../services/api/app/providers/animation.py)：当前仍为 Mock。
- [3D Provider](../services/api/app/providers/model.py)：TripoSR 环境、GLB、日志与超时。

这证明相关代码存在，不证明网页、模型环境与桌面成品已经形成通用端到端产品。本轮没有刷新其运行验收结果。

## 3. 当前定制桌宠能复用什么

- 透明桌面窗口、命中轮廓与鼠标穿透、屏幕边界、自动活动调度、拖动等运行器基础。
- 双向跑步素材、静止微动、眨眼、招手、微笑、鞠躬、理发、镜子、思考、捂嘴笑/哈欠、摸脸、伸展、看左右、爱心、睡觉与手机动作的迭代经验。
- 手臂连续角度、有限手腕弯折、前后遮挡、道具锚定与头部固定尺度等约束。
- 现有可重复动作捕获脚本，以及原尺寸预览、局部细节、阶段接触图和帧级观察报告。

相关文件：

- [运行器](../apps/desktop/scripts/pet_controller.gd)
- [动画控制](../apps/desktop/scripts/animation/static_sprite_animation.gd)
- [手势绑定](../apps/desktop/scripts/animation/gesture_rig.gd)
- [手机动作](../apps/desktop/scripts/animation/phone_action.gd)
- [行为调度](../apps/desktop/scripts/ambient_repertoire.gd)
- [动作捕获](../apps/desktop/tools/preview_gestures.gd)

但 `gesture_rig.gd` 和 `phone_action.gd` 中仍有特定人物的原点、肩肘腕、头部裁切和颈部接合坐标；它们不能不经转换用于每个新上传的人物。手机等动作还依赖专用生成姿态素材。

最近 v38 的既有证据在 `deliverables/CodexDesktopPet/source/live_v38_release/`：记录了 8 类抬手动作的完整渲染和修订前后参数。按现有报告统计，渲染 1847 帧、目标 60 Hz，观察值约 59.42–60.49 FPS；这是本机该人物的已有记录，本轮未重新测量，也不代表通用照片流程或所有目标电脑达到同一结果。

当前角色显示 scale 为 0.88；左右跑各 8 张图，以 12 FPS 播放。连续骨架更新频率、素材帧率和显示器刷新率是不同指标。

## 4. 必须先解决的协议缺口

共享定义：

- [TypeScript](../packages/pet-schema/src/index.ts)
- [JSON Schema](../packages/pet-schema/schemas/pet.schema.json)
- [Pydantic](../services/api/app/models.py)

共享 `appearance` 主要为 sprite / model / scale，JSON Schema 不允许额外属性，Pydantic 同样 `extra="forbid"`。定制成品包则使用 `animationFrames / animationFps / animationFpsByAction / gestureRig`，并使用不同于 API 正则的 ID。

因此，“共享格式一致”目前只能作为架构目标，不能作为全部现有资源的真实兼容保证。新链路必须先明确 2.0 schema 和两种旧包迁移方式。

## 5. 已发现的产品化缺口

| 缺口 | 影响 | 下一步 |
| --- | --- | --- |
| 没有通用卡通重绘 Provider | 滤镜不能达到现在定制卡通人物的效果 | P0 参考图重绘验证 |
| 没有通用分层/绑定生成器 | 换人就要手改坐标与素材 | 标准姿态、零件模板、补绘、绑定编辑 |
| 任务缺少持久化生命周期 | 长时间推理失败/刷新后难恢复 | jobs 表、Worker、阶段产物与重试 |
| 网页自动进入 3D 实验流程 | 增加 GPU 要求和等待，偏离已确认的 2D 主线 | 作为单独可选实验入口 |
| 启动以进程存活判断 | 存活不代表窗口和人物已加载 | Runtime ready 确认和失败日志 |
| 导出 ZIP 非 Windows 安装器 | 访客拿到包仍需运行器 | 创建器/播放器分别分发 |
| 原项目上传/恢复会清理部分派生产物 | 不满足长期保留每次修订的通用产品设计 | 版本化目录，显式清理操作 |
| 开发 AI 脚本假设固定磁盘和 CUDA | 普通用户安装不可靠 | 路径选择、设备探测、CPU 配置 |
| 仅有本地来源限制，没有完整会话保护 | 具有本机启动能力的接口需加强边界 | Loopback/Host/Origin + 会话与 CSRF |
| `.gitignore` 未排除私人 deliverables | 全量 add 有公开真人素材风险 | 单独白名单发布候选，重新检查待发布清单 |
| 旧文档相互不同步 | `architecture.md` 仍写 edge-matte 为当前；README 已描述 rembg | 以本审计为现阶段事实，新功能完成后再统一正式文档 |

## 6. 本轮边界

本轮读取当前源码、Git 元信息和历史渲染产物，核对上游项目/模型说明；新增技术设计与审计文档，并添加 README 入口。没有修改应用逻辑，没有运行新测试或下载模型，没有重启现有桌宠，没有发布仓库。

下一步建议是审阅设计后执行 P0，用不同人物样例确认本地重绘、分层绑定与基础动作的可行性，再进入产品实现。
