# 3D Gaussian Splatting (3DGS) 速查

> 2026-06-17 调研，点点有兴趣。
> 3DGS = 一组 2D 照片 → 几百万个彩色小椭球拼成的 3D 场景 → 实时渲染、浏览器能跑。

---

## 一、核心仓库

| 项目 | GitHub | 说明 |
|:---|:---|:---|
| 原版官方实现 | [graphdeco-inria/gaussian-splatting](https://github.com/graphdeco-inria/gaussian-splatting) | SIGGRAPH 2023 论文配套，CUDA |
| 加速版 gsplat | [nerfstudio-project/gsplat](https://github.com/nerfstudio-project/gsplat) | 比原版更快更省内存，Python 绑定 |
| 资源大全 | [MrNeRF/awesome-3D-gaussian-splatting](https://github.com/MrNeRF/awesome-3D-gaussian-splatting) | 论文/实现/查看器/工具链汇总 |

## 二、零代码直接看/编辑（浏览器打开就能用）

| 工具 | 链接 | 用途 |
|:---|:---|:---|
| **SuperSplat** 🏆 | [supersplat.xyz](https://supersplat.xyz) | 拖入 .ply 直接看、编辑、裁剪、导出 → 最推荐 |
| Polycam | [poly.cam](https://poly.cam) | 手机拍照 → 自动生成 3DGS 场景 |
| Evova 3D Showroom | [evova.ai](https://evova.ai) | 上传 .ply → 生成可分享链接/可嵌入 iframe |
| Mip-Splatting 查看器 | [niujinshuchong.github.io/mip-splatting-demo](https://niujinshuchong.github.io/mip-splatting-demo/) | 拖入 .ply/.splat/.ksplat 在线看 |

## 三、Web 渲染库（自建查看器用）

| 项目 | GitHub | 说明 |
|:---|:---|:---|
| GaussianSplats3D 🌐 | [mkkellogg/GaussianSplats3D](https://github.com/mkkellogg/GaussianSplats3D) | Three.js 实现，浏览器跑，支持 .ply/.splat/.ksplat |
| antimatter15/splat 🖥️ | [antimatter15/splat](https://github.com/antimatter15/splat) | WebGL 轻量查看器 |
| 线上 Demo | [projects.markkellogg.org/threejs/demo_gaussian_splats_3d.php](https://projects.markkellogg.org/threejs/demo_gaussian_splats_3d.php) | 盆景树 3DGS 场景，直接打开 |后面想想后面怎么调用这块，先存在这里 到时候可以直接用。 

## 四、本地已克隆

```
tmp/3dgs-demo/ (GaussianSplats3D)
```
当前因缺少样例 .ply 文件未跑通本地 demo，推荐直接用线上查看器。

## 五、通俗理解

- **NeRF**：AI 学会「光怎么反射」，每次看都要现场算
- **3DGS**：把场景拆成几百万个半透明彩色小斑点丢在空间里，直接渲染 → 训练快 + 实时渲染 + 浏览器也能跑
- 应用：VR/AR、游戏场景重建、房地产看房、文物保护扫描、电影特效
