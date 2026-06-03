# 材质重命名原名对照

> 日期: 2026-06-03
> 规范: docs/项目资产命名与整理规范.md
> 脚本: scripts/rename-materials.py

## 改名规则回顾

| 操作 | 示例 |
|------|------|
| 后缀标准化 | `_Albedo`→`_Col`, `_Normal`→`_N`, `_MaskMap`→`_Mask`, `_Height`→`_H` |
| 材质球加前缀 | `Brick.mat` → `Mat_Brick.mat` |
| 清除下载前缀 | `TexturesCom_Wall_Brick_...` → `Wall_Brick_...` |
| 清除尺寸标记 | `Wall_2K`, `Wall_4K-PNG`, `Wall_1K` → `Wall` |
| 空格→下划线 | `Brick Wall.mat` → `Brick_Wall.mat` |
| 首字母大写 | `wall_base` → `Wall_Base` |

## 总览

| 分类 | 文件数 | 记录完整度 |
|------|--------|-----------|
| 砖石瓦砾 (Rubble) | 14 | ✅ 原名→新名 |
| 木材/树枝/树桩 (Wood2) | 46 | ✅ 原名→新名 |
| Doodats_ForestWinter | 13 | ✅ 原名→新名 |
| Rocks_ForestWinter | 19 | ✅ 原名→新名 |
| Materials_Standard | 27 | ⚠️ 反向推导 |
| Terrain_Materials | 27 | ⚠️ 反向推导 |

---

## ✅ 砖石瓦砾 (Rubble)

| 原名 | 新名 |
|------|------|
| Brick Rubble.mat  |  Mat_Brick_Rubble.mat |
| Brick_Rubble_BaseCol.tif  |  Brick_Rubble_Col.tif |
| Brick_Rubble_BaseCol2.tif  |  Brick_Rubble_Col.tif |
| Brick_Rubble_Mask.png  |  Brick_Rubble_Mask.png |
| Brick_Rubble_MaskA_Alpha.tif  |  Brick_Rubble_MaskA.tif |
| Brick_Rubble_MaskA_B_Detial.tif  |  Brick_Rubble_MaskA_B_Detail.tif |
| Brick_Rubble_MaskA.tif  |  Brick_Rubble_MaskA.tif |
| Brick_Rubble_NM.TGA  |  Brick_Rubble_N.tga |
| Brick_RubbleA.tif  |  Brick_RubbleA.tif |
| Brick Rubble Layer.mat  |  Mat_Brick_Rubble_Layer.mat |
| Concrete_Rubble_A_Color_2.tif  |  Concrete_Rubble_A_2.tif |
| Concrete_Rubble MaskMap_BC.png  |  Concrete_Rubble_Mask.png |
| Concrete_Rubble.mat  |  Mat_Concrete_Rubble.mat |

## ✅ 木材/树枝/树桩 (Wood2)

| 原名 | 新名 |
|------|------|
| Branch.mat  |  Mat_Branch.mat |
| Branch_Albedo.png  |  Branch_Col.png |
| Branch_Albedo_2.png  |  Branch_Col_2.png |
| Branch_MaskMap.png  |  Branch_Mask.png |
| Branch_Normal.png  |  Branch_N.png |
| Branch_pjxuR_Albedo.png  |  Branch_PjxuR_Col.png |
| Branch_pjxuR_MaskMap.png  |  Branch_PjxuR_Mask.png |
| Branch_pjxuR_Normal.png  |  Branch_PjxuR_N.png |
| DeadStump.mat  |  Mat_DeadStump.mat |
| DeadStump_Albedo.png  |  DeadStump_Col.png |
| DeadStump_MaskMap.png  |  DeadStump_Mask.png |
| DeadStump_Normal.png  |  DeadStump_N.png |
| HE_bark_structure_MaskMap.png  |  HE_Bark_Structure_Mask.png |
| Log qdtdP_Albedo.png  |  Log_QdtdP_Col.png |
| Log qdtdP_MaskMap.png  |  Log_QdtdP_Mask.png |
| Log qdtdP_Normal.png  |  Log_QdtdP_N.png |
| Log qdtdP.mat  |  Mat_Log_QdtdP.mat |
| Logs.mat  |  Mat_Logs.mat |
| Logs_Albedo.png  |  Logs_Col.png |
| Logs_Albedo_2.png  |  Logs_Col_2.png |
| Logs_MaskMap.png  |  Logs_Mask.png |
| Logs_Normal.png  |  Logs_N.png |
| Stumps.mat  |  Mat_Stumps.mat |
| Stumps_Albedo.png  |  Stumps_Col.png |
| Stumps_Albedo_2.png  |  Stumps_Col_2.png |
| Stumps_MaskMap.png  |  Stumps_Mask.png |
| Stumps_Normal.png  |  Stumps_N.png |
| Wood qdtdP_Albedo.png  |  Wood_QdtdP_Col.png |
| Wood qdtdP_MaskMap.png  |  Wood_QdtdP_Mask.png |
| Wood qdtdP_Normal.png  |  Wood_QdtdP_N.png |
| Wood rfgxx_Albedo.png  |  Wood_Rfgxx_Col.png |
| Wood rfgxx_MaskMap.png  |  Wood_Rfgxx_Mask.png |
| Wood rfgxx_Normal.png  |  Wood_Rfgxx_N.png |
| Wood Rfurn_Albedo.png  |  Wood_Rfurn_Col.png |
| Wood Rfurn_MaskMap.png  |  Wood_Rfurn_Mask.png |
| Wood Rfurn_Normal.png  |  Wood_Rfurn_N.png |
| Wood_RoughnessMask1.png  |  Wood_Rough.png |
| Wood_RoughnessMask6.png  |  Wood_Rough.png |
| Wood_RoughnessMask9.png  |  Wood_Rough.png |
| Wood_RoughnessMask12.png  |  Wood_Rough.png |
| Wood_Log_rfixH_normal_OS.tif  |  Wood_Log_RfixH_Normal_OS.tif |
| Wood_Bark_structur_MaskMap.png  |  Wood_Bark_Structur_Mask.png |
| Wood_Bark_structur_Albedo.png  |  Wood_Bark_Structur_Col.png |
| Wood_Bark_structur_Normal.png  |  Wood_Bark_Structur_N.png |
| Wood_Bark_structur.mat  |  Mat_Wood_Bark_Structur.mat |

## ✅ Doodats_ForestWinter

| 原名 | 新名 |
|------|------|
| M_Branches_01_BC.PNG  |  M_Branches_01_Col.png |
| M_Branches_01_M.PNG  |  M_Branches_01_Mask.png |
| M_Branches_01_N.PNG  |  M_Branches_01_N.png |
| M_Debris_01_BC.PNG  |  M_Debris_01_Col.png |
| M_Debris_01_M.PNG  |  M_Debris_01_Mask.png |
| M_Debris_01_N.png  |  M_Debris_01_N.png |
| M_Log_01_BC.PNG  |  M_Log_01_Col.png |
| M_Log_01_M.PNG  |  M_Log_01_Mask.png |
| M_Log_01_N.PNG  |  M_Log_01_N.png |
| M_Stump_01_BC.PNG  |  M_Stump_01_Col.png |
| M_Stump_01_M.PNG  |  M_Stump_01_Mask.png |
| M_Stump_01_N.PNG  |  M_Stump_01_N.png |

## ✅ Rocks_ForestWinter

| 原名 | 新名 |
|------|------|
| M_Soil_01_BC.PNG  |  M_Soil_01_Col.png |
| M_Soil_01_M.png  |  M_Soil_01_Mask.png |
| M_Soil_01_N.png  |  M_Soil_01_N.png |
| Pebbles_01_BC.PNG  |  Pebbles_01_Col.png |
| Pebbles_01_N.PNG  |  Pebbles_01_N.png |
| Pebbles_01_M.PNG  |  Pebbles_01_Mask.png |
| Pebbles_02_BC.PNG  |  Pebbles_02_Col.png |
| Pebbles_02_M.PNG  |  Pebbles_02_Mask.png |
| Pebbles_02_N.PNG  |  Pebbles_02_N.png |
| Rock_01_BC.PNG  |  Rock_01_Col.png |
| Rock_01_M.png  |  Rock_01_Mask.png |
| Rock_01_N.PNG  |  Rock_01_N.png |
| Rock_03_BC.PNG  |  Rock_03_Col.png |
| Rock_03_M.png  |  Rock_03_Mask.png |
| Rock_03_N.PNG  |  Rock_03_N.png |
| Stone_02_BC.PNG  |  Stone_02_Col.png |
| Stone_02_M.png  |  Stone_02_Mask.png |
| Stone_02_N.png  |  Stone_02_N.png |

---

## ⚠️ Materials_Standard（反向推导）

> 执行时未抓完整日志，原名由后缀规则反向推导，不保证 100% 精确。
> 推导逻辑：`_Col` → 最可能 `_Albedo`；`_N` → 最可能 `_Normal`；`_Mask` → 最可能 `_MaskMap`

| 当前名 | 推测原名 | 其他可能 |
|--------|----------|----------|
| Decal_Grid01.prefab | [未重命名或无后缀映射] | — |
| Decal_Grid01_11°.prefab | [未重命名或无后缀映射] | — |
| DBK_Concrete_RGBA_Mask_B2.tga | [未重命名或无后缀映射] | — |
| Mat_3layer_floor.mat | [未重命名或无后缀映射] | — |
| Mat_4layer_Brick_Rustic2.mat | [未重命名或无后缀映射] | — |
| Mat_4layer_P.mat | [未重命名或无后缀映射] | — |
| Mat_WallBase01.mat | [未重命名或无后缀映射] | — |
| WallBase01_Col.jpg | WallBase01_Albedo.jpg | _BaseColor, _BaseCol |
| WallBase01_Mask.png | WallBase01_MaskMap.png | _M |
| WallBase01_N.jpg | WallBase01_Normal.jpg | _NM, _NRM |
| WallBase01_disp.jpg | [未重命名或无后缀映射] | — |
| info.txt | [未重命名或无后缀映射] | — |
| Mat_WallBase02.mat | [未重命名或无后缀映射] | — |
| WallBase02_H.jpg | WallBase02_Height.jpg | _Hight |
| WallBase02_Mask.png | WallBase02_MaskMap.png | _M |
| WallBase02_N.jpg | WallBase02_Normal.jpg | _NM, _NRM |
| WallBase02_diff.jpg | [未重命名或无后缀映射] | — |
| info.txt | [未重命名或无后缀映射] | — |
| Mat_WallBase03.mat | [未重命名或无后缀映射] | — |
| WallBase03_Mask.png | WallBase03_MaskMap.png | _M |
| WallBase03_N.jpg | WallBase03_Normal.jpg | _NM, _NRM |
| WallBase03_diff.jpg | [未重命名或无后缀映射] | — |
| WallBase03_disp.jpg | [未重命名或无后缀映射] | — |
| info.txt | [未重命名或无后缀映射] | — |
| Bunding01_col.jpg | [未重命名或无后缀映射] | — |
| Mat_Bunding01.mat | [未重命名或无后缀映射] | — |
| tex.txt | [未重命名或无后缀映射] | — |
| Ceiling01_Mask.png | Ceiling01_MaskMap.png | _M |
| Ceiling01_N.png | Ceiling01_Normal.png | _NM, _NRM |
| Ceiling01_basecolor.png | [未重命名或无后缀映射] | — |
| Ceiling01_basecolor_grey.png | [未重命名或无后缀映射] | — |
| Mat_Ceiling01_UV0_075.mat | [未重命名或无后缀映射] | — |
| Mat_Ceiling01_UV0_1.mat | [未重命名或无后缀映射] | — |
| Mat_Ceiling01_UV0_1_grey.mat | [未重命名或无后缀映射] | — |
| Mat_Ceiling01_UV1_075.mat | [未重命名或无后缀映射] | — |
| tex.txt | [未重命名或无后缀映射] | — |
| Ceiling02_Mask.tif | Ceiling02_MaskMap.tif | _M |
| Ceiling02_N.tif | Ceiling02_Normal.tif | _NM, _NRM |
| Ceiling02_basecolor.tif | [未重命名或无后缀映射] | — |
| Mat_Ceiling02_UV0.mat | [未重命名或无后缀映射] | — |
| tex.txt | [未重命名或无后缀映射] | — |
| Mat_Ceiling03_Mask.png | Mat_Ceiling03_MaskMap.png | _M |
| Mat_Ceiling03_N.png | Mat_Ceiling03_Normal.png | _NM, _NRM |
| Mat_Ceiling03_UV0.mat | [未重命名或无后缀映射] | — |
| Mat_Ceiling03_UV0_要删除一个.mat | [未重命名或无后缀映射] | — |
| Mat_Ceiling03_UV1.mat | [未重命名或无后缀映射] | — |
| Mat_Ceiling03_basecolor.png | [未重命名或无后缀映射] | — |
| tex.txt | [未重命名或无后缀映射] | — |
| Ceiling04_Col.tif | Ceiling04_Albedo.tif | _BaseColor, _BaseCol |
| Ceiling04_H.tif | Ceiling04_Height.tif | _Hight |
| Ceiling04_Mask.png | Ceiling04_MaskMap.png | _M |
| Ceiling04_N.tif | Ceiling04_Normal.tif | _NM, _NRM |
| Mat_Ceiling04.mat | [未重命名或无后缀映射] | — |
| tex.txt | [未重命名或无后缀映射] | — |
| Bricks03_GLOSSMask2.png | [未重命名或无后缀映射] | — |
| Grout_RoughnessMask3.png | [未重命名或无后缀映射] | — |
| Mat_chimney_Baselayer.mat | [未重命名或无后缀映射] | — |
| Mat_chimney_Pottery.mat | [未重命名或无后缀映射] | — |
| Mat_chimney_base.mat | [未重命名或无后缀映射] | — |
| Mat_chimney_line.mat | [未重命名或无后缀映射] | — |
| Yancong_N.png | Yancong_Normal.png | _NM, _NRM |
| yancong_AOC2.png | [未重命名或无后缀映射] | — |
| Mat_Chimney_Bricks099.mat | [未重命名或无后缀映射] | — |
| Mat_Chimney_Concrete_Plaster.mat | [未重命名或无后缀映射] | — |
| Mat_Chimney_Wall_BrickIndustrial2.mat | [未重命名或无后缀映射] | — |
| Mat_Chimney_Wall_Brick_Rustic2.mat | [未重命名或无后缀映射] | — |
| Mat_Chimney_Wall_Brick_Rustic2_UV0.mat | [未重命名或无后缀映射] | — |
| Mat_Chimney_Wall_BricksBeige002.mat | [未重命名或无后缀映射] | — |
| Mat_Chimney_Wall_Stone2.mat | [未重命名或无后缀映射] | — |
| Mat_Chimney_Wall_StoneBricksBeige001.mat | [未重命名或无后缀映射] | — |
| Mat_Chimney_Wall_StoneBricksBeige002.mat | [未重命名或无后缀映射] | — |
| Mat_Chimney_Wall_church_brick_02.mat | [未重命名或无后缀映射] | — |
| Mat_Chimney_Wall_church_brick_02_UV0.mat | [未重命名或无后缀映射] | — |
| Mat_Chimney_Wall_church_bricks_03.mat | [未重命名或无后缀映射] | — |
| Con_Breakage_Col.tga | Con_Breakage_Albedo.tga | _BaseColor, _BaseCol |
| Con_Breakage_N.tga | Con_Breakage_Normal.tga | _NM, _NRM |
| Con_Breakage_mask.tga | [未重命名或无后缀映射] | — |
| Mat_Con_Breakage.mat | [未重命名或无后缀映射] | — |
| tex.txt | [未重命名或无后缀映射] | — |
| Con_Cracks_Mask.png | Con_Cracks_MaskMap.png | _M |
| Con_Cracks_N.png | Con_Cracks_Normal.png | _NM, _NRM |
| Con_Cracks_col.png | [未重命名或无后缀映射] | — |
| Mat_Con_Cracks#Grey.mat | [未重命名或无后缀映射] | — |
| Mat_Con_Cracks.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_Con_Cracks#Grey.mat | [未重命名或无后缀映射] | — |
| tex.txt | [未重命名或无后缀映射] | — |
| Decal_Grid01_Col.tif | Decal_Grid01_Albedo.tif | _BaseColor, _BaseCol |
| Decal_Grid01_Mask.png | Decal_Grid01_MaskMap.png | _M |
| Decal_Grid01_N.tif | Decal_Grid01_Normal.tif | _NM, _NRM |
| Mat_Decal_Grid01.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_Grid01_01.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_Grid01_02.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_Grid01_11°.mat | [未重命名或无后缀映射] | — |
| Mat_Grid01.mat | [未重命名或无后缀映射] | — |
| tex.txt | [未重命名或无后缀映射] | — |
| ConBig_A.tif | [未重命名或无后缀映射] | — |
| ConBig_N.tif | ConBig_Normal.tif | _NM, _NRM |
| ConBig_mask.tif | [未重命名或无后缀映射] | — |
| Mat_Grid02.mat | [未重命名或无后缀映射] | — |
| Con_Plaster_Mask.png | Con_Plaster_MaskMap.png | _M |
| Con_Plaster_Mask.tif | Con_Plaster_MaskMap.tif | _M |
| Con_Plaster_N.png | Con_Plaster_Normal.png | _NM, _NRM |
| Con_Plastercolor.png | [未重命名或无后缀映射] | — |
| Mat_Con_Plaster#Black.mat | [未重命名或无后缀映射] | — |
| Mat_Con_Plaster#Blue.mat | [未重命名或无后缀映射] | — |
| Mat_Con_Plaster#Dark.mat | [未重命名或无后缀映射] | — |
| Mat_Con_Plaster#Dark_layer.mat | [未重命名或无后缀映射] | — |
| Mat_Con_Plaster#Grey.mat | [未重命名或无后缀映射] | — |
| Mat_Con_Plaster#Grey_layer.mat | [未重命名或无后缀映射] | — |
| Mat_Con_Plaster#Light.mat | [未重命名或无后缀映射] | — |
| Mat_Con_Plaster#Light_dirty.mat | [未重命名或无后缀映射] | — |
| Mat_Con_Plaster#Orange.mat | [未重命名或无后缀映射] | — |
| Mat_Con_Plaster#Red.mat | [未重命名或无后缀映射] | — |
| tex.txt | [未重命名或无后缀映射] | — |
| Floor_Col.png | Floor_Albedo.png | _BaseColor, _BaseCol |
| Floor_Mask.png | Floor_MaskMap.png | _M |
| Floor_N.png | Floor_Normal.png | _NM, _NRM |
| Mat_Decal_Floor.mat | [未重命名或无后缀映射] | — |
| Mat_Floor.mat | [未重命名或无后缀映射] | — |
| tex.txt | [未重命名或无后缀映射] | — |
| Floor_Old_Col.png | Floor_Old_Albedo.png | _BaseColor, _BaseCol |
| Floor_Old_Mask.png | Floor_Old_MaskMap.png | _M |
| Floor_Old_N.png | Floor_Old_Normal.png | _NM, _NRM |
| Mat_Floor_Old.mat | [未重命名或无后缀映射] | — |
| tex.txt | [未重命名或无后缀映射] | — |
| Mat_Glass.mat | [未重命名或无后缀映射] | — |
| Mat_Light.mat | [未重命名或无后缀映射] | — |
| Inside_Painted01_Col.jpg | Inside_Painted01_Albedo.jpg | _BaseColor, _BaseCol |
| Inside_Painted01_Mask.png | Inside_Painted01_MaskMap.png | _M |
| Inside_Painted01_N.jpg | Inside_Painted01_Normal.jpg | _NM, _NRM |
| Mat_Inside_Painted01_UV0.mat | [未重命名或无后缀映射] | — |
| Mat_Inside_Painted01_UV1.mat | [未重命名或无后缀映射] | — |
| Mat_Inside_Painted01_检查是否删除.mat | [未重命名或无后缀映射] | — |
| tex.txt | [未重命名或无后缀映射] | — |
| Inside_Paint02_Col.tif | Inside_Paint02_Albedo.tif | _BaseColor, _BaseCol |
| Inside_Paint02_Mask.png | Inside_Paint02_MaskMap.png | _M |
| Inside_Paint02_N.tif | Inside_Paint02_Normal.tif | _NM, _NRM |
| Mat_Inside_Paint02.mat | [未重命名或无后缀映射] | — |
| tex.txt | [未重命名或无后缀映射] | — |
| Mat_WallPaper_Green02.mat | [未重命名或无后缀映射] | — |
| WallPaper_Green02_Col.jpg | WallPaper_Green02_Albedo.jpg | _BaseColor, _BaseCol |
| WallPaper_Green02_Mask.png | WallPaper_Green02_MaskMap.png | _M |
| WallPaper_Green02_N.jpg | WallPaper_Green02_Normal.jpg | _NM, _NRM |
| Marble_Slab2_Col.tif | Marble_Slab2_Albedo.tif | _BaseColor, _BaseCol |
| Mat_Marble_slab2.mat | [未重命名或无后缀映射] | — |
| tex.txt | [未重命名或无后缀映射] | — |
| Mat_Line.mat | [未重命名或无后缀映射] | — |
| Mat_Metal01_Col.tif | Mat_Metal01_Albedo.tif | _BaseColor, _BaseCol |
| Mat_Metal01_Drak.mat | [未重命名或无后缀映射] | — |
| Mat_Metal01_Drak_layer.mat | [未重命名或无后缀映射] | — |
| Mat_Metal01_Grey.mat | [未重命名或无后缀映射] | — |
| Mat_Metal01_Light.mat | [未重命名或无后缀映射] | — |
| Mat_Metal01_Mask.png | Mat_Metal01_MaskMap.png | _M |
| Mat_Metal01_N.tif | Mat_Metal01_Normal.tif | _NM, _NRM |
| Mat_Metal01_roughness.tif | [未重命名或无后缀映射] | — |
| Mat_Metal02.mat | [未重命名或无后缀映射] | — |
| Metal02_Col.tif | Metal02_Albedo.tif | _BaseColor, _BaseCol |
| Metal02_N.tif | Metal02_Normal.tif | _NM, _NRM |
| Metal02_mask.tif | [未重命名或无后缀映射] | — |
| 不建议使用 遗留材质.txt | [未重命名或无后缀映射] | — |
| Mat_Metal_Rust.mat | [未重命名或无后缀映射] | — |
| Mat_Metal_Rust_Dark.mat | [未重命名或无后缀映射] | — |
| Mat_Metal_Rust_Green.mat | [未重命名或无后缀映射] | — |
| Metal_Rust_Col.jpg | Metal_Rust_Albedo.jpg | _BaseColor, _BaseCol |
| Metal_Rust_Color_green.tif | [未重命名或无后缀映射] | — |
| Metal_Rust_Mask.png | Metal_Rust_MaskMap.png | _M |
| Metal_Rust_N.jpg | Metal_Rust_Normal.jpg | _NM, _NRM |
| Mat_Rust_heavy#Brown.mat | [未重命名或无后缀映射] | — |
| Mat_Rust_heavy#Dark.mat | [未重命名或无后缀映射] | — |
| Mat_Rust_heavy#Dark_Layer.mat | [未重命名或无后缀映射] | — |
| Mat_Rust_heavy#green.mat | [未重命名或无后缀映射] | — |
| Mat_Rust_heavy#white.mat | [未重命名或无后缀映射] | — |
| Mat_Rust_heavy.mat | [未重命名或无后缀映射] | — |
| Metal_Rust_Heavy_N.tif | Metal_Rust_Heavy_Normal.tif | _NM, _NRM |
| Metal_Rust_heavy_Green_col.tif | [未重命名或无后缀映射] | — |
| Metal_Rust_heavy_Mask.tif | Metal_Rust_heavy_MaskMap.tif | _M |
| Metal_Rust_heavy_White_col.tif | [未重命名或无后缀映射] | — |
| Mat_Rust_lightly.mat | [未重命名或无后缀映射] | — |
| Mat_Rust_lightly_Green.mat | [未重命名或无后缀映射] | — |
| Mat_Rust_lightly_white.mat | [未重命名或无后缀映射] | — |
| X3m_Metal_Mask.tif | X3m_Metal_MaskMap.tif | _M |
| X3m_Metal_N.tif | X3m_Metal_Normal.tif | _NM, _NRM |
| x3m_Green_BaseMap.tif | [未重命名或无后缀映射] | — |
| x3m_White_BaseMap.tif | [未重命名或无后缀映射] | — |
| Mat_Rust_medium.mat | [未重命名或无后缀映射] | — |
| Mat_Rust_medium_green.mat | [未重命名或无后缀映射] | — |
| Mat_Rust_medium_layer.mat | [未重命名或无后缀映射] | — |
| Mat_Rust_medium_white.mat | [未重命名或无后缀映射] | — |
| X3m_Metal_Mask.tif | X3m_Metal_MaskMap.tif | _M |
| X3m_Metal_N.tif | X3m_Metal_Normal.tif | _NM, _NRM |
| x3m_Green_BaseMap.tif | [未重命名或无后缀映射] | — |
| x3m_White_BaseMap.tif | [未重命名或无后缀映射] | — |
| Rust.png | [未重命名或无后缀映射] | — |
| 建议使用另外三个Rust.txt | [未重命名或无后缀映射] | — |
| Mat_Bricks.mat | [未重命名或无后缀映射] | — |
| Bricks050_Col.jpg | Bricks050_Albedo.jpg | _BaseColor, _BaseCol |
| Bricks050_Mask.png | Bricks050_MaskMap.png | _M |
| Bricks050_NormalGL.jpg | [未重命名或无后缀映射] | — |
| Mat_Bricks_Broken.mat | [未重命名或无后缀映射] | — |
| Bricks_Broken02_A.jpg | [未重命名或无后缀映射] | — |
| Bricks_Broken02_MS.png | [未重命名或无后缀映射] | — |
| Bricks_Broken02_N.jpg | Bricks_Broken02_Normal.jpg | _NM, _NRM |
| Mat_Bricks_Broken02.mat | [未重命名或无后缀映射] | — |
| DBK_Trim_Damage_ColorA.tif | [未重命名或无后缀映射] | — |
| DBK_Trim_LayerMASK.tif | [未重命名或无后缀映射] | — |
| DBK_Trim_LayerMASK2.tif | [未重命名或无后缀映射] | — |
| DBK_Trim_Mask.tif | DBK_Trim_MaskMap.tif | _M |
| DBK_Trim_N.tga | DBK_Trim_Normal.tga | _NM, _NRM |
| Mat_DBK_TRIM#.mat | [未重命名或无后缀映射] | — |
| Mat_DBK_brick#.mat | [未重命名或无后缀映射] | — |
| brick_broken_A.png | [未重命名或无后缀映射] | — |
| brick_broken_N.png | brick_broken_Normal.png | _NM, _NRM |
| Mat_inside_fenshua.mat | [未重命名或无后缀映射] | — |
| PaintedPlaster014_AmbientOcclusion.jpg | [未重命名或无后缀映射] | — |
| PaintedPlaster014_Col.jpg | PaintedPlaster014_Albedo.jpg | _BaseColor, _BaseCol |
| PaintedPlaster014_Displacement.jpg | [未重命名或无后缀映射] | — |
| PaintedPlaster014_NormalGL.jpg | [未重命名或无后缀映射] | — |
| PaintedPlaster014_Rough.jpg | PaintedPlaster014_Roughness.jpg | — |
| PaintedPlaster014_RoughnessMask4.png | [未重命名或无后缀映射] | — |
| Line_A.png | [未重命名或无后缀映射] | — |
| Line_A2.png | [未重命名或无后缀映射] | — |
| Line_N.png | Line_Normal.png | _NM, _NRM |
| Line_RMask7.png | [未重命名或无后缀映射] | — |
| Mat_Line.mat | [未重命名或无后缀映射] | — |
| Mat_StripStone.mat | [未重命名或无后缀映射] | — |
| StripStone_N.jpg | StripStone_Normal.jpg | _NM, _NRM |
| StripStone_ao.jpg | [未重命名或无后缀映射] | — |
| StripStone_ao2.jpg | [未重命名或无后缀映射] | — |
| StripStone_curve.jpg | [未重命名或无后缀映射] | — |
| StripStone_curveMask1.png | [未重命名或无后缀映射] | — |
| StripStone_curveMask2.png | [未重命名或无后缀映射] | — |
| Mat_Wall_sandstone_brick_wall_01.mat | [未重命名或无后缀映射] | — |
| sandstone_brick_wall_01_diff_4k.jpg | [未重命名或无后缀映射] | — |
| sandstone_brick_wall_01_nor_gl_4k.jpg | [未重命名或无后缀映射] | — |
| sandstone_brick_wall_01_rough_4kMask15.png | [未重命名或无后缀映射] | — |
| Mat_Pave01.mat | [未重命名或无后缀映射] | — |
| TCom_Pavement_Regular19_1.8x1.6_Col.tif | TCom_Pavement_Regular19_1.8x1.6_Albedo.tif | _BaseColor, _BaseCol |
| TCom_Pavement_Regular19_1.8x1.6_N.tif | TCom_Pavement_Regular19_1.8x1.6_Normal.tif | _NM, _NRM |
| TCom_Pavement_Regular19_1.8x1.6_RoughnessMask1.png | [未重命名或无后缀映射] | — |
| Mat_Pave02.mat | [未重命名或无后缀映射] | — |
| TCom_Pavement_Regular23_1.9x1.9_Col.tif | TCom_Pavement_Regular23_1.9x1.9_Albedo.tif | _BaseColor, _BaseCol |
| TCom_Pavement_Regular23_1.9x1.9_N.tif | TCom_Pavement_Regular23_1.9x1.9_Normal.tif | _NM, _NRM |
| TCom_Pavement_Regular23_1.9x1.9_RoughnessMask1.png | [未重命名或无后缀映射] | — |
| Mat_Pave03.mat | [未重命名或无后缀映射] | — |
| TCom_Tiles_Floor11_1.8x1.8_Col.tif | TCom_Tiles_Floor11_1.8x1.8_Albedo.tif | _BaseColor, _BaseCol |
| TCom_Tiles_Floor11_1.8x1.8_N.tif | TCom_Tiles_Floor11_1.8x1.8_Normal.tif | _NM, _NRM |
| TCom_Tiles_Floor11_1.8x1.8_RoughnessMask1.png | [未重命名或无后缀映射] | — |
| Map_A_1.tif | [未重命名或无后缀映射] | — |
| Map_MS_1.tif | [未重命名或无后缀映射] | — |
| Map_N_1.tif | [未重命名或无后缀映射] | — |
| Mat_Pict_01.mat | [未重命名或无后缀映射] | — |
| Mat_RidgeTille_Grey.mat | [未重命名或无后缀映射] | — |
| Mat_RidgeTille_Red.mat | [未重命名或无后缀映射] | — |
| RidgeTille_Col.tga | RidgeTille_Albedo.tga | _BaseColor, _BaseCol |
| RidgeTille_N.tga | RidgeTille_Normal.tga | _NM, _NRM |
| RidgeTille_glossMask1.png | [未重命名或无后缀映射] | — |
| mask.tif | [未重命名或无后缀映射] | — |
| mask2.tif | [未重命名或无后缀映射] | — |
| Mat_Roof_Asbestos_Int.mat | [未重命名或无后缀映射] | — |
| Mat_Roof_Asbestos_Out.mat | [未重命名或无后缀映射] | — |
| Roofing_AsbestosOndulated_Ao.tif | [未重命名或无后缀映射] | — |
| Roofing_AsbestosOndulated_Col.tif | Roofing_AsbestosOndulated_Albedo.tif | _BaseColor, _BaseCol |
| Roofing_AsbestosOndulated_N.tif | Roofing_AsbestosOndulated_Normal.tif | _NM, _NRM |
| Roofing_AsbestosOndulated_Roughness.tif | [未重命名或无后缀映射] | — |
| Roofing_AsbestosOndulated_RoughnessMask1.png | [未重命名或无后缀映射] | — |
| Mat_RidgeTille.mat | [未重命名或无后缀映射] | — |
| Mat_Roof_BronzeOld.mat | [未重命名或无后缀映射] | — |
| Mat_Roof_BronzeOld_UV0.mat | [未重命名或无后缀映射] | — |
| Mat_Roofing_BronzeOld.mat | [未重命名或无后缀映射] | — |
| Roofing_BronzeOld_1.5x1.5_512_Col.tif | Roofing_BronzeOld_1.5x1.5_512_Albedo.tif | _BaseColor, _BaseCol |
| Roofing_BronzeOld_1.5x1.5_512_H.tif | Roofing_BronzeOld_1.5x1.5_512_Height.tif | _Hight |
| Roofing_BronzeOld_1.5x1.5_512_N.tif | Roofing_BronzeOld_1.5x1.5_512_Normal.tif | _NM, _NRM |
| Roofing_BronzeOld_1.5x1.5_512_RoughnessMask1.png | [未重命名或无后缀映射] | — |
| Mat_Roof_ItalianNew_1K.mat | [未重命名或无后缀映射] | — |
| Mat_Roofing_ItalianNew_1K.mat | [未重命名或无后缀映射] | — |
| Roofing_ItalianNew_Col.tif | Roofing_ItalianNew_Albedo.tif | _BaseColor, _BaseCol |
| Roofing_ItalianNew_H.tif | Roofing_ItalianNew_Height.tif | _Hight |
| Roofing_ItalianNew_N.tif | Roofing_ItalianNew_Normal.tif | _NM, _NRM |
| Roofing_ItalianNew_RoughnessMask1.png | [未重命名或无后缀映射] | — |
| Mat_Roof_ItalianOld_1K.mat | [未重命名或无后缀映射] | — |
| Mat_Roofing_ItalianOld_1K.mat | [未重命名或无后缀映射] | — |
| Roofing_ItalianOld_Col.tif | Roofing_ItalianOld_Albedo.tif | _BaseColor, _BaseCol |
| Roofing_ItalianOld_H.tif | Roofing_ItalianOld_Height.tif | _Hight |
| Roofing_ItalianOld_N.tif | Roofing_ItalianOld_Normal.tif | _NM, _NRM |
| Roofing_ItalianOld_RoughnessMask1.png | [未重命名或无后缀映射] | — |
| Mat_Roof_Metal_Rust_Lightly_Blue.mat | [未重命名或无后缀映射] | — |
| Mat_Roof_Metal_Rust_Lightly_White.mat | [未重命名或无后缀映射] | — |
| Mat_Roof_Metal_Rust_Lightly_White2.mat | [未重命名或无后缀映射] | — |
| TCom_Metal_Corrugated3_Albedo2.tif | [未重命名或无后缀映射] | — |
| TCom_Metal_Corrugated3_Albedo3.tif | [未重命名或无后缀映射] | — |
| TCom_Metal_Corrugated3_Ao.tif | [未重命名或无后缀映射] | — |
| TCom_Metal_Corrugated3_Col.tif | TCom_Metal_Corrugated3_Albedo.tif | _BaseColor, _BaseCol |
| TCom_Metal_Corrugated3_N.tif | TCom_Metal_Corrugated3_Normal.tif | _NM, _NRM |
| TCom_Metal_Corrugated3_Roughness.tif | [未重命名或无后缀映射] | — |
| TCom_Metal_Corrugated3_RoughnessMask1.png | [未重命名或无后缀映射] | — |
| Mat_Roof_Metal_Rust_Medium_White.mat | [未重命名或无后缀映射] | — |
| TCom_MetalCorrugatedRusted_LightRust_Ao.tif | [未重命名或无后缀映射] | — |
| TCom_MetalCorrugatedRusted_LightRust_Col.tif | TCom_MetalCorrugatedRusted_LightRust_Albedo.tif | _BaseColor, _BaseCol |
| TCom_MetalCorrugatedRusted_LightRust_Metallic.tif | [未重命名或无后缀映射] | — |
| TCom_MetalCorrugatedRusted_LightRust_N.tif | TCom_MetalCorrugatedRusted_LightRust_Normal.tif | _NM, _NRM |
| TCom_MetalCorrugatedRusted_LightRust_Roughness.tif | [未重命名或无后缀映射] | — |
| TCom_MetalCorrugatedRusted_LightRust_RoughnessMask1.png | [未重命名或无后缀映射] | — |
| Mat_Roof_Round01_Grey_UV0.mat | [未重命名或无后缀映射] | — |
| Mat_Roof_Round01_Grey_UV1.mat | [未重命名或无后缀映射] | — |
| Mat_Roof_Round01_Red_UV0.mat | [未重命名或无后缀映射] | — |
| Mat_Roof_Round01_Red_UV1.mat | [未重命名或无后缀映射] | — |
| Mat_Roofing_Round01_Red_UV0.mat | [未重命名或无后缀映射] | — |
| Mat_Roofing_Round01_Red_UV1.mat | [未重命名或无后缀映射] | — |
| Roofing_RoundOld_Albedo_Grey.tif | [未重命名或无后缀映射] | — |
| Roofing_RoundOld_Col.tif | Roofing_RoundOld_Albedo.tif | _BaseColor, _BaseCol |
| Roofing_RoundOld_H.tif | Roofing_RoundOld_Height.tif | _Hight |
| Roofing_RoundOld_N.tif | Roofing_RoundOld_Normal.tif | _NM, _NRM |
| Roofing_RoundOld_RoughnessMask1.png | [未重命名或无后缀映射] | — |
| Mat_RidgeTille#.mat | [未重命名或无后缀映射] | — |
| Mat_Roof_RoundSlate_1K.mat | [未重命名或无后缀映射] | — |
| Mat_Roof_RoundSlate_1K_UV0.mat | [未重命名或无后缀映射] | — |
| Mat_Roofing_RoundSlate_1K.mat | [未重命名或无后缀映射] | — |
| Mat_TexturesCom_Roofing_Slate_1K_albedo.mat | [未重命名或无后缀映射] | — |
| Roofing_Slate_Col.tif | Roofing_Slate_Albedo.tif | _BaseColor, _BaseCol |
| Roofing_Slate_H.tif | Roofing_Slate_Height.tif | _Hight |
| Roofing_Slate_N.tif | Roofing_Slate_Normal.tif | _NM, _NRM |
| Roofing_Slate_RoughnessMask1.png | [未重命名或无后缀映射] | — |
| Mat_Roof_Roundwood_1K.mat | [未重命名或无后缀映射] | — |
| Mat_Roof_Roundwood_1K_UV0.mat | [未重命名或无后缀映射] | — |
| Mat_Roofing_Roundwood_1K.mat | [未重命名或无后缀映射] | — |
| SmallWoodenShingles_0.6x0.6_512_Col.tif | SmallWoodenShingles_0.6x0.6_512_Albedo.tif | _BaseColor, _BaseCol |
| SmallWoodenShingles_0.6x0.6_512_H.tif | SmallWoodenShingles_0.6x0.6_512_Height.tif | _Hight |
| SmallWoodenShingles_0.6x0.6_512_N.tif | SmallWoodenShingles_0.6x0.6_512_Normal.tif | _NM, _NRM |
| SmallWoodenShingles_0.6x0.6_512_RoughnessMask1.png | [未重命名或无后缀映射] | — |
| Mat_RidgeTille.mat | [未重命名或无后缀映射] | — |
| Mat_Roof_S_grey.mat | [未重命名或无后缀映射] | — |
| Mat_Roof_S_grey_UV0.mat | [未重命名或无后缀映射] | — |
| Mat_Roofing_S_grey.mat | [未重命名或无后缀映射] | — |
| grey_roof_tiles_diff_4k.jpg | [未重命名或无后缀映射] | — |
| grey_roof_tiles_disp_4k.png | [未重命名或无后缀映射] | — |
| grey_roof_tiles_nor_gl_4k.exr | [未重命名或无后缀映射] | — |
| grey_roof_tiles_rough_4kMask1.png | [未重命名或无后缀映射] | — |
| Mat_RidgeTille_2.mat | [未重命名或无后缀映射] | — |
| Mat_Roof_S_Old07.mat | [未重命名或无后缀映射] | — |
| Mat_Roof_S_Old07_UV0.mat | [未重命名或无后缀映射] | — |
| Mat_Roofing_S_Old07.mat | [未重命名或无后缀映射] | — |
| roof_07_Mask.tif | roof_07_MaskMap.tif | _M |
| roof_07_diff_4k.jpg | [未重命名或无后缀映射] | — |
| roof_07_disp_4k.png | [未重命名或无后缀映射] | — |
| roof_07_nor_gl_4k.exr | [未重命名或无后缀映射] | — |
| roof_07_rough_4kMask1.png | [未重命名或无后缀映射] | — |
| Mat_RidgeTille_2.mat | [未重命名或无后缀映射] | — |
| Mat_Roof_S_PantileOld.mat | [未重命名或无后缀映射] | — |
| Mat_Roofing_PantileOld.mat | [未重命名或无后缀映射] | — |
| TCom_Roofing_PantileOld_Col.tif | TCom_Roofing_PantileOld_Albedo.tif | _BaseColor, _BaseCol |
| TCom_Roofing_PantileOld_H.tif | TCom_Roofing_PantileOld_Height.tif | _Hight |
| TCom_Roofing_PantileOld_N.tif | TCom_Roofing_PantileOld_Normal.tif | _NM, _NRM |
| TCom_Roofing_PantileOld_RoughnessMask1.png | [未重命名或无后缀映射] | — |
| TCom_Roofing_PantileOld_RoughnessMask1.tif | [未重命名或无后缀映射] | — |
| TCom_Roofing_PantileOld_RoughnessMask1副本.tif | [未重命名或无后缀映射] | — |
| Mat_Roof_S_RED.mat | [未重命名或无后缀映射] | — |
| Mat_Roofing_S_RED.mat | [未重命名或无后缀映射] | — |
| Roof_Col.tif | Roof_Albedo.tif | _BaseColor, _BaseCol |
| Roof_H.tif | Roof_Height.tif | _Hight |
| Roof_N.tif | Roof_Normal.tif | _NM, _NRM |
| roof_roughnessMask1.png | [未重命名或无后缀映射] | — |
| Mat_Roof_SquareOld.mat | [未重命名或无后缀映射] | — |
| Mat_Roofing_SquareOld.mat | [未重命名或无后缀映射] | — |
| TCom_Roofing_SquareOld_Col.tif | TCom_Roofing_SquareOld_Albedo.tif | _BaseColor, _BaseCol |
| TCom_Roofing_SquareOld_H.tif | TCom_Roofing_SquareOld_Height.tif | _Hight |
| TCom_Roofing_SquareOld_N.tif | TCom_Roofing_SquareOld_Normal.tif | _NM, _NRM |
| TCom_Roofing_SquareOld_RoughnessMask1.png | [未重命名或无后缀映射] | — |
| Mat_RidgeTille_1.mat | [未重命名或无后缀映射] | — |
| Mat_Roof_SquareOld2.mat | [未重命名或无后缀映射] | — |
| Mat_Roof_SquareOld2_Grey_UV0.mat | [未重命名或无后缀映射] | — |
| Mat_Roof_SquareOld2_Grey_UV1.mat | [未重命名或无后缀映射] | — |
| Mat_Roof_SquareOld2_UV0.mat | [未重命名或无后缀映射] | — |
| Mat_Roofing_SquareOld2.mat | [未重命名或无后缀映射] | — |
| Roofing_SquareOld2_Albedo_Grey.tif | [未重命名或无后缀映射] | — |
| Roofing_SquareOld2_Col.tif | Roofing_SquareOld2_Albedo.tif | _BaseColor, _BaseCol |
| Roofing_SquareOld2_H.tif | Roofing_SquareOld2_Height.tif | _Hight |
| Roofing_SquareOld2_N.tif | Roofing_SquareOld2_Normal.tif | _NM, _NRM |
| Roofing_SquareOld2_RoughnessMask1.png | [未重命名或无后缀映射] | — |
| Roofing_SquareOld2_RoughnessMask1副本.tif | [未重命名或无后缀映射] | — |
| Mat_RoofTilesSlate002.mat | [未重命名或无后缀映射] | — |
| Mat_RoofTilesSlate002_2.mat | [未重命名或无后缀映射] | — |
| Mat_RoofTilesSlate002_UV0.mat | [未重命名或无后缀映射] | — |
| RoofTilesSlate002_COL.jpg | [未重命名或无后缀映射] | — |
| RoofTilesSlate002_DISP.jpg | [未重命名或无后缀映射] | — |
| RoofTilesSlate002_GLOSSMask25.png | [未重命名或无后缀映射] | — |
| RoofTilesSlate002_NRM.png | [未重命名或无后缀映射] | — |
| Mat_Roof_WoodPlanks.mat | [未重命名或无后缀映射] | — |
| Mat_Roof_WoodPlanks02.mat | [未重命名或无后缀映射] | — |
| Mat_Roofing_WoodPlanks.mat | [未重命名或无后缀映射] | — |
| Mat_Roofing_WoodPlanks_UV0.mat | [未重命名或无后缀映射] | — |
| TCom_Roofing_WoodPlanks_Albedo2.tif | [未重命名或无后缀映射] | — |
| TCom_Roofing_WoodPlanks_Col.tif | TCom_Roofing_WoodPlanks_Albedo.tif | _BaseColor, _BaseCol |
| TCom_Roofing_WoodPlanks_H.tif | TCom_Roofing_WoodPlanks_Height.tif | _Hight |
| TCom_Roofing_WoodPlanks_N.tif | TCom_Roofing_WoodPlanks_Normal.tif | _NM, _NRM |
| TCom_Roofing_WoodPlanks_RoughnessMask2.png | [未重命名或无后缀映射] | — |
| Mat_Paint_Blue.mat | [未重命名或无后缀映射] | — |
| Mat_Paint_Green.mat | [未重命名或无后缀映射] | — |
| Mat_Paint_Red.mat | [未重命名或无后缀映射] | — |
| Mat_Paint_Tan02_UV0.mat | [未重命名或无后缀映射] | — |
| Mat_Paint_Tan02_UV1.mat | [未重命名或无后缀映射] | — |
| Mat_Paint_Tan02_White_UV0.mat | [未重命名或无后缀映射] | — |
| Mat_Paint_Tan_UV0.mat | [未重命名或无后缀映射] | — |
| Mat_Paint_Tan_UV0_light_yellow.mat | [未重命名或无后缀映射] | — |
| Mat_Paint_Tan_UV0_light_yellow_待删除.mat | [未重命名或无后缀映射] | — |
| Mat_Paint_Tan_UV1.mat | [未重命名或无后缀映射] | — |
| Mat_Paint_White_UV0.mat | [未重命名或无后缀映射] | — |
| Mat_Paint_White_UV1.mat | [未重命名或无后缀映射] | — |
| Mat_Paint_Yellow_UV0.mat | [未重命名或无后缀映射] | — |
| Plaster002_Col.jpg | Plaster002_Albedo.jpg | _BaseColor, _BaseCol |
| Plaster002_Mask.tif | Plaster002_MaskMap.tif | _M |
| Plaster002_NormalGL.jpg | [未重命名或无后缀映射] | — |
| Bricks03_COL_VAR1.jpg | [未重命名或无后缀映射] | — |
| Bricks03_DISPMask3.png | [未重命名或无后缀映射] | — |
| Bricks03_NRM.jpg | [未重命名或无后缀映射] | — |
| Mat_Brick_stone.mat | [未重命名或无后缀映射] | — |
| Mat_Brick_stone_UV0.mat | [未重命名或无后缀映射] | — |
| Mat_Bricks_Stone_BricksBeige.mat | [未重命名或无后缀映射] | — |
| whiteMask1.png | [未重命名或无后缀映射] | — |
| Bricks099-JPG_Col.jpg | Bricks099-JPG_Albedo.jpg | _BaseColor, _BaseCol |
| Bricks099-JPG_Mask.png | Bricks099-JPG_MaskMap.png | _M |
| Bricks099-JPG_NormalGL.jpg | [未重命名或无后缀映射] | — |
| Mat_StoneWall_Bricks099.mat | [未重命名或无后缀映射] | — |
| StoneBricksBeige001_AO_3K.jpg | [未重命名或无后缀映射] | — |
| StoneBricksBeige001_COL_3K.jpg | [未重命名或无后缀映射] | — |
| StoneBricksBeige001_DISP16_3K.tif | [未重命名或无后缀映射] | — |
| StoneBricksBeige001_DISP_3K.jpg | [未重命名或无后缀映射] | — |
| StoneBricksBeige001_GLOSS_3K.jpg | [未重命名或无后缀映射] | — |
| StoneBricksBeige001_NRM_3K.jpg | [未重命名或无后缀映射] | — |
| StoneBricksBeige001_REFL_3K.jpg | [未重命名或无后缀映射] | — |
| Mat_StoneBricksBeige002.mat | [未重命名或无后缀映射] | — |
| Mat_StoneBricksBeige002_UV0.mat | [未重命名或无后缀映射] | — |
| Mat_StoneBricksBeige002_UV1.mat | [未重命名或无后缀映射] | — |
| StoneBricksBeige002_COL_3K.jpg | [未重命名或无后缀映射] | — |
| StoneBricksBeige002_DISP_3K.jpg | [未重命名或无后缀映射] | — |
| StoneBricksBeige002_GLOSS_3KMask1.png | [未重命名或无后缀映射] | — |
| StoneBricksBeige002_NRM_3K.jpg | [未重命名或无后缀映射] | — |
| BrownCastleBrickWall_Col.tif | BrownCastleBrickWall_Albedo.tif | _BaseColor, _BaseCol |
| BrownCastleBrickWall_Height2.tif | [未重命名或无后缀映射] | — |
| BrownCastleBrickWall_MetallicSmoothness.tif | [未重命名或无后缀映射] | — |
| BrownCastleBrickWall_N.tif | BrownCastleBrickWall_Normal.tif | _NM, _NRM |
| Mat_StoneWall_BrownCastle.mat | [未重命名或无后缀映射] | — |
| Mat_StoneWall_BrownCastle_UV0.mat | [未重命名或无后缀映射] | — |
| Mat_StoneWall_MedievalWall02.mat | [未重命名或无后缀映射] | — |
| medieval_wall_02_diff_2k.jpg | [未重命名或无后缀映射] | — |
| medieval_wall_02_nor_gl_2k.exr | [未重命名或无后缀映射] | — |
| medieval_wall_02_rough_2kMask1.png | [未重命名或无后缀映射] | — |
| MainIntact_1.prefab | [未重命名或无后缀映射] | — |
| Mat_Wall_Stone2.mat | [未重命名或无后缀映射] | — |
| Mat_Wall_Stone2_UV0.mat | [未重命名或无后缀映射] | — |
| Mat_Wall_Stone2_UV1.mat | [未重命名或无后缀映射] | — |
| Wall_Stone2_3x3_Col.tif | Wall_Stone2_3x3_Albedo.tif | _BaseColor, _BaseCol |
| Wall_Stone2_3x3_H.tif | Wall_Stone2_3x3_Height.tif | _Hight |
| Wall_Stone2_3x3_N.tif | Wall_Stone2_3x3_Normal.tif | _NM, _NRM |
| Wall_Stone2_3x3_RoughnessMask14.png | [未重命名或无后缀映射] | — |
| Mat_StoneWall_BricksBeige001.mat | [未重命名或无后缀映射] | — |
| Mat_StoneWall_BricksBeige001_UV0.mat | [未重命名或无后缀映射] | — |
| StoneBricksBeige001_COL_3K.jpg | [未重命名或无后缀映射] | — |
| StoneBricksBeige001_DISP_3K.jpg | [未重命名或无后缀映射] | — |
| StoneBricksBeige001_GLOSS_3KMask1.png | [未重命名或无后缀映射] | — |
| StoneBricksBeige001_NRM_3K.jpg | [未重命名或无后缀映射] | — |
| Mat_TexturesCom_Wall_BrickIndustrial2 uv0.mat | [未重命名或无后缀映射] | — |
| Mat_TexturesCom_Wall_BrickIndustrial2.mat | [未重命名或无后缀映射] | — |
| Mat_TexturesCom_Wall_BrickIndustrial2_UV0.mat | [未重命名或无后缀映射] | — |
| Wall_BrickIndustrial2_2.5x2.5_Col.tif | Wall_BrickIndustrial2_2.5x2.5_Albedo.tif | _BaseColor, _BaseCol |
| Wall_BrickIndustrial2_2.5x2.5_N.tif | Wall_BrickIndustrial2_2.5x2.5_Normal.tif | _NM, _NRM |
| Wall_BrickIndustrial2_2.5x2.5_RoughnessMask23.png | [未重命名或无后缀映射] | — |
| Mat_Wall_BrickIndustrial6.mat | [未重命名或无后缀映射] | — |
| Wall_BrickIndustrial6_4x4_Col.tif | Wall_BrickIndustrial6_4x4_Albedo.tif | _BaseColor, _BaseCol |
| Wall_BrickIndustrial6_4x4_N.tif | Wall_BrickIndustrial6_4x4_Normal.tif | _NM, _NRM |
| Wall_BrickIndustrial6_4x4_RoughnessMask1.png | [未重命名或无后缀映射] | — |
| Brick_Rustic2_Col.tif | Brick_Rustic2_Albedo.tif | _BaseColor, _BaseCol |
| Brick_Rustic2_H.tif | Brick_Rustic2_Height.tif | _Hight |
| Brick_Rustic2_N.tif | Brick_Rustic2_Normal.tif | _NM, _NRM |
| Brick_Rustic2_RoughnessMask19.png | [未重命名或无后缀映射] | — |
| Mat_TexturesCom_Brick_Rustic2_UV0.mat | [未重命名或无后缀映射] | — |
| Mat_TexturesCom_Brick_Rustic2_UV1.mat | [未重命名或无后缀映射] | — |
| Mat_Wall_church_brick_02.mat | [未重命名或无后缀映射] | — |
| Mat_Wall_church_brick_02_UV0.mat | [未重命名或无后缀映射] | — |
| church_bricks_02_diff_png_4k.jpg | [未重命名或无后缀映射] | — |
| church_bricks_02_nor_gl_4k.jpg | [未重命名或无后缀映射] | — |
| church_bricks_02_rough_4kMask8.png | [未重命名或无后缀映射] | — |
| Mat_Wall_church_bricks_03.mat | [未重命名或无后缀映射] | — |
| Mat_Wall_church_bricks_03_uv0.mat | [未重命名或无后缀映射] | — |
| church_bricks_03_diff_4k.jpg | [未重命名或无后缀映射] | — |
| church_bricks_03_nor_gl_4k.png | [未重命名或无后缀映射] | — |
| church_bricks_03_rough_4kMask10.png | [未重命名或无后缀映射] | — |
| Mat_Wall_Concrete.mat | [未重命名或无后缀映射] | — |
| Wall_ConcreteFenceSoviet2_4.5x2.25_Col.tif | Wall_ConcreteFenceSoviet2_4.5x2.25_Albedo.tif | _BaseColor, _BaseCol |
| Wall_ConcreteFenceSoviet2_4.5x2.25_N.tif | Wall_ConcreteFenceSoviet2_4.5x2.25_Normal.tif | _NM, _NRM |
| Wall_ConcreteFenceSoviet2_4.5x2.25_RMask1.png | [未重命名或无后缀映射] | — |
| Mat_Wall_ConcreteFenceSoviet.mat | [未重命名或无后缀映射] | — |
| Wall_ConcreteFenceSoviet2_4.30x2.15_Col.tif | Wall_ConcreteFenceSoviet2_4.30x2.15_Albedo.tif | _BaseColor, _BaseCol |
| Wall_ConcreteFenceSoviet2_4.30x2.15_H.tif | Wall_ConcreteFenceSoviet2_4.30x2.15_Height.tif | _Hight |
| Wall_ConcreteFenceSoviet2_4.30x2.15_N.tif | Wall_ConcreteFenceSoviet2_4.30x2.15_Normal.tif | _NM, _NRM |
| Wall_ConcreteFenceSoviet2_4.30x2.15_RoughnessMask1.png | [未重命名或无后缀映射] | — |
| Grout_Col.tif | Grout_Albedo.tif | _BaseColor, _BaseCol |
| Grout_N.tif | Grout_Normal.tif | _NM, _NRM |
| Grout_RoughnessMask9.png | [未重命名或无后缀映射] | — |
| Mat_Wall_concrete_Grout.mat | [未重命名或无后缀映射] | — |
| DBK_Doors_Col.tif | DBK_Doors_Albedo.tif | _BaseColor, _BaseCol |
| DBK_Doors_Damage_N.tga | DBK_Doors_Damage_Normal.tga | _NM, _NRM |
| DBK_Doors_Good_N.tga | DBK_Doors_Good_Normal.tga | _NM, _NRM |
| DBK_Doors_RGBA_Mask_damage.png | [未重命名或无后缀映射] | — |
| DBK_Doors_RGBA_Mask_good.png | [未重命名或无后缀映射] | — |
| DBK_Doors_wenli2.tif | [未重命名或无后缀映射] | — |
| Mat_DBK_Door_brown.mat | [未重命名或无后缀映射] | — |
| Mat_DBK_Door_handle.mat | [未重命名或无后缀映射] | — |
| Mat_DBK_Door_white.mat | [未重命名或无后缀映射] | — |
| Mat_Door_layer_Damage.mat | [未重命名或无后缀映射] | — |
| Mat_Door_layer_Good.mat | [未重命名或无后缀映射] | — |
| layer2.tif | [未重命名或无后缀映射] | — |
| Door pattern_heights.bmp | [未重命名或无后缀映射] | — |
| Door pattern_normals.bmp | [未重命名或无后缀映射] | — |
| Door pattern_occlusion.bmp | [未重命名或无后缀映射] | — |
| Door_pattern_Albedo.tif | [未重命名或无后缀映射] | — |
| Door_pattern_OcclusionMask6.png | [未重命名或无后缀映射] | — |
| Mat_Door_pattern.mat | [未重命名或无后缀映射] | — |
| Gate_Blue_Col.tif | Gate_Blue_Albedo.tif | _BaseColor, _BaseCol |
| Gate_Green_Col.tif | Gate_Green_Albedo.tif | _BaseColor, _BaseCol |
| Gate_N.psd | Gate_Normal.psd | _NM, _NRM |
| Gate_Red_Col.tif | Gate_Red_Albedo.tif | _BaseColor, _BaseCol |
| Gate_Wood_Col.tif | Gate_Wood_Albedo.tif | _BaseColor, _BaseCol |
| Gate_glossMask1.png | [未重命名或无后缀映射] | — |
| Mat_Gate_Blue.mat | [未重命名或无后缀映射] | — |
| Mat_Gate_Green.mat | [未重命名或无后缀映射] | — |
| Mat_Gate_Red.mat | [未重命名或无后缀映射] | — |
| Mat_Gate_wood.mat | [未重命名或无后缀映射] | — |
| Gate_Green_Col.tif | Gate_Green_Albedo.tif | _BaseColor, _BaseCol |
| Gate_Wood_Col.tif | Gate_Wood_Albedo.tif | _BaseColor, _BaseCol |
| Gate_normal_1k.tif | [未重命名或无后缀映射] | — |
| Gate_roughnessMask1.png | [未重命名或无后缀映射] | — |
| Mat_Gate02_Green.mat | [未重命名或无后缀映射] | — |
| Mat_Gate02_Wood.mat | [未重命名或无后缀映射] | — |
| Mat_windowsAndDoor_01_A#Blue.mat | [未重命名或无后缀映射] | — |
| Mat_windowsAndDoor_01_A#Green.mat | [未重命名或无后缀映射] | — |
| Mat_windowsAndDoor_01_A#Red.mat | [未重命名或无后缀映射] | — |
| Mat_windowsAndDoor_01_A#wood.mat | [未重命名或无后缀映射] | — |
| Mat_windowsAndDoor_01_A#wood_dark.mat | [未重命名或无后缀映射] | — |
| WindowsAndDoor_01_A#Blue.tif | [未重命名或无后缀映射] | — |
| WindowsAndDoor_01_A#Green.tif | [未重命名或无后缀映射] | — |
| WindowsAndDoor_01_A#Red.tif | [未重命名或无后缀映射] | — |
| WindowsAndDoor_01_A#Wood.tif | [未重命名或无后缀映射] | — |
| WindowsAndDoor_01_A#Wood2.tif | [未重命名或无后缀映射] | — |
| WindowsAndDoor_01_N.tif | WindowsAndDoor_01_Normal.tif | _NM, _NRM |
| WindowsAndDoor_01_glossMask5.png | [未重命名或无后缀映射] | — |
| Mat_ceiling.mat | [未重命名或无后缀映射] | — |
| WoodWall_Wood_BaseMap.tif | [未重命名或无后缀映射] | — |
| WoodWall_Wood_Mask.tif | WoodWall_Wood_MaskMap.tif | _M |
| WoodWall_Wood_N.tif | WoodWall_Wood_Normal.tif | _NM, _NRM |
| Mat_Wood_Paint_A.mat | [未重命名或无后缀映射] | — |
| Paintwood_Low_Wood_Paint_A_Mask.tif | Paintwood_Low_Wood_Paint_A_MaskMap.tif | _M |
| Paintwood_Low_Wood_Paint_A_N.tif | Paintwood_Low_Wood_Paint_A_Normal.tif | _NM, _NRM |
| paintwood_low_Wood_Paint_A_BaseMap.tif | [未重命名或无后缀映射] | — |
| Mat_Wood_Plank004.mat | [未重命名或无后缀映射] | — |
| Planks004_Col.png | Planks004_Albedo.png | _BaseColor, _BaseCol |
| Planks004_Color2.tif | [未重命名或无后缀映射] | — |
| Planks004_Mask.png | Planks004_MaskMap.png | _M |
| Planks004_N.png | Planks004_Normal.png | _NM, _NRM |
| Mat_Wood_RoughGrungy.mat | [未重命名或无后缀映射] | — |
| Mat_Wood_RoughGrungy_Brown.mat | [未重命名或无后缀映射] | — |
| Mat_Wood_RoughGrungy_Light.mat | [未重命名或无后缀映射] | — |
| Mat_Wood_RoughGrungy_Orange.mat | [未重命名或无后缀映射] | — |
| Mat_Wood_RoughGrungy_RED.mat | [未重命名或无后缀映射] | — |
| RoughGrungyWoodSurface_N.tif | RoughGrungyWoodSurface_Normal.tif | _NM, _NRM |
| RoughGrungyWoodSurface_basecolor.png | [未重命名或无后缀映射] | — |
| RoughGrungyWoodSurface_mask.png | [未重命名或无后缀映射] | — |
| Mat_castle.mat | [未重命名或无后缀映射] | — |
| castle_wall_slates_albedo_2k.jpg | [未重命名或无后缀映射] | — |
| castle_wall_slates_diff_2k.jpg | [未重命名或无后缀映射] | — |
| castle_wall_slates_nor_2k.jpg | [未重命名或无后缀映射] | — |
| castle_wall_slates_rough_2kMask1.png | [未重命名或无后缀映射] | — |
| Mat_concrete_floor.mat | [未重命名或无后缀映射] | — |
| concrete_floor_02_Nor_2k.jpg | [未重命名或无后缀映射] | — |
| concrete_floor_02_diff_2k.jpg | [未重命名或无后缀映射] | — |
| concrete_floor_02_rough_2kMask2.png | [未重命名或无后缀映射] | — |
| mask_Gradient02.tif | [未重命名或无后缀映射] | — |
| rename_log.txt | [未重命名或无后缀映射] | — |
| Mat_rusty_metal.mat | [未重命名或无后缀映射] | — |
| rusty_metal_02_diff_2k.jpg | [未重命名或无后缀映射] | — |
| rusty_metal_02_nor_2k.jpg | [未重命名或无后缀映射] | — |
| rusty_metal_02_rough_2kMask1.png | [未重命名或无后缀映射] | — |
| whiteMask1.png | [未重命名或无后缀映射] | — |

## ⚠️ Terrain_Materials（反向推导）

> 执行时未抓完整日志，原名由后缀规则反向推导，不保证 100% 精确。
> 推导逻辑：`_Col` → 最可能 `_Albedo`；`_N` → 最可能 `_Normal`；`_Mask` → 最可能 `_MaskMap`

| 当前名 | 推测原名 | 其他可能 |
|--------|----------|----------|
| CTL_Coordinates.terrainlayer | [未重命名或无后缀映射] | — |
| Coordinates_A.png | [未重命名或无后缀映射] | — |
| Mat_Coordinates.mat | [未重命名或无后缀映射] | — |
| No_pass.tif | [未重命名或无后缀映射] | — |
| No_pass_02.tif | [未重命名或无后缀映射] | — |
| no pass.terrainlayer | [未重命名或无后缀映射] | — |
| Asphalt01_Col.tif | Asphalt01_Albedo.tif | _BaseColor, _BaseCol |
| Asphalt01_Mask.png | Asphalt01_MaskMap.png | _M |
| Asphalt01_N.tif | Asphalt01_Normal.tif | _NM, _NRM |
| CTL_Asphalt01.terrainlayer | [未重命名或无后缀映射] | — |
| tex.txt | [未重命名或无后缀映射] | — |
| Asphalt02_Col.tif | Asphalt02_Albedo.tif | _BaseColor, _BaseCol |
| Asphalt02_N.tif | Asphalt02_Normal.tif | _NM, _NRM |
| Asphalt02_mask.tif | [未重命名或无后缀映射] | — |
| CTL_Asphalt02.terrainlayer | [未重命名或无后缀映射] | — |
| tex.txt | [未重命名或无后缀映射] | — |
| Asphalt03_Mask.png | Asphalt03_MaskMap.png | _M |
| Asphalt03_N.tif | Asphalt03_Normal.tif | _NM, _NRM |
| Asphalt03_col.tif | [未重命名或无后缀映射] | — |
| Mat_Decal_Asphalt03.mat | [未重命名或无后缀映射] | — |
| tex.txt | [未重命名或无后缀映射] | — |
| Ground_PebblesRiver1_2x2.tif | [未重命名或无后缀映射] | — |
| Ground_PebblesRiver1_2x2_N.tif | Ground_PebblesRiver1_2x2_Normal.tif | _NM, _NRM |
| Ground_PebblesRiver1_2x2_RoughnessMask1.png | [未重命名或无后缀映射] | — |
| Mat_Decal_PebblesRiver1.mat | [未重命名或无后缀映射] | — |
| CTL_Pavement_Cobblestone01.terrainlayer | [未重命名或无后缀映射] | — |
| Pavement_Cobblestone01_N.tif | Pavement_Cobblestone01_Normal.tif | _NM, _NRM |
| Pavement_Cobblestone01_col.tif | [未重命名或无后缀映射] | — |
| Pavement_Cobblestone01_mask.tif | [未重命名或无后缀映射] | — |
| tex.txt | [未重命名或无后缀映射] | — |
| Concrete_Peel01_Col.tif | Concrete_Peel01_Albedo.tif | _BaseColor, _BaseCol |
| Concrete_Peel01_Mask.png | Concrete_Peel01_MaskMap.png | _M |
| Concrete_Peel01_albedoA.tif | [未重命名或无后缀映射] | — |
| Concrete_Peel01_nor.tif | [未重命名或无后缀映射] | — |
| Mat_Concrete_Peel01.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_Concrete_Peel01_02.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_Concrete_Peel01_05.mat | [未重命名或无后缀映射] | — |
| tex.txt | [未重命名或无后缀映射] | — |
| Crack01_col.tif | [未重命名或无后缀映射] | — |
| Mat_Decal_Crack01.mat | [未重命名或无后缀映射] | — |
| tex.txt | [未重命名或无后缀映射] | — |
| Crack02_col.png | [未重命名或无后缀映射] | — |
| Mat_Decal_Crack02.mat | [未重命名或无后缀映射] | — |
| tex.txt | [未重命名或无后缀映射] | — |
| Decal_Crack03_col.png | [未重命名或无后缀映射] | — |
| Mat_Decal_Crack03.mat | [未重命名或无后缀映射] | — |
| tex.txt | [未重命名或无后缀映射] | — |
| Crack04_Col.png | Crack04_Albedo.png | _BaseColor, _BaseCol |
| Crack04_N.tga | Crack04_Normal.tga | _NM, _NRM |
| Mat_Decal_Crack04.mat | [未重命名或无后缀映射] | — |
| Damage01.png | [未重命名或无后缀映射] | — |
| Mat_Decal_Damage01.mat | [未重命名或无后缀映射] | — |
| tex.txt | [未重命名或无后缀映射] | — |
| Damage02.png | [未重命名或无后缀映射] | — |
| Mat_Decal_Damage02.mat | [未重命名或无后缀映射] | — |
| tex.txt | [未重命名或无后缀映射] | — |
| Damage03_Col.png | Damage03_Albedo.png | _BaseColor, _BaseCol |
| Damage03_N.tga | Damage03_Normal.tga | _NM, _NRM |
| Mat_Decal_Damage03.mat | [未重命名或无后缀映射] | — |
| Damage04_Col.tga | Damage04_Albedo.tga | _BaseColor, _BaseCol |
| Damage04_N.psd | Damage04_Normal.psd | _NM, _NRM |
| Mat_Decal_Damage04.mat | [未重命名或无后缀映射] | — |
| Damage05_Col.tga | Damage05_Albedo.tga | _BaseColor, _BaseCol |
| Damage05_N.psd | Damage05_Normal.psd | _NM, _NRM |
| Mat_Decal_Damage05.mat | [未重命名或无后缀映射] | — |
| Damage06_Nor.psd | [未重命名或无后缀映射] | — |
| Damage06_col.tga | [未重命名或无后缀映射] | — |
| Mat_Decal_Damage06.mat | [未重命名或无后缀映射] | — |
| Damage07_Col.tga | Damage07_Albedo.tga | _BaseColor, _BaseCol |
| Damage07_N.psd | Damage07_Normal.psd | _NM, _NRM |
| Mat_Decal_Damage07.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_RoadsDirt01.mat | [未重命名或无后缀映射] | — |
| RoadsDirt01_Mask.png | RoadsDirt01_MaskMap.png | _M |
| RoadsDirt01_col.tif | [未重命名或无后缀映射] | — |
| RoadsDirt01_nor.tif | [未重命名或无后缀映射] | — |
| tex.txt | [未重命名或无后缀映射] | — |
| Mat_Decal_RoadsDirt02.mat | [未重命名或无后缀映射] | — |
| RoadsDirt02_Mask.png | RoadsDirt02_MaskMap.png | _M |
| RoadsDirt02_N.tif | RoadsDirt02_Normal.tif | _NM, _NRM |
| RoadsDirt02_col.tif | [未重命名或无后缀映射] | — |
| tex.txt | [未重命名或无后缀映射] | — |
| Crater01_col.tif | [未重命名或无后缀映射] | — |
| Crater01_nor.tif | [未重命名或无后缀映射] | — |
| Mat_Decal_Crater01.mat | [未重命名或无后缀映射] | — |
| Crater_122-03_A.png | [未重命名或无后缀映射] | — |
| Crater_122-03_N.png | Crater_122-03_Normal.png | _NM, _NRM |
| Mat_Decal_Crater_122_03.mat | [未重命名或无后缀映射] | — |
| Crater_122-04_A.png | [未重命名或无后缀映射] | — |
| Crater_122-04_N.png | Crater_122-04_Normal.png | _NM, _NRM |
| Mat_Decal_Crater_122_04.mat | [未重命名或无后缀映射] | — |
| Crater_122-05_A.png | [未重命名或无后缀映射] | — |
| Crater_122-05_N.png | Crater_122-05_Normal.png | _NM, _NRM |
| Mat_Decal_Crater_122_05.mat | [未重命名或无后缀映射] | — |
| Decal_Field_Type01_02_A2 1.prefab | [未重命名或无后缀映射] | — |
| Decal_Field_Type01_02_A2_Parent.prefab | [未重命名或无后缀映射] | — |
| DefaultMaterial_A.png | [未重命名或无后缀映射] | — |
| DefaultMaterial_h.png | [未重命名或无后缀映射] | — |
| Dirt_Field_38_12_H.jpg | Dirt_Field_38_12_Height.jpg | _Hight |
| Dirt_Field_38_12_N.jpg | Dirt_Field_38_12_Normal.jpg | _NM, _NRM |
| FarmLand01_Col.png | FarmLand01_Albedo.png | _BaseColor, _BaseCol |
| FarmLand01_H.png | FarmLand01_Height.png | _Hight |
| Field_01_A.png | [未重命名或无后缀映射] | — |
| Field_01_H.jpg | Field_01_Height.jpg | _Hight |
| Field_01_N.tga | Field_01_Normal.tga | _NM, _NRM |
| Field_01_h2.tif | [未重命名或无后缀映射] | — |
| Field_05_A.jpg | [未重命名或无后缀映射] | — |
| Field_05_H.jpg | Field_05_Height.jpg | _Hight |
| Ground_Soil11_3x3_Albedo-恢复的.tif | [未重命名或无后缀映射] | — |
| HeightMap.jpg | [未重命名或无后缀映射] | — |
| Mat_Decal_FieldA_10mX10m_43°.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_FieldA_10mX10m_50°.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_FieldA_10mX10m_90°.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_FieldA_30mX30m_.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_FieldA_30mX30m_0°.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_FieldA_30mX30m_22°.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_FieldA_30mX30m_27°.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_FieldA_30mX30m_30°.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_FieldA_30mX30m_358°.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_FieldA_30mX30m_4°.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_FieldA_30mX30m_60°.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_FieldA_30mX30m_72°.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_FieldB_30mX30m_22°.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_FieldC_30mX30m_22°_1.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_FieldD_30mX30m_22°_2.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_Field_autumn_10mX10m_0°.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_Field_autumn_10mX10m_0°_1.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_Field_autumn_10mX10m_140°.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_Field_autumn_10mX10m_150°.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_Field_autumn_10mX10m_165°.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_Field_autumn_10mX10m_35°.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_Field_autumn_10mX10m_55°.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_Field_autumn_10mX10m_70°.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_Field_autumn_10mX10m_90°.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_Field_autumn_30mX30m_160°.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_Field_autumn_30mX30m_50°.mat | [未重命名或无后缀映射] | — |
| dirt_field_38_12_ao.jpg | [未重命名或无后缀映射] | — |
| dirt_field_38_12_diffuse.jpg | [未重命名或无后缀映射] | — |
| dirt_field_38_12_glossiness.jpg | [未重命名或无后缀映射] | — |
| snow_04_disp_4k.jpg | [未重命名或无后缀映射] | — |
| Field_Type-01_02_A2.tif | [未重命名或无后缀映射] | — |
| Mat_Decal_Field_Type-01_02_A2.mat | [未重命名或无后缀映射] | — |
| CTL_Forest01.terrainlayer | [未重命名或无后缀映射] | — |
| Forest01_Col.tif | Forest01_Albedo.tif | _BaseColor, _BaseCol |
| Forest01_Mask.tif | Forest01_MaskMap.tif | _M |
| Forest01_N.tif | Forest01_Normal.tif | _NM, _NRM |
| Mat_Forest01.mat | [未重命名或无后缀映射] | — |
| tex.txt | [未重命名或无后缀映射] | — |
| CTL_Forest02.terrainlayer | [未重命名或无后缀映射] | — |
| Forest02_Col.tif | Forest02_Albedo.tif | _BaseColor, _BaseCol |
| Forest02_H.tif | Forest02_Height.tif | _Hight |
| Forest02_Mask.png | Forest02_MaskMap.png | _M |
| Forest02_N.tif | Forest02_Normal.tif | _NM, _NRM |
| Forest02_ao.tif | [未重命名或无后缀映射] | — |
| Forest02_roughness.tif | [未重命名或无后缀映射] | — |
| tex.txt | [未重命名或无后缀映射] | — |
| Forest03_Col.tif | Forest03_Albedo.tif | _BaseColor, _BaseCol |
| Forest03_N.tif | Forest03_Normal.tif | _NM, _NRM |
| Mat_Decal_forest03.mat | [未重命名或无后缀映射] | — |
| forest03_Mask.png | forest03_MaskMap.png | _M |
| tex.txt | [未重命名或无后缀映射] | — |
| CTL_Forest04.terrainlayer | [未重命名或无后缀映射] | — |
| Forest04_Mask.png | Forest04_MaskMap.png | _M |
| Forest04_N.tif | Forest04_Normal.tif | _NM, _NRM |
| Forest04_albedoA.tif | [未重命名或无后缀映射] | — |
| Mat_Decal_Forest04.mat | [未重命名或无后缀映射] | — |
| tex.txt | [未重命名或无后缀映射] | — |
| Forest05_Mask.png | Forest05_MaskMap.png | _M |
| Forest05_N.tif | Forest05_Normal.tif | _NM, _NRM |
| Forest05_diffA.tif | [未重命名或无后缀映射] | — |
| Mat_Decal_Forest05.mat | [未重命名或无后缀映射] | — |
| tex.txt | [未重命名或无后缀映射] | — |
| Forest06_Col.tif | Forest06_Albedo.tif | _BaseColor, _BaseCol |
| Forest06_Mask.png | Forest06_MaskMap.png | _M |
| Forest06_N.tif | Forest06_Normal.tif | _NM, _NRM |
| Mat_Decal_Forest06_30.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_Forest06_60.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_Forest06_80.mat | [未重命名或无后缀映射] | — |
| tex.txt | [未重命名或无后缀映射] | — |
| CTL_Grass_01.terrainlayer | [未重命名或无后缀映射] | — |
| Grass_01_Col.tif | Grass_01_Albedo.tif | _BaseColor, _BaseCol |
| Grass_01_Mask.tif | Grass_01_MaskMap.tif | _M |
| Grass_01_N.tif | Grass_01_Normal.tif | _NM, _NRM |
| Mat_Grass_01.mat | [未重命名或无后缀映射] | — |
| CTL_Grass_02.terrainlayer | [未重命名或无后缀映射] | — |
| Grass_02_Col.tif | Grass_02_Albedo.tif | _BaseColor, _BaseCol |
| Grass_02_H.tif | Grass_02_Height.tif | _Hight |
| Grass_02_Mask.tif | Grass_02_MaskMap.tif | _M |
| Grass_02_N.tif | Grass_02_Normal.tif | _NM, _NRM |
| CTL_Grass03.terrainlayer | [未重命名或无后缀映射] | — |
| Grass03_Col.png | Grass03_Albedo.png | _BaseColor, _BaseCol |
| Grass03_Mask.png | Grass03_MaskMap.png | _M |
| Grass03_nor.png | [未重命名或无后缀映射] | — |
| tex.txt | [未重命名或无后缀映射] | — |
| CTL_GrassDry.terrainlayer | [未重命名或无后缀映射] | — |
| Grass_Dry_01_Col.tif | Grass_Dry_01_Albedo.tif | _BaseColor, _BaseCol |
| Grass_Dry_01_Mask.tif | Grass_Dry_01_MaskMap.tif | _M |
| Grass_Dry_01_N.tif | Grass_Dry_01_Normal.tif | _NM, _NRM |
| CTL_Grass_Dry_02.terrainlayer | [未重命名或无后缀映射] | — |
| Grass_Dry_02_Col.tif | Grass_Dry_02_Albedo.tif | _BaseColor, _BaseCol |
| Grass_Dry_02_Col_A.tif | [未重命名或无后缀映射] | — |
| Grass_Dry_02_Mask.tif | Grass_Dry_02_MaskMap.tif | _M |
| Grass_Dry_02_N.tif | Grass_Dry_02_Normal.tif | _NM, _NRM |
| Mat_DecalShape_Grass_Dry_02.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_Grass_Dry_02.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_Grass_Dry_02_B.mat | [未重命名或无后缀映射] | — |
| CTL_Heather_01.terrainlayer | [未重命名或无后缀映射] | — |
| Heather_Col.tif | Heather_Albedo.tif | _BaseColor, _BaseCol |
| Heather_Mask.tif | Heather_MaskMap.tif | _M |
| Heather_N.tif | Heather_Normal.tif | _NM, _NRM |
| Mat_Decal_Heather_01.mat | [未重命名或无后缀映射] | — |
| CTL_Earth_Dry.terrainlayer | [未重命名或无后缀映射] | — |
| Earth_Dry_01_H.tif | Earth_Dry_01_Height.tif | _Hight |
| Earth_Dry_01_Mask.png | Earth_Dry_01_MaskMap.png | _M |
| Earth_Dry_01_N.tga | Earth_Dry_01_Normal.tga | _NM, _NRM |
| Earth_Dry_01_col.tif | [未重命名或无后缀映射] | — |
| Mat_DecalShape_Earth_Dry_01.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_Earth_Dry_01.mat | [未重命名或无后缀映射] | — |
| tex.txt | [未重命名或无后缀映射] | — |
| Earth_Dry_02_Mask.png | Earth_Dry_02_MaskMap.png | _M |
| Earth_Dry_02_N.tif | Earth_Dry_02_Normal.tif | _NM, _NRM |
| Earth_Dry_02_albedoA.tif | [未重命名或无后缀映射] | — |
| Mat_Decal_Earth_Dry_02.mat | [未重命名或无后缀映射] | — |
| TL_Earth_Dry_02.terrainlayer | [未重命名或无后缀映射] | — |
| txt.txt | [未重命名或无后缀映射] | — |
| CTL_Earth_Dry_Rocks.terrainlayer | [未重命名或无后缀映射] | — |
| Earth_Dry_Rocks_Mask.png | Earth_Dry_Rocks_MaskMap.png | _M |
| Earth_Dry_Rocks_N.tif | Earth_Dry_Rocks_Normal.tif | _NM, _NRM |
| Earth_Dry_Rocks_albedoA.tif | [未重命名或无后缀映射] | — |
| Mat_Decal_Earth_Dry_Rocks.mat | [未重命名或无后缀映射] | — |
| tex.txt | [未重命名或无后缀映射] | — |
| Earth_Footprints02_AlbedoA.tif | [未重命名或无后缀映射] | — |
| Earth_Footprints02_Mask.png | Earth_Footprints02_MaskMap.png | _M |
| Earth_Footprints02_Nor.jpg | [未重命名或无后缀映射] | — |
| Mat_Decal_Earth_Footprints02.mat | [未重命名或无后缀映射] | — |
| tex.txt | [未重命名或无后缀映射] | — |
| CTL_Earth_Grass.terrainlayer | [未重命名或无后缀映射] | — |
| Earth_Grass_H.tif | Earth_Grass_Height.tif | _Hight |
| Earth_Grass_col.tif | [未重命名或无后缀映射] | — |
| Earth_Grass_nor.tif | [未重命名或无后缀映射] | — |
| CTL_Mud_01.terrainlayer | [未重命名或无后缀映射] | — |
| Mud_01_AO.tif | [未重命名或无后缀映射] | — |
| Mud_01_Col.tif | Mud_01_Albedo.tif | _BaseColor, _BaseCol |
| Mud_01_H.tif | Mud_01_Height.tif | _Hight |
| Mud_01_Mask.tif | Mud_01_MaskMap.tif | _M |
| Mud_01_Nor.tif | [未重命名或无后缀映射] | — |
| Mud_01_Smooth.tif | Mud_01_Smoothness.tif | — |
| CTL_Muddy.terrainlayer | [未重命名或无后缀映射] | — |
| Muddy_Col.tif | Muddy_Albedo.tif | _BaseColor, _BaseCol |
| Muddy_H.tif | Muddy_Height.tif | _Hight |
| Muddy_Mask.tif | Muddy_MaskMap.tif | _M |
| Muddy_N.tif | Muddy_Normal.tif | _NM, _NRM |
| Decal_Earth_Road_01.prefab | [未重命名或无后缀映射] | — |
| Earth_Road_01_Col.tif | Earth_Road_01_Albedo.tif | _BaseColor, _BaseCol |
| Earth_Road_01_N.tif | Earth_Road_01_Normal.tif | _NM, _NRM |
| Earth_Road_01_mask.png | [未重命名或无后缀映射] | — |
| Mat_Decal_Earth_Road_01.mat | [未重命名或无后缀映射] | — |
| Earth_Round_col.tif | [未重命名或无后缀映射] | — |
| Mat_Earth_Earth_Round.mat | [未重命名或无后缀映射] | — |
| tex.txt | [未重命名或无后缀映射] | — |
| Mat_Decal_Rocks_01.mat | [未重命名或无后缀映射] | — |
| rocks_01_Mask.png | rocks_01_MaskMap.png | _M |
| rocks_01_diff.tif | [未重命名或无后缀映射] | — |
| rocks_01_n.jpg | [未重命名或无后缀映射] | — |
| Mat_Decal_Rocks_02.mat | [未重命名或无后缀映射] | — |
| Rocks_02_diff.tif | [未重命名或无后缀映射] | — |
| Rocks_02_mask.png | [未重命名或无后缀映射] | — |
| Rocks_02_nor.jpg | [未重命名或无后缀映射] | — |
| Mat_Decal_Rocks_03.mat | [未重命名或无后缀映射] | — |
| Rocks_03_diff.tif | [未重命名或无后缀映射] | — |
| Rocks_03_nor.tif | [未重命名或无后缀映射] | — |
| CTL_Rocks_Sandy.terrainlayer | [未重命名或无后缀映射] | — |
| Rocks_Sandy_Col.tif | Rocks_Sandy_Albedo.tif | _BaseColor, _BaseCol |
| Rocks_Sandy_N.tif | Rocks_Sandy_Normal.tif | _NM, _NRM |
| Rocks_Sandy_mask.tif | [未重命名或无后缀映射] | — |
| tex.txt | [未重命名或无后缀映射] | — |
| Mat_Decal_Leaves_01.mat | [未重命名或无后缀映射] | — |
| leaves_01_Mask.png | leaves_01_MaskMap.png | _M |
| leaves_01_diff.tif | [未重命名或无后缀映射] | — |
| leaves_01_nor.png | [未重命名或无后缀映射] | — |
| CTL_leaves_02.terrainlayer | [未重命名或无后缀映射] | — |
| Mat_Decal_leaves_02.mat | [未重命名或无后缀映射] | — |
| leaves_02_A.tif | [未重命名或无后缀映射] | — |
| leaves_02_Mask.tga | leaves_02_MaskMap.tga | _M |
| leaves_02_N.png | leaves_02_Normal.png | _NM, _NRM |
| tex.txt | [未重命名或无后缀映射] | — |
| Leaves_Fruit_Col.tif | Leaves_Fruit_Albedo.tif | _BaseColor, _BaseCol |
| Leaves_Fruit_Mask.png | Leaves_Fruit_MaskMap.png | _M |
| Leaves_Fruit_N.tif | Leaves_Fruit_Normal.tif | _NM, _NRM |
| Mat_Decal_Leaves_Fruit.mat | [未重命名或无后缀映射] | — |
| tex.txt | [未重命名或无后缀映射] | — |
| CTL_Moss_01_Layer.terrainlayer | [未重命名或无后缀映射] | — |
| Moss_01_Col.tif | Moss_01_Albedo.tif | _BaseColor, _BaseCol |
| Moss_01_H.tif | Moss_01_Height.tif | _Hight |
| Moss_01_Mask.tif | Moss_01_MaskMap.tif | _M |
| Moss_01_N.tif | Moss_01_Normal.tif | _NM, _NRM |
| CTL_Moss_02.terrainlayer | [未重命名或无后缀映射] | — |
| Moss_02_Col.tif | Moss_02_Albedo.tif | _BaseColor, _BaseCol |
| Moss_02_Mask.tif | Moss_02_MaskMap.tif | _M |
| Moss_02_N.tif | Moss_02_Normal.tif | _NM, _NRM |
| CTL_Mess_03.terrainlayer | [未重命名或无后缀映射] | — |
| Mat_Decal_Mess_03.mat | [未重命名或无后缀映射] | — |
| Mess_03_Col.tif | Mess_03_Albedo.tif | _BaseColor, _BaseCol |
| Mess_03_Mask.png | Mess_03_MaskMap.png | _M |
| Mess_03_N.tif | Mess_03_Normal.tif | _NM, _NRM |
| tex.txt | [未重命名或无后缀映射] | — |
| Mat_Decal_Parking_Apron_01.mat | [未重命名或无后缀映射] | — |
| Parking_Apron_01.tif | [未重命名或无后缀映射] | — |
| Mat_Decal_Pavement_Regular_01.mat | [未重命名或无后缀映射] | — |
| Pavement_Regular_01_A.jpg | [未重命名或无后缀映射] | — |
| Pavement_Regular_01_Mask.png | Pavement_Regular_01_MaskMap.png | _M |
| Pavement_Regular_01_N.tiff | Pavement_Regular_01_Normal.tiff | _NM, _NRM |
| tet.txt | [未重命名或无后缀映射] | — |
| Mat_Decal_Pavement_Regular_01_Corner.mat | [未重命名或无后缀映射] | — |
| Pavement_Regular_01_Corner_Mask.png | Pavement_Regular_01_Corner_MaskMap.png | _M |
| Pavement_Regular_01_Corner_N.tif | Pavement_Regular_01_Corner_Normal.tif | _NM, _NRM |
| Pavement_Regular_01_Corner_albedoA.tif | [未重命名或无后缀映射] | — |
| CTL_Pavement_Sidewalk_010.terrainlayer | [未重命名或无后缀映射] | — |
| Mat_Decal_Pavement_Sidewalk_010.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_Pavement_Sidewalk_010_round.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_Pavement_Sidewalk_010_square.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_Pavement_Sidewalk_010_square_115.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_Pavement_Sidewalk_010_square_181.mat | [未重命名或无后缀映射] | — |
| Pavement_Sidewalk_010_Mask.png | Pavement_Sidewalk_010_MaskMap.png | _M |
| Pavement_Sidewalk_010_N.tif | Pavement_Sidewalk_010_Normal.tif | _NM, _NRM |
| Pavement_Sidewalk_010_albedoA.tif | [未重命名或无后缀映射] | — |
| tex.txt | [未重命名或无后缀映射] | — |
| Mat_Decal_Pavement_Sidewalk_05.mat | [未重命名或无后缀映射] | — |
| Pavement_Sidewalk_05_Col.tif | Pavement_Sidewalk_05_Albedo.tif | _BaseColor, _BaseCol |
| Pavement_Sidewalk_05_N.tif | Pavement_Sidewalk_05_Normal.tif | _NM, _NRM |
| Pavement_Sidewalk_05_mask.tif | [未重命名或无后缀映射] | — |
| Mat_Decal_Pavement_Street_01.mat | [未重命名或无后缀映射] | — |
| Pavement_Street_01_Mask.png | Pavement_Street_01_MaskMap.png | _M |
| Pavement_Street_01_N.tif | Pavement_Street_01_Normal.tif | _NM, _NRM |
| Pavement_Street_01_albedoA.tif | [未重命名或无后缀映射] | — |
| tex.txt | [未重命名或无后缀映射] | — |
| Mat_Pavement_Street_02.mat | [未重命名或无后缀映射] | — |
| Pavement_Street_02_Col.tif | Pavement_Street_02_Albedo.tif | _BaseColor, _BaseCol |
| Pavement_Street_02_Mask.png | Pavement_Street_02_MaskMap.png | _M |
| tex.txt | [未重命名或无后缀映射] | — |
| Decal_Pebbles_B.prefab | [未重命名或无后缀映射] | — |
| CTL_Poorside_Pebbles_01.terrainlayer | [未重命名或无后缀映射] | — |
| Pebbles_01_Col.tif | Pebbles_01_Albedo.tif | _BaseColor, _BaseCol |
| Pebbles_01_Mask.tif | Pebbles_01_MaskMap.tif | _M |
| Pebbles_01_N.tif | Pebbles_01_Normal.tif | _NM, _NRM |
| CTL_PoolSide_Pebbles_02.terrainlayer | [未重命名或无后缀映射] | — |
| Mat_Decal_PoolSide_Pebbles_02.mat | [未重命名或无后缀映射] | — |
| PoolSide_Pebbles_02_Col.tif | PoolSide_Pebbles_02_Albedo.tif | _BaseColor, _BaseCol |
| PoolSide_Pebbles_02_ColA.tif | [未重命名或无后缀映射] | — |
| PoolSide_Pebbles_02_Mask.tif | PoolSide_Pebbles_02_MaskMap.tif | _M |
| PoolSide_Pebbles_02_N.tif | PoolSide_Pebbles_02_Normal.tif | _NM, _NRM |
| CTL_PoolSide_Pools.terrainlayer | [未重命名或无后缀映射] | — |
| Tidal_Pools_Col.tif | Tidal_Pools_Albedo.tif | _BaseColor, _BaseCol |
| Tidal_Pools_Mask.tif | Tidal_Pools_MaskMap.tif | _M |
| Tidal_Pools_N.tif | Tidal_Pools_Normal.tif | _NM, _NRM |
| DecalRoad_TyrePrint01_40.prefab | [未重命名或无后缀映射] | — |
| DecalRoad_TyrePrint01_60.prefab | [未重命名或无后缀映射] | — |
| DecalRoad_TyrePrint01_End_40.prefab | [未重命名或无后缀映射] | — |
| DecalRoad_TyrePrint01_End_60.prefab | [未重命名或无后缀映射] | — |
| DecalShape_Grass_yellow.prefab | [未重命名或无后缀映射] | — |
| DecalShape_Ground.prefab | [未重命名或无后缀映射] | — |
| Decal_AsphaltDamaged0083.prefab | [未重命名或无后缀映射] | — |
| Decal_Asphalt_Base11.prefab | [未重命名或无后缀映射] | — |
| Decal_Concrete_Base11_02.prefab | [未重命名或无后缀映射] | — |
| Decal_Concrete_Base11_05.prefab | [未重命名或无后缀映射] | — |
| Decal_Crater_07.prefab | [未重命名或无后缀映射] | — |
| Decal_Crater_122_03.prefab | [未重命名或无后缀映射] | — |
| Decal_Crater_122_04.prefab | [未重命名或无后缀映射] | — |
| Decal_Crater_122_05.prefab | [未重命名或无后缀映射] | — |
| Decal_DamageFloor0020-1.prefab | [未重命名或无后缀映射] | — |
| Decal_DamageFloor0020_3.prefab | [未重命名或无后缀映射] | — |
| Decal_DamageFloor0022_1.prefab | [未重命名或无后缀映射] | — |
| Decal_DamageFloor0022_2.prefab | [未重命名或无后缀映射] | — |
| Decal_Damage_Type01_01.prefab | [未重命名或无后缀映射] | — |
| Decal_Damage_Type01_02.prefab | [未重命名或无后缀映射] | — |
| Decal_Damage_Type02_01.prefab | [未重命名或无后缀映射] | — |
| Decal_Damage_Type02_02.prefab | [未重命名或无后缀映射] | — |
| Decal_Damage_Type02_03.prefab | [未重命名或无后缀映射] | — |
| Decal_Damage_Type02_04.prefab | [未重命名或无后缀映射] | — |
| Decal_FieldA_10mX10m_43°.prefab | [未重命名或无后缀映射] | — |
| Decal_FieldA_10mX10m_50°.prefab | [未重命名或无后缀映射] | — |
| Decal_FieldA_10mX10m_90°.prefab | [未重命名或无后缀映射] | — |
| Decal_FieldA_15mX15m_0°.prefab | [未重命名或无后缀映射] | — |
| Decal_Field_Type01_02_A2 1.prefab | [未重命名或无后缀映射] | — |
| Decal_Field_Type01_02_A2_Parent.prefab | [未重命名或无后缀映射] | — |
| Decal_Field_autumn_10mX10m_140°.prefab | [未重命名或无后缀映射] | — |
| Decal_Field_autumn_10mX10m_35°.prefab | [未重命名或无后缀映射] | — |
| Decal_Field_autumn_20mX20m_0°.prefab | [未重命名或无后缀映射] | — |
| Decal_Field_autumn_20mX20m_140°.prefab | [未重命名或无后缀映射] | — |
| Decal_Field_autumn_20mX20m_150°.prefab | [未重命名或无后缀映射] | — |
| Decal_Field_autumn_20mX20m_165°.prefab | [未重命名或无后缀映射] | — |
| Decal_Field_autumn_20mX20m_50°.prefab | [未重命名或无后缀映射] | — |
| Decal_Field_autumn_20mX20m_55°.prefab | [未重命名或无后缀映射] | — |
| Decal_Field_autumn_30mX30m_140° .prefab | [未重命名或无后缀映射] | — |
| Decal_Field_autumn_30mX30m_160°.prefab | [未重命名或无后缀映射] | — |
| Decal_Field_autumn_30mX30m_50°.prefab | [未重命名或无后缀映射] | — |
| Decal_FloorsRegular0204_1.prefab | [未重命名或无后缀映射] | — |
| Decal_Footprint002.prefab | [未重命名或无后缀映射] | — |
| Decal_Grass_Green.prefab | [未重命名或无后缀映射] | — |
| Decal_Grass_Green_W10H10.prefab | [未重命名或无后缀映射] | — |
| Decal_Grass_Heather.prefab | [未重命名或无后缀映射] | — |
| Decal_Grass_Soil_A.prefab | [未重命名或无后缀映射] | — |
| Decal_Grass_Soil_B.prefab | [未重命名或无后缀映射] | — |
| Decal_Grass_yellow.prefab | [未重命名或无后缀映射] | — |
| Decal_Ground_Soil.prefab | [未重命名或无后缀映射] | — |
| Decal_Heather.prefab | [未重命名或无后缀映射] | — |
| Decal_Parking Apron.prefab | [未重命名或无后缀映射] | — |
| Decal_Pavement_Sidewalk10_round.prefab | [未重命名或无后缀映射] | — |
| Decal_Pavement_Sidewalk10_square 1.prefab | [未重命名或无后缀映射] | — |
| Decal_Pavement_Sidewalk10_square.prefab | [未重命名或无后缀映射] | — |
| Decal_Pavement_Sidewalk5.prefab | [未重命名或无后缀映射] | — |
| Decal_PebblesRiver1.prefab | [未重命名或无后缀映射] | — |
| Decal_RoadGround.prefab | [未重命名或无后缀映射] | — |
| Decal_RoadsDirt0047-5.prefab | [未重命名或无后缀映射] | — |
| Decal_RoadsDirt0047.prefab | [未重命名或无后缀映射] | — |
| Decal_RoadsDirt0055_1.prefab | [未重命名或无后缀映射] | — |
| Decal_RoadsDirt0067-70.prefab | [未重命名或无后缀映射] | — |
| Decal_RoadsDirt0067-X.prefab | [未重命名或无后缀映射] | — |
| Decal_RockGround02.prefab | [未重命名或无后缀映射] | — |
| Decal_RockMossy.prefab | [未重命名或无后缀映射] | — |
| Decal_RocksGround01.prefab | [未重命名或无后缀映射] | — |
| Decal_Soil11.prefab | [未重命名或无后缀映射] | — |
| Decal_Soil12.prefab | [未重命名或无后缀映射] | — |
| Decal_SoilMud0058.prefab | [未重命名或无后缀映射] | — |
| Decal_SoilMud0058_W20xH8.prefab | [未重命名或无后缀映射] | — |
| Decal_SoilMudW30H10.prefab | [未重命名或无后缀映射] | — |
| Decal_SoilMud_W20H5.prefab | [未重命名或无后缀映射] | — |
| Decal_SoilMud_W50H12.prefab | [未重命名或无后缀映射] | — |
| Decal_SoilTiremarks.prefab | [未重命名或无后缀映射] | — |
| Decal_Soilrocky1A.prefab | [未重命名或无后缀映射] | — |
| Decal_Soilrocky2C.prefab | [未重命名或无后缀映射] | — |
| Decal_Stain0094_2.prefab | [未重命名或无后缀映射] | — |
| Decal_Stain0094_2_2.prefab | [未重命名或无后缀映射] | — |
| Decal_Stain01_20.prefab | [未重命名或无后缀映射] | — |
| Decal_Stain01_30.prefab | [未重命名或无后缀映射] | — |
| Decal_Stain01_40.prefab | [未重命名或无后缀映射] | — |
| Decal_Stain02_10m-35.prefab | [未重命名或无后缀映射] | — |
| Decal_Stain02_10m_35.prefab | [未重命名或无后缀映射] | — |
| Decal_Stain02_20m-35.prefab | [未重命名或无后缀映射] | — |
| Decal_Stain02_50m-15.prefab | [未重命名或无后缀映射] | — |
| Decal_Stain02_50m-25.prefab | [未重命名或无后缀映射] | — |
| Decal_Stain02_50m-35.prefab | [未重命名或无后缀映射] | — |
| Decal_Stain02_50m_25.prefab | [未重命名或无后缀映射] | — |
| Decal_Stain03-10m-50.prefab | [未重命名或无后缀映射] | — |
| Decal_Stain03-50m-30.prefab | [未重命名或无后缀映射] | — |
| Decal_Stain03_10m_30.prefab | [未重命名或无后缀映射] | — |
| Decal_Stain03_50m_30.prefab | [未重命名或无后缀映射] | — |
| Decal_SticksAndStones.prefab | [未重命名或无后缀映射] | — |
| Decal_Tracks_Type-01_01T.prefab | [未重命名或无后缀映射] | — |
| Decal_Tracks_Type-01_03.prefab | [未重命名或无后缀映射] | — |
| Decal_Tracks_Type-01_04.prefab | [未重命名或无后缀映射] | — |
| Decal_TreeRootsPine.prefab | [未重命名或无后缀映射] | — |
| Decal_TreeRootsPine_Ground.prefab | [未重命名或无后缀映射] | — |
| Decal_TwigsAndBranches_30.prefab | [未重命名或无后缀映射] | — |
| Decal_TwigsAndBranches_60.prefab | [未重命名或无后缀映射] | — |
| Decal_TwigsAndBranches_80.prefab | [未重命名或无后缀映射] | — |
| Decal_Water_Type-01_02.prefab | [未重命名或无后缀映射] | — |
| Decal_Water_Type-01_03.prefab | [未重命名或无后缀映射] | — |
| Decal_Water_Type-01_04.prefab | [未重命名或无后缀映射] | — |
| Decal_leavesAndFruit.prefab | [未重命名或无后缀映射] | — |
| Decal_leaves_Green.prefab | [未重命名或无后缀映射] | — |
| Decal_leaves_yellow.prefab | [未重命名或无后缀映射] | — |
| Pavement_Sidewalk10_W22H22.prefab | [未重命名或无后缀映射] | — |
| Mat_Decal_Water_Type-01_02.mat | [未重命名或无后缀映射] | — |
| Water_Type-01_02_Col.png | Water_Type-01_02_Albedo.png | _BaseColor, _BaseCol |
| Water_Type-01_02_Mask.png | Water_Type-01_02_MaskMap.png | _M |
| Water_Type-01_02_N.png | Water_Type-01_02_Normal.png | _NM, _NRM |
| Mat_Decal_Water_Type-01_03.mat | [未重命名或无后缀映射] | — |
| Water_Type-01_03_Col.png | Water_Type-01_03_Albedo.png | _BaseColor, _BaseCol |
| Water_Type-01_03_Mask.png | Water_Type-01_03_MaskMap.png | _M |
| Water_Type-01_03_N.png | Water_Type-01_03_Normal.png | _NM, _NRM |
| Mat_Decal_Water_Type-01_04.mat | [未重命名或无后缀映射] | — |
| Water_Type-01_04_Col.png | Water_Type-01_04_Albedo.png | _BaseColor, _BaseCol |
| Water_Type-01_04_Mask.png | Water_Type-01_04_MaskMap.png | _M |
| Water_Type-01_04_N.png | Water_Type-01_04_Normal.png | _NM, _NRM |
| Decal_Rail_Ground.prefab | [未重命名或无后缀映射] | — |
| Mat_Decal_AirField.mat | [未重命名或无后缀映射] | — |
| Roads0069_1DA.tif | [未重命名或无后缀映射] | — |
| Roads0069_1N.tif | [未重命名或无后缀映射] | — |
| Roads0069_1RMask1.png | [未重命名或无后缀映射] | — |
| TexturesCom_Roads0069_1_seamless_H.bmp | TexturesCom_Roads0069_1_seamless_Height.bmp | _Hight |
| Dirt_path_swamp_grass.tga | [未重命名或无后缀映射] | — |
| Dirt_path_swamp_grass_NM.tga | [未重命名或无后缀映射] | — |
| Dirt_path_swamp_grass_v1.tga | [未重命名或无后缀映射] | — |
| Mat_Decal_Dirt_Grass.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_RoadGrass0016.mat | [未重命名或无后缀映射] | — |
| RoadsDirt0016_1M_A.tif | [未重命名或无后缀映射] | — |
| RoadsDirt0016_1M_G.tif | [未重命名或无后缀映射] | — |
| RoadsDirt0016_1M_GMask1.png | [未重命名或无后缀映射] | — |
| RoadsDirt0016_1M_H.tiff | RoadsDirt0016_1M_Height.tiff | _Hight |
| RoadsDirt0016_1M_N.tif | RoadsDirt0016_1M_Normal.tif | _NM, _NRM |
| TexturesCom_RoadsDirt0016_1_seamless_M_AO.bmp | [未重命名或无后缀映射] | — |
| Dirt_path_swamp_transition.tga | [未重命名或无后缀映射] | — |
| Dirt_path_swamp_transition_NM.tga | [未重命名或无后缀映射] | — |
| Mat_Decal_Dirt_swamp_transition.mat | [未重命名或无后缀映射] | — |
| Dirt_gravel.tif | [未重命名或无后缀映射] | — |
| Dirt_gravel_Normal.tif | [未重命名或无后缀映射] | — |
| Dirt_gravel_Start.tif | [未重命名或无后缀映射] | — |
| Dirt_gravel_Y__Albedo2.tif | [未重命名或无后缀映射] | — |
| Dirt_gravel_Y__Mask.tif | Dirt_gravel_Y__MaskMap.tif | _M |
| Dirt_gravel_Y__N.tga | Dirt_gravel_Y__Normal.tga | _NM, _NRM |
| Dirt_gravel_aoMask.tif | [未重命名或无后缀映射] | — |
| Mat_Decal_Dirt_Gravel_start.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_Dirt_gravel.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_Dirt_gravel_Y_crossing.mat | [未重命名或无后缀映射] | — |
| Road_Gravel_3x3_AlbedoA2.tif | [未重命名或无后缀映射] | — |
| Decal_Road_DirtEND.prefab | [未重命名或无后缀映射] | — |
| Dirt_flat.tif | [未重命名或无后缀映射] | — |
| Dirt_flat_Alpha02.tif | [未重命名或无后缀映射] | — |
| Dirt_flat_Alpha03.tif | [未重命名或无后缀映射] | — |
| Dirt_flat_Alpha04.tif | [未重命名或无后缀映射] | — |
| Dirt_flat_End.tif | [未重命名或无后缀映射] | — |
| Dirt_flat_MS.tif | [未重命名或无后缀映射] | — |
| Dirt_flat_Y_Crossing.tga | [未重命名或无后缀映射] | — |
| Dirt_flat_start.tif | [未重命名或无后缀映射] | — |
| Dirt_flat_start_8m.tif | [未重命名或无后缀映射] | — |
| Mat_Dirt_flat.mat | [未重命名或无后缀映射] | — |
| Mat_Dirt_flat_1.mat | [未重命名或无后缀映射] | — |
| Mat_Dirt_flat_End.mat | [未重命名或无后缀映射] | — |
| Mat_Dirt_flat_Y_Crossing.mat | [未重命名或无后缀映射] | — |
| Mat_Dirt_flat_crossing.mat | [未重命名或无后缀映射] | — |
| Mat_Dirt_flat_start.mat | [未重命名或无后缀映射] | — |
| Dirt_path_swamp.tga | [未重命名或无后缀映射] | — |
| Dirt_path_swamp_NM.tga | [未重命名或无后缀映射] | — |
| Mat_Dirt_swamp.mat | [未重命名或无后缀映射] | — |
| Mat_MuddyDirtRoad.mat | [未重命名或无后缀映射] | — |
| MuddyDirtRoad_BasecolorAlpha.png | [未重命名或无后缀映射] | — |
| MuddyDirtRoad_Gloss.tif | MuddyDirtRoad_Glossiness.tif | — |
| MuddyDirtRoad_N.png | MuddyDirtRoad_Normal.png | _NM, _NRM |
| MuddyDirtRoad_metallic.png | [未重命名或无后缀映射] | — |
| Mat_Path_Double_Rock.mat | [未重命名或无后缀映射] | — |
| RoadsDirt0031_1_L.tif | [未重命名或无后缀映射] | — |
| RoadsDirt0031_1_L_GMask1.png | [未重命名或无后缀映射] | — |
| RoadsDirt0031_1_L_N.tif | RoadsDirt0031_1_L_Normal.tif | _NM, _NRM |
| TexturesCom_RoadsDirt0031_1_L_H.bmp | TexturesCom_RoadsDirt0031_1_L_Height.bmp | _Hight |
| Mat_M_Path_Double.mat | [未重命名或无后缀映射] | — |
| T_Ground_Meadow_Road_01_A_Mask.tga | T_Ground_Meadow_Road_01_A_MaskMap.tga | _M |
| T_ground_meadow_road_01_AO_H_SM.tga | [未重命名或无后缀映射] | — |
| T_ground_meadow_road_01_H.png | T_ground_meadow_road_01_Height.png | _Hight |
| T_ground_meadow_road_01_N.png | T_ground_meadow_road_01_Normal.png | _NM, _NRM |
| Mat_M_Path_single.mat | [未重命名或无后缀映射] | — |
| T_Ground_Meadow_Road_02_A_Mask.tga | T_Ground_Meadow_Road_02_A_MaskMap.tga | _M |
| T_ground_meadow_road_02_AO_H_SM.tga | [未重命名或无后缀映射] | — |
| T_ground_meadow_road_02_H.png | T_ground_meadow_road_02_Height.png | _Hight |
| T_ground_meadow_road_02_N.png | T_ground_meadow_road_02_Normal.png | _NM, _NRM |
| Mat_Pavement_ConcretePlates4.mat | [未重命名或无后缀映射] | — |
| Pavement_ConcretePlates4_4.8x6_Col.tif | Pavement_ConcretePlates4_4.8x6_Albedo.tif | _BaseColor, _BaseCol |
| Pavement_ConcretePlates4_4.8x6_N.tif | Pavement_ConcretePlates4_4.8x6_Normal.tif | _NM, _NRM |
| Pavement_ConcretePlates4_4.8x6_RoughnessMask1.png | [未重命名或无后缀映射] | — |
| Mat_Pavement_Forest.mat | [未重命名或无后缀映射] | — |
| Pavement_CobblestoneForest6_2x2_AlbedoA.tif | [未重命名或无后缀映射] | — |
| Pavement_CobblestoneForest6_2x2_H.tif | Pavement_CobblestoneForest6_2x2_Height.tif | _Hight |
| Pavement_CobblestoneForest6_2x2_Mask.png | Pavement_CobblestoneForest6_2x2_MaskMap.png | _M |
| Pavement_CobblestoneForest6_2x2_N.tif | Pavement_CobblestoneForest6_2x2_Normal.tif | _NM, _NRM |
| Mat_TexturesCom_Pavement_Road01.mat | [未重命名或无后缀映射] | — |
| Road_Col.jpg | Road_Albedo.jpg | _BaseColor, _BaseCol |
| road_H.jpg | road_Height.jpg | _Hight |
| road_Mask.png | road_MaskMap.png | _M |
| road_N.jpg | road_Normal.jpg | _NM, _NRM |
| Mat_Pavement_Street_DO1.mat | [未重命名或无后缀映射] | — |
| Mat_Pavement_Street_DO2.mat | [未重命名或无后缀映射] | — |
| Pavement_CobblestoneStreet4_3x3_AlbedoA.tif | [未重命名或无后缀映射] | — |
| Pavement_CobblestoneStreet4_3x3_Col.tif | Pavement_CobblestoneStreet4_3x3_Albedo.tif | _BaseColor, _BaseCol |
| Pavement_CobblestoneStreet4_3x3_H.tif | Pavement_CobblestoneStreet4_3x3_Height.tif | _Hight |
| Pavement_CobblestoneStreet4_3x3_N.tif | Pavement_CobblestoneStreet4_3x3_Normal.tif | _NM, _NRM |
| Pavement_CobblestoneStreet4_3x3_RoughnessMask6.png | [未重命名或无后缀映射] | — |
| Mat_Pavement_Street02.mat | [未重命名或无后缀映射] | — |
| Mat_Pavement_Street02_T_Crossing.mat | [未重命名或无后缀映射] | — |
| Street_H.tga | Street_Height.tga | _Hight |
| Street_N.tga | Street_Normal.tga | _NM, _NRM |
| Street_albedo2.tif | [未重命名或无后缀映射] | — |
| Street_mask.tif | [未重命名或无后缀映射] | — |
| CTL_Pavement_Wave.terrainlayer | [未重命名或无后缀映射] | — |
| Mat_Pavement_Wave.mat | [未重命名或无后缀映射] | — |
| Pavement_CobblestoneWave_1x1_Col.tif | Pavement_CobblestoneWave_1x1_Albedo.tif | _BaseColor, _BaseCol |
| Pavement_CobblestoneWave_1x1_H.tif | Pavement_CobblestoneWave_1x1_Height.tif | _Hight |
| Pavement_CobblestoneWave_1x1_N.tif | Pavement_CobblestoneWave_1x1_Normal.tif | _NM, _NRM |
| Pavement_CobblestoneWave_1x1_RoughnessMask9.png | [未重命名或无后缀映射] | — |
| Mat_Pavement_Wave02.mat | [未重命名或无后缀映射] | — |
| Wave_Col.tif | Wave_Albedo.tif | _BaseColor, _BaseCol |
| Wave_H.tif | Wave_Height.tif | _Hight |
| Wave_N.tif | Wave_Normal.tif | _NM, _NRM |
| wave_mask.tif | [未重命名或无后缀映射] | — |
| Mat_TexturesCom_Pavement_Road02.mat | [未重命名或无后缀映射] | — |
| Road02_Default_Col.jpg | Road02_Default_Albedo.jpg | _BaseColor, _BaseCol |
| Road02_Default_N.jpg | Road02_Default_Normal.jpg | _NM, _NRM |
| road02_Default_H.jpg | road02_Default_Height.jpg | _Hight |
| road02_Default_roughnessMask12.png | [未重命名或无后缀映射] | — |
| CTL_Pebbles_C.terrainlayer | [未重命名或无后缀映射] | — |
| Pebbles_C_Col.tif | Pebbles_C_Albedo.tif | _BaseColor, _BaseCol |
| Pebbles_C_Mask.tif | Pebbles_C_MaskMap.tif | _M |
| Pebbles_C_N.tif | Pebbles_C_Normal.tif | _NM, _NRM |
| Mat_Primary_Road.mat | [未重命名或无后缀映射] | — |
| Primary_Road_C.tga | [未重命名或无后缀映射] | — |
| Primary_Road_C2.tga | [未重命名或无后缀映射] | — |
| Primary_Road_N.tga | Primary_Road_Normal.tga | _NM, _NRM |
| Primary_Road_Start_C.tif | [未重命名或无后缀映射] | — |
| Mat_Decal_Primary_Road_Old.mat | [未重命名或无后缀映射] | — |
| Mat_Primary_Road_old.mat | [未重命名或无后缀映射] | — |
| Decal_Primary Road Old.prefab | [未重命名或无后缀映射] | — |
| RoadAsphaltWorn008_COL_VAR3_1.tif | [未重命名或无后缀映射] | — |
| RoadAsphaltWorn008_GLOSSMask1.png | [未重命名或无后缀映射] | — |
| RoadAsphaltWorn008_NRM.jpg | [未重命名或无后缀映射] | — |
| Road_OLD_Decal_Mask1.png | [未重命名或无后缀映射] | — |
| Road_OLD_Decal_N.jpg | Road_OLD_Decal_Normal.jpg | _NM, _NRM |
| Road_Old_Decal_COL.tif | [未重命名或无后缀映射] | — |
| Mat_Rail_Ground.mat | [未重命名或无后缀映射] | — |
| Mat_Rail_Ground_Decal.mat | [未重命名或无后缀映射] | — |
| Rail_Ground_AO.tif | [未重命名或无后缀映射] | — |
| Rail_ground_Decal.tif | [未重命名或无后缀映射] | — |
| Rail_ground_NM.tif | [未重命名或无后缀映射] | — |
| Rail_ground_TGA.tga | [未重命名或无后缀映射] | — |
| CiffTest_AO.tif | [未重命名或无后缀映射] | — |
| CiffTest_BaseColorAlpha_.tif | [未重命名或无后缀映射] | — |
| CiffTest_H.tif | CiffTest_Height.tif | _Hight |
| CiffTest_Mask.png | CiffTest_MaskMap.png | _M |
| CiffTest_N.tif | CiffTest_Normal.tif | _NM, _NRM |
| CiffTest_Rough.tif | CiffTest_Roughness.tif | — |
| Mat_CiffTest.mat | [未重命名或无后缀映射] | — |
| Mat_RoadEdge01.mat | [未重命名或无后缀映射] | — |
| SoilCliff0002_A.tif | [未重命名或无后缀映射] | — |
| SoilCliff0002_Mask.png | SoilCliff0002_MaskMap.png | _M |
| SoilCliff0002_N.tif | SoilCliff0002_Normal.tif | _NM, _NRM |
| Mat_RoadEdge0128.mat | [未重命名或无后缀映射] | — |
| Roads0128_1L.tif | [未重命名或无后缀映射] | — |
| Roads0128_1LAOMask1.png | [未重命名或无后缀映射] | — |
| Roads0128_1LN.tif | [未重命名或无后缀映射] | — |
| TexturesCom_Roads0128_1_seamless_LH.bmp | [未重命名或无后缀映射] | — |
| Mat_RockGround02.mat | [未重命名或无后缀映射] | — |
| RockGround02_A.tif | [未重命名或无后缀映射] | — |
| RockGround02_Mask2.png | [未重命名或无后缀映射] | — |
| RockGround02_N.tif | RockGround02_Normal.tif | _NM, _NRM |
| Mat_Rock_Ground03.mat | [未重命名或无后缀映射] | — |
| RockGround03_A.tif | [未重命名或无后缀映射] | — |
| RockGround03_Mask.png | RockGround03_MaskMap.png | _M |
| RockGround03_N.tif | RockGround03_Normal.tif | _NM, _NRM |
| CTL_GrassDry_Rocks.terrainlayer | [未重命名或无后缀映射] | — |
| Soil_Rocks_Col.tif | Soil_Rocks_Albedo.tif | _BaseColor, _BaseCol |
| Soil_Rocks_Mask.tif | Soil_Rocks_MaskMap.tif | _M |
| Soil_Rocks_N.tif | Soil_Rocks_Normal.tif | _NM, _NRM |
| Mat_MuddyDirtRoad_3x3_RoadAlpha_lit.mat | [未重命名或无后缀映射] | — |
| MuddyDirtRoad_BasecolorAlpha2.png | [未重命名或无后缀映射] | — |
| MuddyDirtRoad_Mask.png | MuddyDirtRoad_MaskMap.png | _M |
| MuddyDirtRoad_N.png | MuddyDirtRoad_Normal.png | _NM, _NRM |
| Track_ruts_02_3mx3m_AO2.tif | [未重命名或无后缀映射] | — |
| Track_ruts_02_3mx3m_Metallic2.tif | [未重命名或无后缀映射] | — |
| Track_ruts_02_3mx3m_Roughness2.tif | [未重命名或无后缀映射] | — |
| Track_ruts_02_3mx3m_Roughness2Mask1Mask1.png | [未重命名或无后缀映射] | — |
| Mat_train_rail.mat | [未重命名或无后缀映射] | — |
| rail.jpg | [未重命名或无后缀映射] | — |
| Mat_TyrePrint01.mat | [未重命名或无后缀映射] | — |
| Mat_TyrePrint01End.mat | [未重命名或无后缀映射] | — |
| Mat_TyrePrint01Start.mat | [未重命名或无后缀映射] | — |
| Road_Dirt2_4x4_Albedo3.tif | [未重命名或无后缀映射] | — |
| Road_Dirt2_4x4_Albedo3A.tif | [未重命名或无后缀映射] | — |
| Road_Dirt2_4x4_Albedo3B.tif | [未重命名或无后缀映射] | — |
| Road_Dirt2_4x4_Albedo3_N_1.tif | [未重命名或无后缀映射] | — |
| Mat_TyrePrint02_SoilBeach.mat | [未重命名或无后缀映射] | — |
| SoilBeach0019_1N.tif | [未重命名或无后缀映射] | — |
| SoilBeach0019_1SA_1.tif | [未重命名或无后缀映射] | — |
| Mat_TyrePrint03_Track.mat | [未重命名或无后缀映射] | — |
| RoadsDirt0005_1MA_1.tif | [未重命名或无后缀映射] | — |
| TexturesCom_RoadsDirt0005_1_seamless_N.bmp | TexturesCom_RoadsDirt0005_1_seamless_Normal.bmp | _NM, _NRM |
| Mat_aerial_mud_1.mat | [未重命名或无后缀映射] | — |
| Mat_aerial_mud_1_end.mat | [未重命名或无后缀映射] | — |
| Mat_aerial_mud_1_start.mat | [未重命名或无后缀映射] | — |
| aerial_mud_1_Mask_4k.tif | [未重命名或无后缀映射] | — |
| aerial_mud_1_N_4k.tif | [未重命名或无后缀映射] | — |
| aerial_mud_1_diff3_4k.tif | [未重命名或无后缀映射] | — |
| aerial_mud_1_diff_down_4k.tif | [未重命名或无后缀映射] | — |
| aerial_mud_1_diff_up_4k.tif | [未重命名或无后缀映射] | — |
| Mat_Tyre_Tracks_Dry.mat | [未重命名或无后缀映射] | — |
| Tire_tracks_C.tif | [未重命名或无后缀映射] | — |
| Tire_tracks_Mask.png | Tire_tracks_MaskMap.png | _M |
| Tire_tracks_N.jpg | Tire_tracks_Normal.jpg | _NM, _NRM |
| Ground_SandTireTrack_B_2x1_AlbedoA.tif | [未重命名或无后缀映射] | — |
| Ground_SandTireTrack_B_2x1_AlbedoA2.tif | [未重命名或无后缀映射] | — |
| Ground_SandTireTrack_B_2x1_Height2.tif | [未重命名或无后缀映射] | — |
| Ground_SandTireTrack_B_2x1_Normal2.tif | [未重命名或无后缀映射] | — |
| Ground_SandTireTrack_B_2x1_Roughness2Mask2.png | [未重命名或无后缀映射] | — |
| Mat_SandTireTrack_B.mat | [未重命名或无后缀映射] | — |
| GroundTireTracksWet002_COL01A_3K.tif | [未重命名或无后缀映射] | — |
| GroundTireTracksWet002_COL202A_3K.tif | [未重命名或无后缀映射] | — |
| GroundTireTracksWet002_COL2A_3K.tif | [未重命名或无后缀映射] | — |
| GroundTireTracksWet002_DISP01_3K.tif | [未重命名或无后缀映射] | — |
| GroundTireTracksWet002_DISP02_3K.tif | [未重命名或无后缀映射] | — |
| GroundTireTracksWet002_DISP2_3K.jpg | [未重命名或无后缀映射] | — |
| GroundTireTracksWet002_GLOSS_3KMask21.png | [未重命名或无后缀映射] | — |
| GroundTireTracksWet002_Mask02.png | [未重命名或无后缀映射] | — |
| GroundTireTracksWet002_N01.jpg | [未重命名或无后缀映射] | — |
| GroundTireTracksWet002_N02.tif | [未重命名或无后缀映射] | — |
| GroundTireTracksWet002_NRM_3K.jpg | [未重命名或无后缀映射] | — |
| GroundTireTracksWet002_mask01.png | [未重命名或无后缀映射] | — |
| Mat_GroundTireTracksWet002.mat | [未重命名或无后缀映射] | — |
| Mat_GroundTireTracksWet002_01.mat | [未重命名或无后缀映射] | — |
| Mat_GroundTireTracksWet002_02.mat | [未重命名或无后缀映射] | — |
| Mat_Pathway.mat | [未重命名或无后缀映射] | — |
| Pathway_Col.tif | Pathway_Albedo.tif | _BaseColor, _BaseCol |
| Pathway_N.tif | Pathway_Normal.tif | _NM, _NRM |
| pathway_Mask.png | pathway_MaskMap.png | _M |
| CiffTestDecalA_W6H12.prefab | [未重命名或无后缀映射] | — |
| CiffTestDecalB_W6H12.prefab | [未重命名或无后缀映射] | — |
| CiffTestDecalB_W6H12_Test.prefab | [未重命名或无后缀映射] | — |
| CiffTestDecalC_W6H12.prefab | [未重命名或无后缀映射] | — |
| CiffTestDecalD_W6H24.prefab | [未重命名或无后缀映射] | — |
| Mat_Decal_RoadEdge_01_A.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_RoadEdge_01_B.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_RoadEdge_01_C.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_RoadEdge_01_D.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_RoadEdge_01_EasyRoaed.mat | [未重命名或无后缀映射] | — |
| RoadEdge_01_A_Col.tif | RoadEdge_01_A_Albedo.tif | _BaseColor, _BaseCol |
| RoadEdge_01_A_Mask.png | RoadEdge_01_A_MaskMap.png | _M |
| RoadEdge_01_A_N.tif | RoadEdge_01_A_Normal.tif | _NM, _NRM |
| RoadEdge_01_B_ColorA.tif | [未重命名或无后缀映射] | — |
| RoadEdge_01_B_Mask.png | RoadEdge_01_B_MaskMap.png | _M |
| RoadEdge_01_B_N.tif | RoadEdge_01_B_Normal.tif | _NM, _NRM |
| RoadEdge_01_C_ColorA.tif | [未重命名或无后缀映射] | — |
| RoadEdge_01_C_Mask.png | RoadEdge_01_C_MaskMap.png | _M |
| RoadEdge_01_C_N.tif | RoadEdge_01_C_Normal.tif | _NM, _NRM |
| RoadEdge_01_D_ColorA.tif | [未重命名或无后缀映射] | — |
| RoadEdge_01_D_ColorA_EasyRoad.tif | [未重命名或无后缀映射] | — |
| RoadEdge_01_D_Mask.png | RoadEdge_01_D_MaskMap.png | _M |
| RoadEdge_01_D_N.tif | RoadEdge_01_D_Normal.tif | _NM, _NRM |
| RoadEdge_01_Mask.png | RoadEdge_01_MaskMap.png | _M |
| RoadEdge_01_N.tif | RoadEdge_01_Normal.tif | _NM, _NRM |
| txt.txt | [未重命名或无后缀映射] | — |
| CTL_Rock_01.terrainlayer | [未重命名或无后缀映射] | — |
| Rock_01_Col.tif | Rock_01_Albedo.tif | _BaseColor, _BaseCol |
| Rock_01_Mask.tif | Rock_01_MaskMap.tif | _M |
| Rock_01_N.tif | Rock_01_Normal.tif | _NM, _NRM |
| tex.txt | [未重命名或无后缀映射] | — |
| CTL_Rock_02.terrainlayer | [未重命名或无后缀映射] | — |
| Rock_02_Col.tif | Rock_02_Albedo.tif | _BaseColor, _BaseCol |
| Rock_02_Mask.png | Rock_02_MaskMap.png | _M |
| Rock_02_N.tif | Rock_02_Normal.tif | _NM, _NRM |
| tex.txt | [未重命名或无后缀映射] | — |
| Rock_03_Col.tif | Rock_03_Albedo.tif | _BaseColor, _BaseCol |
| Rock_03_Mask.png | Rock_03_MaskMap.png | _M |
| Rock_03_N.tif | Rock_03_Normal.tif | _NM, _NRM |
| txt.txt | [未重命名或无后缀映射] | — |
| Rock_04_Col.png | Rock_04_Albedo.png | _BaseColor, _BaseCol |
| Rock_04_Mask.png | Rock_04_MaskMap.png | _M |
| Rock_04_N.png | Rock_04_Normal.png | _NM, _NRM |
| CTL_Sand_01.terrainlayer | [未重命名或无后缀映射] | — |
| Sand_01_Col.tif | Sand_01_Albedo.tif | _BaseColor, _BaseCol |
| Sand_01_Mask.tif | Sand_01_MaskMap.tif | _M |
| Sand_01_N.tif | Sand_01_Normal.tif | _NM, _NRM |
| CTL_Sand_02.terrainlayer | [未重命名或无后缀映射] | — |
| Sand_02_Col.tif | Sand_02_Albedo.tif | _BaseColor, _BaseCol |
| Sand_02_Mask.tif | Sand_02_MaskMap.tif | _M |
| Sand_02_N.tif | Sand_02_Normal.tif | _NM, _NRM |
| CTL_Sand_03.terrainlayer | [未重命名或无后缀映射] | — |
| Sand_03_Col.tif | Sand_03_Albedo.tif | _BaseColor, _BaseCol |
| Sand_03_Mask.tif | Sand_03_MaskMap.tif | _M |
| Sand_03_N.tif | Sand_03_Normal.tif | _NM, _NRM |
| CTL_Snow_01.terrainlayer | [未重命名或无后缀映射] | — |
| Snow_01_Col.tif | Snow_01_Albedo.tif | _BaseColor, _BaseCol |
| Snow_01_Mask.tif | Snow_01_MaskMap.tif | _M |
| Snow_01_N.tif | Snow_01_Normal.tif | _NM, _NRM |
| CTL_Snow_02.terrainlayer | [未重命名或无后缀映射] | — |
| Snow_02_Col.tif | Snow_02_Albedo.tif | _BaseColor, _BaseCol |
| Snow_02_Mask.tif | Snow_02_MaskMap.tif | _M |
| Snow_02_N.tif | Snow_02_Normal.tif | _NM, _NRM |
| CTL_Snow_03.terrainlayer | [未重命名或无后缀映射] | — |
| Snow_03_Col.tif | Snow_03_Albedo.tif | _BaseColor, _BaseCol |
| Snow_03_Mask.tif | Snow_03_MaskMap.tif | _M |
| Snow_03_N.tif | Snow_03_Normal.tif | _NM, _NRM |
| Mat_Decal_Stain_01.mat | [未重命名或无后缀映射] | — |
| Stain_01_col.png | [未重命名或无后缀映射] | — |
| txt.txt | [未重命名或无后缀映射] | — |
| Mat_Decal_Stain_02_20.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_Stain_02_30.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_Stain_02_40.mat | [未重命名或无后缀映射] | — |
| Stain_02_col.png | [未重命名或无后缀映射] | — |
| txt.txt | [未重命名或无后缀映射] | — |
| Mat_Decal_Stain_03_15.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_Stain_03_25.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_Stain_03_30.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_Stain_03_35.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_Stain_03_70.mat | [未重命名或无后缀映射] | — |
| Stain_03_col.png | [未重命名或无后缀映射] | — |
| txt.txt | [未重命名或无后缀映射] | — |
| Mat_Decal_Stain_04_30.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_Stain_04_50.mat | [未重命名或无后缀映射] | — |
| Stain_04_col.tif | [未重命名或无后缀映射] | — |
| txt.txt | [未重命名或无后缀映射] | — |
| Mat_Stone_Trim.mat | [未重命名或无后缀映射] | — |
| Stone_Trim_Col.png | Stone_Trim_Albedo.png | _BaseColor, _BaseCol |
| Stone_Trim_Mask.png | Stone_Trim_MaskMap.png | _M |
| Stone_Trim_N.png | Stone_Trim_Normal.png | _NM, _NRM |
| Mat_Decal_Road_Tracks_01.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_Road_Tracks_01_40.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_Road_Tracks_01_60.mat | [未重命名或无后缀映射] | — |
| Road_Dirt2_4x4_Albedo4_N.tif | Road_Dirt2_4x4_Albedo4_Normal.tif | _NM, _NRM |
| Road_Tracks_01_Mask.png | Road_Tracks_01_MaskMap.png | _M |
| Road_Tracks_01_albedo6.tif | [未重命名或无后缀映射] | — |
| txt.txt | [未重命名或无后缀映射] | — |
| Mat_Decal_Tracks_01.mat | [未重命名或无后缀映射] | — |
| Tracks_01_A.png | [未重命名或无后缀映射] | — |
| Tracks_01_N.png | Tracks_01_Normal.png | _NM, _NRM |
| Mat_Decal_Tracks_03.mat | [未重命名或无后缀映射] | — |
| Tracks_03_A.png | [未重命名或无后缀映射] | — |
| Tracks_03_N.png | Tracks_03_Normal.png | _NM, _NRM |
| Mat_Decal_Tracks_04.mat | [未重命名或无后缀映射] | — |
| Tracks_04_A.png | [未重命名或无后缀映射] | — |
| Tracks_04_N.png | Tracks_04_Normal.png | _NM, _NRM |
| Mat_Decal_Tracks_05.mat | [未重命名或无后缀映射] | — |
| Tracks_05_Mask.png | Tracks_05_MaskMap.png | _M |
| Tracks_05_N.tif | Tracks_05_Normal.tif | _NM, _NRM |
| Tracks_05_cor.tif | [未重命名或无后缀映射] | — |
| txt.txt | [未重命名或无后缀映射] | — |
| Mat_Decal_Tracks_06.mat | [未重命名或无后缀映射] | — |
| Tracks_06_A.tif | [未重命名或无后缀映射] | — |
| Tracks_06_Mask.png | Tracks_06_MaskMap.png | _M |
| Tracks_06_N.tif | Tracks_06_Normal.tif | _NM, _NRM |
| txt.txt | [未重命名或无后缀映射] | — |
| Mat_Decal_Tracks_07-100.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_Tracks_07-50.mat | [未重命名或无后缀映射] | — |
| Mat_Decal_Tracks_07-70.mat | [未重命名或无后缀映射] | — |
| Tracks_07_A.tif | [未重命名或无后缀映射] | — |
| Tracks_07_Mask.png | Tracks_07_MaskMap.png | _M |
| Tracks_07_N.tif | Tracks_07_Normal.tif | _NM, _NRM |
| txt.txt | [未重命名或无后缀映射] | — |
| Mat_Decal_Tracks_08.mat | [未重命名或无后缀映射] | — |
| Tracks_08_Col.tif | Tracks_08_Albedo.tif | _BaseColor, _BaseCol |
| Tracks_08_N.tif | Tracks_08_Normal.tif | _NM, _NRM |
| txt.txt | [未重命名或无后缀映射] | — |
| rename_log.txt | [未重命名或无后缀映射] | — |

