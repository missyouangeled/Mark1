# Wall 重命名计划

> 生成时间: 2026-06-05 16:29
> 源目录: Assets/AssetScene/SceneModels/Wall/
> 总文件数: 250 | Prefab:59 Material:5 FBX:37 贴图:13 .meta:135
> 顶层文件夹: Gate_double / Gate_single / Wall_Standard / Wall_Stone
> 本计划基于 V3 基础规则 + Wall 专项规则

---

## 一、前缀规则

| # | 文件类型 | 前缀 | 示例 |
|---|---------|------|------|
| 1 | `.prefab` / `.fbx` / 贴图 | `Props_` | `Wall_H_01m_02m.prefab` → `Props_Wall_H_01m_02m.prefab` |
| 2 | `.mat` 材质球 | `Mat_` | `Mat_Wall_Fence_02.mat`（已符合） |
| 3 | `.meta` | 跟随主文件同步 | 不单独命名 |

## 二、清理规则

| # | 规则 | 说明 |
|---|------|------|
| 1 | 删除 `Type_` / `SceneStatic_` | 类型/前缀标记删除 |
| 2 | 删除 `-` 及后面 | 连字符后缀删掉 |
| 3 | PascalCase 拆分 | `WithPost` → `With_Post` |

## 三、目录结构规则

| # | 规则 | 说明 |
|---|------|------|
| 1 | Gate_single/Material/All/ 扁平化 | All 子文件夹材质/贴图拉平到 Material/ 根目录 |
| 2 | Wall_Standard Prefab 子文件夹 | H1M/H2M/H2M6/Rubble 各建 Model/ 和 Material/ 子文件夹 |
| 3 | Wall_Standard/Model → Prefab 搬迁 | Model/*.fbx 按名字搬入对应 Prefab/{H1M|H2M|H2M6|Rubble}/Model/ |
| 4 | Wall_Fence_02 材质合入 | 移入 H1M/Material/（供其他子文件夹共用） |

## 四、排除规则（不动目录结构）

| # | 文件夹 | 原因 |
|---|--------|------|
| 1 | Gate_double/ | 已符合 Prefab/Model/Materials 结构，仅重命名 |
| 2 | Gate_single/Prefab/ + model/ | 位置不动，仅扁平化 Material/All + 重命名 |
| 3 | Wall_Stone/ | 已符合 Prefab/Model/Materials 结构，仅重命名 |

## 五、特殊处理

| # | 文件夹 | 处理 |
|---|--------|------|
| 1 | Gate_single Prefab | `Gate_Single_Type_02#BrickIndustrial_06` → `Props_Gate_Single`（去 Type-/去 #后缀） |
| ⚠️ | **H2M PaintWhite 丢失** | 12 个 `#PaintWhite` 变体 prefab 被 `#BrickIndustrial_06` 同名覆盖。待从 git 恢复。详见 H2M 章节 |

---

## 六、文件清单

## Gate_double/

| 文件名 | 路径（相对 Wall/） | 类型 |
|---|---|---|
| `Materials.meta` | `Gate_double/Materials.meta` | .meta |
| `Model.meta` | `Gate_double/Model.meta` | .meta |
| `Prefab.meta` | `Gate_double/Prefab.meta` | .meta |
| `Mat_Wall_Gate_Double.mat` | `Gate_double/Materials/Mat_Wall_Gate_Double.mat` | Material |
| `Mat_Wall_Gate_Double.mat.meta` | `Gate_double/Materials/Mat_Wall_Gate_Double.mat.meta` | .meta |
| `Props_Wall_Gate_Double_Albedo.tif` | `Gate_double/Materials/Props_Wall_Gate_Double_Albedo.tif` | 贴图 |
| `Props_Wall_Gate_Double_Albedo.tif.meta` | `Gate_double/Materials/Props_Wall_Gate_Double_Albedo.tif.meta` | .meta |
| `Props_Wall_Gate_Double_Mask.png` | `Gate_double/Materials/Props_Wall_Gate_Double_Mask.png` | 贴图 |
| `Props_Wall_Gate_Double_Mask.png.meta` | `Gate_double/Materials/Props_Wall_Gate_Double_Mask.png.meta` | .meta |
| `Props_Wall_Gate_Double_Normal.tif` | `Gate_double/Materials/Props_Wall_Gate_Double_Normal.tif` | 贴图 |
| `Props_Wall_Gate_Double_Normal.tif.meta` | `Gate_double/Materials/Props_Wall_Gate_Double_Normal.tif.meta` | .meta |
| `Props_Wall_Gate_Double_01.FBX` | `Gate_double/Model/Props_Wall_Gate_Double_01.FBX` | FBX |
| `Props_Wall_Gate_Double_01.FBX.meta` | `Gate_double/Model/Props_Wall_Gate_Double_01.FBX.meta` | .meta |
| `Props_Wall_Gate_Double_02.FBX` | `Gate_double/Model/Props_Wall_Gate_Double_02.FBX` | FBX |
| `Props_Wall_Gate_Double_02.FBX.meta` | `Gate_double/Model/Props_Wall_Gate_Double_02.FBX.meta` | .meta |
| `Props_Wall_Gate_Double_03.FBX` | `Gate_double/Model/Props_Wall_Gate_Double_03.FBX` | FBX |
| `Props_Wall_Gate_Double_03.FBX.meta` | `Gate_double/Model/Props_Wall_Gate_Double_03.FBX.meta` | .meta |
| `Props_Wall_Gate_Double_01.prefab` | `Gate_double/Prefab/Props_Wall_Gate_Double_01.prefab` | Prefab |
| `Props_Wall_Gate_Double_01.prefab.meta` | `Gate_double/Prefab/Props_Wall_Gate_Double_01.prefab.meta` | .meta |
| `Props_Wall_Gate_Double_02.prefab` | `Gate_double/Prefab/Props_Wall_Gate_Double_02.prefab` | Prefab |
| `Props_Wall_Gate_Double_02.prefab.meta` | `Gate_double/Prefab/Props_Wall_Gate_Double_02.prefab.meta` | .meta |
| `Props_Wall_Gate_Double_03.prefab` | `Gate_double/Prefab/Props_Wall_Gate_Double_03.prefab` | Prefab |
| `Props_Wall_Gate_Double_03.prefab.meta` | `Gate_double/Prefab/Props_Wall_Gate_Double_03.prefab.meta` | .meta |

## Gate_single/

| 文件名 | 路径（相对 Wall/） | 类型 |
|---|---|---|
| `Material.meta` | `Gate_single/Material.meta` | .meta |
| `Prefab.meta` | `Gate_single/Prefab.meta` | .meta |
| `model.meta` | `Gate_single/model.meta` | .meta |
| `Mat_Main.mat` | `Gate_single/Material/Mat_Main.mat` | Material |
| `Mat_Main.mat.meta` | `Gate_single/Material/Mat_Main.mat.meta` | .meta |
| `Props_Albedo.tif` | `Gate_single/Material/Props_Albedo.tif` | 贴图 |
| `Props_Albedo.tif.meta` | `Gate_single/Material/Props_Albedo.tif.meta` | .meta |
| `Props_Main_Mask.png` | `Gate_single/Material/Props_Main_Mask.png` | 贴图 |
| `Props_Main_Mask.png.meta` | `Gate_single/Material/Props_Main_Mask.png.meta` | .meta |
| `Props_Normal.tif` | `Gate_single/Material/Props_Normal.tif` | 贴图 |
| `Props_Normal.tif.meta` | `Gate_single/Material/Props_Normal.tif.meta` | .meta |
| `Props_Gate_Single.fbx` | `Gate_single/model/Props_Gate_Single.fbx` | FBX |
| `Props_Gate_Single.fbx.meta` | `Gate_single/model/Props_Gate_Single.fbx.meta` | .meta |
| `Props_Gate_Single.prefab` | `Gate_single/Prefab/Props_Gate_Single.prefab` | Prefab |
| `Props_Gate_Single.prefab.meta` | `Gate_single/Prefab/Props_Gate_Single.prefab.meta` | .meta |

## Wall_Standard/

| 文件名 | 路径（相对 Wall/） | 类型 |
|---|---|---|
| `Materials.meta` | `Wall_Standard/Materials.meta` | .meta |
| `Model.meta` | `Wall_Standard/Model.meta` | .meta |
| `Prefab.meta` | `Wall_Standard/Prefab.meta` | .meta |
| `H1M.meta` | `Wall_Standard/Prefab/H1M.meta` | .meta |
| `H2M.meta` | `Wall_Standard/Prefab/H2M.meta` | .meta |
| `H2M6.meta` | `Wall_Standard/Prefab/H2M6.meta` | .meta |
| `Rubble.meta` | `Wall_Standard/Prefab/Rubble.meta` | .meta |
| `Props_Wall_H_01m_02m.prefab` | `Wall_Standard/Prefab/H1M/Props_Wall_H_01m_02m.prefab` | Prefab |
| `Props_Wall_H_01m_02m.prefab.meta` | `Wall_Standard/Prefab/H1M/Props_Wall_H_01m_02m.prefab.meta` | .meta |
| `Props_Wall_H_01m_02m_Fence.prefab` | `Wall_Standard/Prefab/H1M/Props_Wall_H_01m_02m_Fence.prefab` | Prefab |
| `Props_Wall_H_01m_02m_Fence.prefab.meta` | `Wall_Standard/Prefab/H1M/Props_Wall_H_01m_02m_Fence.prefab.meta` | .meta |
| `Props_Wall_H_01m_02m_Fence_X.prefab` | `Wall_Standard/Prefab/H1M/Props_Wall_H_01m_02m_Fence_X.prefab` | Prefab |
| `Props_Wall_H_01m_02m_Fence_X.prefab.meta` | `Wall_Standard/Prefab/H1M/Props_Wall_H_01m_02m_Fence_X.prefab.meta` | .meta |
| `Props_Wall_H_01m_02m_X.prefab` | `Wall_Standard/Prefab/H1M/Props_Wall_H_01m_02m_X.prefab` | Prefab |
| `Props_Wall_H_01m_02m_X.prefab.meta` | `Wall_Standard/Prefab/H1M/Props_Wall_H_01m_02m_X.prefab.meta` | .meta |
| `Props_Wall_H_01m_03m.prefab` | `Wall_Standard/Prefab/H1M/Props_Wall_H_01m_03m.prefab` | Prefab |
| `Props_Wall_H_01m_03m.prefab.meta` | `Wall_Standard/Prefab/H1M/Props_Wall_H_01m_03m.prefab.meta` | .meta |
| `Props_Wall_H_01m_03m_Fence.prefab` | `Wall_Standard/Prefab/H1M/Props_Wall_H_01m_03m_Fence.prefab` | Prefab |
| `Props_Wall_H_01m_03m_Fence.prefab.meta` | `Wall_Standard/Prefab/H1M/Props_Wall_H_01m_03m_Fence.prefab.meta` | .meta |
| `Props_Wall_H_01m_03m_Fence_X.prefab` | `Wall_Standard/Prefab/H1M/Props_Wall_H_01m_03m_Fence_X.prefab` | Prefab |
| `Props_Wall_H_01m_03m_Fence_X.prefab.meta` | `Wall_Standard/Prefab/H1M/Props_Wall_H_01m_03m_Fence_X.prefab.meta` | .meta |
| `Props_Wall_H_01m_03m_X.prefab` | `Wall_Standard/Prefab/H1M/Props_Wall_H_01m_03m_X.prefab` | Prefab |
| `Props_Wall_H_01m_03m_X.prefab.meta` | `Wall_Standard/Prefab/H1M/Props_Wall_H_01m_03m_X.prefab.meta` | .meta |
| `Props_Wall_H_01m_05m.prefab` | `Wall_Standard/Prefab/H1M/Props_Wall_H_01m_05m.prefab` | Prefab |
| `Props_Wall_H_01m_05m.prefab.meta` | `Wall_Standard/Prefab/H1M/Props_Wall_H_01m_05m.prefab.meta` | .meta |
| `Props_Wall_H_01m_05m_Fence.prefab` | `Wall_Standard/Prefab/H1M/Props_Wall_H_01m_05m_Fence.prefab` | Prefab |
| `Props_Wall_H_01m_05m_Fence.prefab.meta` | `Wall_Standard/Prefab/H1M/Props_Wall_H_01m_05m_Fence.prefab.meta` | .meta |
| `Props_Wall_H_01m_05m_Fence_X.prefab` | `Wall_Standard/Prefab/H1M/Props_Wall_H_01m_05m_Fence_X.prefab` | Prefab |
| `Props_Wall_H_01m_05m_Fence_X.prefab.meta` | `Wall_Standard/Prefab/H1M/Props_Wall_H_01m_05m_Fence_X.prefab.meta` | .meta |
| `Props_Wall_H_01m_05m_X.prefab` | `Wall_Standard/Prefab/H1M/Props_Wall_H_01m_05m_X.prefab` | Prefab |
| `Props_Wall_H_01m_05m_X.prefab.meta` | `Wall_Standard/Prefab/H1M/Props_Wall_H_01m_05m_X.prefab.meta` | .meta |
| `Props_Wall_H_01m_Post.prefab` | `Wall_Standard/Prefab/H1M/Props_Wall_H_01m_Post.prefab` | Prefab |
| `Props_Wall_H_01m_Post.prefab.meta` | `Wall_Standard/Prefab/H1M/Props_Wall_H_01m_Post.prefab.meta` | .meta |
| `Props_Wall_H_01m_Post_X.prefab` | `Wall_Standard/Prefab/H1M/Props_Wall_H_01m_Post_X.prefab` | Prefab |
| `Props_Wall_H_01m_Post_X.prefab.meta` | `Wall_Standard/Prefab/H1M/Props_Wall_H_01m_Post_X.prefab.meta` | .meta |
| `Props_Wall_H_01m_Turn_Fence.prefab` | `Wall_Standard/Prefab/H1M/Props_Wall_H_01m_Turn_Fence.prefab` | Prefab |
| `Props_Wall_H_01m_Turn_Fence.prefab.meta` | `Wall_Standard/Prefab/H1M/Props_Wall_H_01m_Turn_Fence.prefab.meta` | .meta |
| `Props_Wall_H_01m_Turn_Fence_X.prefab` | `Wall_Standard/Prefab/H1M/Props_Wall_H_01m_Turn_Fence_X.prefab` | Prefab |
| `Props_Wall_H_01m_Turn_Fence_X.prefab.meta` | `Wall_Standard/Prefab/H1M/Props_Wall_H_01m_Turn_Fence_X.prefab.meta` | .meta |
| `Props_Wall_Fence_H_00M75_0M5.FBX` | `Wall_Standard/Prefab/H1M/Model/Props_Wall_Fence_H_00M75_0M5.FBX` | FBX |
| `Props_Wall_Fence_H_00M75_0M5.FBX.meta` | `Wall_Standard/Prefab/H1M/Model/Props_Wall_Fence_H_00M75_0M5.FBX.meta` | .meta |
| `Props_Wall_Fence_H_00M75_2M.FBX` | `Wall_Standard/Prefab/H1M/Model/Props_Wall_Fence_H_00M75_2M.FBX` | FBX |
| `Props_Wall_Fence_H_00M75_2M.FBX.meta` | `Wall_Standard/Prefab/H1M/Model/Props_Wall_Fence_H_00M75_2M.FBX.meta` | .meta |
| `Props_Wall_H_01m_02m.fbx` | `Wall_Standard/Prefab/H1M/Model/Props_Wall_H_01m_02m.fbx` | FBX |
| `Props_Wall_H_01m_02m.fbx.meta` | `Wall_Standard/Prefab/H1M/Model/Props_Wall_H_01m_02m.fbx.meta` | .meta |
| `Props_Wall_H_01m_03m.fbx` | `Wall_Standard/Prefab/H1M/Model/Props_Wall_H_01m_03m.fbx` | FBX |
| `Props_Wall_H_01m_03m.fbx.meta` | `Wall_Standard/Prefab/H1M/Model/Props_Wall_H_01m_03m.fbx.meta` | .meta |
| `Props_Wall_H_01m_05m.fbx` | `Wall_Standard/Prefab/H1M/Model/Props_Wall_H_01m_05m.fbx` | FBX |
| `Props_Wall_H_01m_05m.fbx.meta` | `Wall_Standard/Prefab/H1M/Model/Props_Wall_H_01m_05m.fbx.meta` | .meta |
| `Props_Wall_H_01m_Post.fbx` | `Wall_Standard/Prefab/H1M/Model/Props_Wall_H_01m_Post.fbx` | FBX |
| `Props_Wall_H_01m_Post.fbx.meta` | `Wall_Standard/Prefab/H1M/Model/Props_Wall_H_01m_Post.fbx.meta` | .meta |
| `Props_Wall_H_01m_Turn.fbx` | `Wall_Standard/Prefab/H1M/Model/Props_Wall_H_01m_Turn.fbx` | FBX |
| `Props_Wall_H_01m_Turn.fbx.meta` | `Wall_Standard/Prefab/H1M/Model/Props_Wall_H_01m_Turn.fbx.meta` | .meta |
| `Mat_Wall_Fence_02.mat` | `Wall_Standard/Prefab/H1M/Material/Mat_Wall_Fence_02.mat` | Material |
| `Mat_Wall_Fence_02.mat.meta` | `Wall_Standard/Prefab/H1M/Material/Mat_Wall_Fence_02.mat.meta` | .meta |
| `Props_Wall_Fence_02_Albedo.tif` | `Wall_Standard/Prefab/H1M/Material/Props_Wall_Fence_02_Albedo.tif` | 贴图 |
| `Props_Wall_Fence_02_Albedo.tif.meta` | `Wall_Standard/Prefab/H1M/Material/Props_Wall_Fence_02_Albedo.tif.meta` | .meta |
| `Props_Wall_Fence_02_Normal.tif` | `Wall_Standard/Prefab/H1M/Material/Props_Wall_Fence_02_Normal.tif` | 贴图 |
| `Props_Wall_Fence_02_Normal.tif.meta` | `Wall_Standard/Prefab/H1M/Material/Props_Wall_Fence_02_Normal.tif.meta` | .meta |
| `Props_Wall_Fence_02_mask.tif` | `Wall_Standard/Prefab/H1M/Material/Props_Wall_Fence_02_mask.tif` | 贴图 |
| `Props_Wall_Fence_02_mask.tif.meta` | `Wall_Standard/Prefab/H1M/Material/Props_Wall_Fence_02_mask.tif.meta` | .meta |
| `Props_Wall_H_02m_02m_BrickIndustrial_06_X.prefab` | `Wall_Standard/Prefab/H2M/Props_Wall_H_02m_02m_BrickIndustrial_06_X.prefab` | Prefab |
| `Props_Wall_H_02m_02m_BrickIndustrial_06_X.prefab.meta` | `Wall_Standard/Prefab/H2M/Props_Wall_H_02m_02m_BrickIndustrial_06_X.prefab.meta` | .meta |
| `Props_Wall_H_02m_03m_BrickIndustrial_06.prefab` | `Wall_Standard/Prefab/H2M/Props_Wall_H_02m_03m_BrickIndustrial_06.prefab` | Prefab |
| `Props_Wall_H_02m_03m_BrickIndustrial_06.prefab.meta` | `Wall_Standard/Prefab/H2M/Props_Wall_H_02m_03m_BrickIndustrial_06.prefab.meta` | .meta |
| `Props_Wall_H_02m_05m_BrickIndustrial_06_Xx.prefab` | `Wall_Standard/Prefab/H2M/Props_Wall_H_02m_05m_BrickIndustrial_06_Xx.prefab` | Prefab |
| `Props_Wall_H_02m_05m_BrickIndustrial_06_Xx.prefab.meta` | `Wall_Standard/Prefab/H2M/Props_Wall_H_02m_05m_BrickIndustrial_06_Xx.prefab.meta` | .meta |
| `Props_Wall_H_02m_05m_Xx_01_BrickIndustrial_06_X.prefab` | `Wall_Standard/Prefab/H2M/Props_Wall_H_02m_05m_Xx_01_BrickIndustrial_06_X.prefab` | Prefab |
| `Props_Wall_H_02m_05m_Xx_01_BrickIndustrial_06_X.prefab.meta` | `Wall_Standard/Prefab/H2M/Props_Wall_H_02m_05m_Xx_01_BrickIndustrial_06_X.prefab.meta` | .meta |
| `Props_Wall_H_02m_05m_Xx_02_BrickIndustrial_06_X.prefab` | `Wall_Standard/Prefab/H2M/Props_Wall_H_02m_05m_Xx_02_BrickIndustrial_06_X.prefab` | Prefab |
| `Props_Wall_H_02m_05m_Xx_02_BrickIndustrial_06_X.prefab.meta` | `Wall_Standard/Prefab/H2M/Props_Wall_H_02m_05m_Xx_02_BrickIndustrial_06_X.prefab.meta` | .meta |
| `Props_Wall_H_02m_05m_Xx_03_BrickIndustrial_06_X.prefab` | `Wall_Standard/Prefab/H2M/Props_Wall_H_02m_05m_Xx_03_BrickIndustrial_06_X.prefab` | Prefab |
| `Props_Wall_H_02m_05m_Xx_03_BrickIndustrial_06_X.prefab.meta` | `Wall_Standard/Prefab/H2M/Props_Wall_H_02m_05m_Xx_03_BrickIndustrial_06_X.prefab.meta` | .meta |
| `Props_Wall_H_02m_05m_Xx_04_BrickIndustrial_06_X.prefab` | `Wall_Standard/Prefab/H2M/Props_Wall_H_02m_05m_Xx_04_BrickIndustrial_06_X.prefab` | Prefab |
| `Props_Wall_H_02m_05m_Xx_04_BrickIndustrial_06_X.prefab.meta` | `Wall_Standard/Prefab/H2M/Props_Wall_H_02m_05m_Xx_04_BrickIndustrial_06_X.prefab.meta` | .meta |
| `Props_Wall_H_02m_Post_PaintWhite_06_X.prefab` | `Wall_Standard/Prefab/H2M/Props_Wall_H_02m_Post_PaintWhite_06_X.prefab` | Prefab |
| `Props_Wall_H_02m_Post_PaintWhite_06_X.prefab.meta` | `Wall_Standard/Prefab/H2M/Props_Wall_H_02m_Post_PaintWhite_06_X.prefab.meta` | .meta |
| `Props_Wall_H_02m_02m_X.fbx` | `Wall_Standard/Prefab/H2M/Model/Props_Wall_H_02m_02m_X.fbx` | FBX |
| `Props_Wall_H_02m_02m_X.fbx.meta` | `Wall_Standard/Prefab/H2M/Model/Props_Wall_H_02m_02m_X.fbx.meta` | .meta |
| `Props_Wall_H_02m_03m_X.fbx` | `Wall_Standard/Prefab/H2M/Model/Props_Wall_H_02m_03m_X.fbx` | FBX |
| `Props_Wall_H_02m_03m_X.fbx.meta` | `Wall_Standard/Prefab/H2M/Model/Props_Wall_H_02m_03m_X.fbx.meta` | .meta |
| `Props_Wall_H_02m_05m_With_Post.fbx` | `Wall_Standard/Prefab/H2M/Model/Props_Wall_H_02m_05m_With_Post.fbx` | FBX |
| `Props_Wall_H_02m_05m_With_Post.fbx.meta` | `Wall_Standard/Prefab/H2M/Model/Props_Wall_H_02m_05m_With_Post.fbx.meta` | .meta |
| `Props_Wall_H_02m_05m_X.fbx` | `Wall_Standard/Prefab/H2M/Model/Props_Wall_H_02m_05m_X.fbx` | FBX |
| `Props_Wall_H_02m_05m_X.fbx.meta` | `Wall_Standard/Prefab/H2M/Model/Props_Wall_H_02m_05m_X.fbx.meta` | .meta |
| `Props_Wall_H_02m_05m_Xx_01.fbx` | `Wall_Standard/Prefab/H2M/Model/Props_Wall_H_02m_05m_Xx_01.fbx` | FBX |
| `Props_Wall_H_02m_05m_Xx_01.fbx.meta` | `Wall_Standard/Prefab/H2M/Model/Props_Wall_H_02m_05m_Xx_01.fbx.meta` | .meta |
| `Props_Wall_H_02m_05m_Xx_02.fbx` | `Wall_Standard/Prefab/H2M/Model/Props_Wall_H_02m_05m_Xx_02.fbx` | FBX |
| `Props_Wall_H_02m_05m_Xx_02.fbx.meta` | `Wall_Standard/Prefab/H2M/Model/Props_Wall_H_02m_05m_Xx_02.fbx.meta` | .meta |
| `Props_Wall_H_02m_05m_Xx_03.fbx` | `Wall_Standard/Prefab/H2M/Model/Props_Wall_H_02m_05m_Xx_03.fbx` | FBX |
| `Props_Wall_H_02m_05m_Xx_03.fbx.meta` | `Wall_Standard/Prefab/H2M/Model/Props_Wall_H_02m_05m_Xx_03.fbx.meta` | .meta |
| `Props_Wall_H_02m_05m_Xx_04.fbx` | `Wall_Standard/Prefab/H2M/Model/Props_Wall_H_02m_05m_Xx_04.fbx` | FBX |
| `Props_Wall_H_02m_05m_Xx_04.fbx.meta` | `Wall_Standard/Prefab/H2M/Model/Props_Wall_H_02m_05m_Xx_04.fbx.meta` | .meta |
| `Props_Wall_H_02m_Post_X.fbx` | `Wall_Standard/Prefab/H2M/Model/Props_Wall_H_02m_Post_X.fbx` | FBX |
| `Props_Wall_H_02m_Post_X.fbx.meta` | `Wall_Standard/Prefab/H2M/Model/Props_Wall_H_02m_Post_X.fbx.meta` | .meta |
| `Props_Wall_H_02m6_5m_BrickIndustrial_06.prefab` | `Wall_Standard/Prefab/H2M6/Props_Wall_H_02m6_5m_BrickIndustrial_06.prefab` | Prefab |
| `Props_Wall_H_02m6_5m_BrickIndustrial_06.prefab.meta` | `Wall_Standard/Prefab/H2M6/Props_Wall_H_02m6_5m_BrickIndustrial_06.prefab.meta` | .meta |
| `Props_Wall_H_02m6_5m_BrickIndustrial_06_X.prefab` | `Wall_Standard/Prefab/H2M6/Props_Wall_H_02m6_5m_BrickIndustrial_06_X.prefab` | Prefab |
| `Props_Wall_H_02m6_5m_BrickIndustrial_06_X.prefab.meta` | `Wall_Standard/Prefab/H2M6/Props_Wall_H_02m6_5m_BrickIndustrial_06_X.prefab.meta` | .meta |
| `Props_Wall_H_02m6_5m_PaintWhite.prefab` | `Wall_Standard/Prefab/H2M6/Props_Wall_H_02m6_5m_PaintWhite.prefab` | Prefab |
| `Props_Wall_H_02m6_5m_PaintWhite.prefab.meta` | `Wall_Standard/Prefab/H2M6/Props_Wall_H_02m6_5m_PaintWhite.prefab.meta` | .meta |
| `Props_Wall_H_02m6_5m_PaintWhite_X.prefab` | `Wall_Standard/Prefab/H2M6/Props_Wall_H_02m6_5m_PaintWhite_X.prefab` | Prefab |
| `Props_Wall_H_02m6_5m_PaintWhite_X.prefab.meta` | `Wall_Standard/Prefab/H2M6/Props_Wall_H_02m6_5m_PaintWhite_X.prefab.meta` | .meta |
| `Props_Wall_H_02m6_5m_Xx_01_BrickIndustrial_06.prefab` | `Wall_Standard/Prefab/H2M6/Props_Wall_H_02m6_5m_Xx_01_BrickIndustrial_06.prefab` | Prefab |
| `Props_Wall_H_02m6_5m_Xx_01_BrickIndustrial_06.prefab.meta` | `Wall_Standard/Prefab/H2M6/Props_Wall_H_02m6_5m_Xx_01_BrickIndustrial_06.prefab.meta` | .meta |
| `Props_Wall_H_02m6_5m_Xx_01_BrickIndustrial_06_X.prefab` | `Wall_Standard/Prefab/H2M6/Props_Wall_H_02m6_5m_Xx_01_BrickIndustrial_06_X.prefab` | Prefab |
| `Props_Wall_H_02m6_5m_Xx_01_BrickIndustrial_06_X.prefab.meta` | `Wall_Standard/Prefab/H2M6/Props_Wall_H_02m6_5m_Xx_01_BrickIndustrial_06_X.prefab.meta` | .meta |
| `Props_Wall_H_02m6_5m_Xx_01_PaintWhite.prefab` | `Wall_Standard/Prefab/H2M6/Props_Wall_H_02m6_5m_Xx_01_PaintWhite.prefab` | Prefab |
| `Props_Wall_H_02m6_5m_Xx_01_PaintWhite.prefab.meta` | `Wall_Standard/Prefab/H2M6/Props_Wall_H_02m6_5m_Xx_01_PaintWhite.prefab.meta` | .meta |
| `Props_Wall_H_02m6_5m_Xx_01_PaintWhite_X.prefab` | `Wall_Standard/Prefab/H2M6/Props_Wall_H_02m6_5m_Xx_01_PaintWhite_X.prefab` | Prefab |
| `Props_Wall_H_02m6_5m_Xx_01_PaintWhite_X.prefab.meta` | `Wall_Standard/Prefab/H2M6/Props_Wall_H_02m6_5m_Xx_01_PaintWhite_X.prefab.meta` | .meta |
| `Props_Wall_H_02m6_5m_Xx_02_BrickIndustrial_06.prefab` | `Wall_Standard/Prefab/H2M6/Props_Wall_H_02m6_5m_Xx_02_BrickIndustrial_06.prefab` | Prefab |
| `Props_Wall_H_02m6_5m_Xx_02_BrickIndustrial_06.prefab.meta` | `Wall_Standard/Prefab/H2M6/Props_Wall_H_02m6_5m_Xx_02_BrickIndustrial_06.prefab.meta` | .meta |
| `Props_Wall_H_02m6_5m_Xx_02_BrickIndustrial_06_X.prefab` | `Wall_Standard/Prefab/H2M6/Props_Wall_H_02m6_5m_Xx_02_BrickIndustrial_06_X.prefab` | Prefab |
| `Props_Wall_H_02m6_5m_Xx_02_BrickIndustrial_06_X.prefab.meta` | `Wall_Standard/Prefab/H2M6/Props_Wall_H_02m6_5m_Xx_02_BrickIndustrial_06_X.prefab.meta` | .meta |
| `Props_Wall_H_02m6_5m_Xx_02_PaintWhite.prefab` | `Wall_Standard/Prefab/H2M6/Props_Wall_H_02m6_5m_Xx_02_PaintWhite.prefab` | Prefab |
| `Props_Wall_H_02m6_5m_Xx_02_PaintWhite.prefab.meta` | `Wall_Standard/Prefab/H2M6/Props_Wall_H_02m6_5m_Xx_02_PaintWhite.prefab.meta` | .meta |
| `Props_Wall_H_02m6_5m_Xx_02_PaintWhite_X.prefab` | `Wall_Standard/Prefab/H2M6/Props_Wall_H_02m6_5m_Xx_02_PaintWhite_X.prefab` | Prefab |
| `Props_Wall_H_02m6_5m_Xx_02_PaintWhite_X.prefab.meta` | `Wall_Standard/Prefab/H2M6/Props_Wall_H_02m6_5m_Xx_02_PaintWhite_X.prefab.meta` | .meta |
| `Props_Wall_H_02m6_Post_BrickIndustrial_06.prefab` | `Wall_Standard/Prefab/H2M6/Props_Wall_H_02m6_Post_BrickIndustrial_06.prefab` | Prefab |
| `Props_Wall_H_02m6_Post_BrickIndustrial_06.prefab.meta` | `Wall_Standard/Prefab/H2M6/Props_Wall_H_02m6_Post_BrickIndustrial_06.prefab.meta` | .meta |
| `Props_Wall_H_02m6_Post_BrickIndustrial_06_X.prefab` | `Wall_Standard/Prefab/H2M6/Props_Wall_H_02m6_Post_BrickIndustrial_06_X.prefab` | Prefab |
| `Props_Wall_H_02m6_Post_BrickIndustrial_06_X.prefab.meta` | `Wall_Standard/Prefab/H2M6/Props_Wall_H_02m6_Post_BrickIndustrial_06_X.prefab.meta` | .meta |
| `Props_Wall_H_02m6_Post_PaintWhite.prefab` | `Wall_Standard/Prefab/H2M6/Props_Wall_H_02m6_Post_PaintWhite.prefab` | Prefab |
| `Props_Wall_H_02m6_Post_PaintWhite.prefab.meta` | `Wall_Standard/Prefab/H2M6/Props_Wall_H_02m6_Post_PaintWhite.prefab.meta` | .meta |
| `Props_Wall_H_02m6_Post_PaintWhite_X.prefab` | `Wall_Standard/Prefab/H2M6/Props_Wall_H_02m6_Post_PaintWhite_X.prefab` | Prefab |
| `Props_Wall_H_02m6_Post_PaintWhite_X.prefab.meta` | `Wall_Standard/Prefab/H2M6/Props_Wall_H_02m6_Post_PaintWhite_X.prefab.meta` | .meta |
| `Props_Wall_H_02m6_5m_X.fbx` | `Wall_Standard/Prefab/H2M6/Model/Props_Wall_H_02m6_5m_X.fbx` | FBX |
| `Props_Wall_H_02m6_5m_X.fbx.meta` | `Wall_Standard/Prefab/H2M6/Model/Props_Wall_H_02m6_5m_X.fbx.meta` | .meta |
| `Props_Wall_H_02m6_5m_Xx_01.fbx` | `Wall_Standard/Prefab/H2M6/Model/Props_Wall_H_02m6_5m_Xx_01.fbx` | FBX |
| `Props_Wall_H_02m6_5m_Xx_01.fbx.meta` | `Wall_Standard/Prefab/H2M6/Model/Props_Wall_H_02m6_5m_Xx_01.fbx.meta` | .meta |
| `Props_Wall_H_02m6_5m_Xx_02.fbx` | `Wall_Standard/Prefab/H2M6/Model/Props_Wall_H_02m6_5m_Xx_02.fbx` | FBX |
| `Props_Wall_H_02m6_5m_Xx_02.fbx.meta` | `Wall_Standard/Prefab/H2M6/Model/Props_Wall_H_02m6_5m_Xx_02.fbx.meta` | .meta |
| `Props_Wall_H_02m6_Post_X.fbx` | `Wall_Standard/Prefab/H2M6/Model/Props_Wall_H_02m6_Post_X.fbx` | FBX |
| `Props_Wall_H_02m6_Post_X.fbx.meta` | `Wall_Standard/Prefab/H2M6/Model/Props_Wall_H_02m6_Post_X.fbx.meta` | .meta |
| `Props_Rubble_Bricks_01.prefab` | `Wall_Standard/Prefab/Rubble/Props_Rubble_Bricks_01.prefab` | Prefab |
| `Props_Rubble_Bricks_01.prefab.meta` | `Wall_Standard/Prefab/Rubble/Props_Rubble_Bricks_01.prefab.meta` | .meta |
| `Props_Rubble_Bricks_02.prefab` | `Wall_Standard/Prefab/Rubble/Props_Rubble_Bricks_02.prefab` | Prefab |
| `Props_Rubble_Bricks_02.prefab.meta` | `Wall_Standard/Prefab/Rubble/Props_Rubble_Bricks_02.prefab.meta` | .meta |
| `Props_Rubble_Bricks_03.prefab` | `Wall_Standard/Prefab/Rubble/Props_Rubble_Bricks_03.prefab` | Prefab |
| `Props_Rubble_Bricks_03.prefab.meta` | `Wall_Standard/Prefab/Rubble/Props_Rubble_Bricks_03.prefab.meta` | .meta |
| `Props_Rubble_Bricks_04.prefab` | `Wall_Standard/Prefab/Rubble/Props_Rubble_Bricks_04.prefab` | Prefab |
| `Props_Rubble_Bricks_04.prefab.meta` | `Wall_Standard/Prefab/Rubble/Props_Rubble_Bricks_04.prefab.meta` | .meta |
| `Props_Rubble_Bricks_05.prefab` | `Wall_Standard/Prefab/Rubble/Props_Rubble_Bricks_05.prefab` | Prefab |
| `Props_Rubble_Bricks_05.prefab.meta` | `Wall_Standard/Prefab/Rubble/Props_Rubble_Bricks_05.prefab.meta` | .meta |
| `Props_Bricks_01.fbx` | `Wall_Standard/Prefab/Rubble/Model/Props_Bricks_01.fbx` | FBX |
| `Props_Bricks_01.fbx.meta` | `Wall_Standard/Prefab/Rubble/Model/Props_Bricks_01.fbx.meta` | .meta |
| `Props_Bricks_02.fbx` | `Wall_Standard/Prefab/Rubble/Model/Props_Bricks_02.fbx` | FBX |
| `Props_Bricks_02.fbx.meta` | `Wall_Standard/Prefab/Rubble/Model/Props_Bricks_02.fbx.meta` | .meta |
| `Props_Bricks_03.fbx` | `Wall_Standard/Prefab/Rubble/Model/Props_Bricks_03.fbx` | FBX |
| `Props_Bricks_03.fbx.meta` | `Wall_Standard/Prefab/Rubble/Model/Props_Bricks_03.fbx.meta` | .meta |
| `Props_Bricks_04.fbx` | `Wall_Standard/Prefab/Rubble/Model/Props_Bricks_04.fbx` | FBX |
| `Props_Bricks_04.fbx.meta` | `Wall_Standard/Prefab/Rubble/Model/Props_Bricks_04.fbx.meta` | .meta |
| `Props_Bricks_05.fbx` | `Wall_Standard/Prefab/Rubble/Model/Props_Bricks_05.fbx` | FBX |
| `Props_Bricks_05.fbx.meta` | `Wall_Standard/Prefab/Rubble/Model/Props_Bricks_05.fbx.meta` | .meta |

## Wall_Stone/

| 文件名 | 路径（相对 Wall/） | 类型 |
|---|---|---|
| `Materials.meta` | `Wall_Stone/Materials.meta` | .meta |
| `Model.meta` | `Wall_Stone/Model.meta` | .meta |
| `Prefab.meta` | `Wall_Stone/Prefab.meta` | .meta |
| `Mat_Wall_Stone_Grey.mat` | `Wall_Stone/Materials/Mat_Wall_Stone_Grey.mat` | Material |
| `Mat_Wall_Stone_Grey.mat.meta` | `Wall_Stone/Materials/Mat_Wall_Stone_Grey.mat.meta` | .meta |
| `Mat_Wall_Stone_Moss.mat` | `Wall_Stone/Materials/Mat_Wall_Stone_Moss.mat` | Material |
| `Mat_Wall_Stone_Moss.mat.meta` | `Wall_Stone/Materials/Mat_Wall_Stone_Moss.mat.meta` | .meta |
| `Props_Wall_Stone_Grey_Albedo.png` | `Wall_Stone/Materials/Props_Wall_Stone_Grey_Albedo.png` | 贴图 |
| `Props_Wall_Stone_Grey_Albedo.png.meta` | `Wall_Stone/Materials/Props_Wall_Stone_Grey_Albedo.png.meta` | .meta |
| `Props_Wall_Stone_Grey_mask.tif` | `Wall_Stone/Materials/Props_Wall_Stone_Grey_mask.tif` | 贴图 |
| `Props_Wall_Stone_Grey_mask.tif.meta` | `Wall_Stone/Materials/Props_Wall_Stone_Grey_mask.tif.meta` | .meta |
| `Props_Wall_Stone_Moss_Albedo.png` | `Wall_Stone/Materials/Props_Wall_Stone_Moss_Albedo.png` | 贴图 |
| `Props_Wall_Stone_Moss_Albedo.png.meta` | `Wall_Stone/Materials/Props_Wall_Stone_Moss_Albedo.png.meta` | .meta |
| `Props_Wall_Stone_normal.png` | `Wall_Stone/Materials/Props_Wall_Stone_normal.png` | 贴图 |
| `Props_Wall_Stone_normal.png.meta` | `Wall_Stone/Materials/Props_Wall_Stone_normal.png.meta` | .meta |
| `txt.txt` | `Wall_Stone/Materials/txt.txt` | 文本 |
| `txt.txt.meta` | `Wall_Stone/Materials/txt.txt.meta` | .meta |
| `Props_Pebble_Group_01_Sm.fbx` | `Wall_Stone/Model/Props_Pebble_Group_01_Sm.fbx` | FBX |
| `Props_Pebble_Group_01_Sm.fbx.meta` | `Wall_Stone/Model/Props_Pebble_Group_01_Sm.fbx.meta` | .meta |
| `Props_Pebble_Group_02_Sm.fbx` | `Wall_Stone/Model/Props_Pebble_Group_02_Sm.fbx` | FBX |
| `Props_Pebble_Group_02_Sm.fbx.meta` | `Wall_Stone/Model/Props_Pebble_Group_02_Sm.fbx.meta` | .meta |
| `Props_Pebble_Group_03_Sm.fbx` | `Wall_Stone/Model/Props_Pebble_Group_03_Sm.fbx` | FBX |
| `Props_Pebble_Group_03_Sm.fbx.meta` | `Wall_Stone/Model/Props_Pebble_Group_03_Sm.fbx.meta` | .meta |
| `Props_Pebble_Group_04_Sm.fbx` | `Wall_Stone/Model/Props_Pebble_Group_04_Sm.fbx` | FBX |
| `Props_Pebble_Group_04_Sm.fbx.meta` | `Wall_Stone/Model/Props_Pebble_Group_04_Sm.fbx.meta` | .meta |
| `Props_Wall_Stone_H_01m_02m5.fbx` | `Wall_Stone/Model/Props_Wall_Stone_H_01m_02m5.fbx` | FBX |
| `Props_Wall_Stone_H_01m_02m5.fbx.meta` | `Wall_Stone/Model/Props_Wall_Stone_H_01m_02m5.fbx.meta` | .meta |
| `Props_Wall_Stone_H_01m_05m.fbx` | `Wall_Stone/Model/Props_Wall_Stone_H_01m_05m.fbx` | FBX |
| `Props_Wall_Stone_H_01m_05m.fbx.meta` | `Wall_Stone/Model/Props_Wall_Stone_H_01m_05m.fbx.meta` | .meta |
| `Props_Wall_Stone_Xx_01.fbx` | `Wall_Stone/Model/Props_Wall_Stone_Xx_01.fbx` | FBX |
| `Props_Wall_Stone_Xx_01.fbx.meta` | `Wall_Stone/Model/Props_Wall_Stone_Xx_01.fbx.meta` | .meta |
| `Props_Wall_Stone_Xx_02.fbx` | `Wall_Stone/Model/Props_Wall_Stone_Xx_02.fbx` | FBX |
| `Props_Wall_Stone_Xx_02.fbx.meta` | `Wall_Stone/Model/Props_Wall_Stone_Xx_02.fbx.meta` | .meta |
| `Props_Pebble_Group_01_Sm.prefab` | `Wall_Stone/Prefab/Props_Pebble_Group_01_Sm.prefab` | Prefab |
| `Props_Pebble_Group_01_Sm.prefab.meta` | `Wall_Stone/Prefab/Props_Pebble_Group_01_Sm.prefab.meta` | .meta |
| `Props_Pebble_Group_02_Sm.prefab` | `Wall_Stone/Prefab/Props_Pebble_Group_02_Sm.prefab` | Prefab |
| `Props_Pebble_Group_02_Sm.prefab.meta` | `Wall_Stone/Prefab/Props_Pebble_Group_02_Sm.prefab.meta` | .meta |
| `Props_Pebble_Group_03_Sm.prefab` | `Wall_Stone/Prefab/Props_Pebble_Group_03_Sm.prefab` | Prefab |
| `Props_Pebble_Group_03_Sm.prefab.meta` | `Wall_Stone/Prefab/Props_Pebble_Group_03_Sm.prefab.meta` | .meta |
| `Props_Pebble_Group_04_Sm.prefab` | `Wall_Stone/Prefab/Props_Pebble_Group_04_Sm.prefab` | Prefab |
| `Props_Pebble_Group_04_Sm.prefab.meta` | `Wall_Stone/Prefab/Props_Pebble_Group_04_Sm.prefab.meta` | .meta |
| `Props_Wall_Stone_H_01m_02m5.prefab` | `Wall_Stone/Prefab/Props_Wall_Stone_H_01m_02m5.prefab` | Prefab |
| `Props_Wall_Stone_H_01m_02m5.prefab.meta` | `Wall_Stone/Prefab/Props_Wall_Stone_H_01m_02m5.prefab.meta` | .meta |
| `Props_Wall_Stone_H_01m_02m5_X.prefab` | `Wall_Stone/Prefab/Props_Wall_Stone_H_01m_02m5_X.prefab` | Prefab |
| `Props_Wall_Stone_H_01m_02m5_X.prefab.meta` | `Wall_Stone/Prefab/Props_Wall_Stone_H_01m_02m5_X.prefab.meta` | .meta |
| `Props_Wall_Stone_H_01m_05m.prefab` | `Wall_Stone/Prefab/Props_Wall_Stone_H_01m_05m.prefab` | Prefab |
| `Props_Wall_Stone_H_01m_05m.prefab.meta` | `Wall_Stone/Prefab/Props_Wall_Stone_H_01m_05m.prefab.meta` | .meta |
| `Props_Wall_Stone_H_01m_05m_X.prefab` | `Wall_Stone/Prefab/Props_Wall_Stone_H_01m_05m_X.prefab` | Prefab |
| `Props_Wall_Stone_H_01m_05m_X.prefab.meta` | `Wall_Stone/Prefab/Props_Wall_Stone_H_01m_05m_X.prefab.meta` | .meta |
| `Props_Wall_Stone_Xx_01.prefab` | `Wall_Stone/Prefab/Props_Wall_Stone_Xx_01.prefab` | Prefab |
| `Props_Wall_Stone_Xx_01.prefab.meta` | `Wall_Stone/Prefab/Props_Wall_Stone_Xx_01.prefab.meta` | .meta |
| `Props_Wall_Stone_Xx_02.prefab` | `Wall_Stone/Prefab/Props_Wall_Stone_Xx_02.prefab` | Prefab |
| `Props_Wall_Stone_Xx_02.prefab.meta` | `Wall_Stone/Prefab/Props_Wall_Stone_Xx_02.prefab.meta` | .meta |

## Wall/（根目录 .meta）

| 文件名 | 路径（相对 Wall/） | 类型 |
|---|---|---|
| `Gate_double.meta` | `Gate_double.meta` | .meta |
| `Gate_single.meta` | `Gate_single.meta` | .meta |
| `Wall_Standard.meta` | `Wall_Standard.meta` | .meta |
| `Wall_Stone.meta` | `Wall_Stone.meta` | .meta |