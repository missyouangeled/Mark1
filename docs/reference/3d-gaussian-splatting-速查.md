# 3D Gaussian Splatting (3DGS) 详细档案

> 📅 2026-06-17 调研整理
> 从入门到实操，一步到位。

---

## 一、这是什么

**3D Gaussian Splatting = 把一组 2D 照片/视频变成可自由漫游的 3D 场景。**

技术原理：
- 用几百万个彩色半透明小椭球（"3D 高斯"）拼出 3D 场景
- 每个椭球有自己的位置、方向、大小、颜色、透明度
- 不是 AI 推理，而是直接渲染——所以快到浏览器都能实时跑
- 2023 年 SIGGRAPH 最佳论文奖，2024-2026 年爆发式普及

一句话：拍一圈照片 → 得到一个你可以走进去的 3D 世界。

应用：VR/AR、游戏场景重建、房地产三维看房、文物保护数字存档、电影特效场景生成。

---

## 二、核心仓库（开发者向）

| 项目 | GitHub | 说明 |
|:---|:---|:---|
| 原版官方实现 | [graphdeco-inria/gaussian-splatting](https://github.com/graphdeco-inria/gaussian-splatting) | SIGGRAPH 2023 论文配套代码，CUDA |
| 加速版 gsplat | [nerfstudio-project/gsplat](https://github.com/nerfstudio-project/gsplat) | 比原版更快更省内存，Python 绑定，Nerfstudio 生态 |
| 资源大全 | [MrNeRF/awesome-3D-gaussian-splatting](https://github.com/MrNeRF/awesome-3D-gaussian-splatting) | 论文清单、各种实现、查看器、工具链汇总 |

---

## 三、零代码在线查看/编辑（浏览器打开就能用）

| 工具 | 链接 | 用途 |
|:---|:---|:---|
| **SuperSplat** 🏆 | [supersplat.xyz](https://supersplat.xyz) | 拖入 .ply → 直接看、编辑、裁剪、压缩、导出 |
| Polycam Web 查看器 | [poly.cam/tools/gaussian-splatting](https://poly.cam/tools/gaussian-splatting) | 上传照片/视频生成 3DGS，网页端 |
| Mip-Splatting 查看器 | [niujinshuchong.github.io/mip-splatting-demo](https://niujinshuchong.github.io/mip-splatting-demo/) | 拖入 .ply/.splat/.ksplat 在线看 |
| 官方线上 Demo | [projects.markkellogg.org/threejs/demo](https://projects.markkellogg.org/threejs/demo_gaussian_splats_3d.php) | 盆景树 3DGS 场景，直接打开感受效果 |
| Evova 3D Showroom | [evova.ai](https://evova.ai) | 上传 .ply → 生成可分享链接/可嵌入 iframe |

---

## 四、📱 手机 App：拍照/拍视频 → 自动生成 3DGS（零门槛）

### 方案一：Polycam（iPhone + Android）

| 项 | 信息 |
|:---|:---|
| 下载 | App Store / Google Play 搜 "Polycam" |
| 价格 | 免费（7 天免费试用 Pro） |
| 功能 | 拍照 / 录视频 → 云端自动生成 3DGS → 网页查看 / 导出 .ply |
| 注册 | 首次使用需注册账号 |

**操作步骤：**

1. 手机下载并打开 **Polycam**
2. 注册/登录账号
3. 点击 **Create** → 选择 **Gaussian Splat**
4. 两种方式拍照：
   - **拍照模式**：从左、从右、从上、从下绕着目标拍 20-200 张照片（JPG/PNG），多角度覆盖
   - **视频模式**：绕目标匀速拍一段视频（MP4），15 秒以上
   - 无人机也行——DJI 用 "Point of Interest" 环绕功能效果极佳
5. 上传 → 云端处理 → 几分钟后得到可交互的 3DGS 场景
6. 导出：Polycam 内支持导出 .ply 文件，可丢进 SuperSplat 继续编辑

**拍摄注意事项：**
- ✅ 光线均匀、避免强烈逆光
- ✅ 图片清晰、无运动模糊
- ✅ 多角度覆盖（上下左右前后面都拍到）
- ❌ 避免浅景深（虚化背景）
- ❌ 避免反光极强的表面
- 图片越多越清晰（默认建议 20-200 张）

### 方案二：Scaniverse（iPhone + Android，完全免费）

| 项 | 信息 |
|:---|:---|
| 下载 | App Store / Google Play 搜 "Scaniverse" |
| 开发商 | Niantic（Pokémon GO 的开发商） |
| 价格 | **完全免费**，无限制，端侧处理不消耗云端额度 |
| 特色 | iPhone 端本地处理（不联网也能生成）、轻松导出 .ply / .splat / SPZ |

**操作步骤：**

1. 下载并打开 **Scaniverse**
2. 点击 **New Scan** → 选择 **Splat** 模式
3. 对着目标物体/场景，保持手机匀速移动 1-2 分钟，从多个角度拍摄
4. 手机会自动本地处理（iPhone 端无需联网）→ 几分钟后生成 3DGS
5. 可导出：
   - **PLY** — 标准 3DGS 格式，丢进 SuperSplat 编辑
   - **SPZ** — Niantic Studio 格式
   - **OBJ / FBX / GLB / USDZ / LAS** — 传统 3D 格式（mesh）

**与 Polycam 对比：**

| 特性 | Polycam | Scaniverse |
|:---|:---|:---|
| 价格 | 免费版有限制 | **完全免费无限制** |
| 处理方式 | 云端处理 | iPhone 端本地处理 |
| 需要联网 | 是 | 否（本地模式） |
| 导出格式 | .ply, .obj 等 | .ply, .splat, .spz, .obj, .fbx, .glb 等 |
| 社区/地图 | 有 | 有全球扫描地图 |

### 方案三：Luma AI（已不推荐）

Luma AI 曾被广泛推荐，但 Genies 收购后路线改变，推荐使用 Polycam 或 Scaniverse。

---

## 五、生成后怎么玩

### 路径 A：手机上直接看 + 分享
- Polycam / Scaniverse 内直接看，生成链接发给别人

### 路径 B：导出 → SuperSplat 编辑
1. 从 App 导出 .ply 文件
2. 打开 [supersplat.xyz](https://supersplat.xyz)
3. 拖入 .ply → 裁剪、旋转、压缩、调色 → 导出

### 路径 C：嵌入网页
- Evova 3D Showroom：上传 .ply → 生成 HTML iframe 代码 → 贴到任意网页

### 路径 D：丢进游戏引擎
- Unity：用 [UnityGaussianSplatting](https://github.com/aras-p/UnityGaussianSplatting) 插件导入
- Unreal：市场有 [3D Gaussians Plugin](https://www.unrealengine.com/marketplace/en-US/product/3d-gaussians-plugin)

---

## 六、本地已克隆参考

```
tmp/3dgs-demo/ （GaussianSplats3D — Three.js 查看器）
```
因缺少样例 .ply 文件未跑通完整本地 demo，推荐直接用线上查看器。

---

## 七、进阶路线

| 阶段 | 做什么 |
|:---|:---|
| 🟢 入门 | 用 Polycam/Scaniverse 拍一个物体，手机上看看效果 |
| 🟡 进阶 | 导出 .ply → SuperSplat 编辑 → 分享链接给别人 |
| 🟠 创作 | 嵌入网页、导入 Unity/UE、做自己的 3D 展示 |
| 🔴 自训练 | 用 gsplat / INRIA 原版在 GPU 上自己训练模型 |

---

## 八、常见问题

**Q: 拍多少张照片够？**
最少 20 张，推荐 50-100 张。角度越多越好——上下左右前后全拍一遍。

**Q: 视频行不行？**
行。Polycam 支持 MP4 视频输入，绕目标匀速拍摄效果很好。

**Q: 生成的 .ply 文件多大？**
取决于 splat 数量。10 万 splats ≈ 几十 MB；100 万 splats ≈ 几百 MB；200 万 splats 可能上 GB。

**Q: 需要什么手机？**
普通智能手机就行。iPhone 有 LiDAR 会更好但不必须；Scaniverse 甚至支持非 Pro iPhone。

**Q: 需要 GPU 吗？**
只在手机上生成：不需要（云端/端侧处理）。本地自己训练模型：需要 CUDA GPU。

---

*后续有新的实践经验或工具发现，直接追加到本文件。*
