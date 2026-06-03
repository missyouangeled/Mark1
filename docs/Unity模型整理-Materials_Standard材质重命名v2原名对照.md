# Materials_Standard 材质重命名原名对照 v2

> 生成时间：2026-06-03  
> 规范版本：2026-06-03 更新版  
> 重命名脚本：scripts/rename-materials.py  
> 目录：Materials_Standard/

## 统计

| 类型 | 数量 |
|------|------|
| 贴图 .exr | 3 |
| 贴图 .jpg | 48 |
| 贴图 .png | 87 |
| 贴图 .psd | 1 |
| 贴图 .tga | 7 |
| 贴图 .tif | 121 |
| **合计** | **267** |

## 改名规则摘要

| 变更项 | 示例 |
|--------|------|
| 后缀全称化 | `_Col`→`Color`, `_N`→`Normal`, `_H`→`Height`, `_diff`→`Diffuse` |
| Albedo/Diffuse/Color 不互转 | `_Albedo`保持, `_diff`→`Diffuse`, `_Col`→`Color` |
| Mask 统一 | `GLOSSMask2`/`RoughnessMask`/`_SM`/`_MS` → `Mask` |
| Displacement→Height | `_Displacement`/`_disp`→`Height` |
| 倒装 | `castle_wall_slates`→`Wall_Castle_Slate`, `concrete_floor`→`Floor_Concrete` |
| 复合词拆分 | `BronzeOld`→`Bronze_Old`, `ItalianNew`→`Italian_New` |
| 数字补零 | `Bricks03`→`Bricks_03`, `glass1`→`Glass_01` |
| 清除供应商前缀 | `TCom_`/`TexturesCom_` 移除 |
| 清除容量标记 | `_1K`/`_2K`/`_4K`/`_512`/`_1.5x1.5` 移除 |
| # 分隔材质属性 | `#Red`/`#Dark`/`#Light` 保持 |

## 完整对照表

| # | 原名 | → 新名 |
|---|------|--------|
| 1 | mask_Gradient02.tif | Mask_Gradient_02.tif |
| 2 | whiteMask1.png | WhiteMask_01.png |
| 3 | WallBase01_Col.jpg | WallBase_01_Color.jpg |
| 4 | WallBase01_disp.jpg | WallBase_01_Height.jpg |
| 5 | WallBase01_Mask.png | WallBase_01_Mask.png |
| 6 | WallBase01_N.jpg | WallBase_01_Normal.jpg |
| 7 | WallBase02_diff.jpg | WallBase_02_Diffuse.jpg |
| 8 | WallBase02_H.jpg | WallBase_02_Height.jpg |
| 9 | WallBase02_Mask.png | WallBase_02_Mask.png |
| 10 | WallBase02_N.jpg | WallBase_02_Normal.jpg |
| 11 | WallBase03_diff.jpg | WallBase_03_Diffuse.jpg |
| 12 | WallBase03_disp.jpg | WallBase_03_Height.jpg |
| 13 | WallBase03_Mask.png | WallBase_03_Mask.png |
| 14 | WallBase03_N.jpg | WallBase_03_Normal.jpg |
| 15 | Bunding01_col.jpg | Bunding_01_Color.jpg |
| 16 | castle_wall_slates_albedo_2k.jpg | Wall_Castle_Slate_Albedo.jpg |
| 17 | castle_wall_slates_diff_2k.jpg | Wall_Castle_Slate_Diffuse.jpg |
| 18 | castle_wall_slates_nor_2k.jpg | Wall_Castle_Slate_Normal.jpg |
| 19 | castle_wall_slates_rough_2kMask1.png | Wall_Castle_Slate_RoughMask_01.png |
| 20 | Ceiling01_basecolor.png | Ceiling_01_Color.png |
| 21 | Ceiling01_basecolor_grey.png | Ceiling_01_Basecolor_Grey.png |
| 22 | Ceiling01_Mask.png | Ceiling_01_Mask.png |
| 23 | Ceiling01_N.png | Ceiling_01_Normal.png |
| 24 | Ceiling02_basecolor.tif | Ceiling_02_Color.tif |
| 25 | Ceiling02_Mask.tif | Ceiling_02_Mask.tif |
| 26 | Ceiling02_N.tif | Ceiling_02_Normal.tif |
| 27 | Mat_Ceiling03_basecolor.png | Mat_Ceiling_03_Color.png |
| 28 | Mat_Ceiling03_Mask.png | Mat_Ceiling_03_Mask.png |
| 29 | Mat_Ceiling03_N.png | Mat_Ceiling_03_Normal.png |
| 30 | Ceiling04_Col.tif | Ceiling_04_Color.tif |
| 31 | Ceiling04_H.tif | Ceiling_04_Height.tif |
| 32 | Ceiling04_Mask.png | Ceiling_04_Mask.png |
| 33 | Ceiling04_N.tif | Ceiling_04_Normal.tif |
| 34 | Bricks03_GLOSSMask2.png | Bricks_03_Mask.png |
| 35 | Grout_RoughnessMask3.png | Grout_RoughnessMask_03.png |
| 36 | Yancong_N.png | Yancong_Normal.png |
| 37 | yancong_AOC2.png | Yancong_AOC_02.png |
| 38 | Con_Breakage_Col.tga | Con_Breakage_Color.tga |
| 39 | Con_Breakage_N.tga | Con_Breakage_Normal.tga |
| 40 | Con_Cracks_col.png | Con_Cracks_Color.png |
| 41 | Con_Cracks_N.png | Con_Cracks_Normal.png |
| 42 | Decal_Grid01_Col.tif | Decal_Grid_01_Color.tif |
| 43 | Decal_Grid01_Mask.png | Decal_Grid_01_Mask.png |
| 44 | Decal_Grid01_N.tif | Decal_Grid_01_Normal.tif |
| 45 | ConBig_A.tif | ConBig_Albedo.tif |
| 46 | ConBig_N.tif | ConBig_Normal.tif |
| 47 | Con_Plaster_N.png | Con_Plaster_Normal.png |
| 48 | concrete_floor_02_diff_2k.jpg | Floor_Concrete_02_Diffuse.jpg |
| 49 | concrete_floor_02_Nor_2k.jpg | Floor_Concrete_02_Normal.jpg |
| 50 | concrete_floor_02_rough_2kMask2.png | Floor_Concrete_02_RoughMask_02.png |
| 51 | Floor_Col.png | Floor_Color.png |
| 52 | Floor_N.png | Floor_Normal.png |
| 53 | Floor_Old_Col.png | Floor_Old_Color.png |
| 54 | Floor_Old_N.png | Floor_Old_Normal.png |
| 55 | Inside_Painted01_Col.jpg | Inside_Painted_01_Color.jpg |
| 56 | Inside_Painted01_Mask.png | Inside_Painted_01_Mask.png |
| 57 | Inside_Painted01_N.jpg | Inside_Painted_01_Normal.jpg |
| 58 | Inside_Paint02_Col.tif | Inside_Paint_02_Color.tif |
| 59 | Inside_Paint02_Mask.png | Inside_Paint_02_Mask.png |
| 60 | Inside_Paint02_N.tif | Inside_Paint_02_Normal.tif |
| 61 | WallPaper_Green02_Col.jpg | WallPaper_Green_02_Color.jpg |
| 62 | WallPaper_Green02_Mask.png | WallPaper_Green_02_Mask.png |
| 63 | WallPaper_Green02_N.jpg | WallPaper_Green_02_Normal.jpg |
| 64 | Marble_Slab2_Col.tif | Marble_Slab_02_Color.tif |
| 65 | Mat_Metal01_Col.tif | Mat_Metal_01_Color.tif |
| 66 | Mat_Metal01_Mask.png | Mat_Metal_01_Mask.png |
| 67 | Mat_Metal01_N.tif | Mat_Metal_01_Normal.tif |
| 68 | Mat_Metal01_roughness.tif | Mat_Metal_01_Roughness.tif |
| 69 | Metal02_Col.tif | Metal_02_Color.tif |
| 70 | Metal02_mask.tif | Metal_02_Mask.tif |
| 71 | Metal02_N.tif | Metal_02_Normal.tif |
| 72 | Metal_Rust_Col.jpg | Metal_Rust_Color.jpg |
| 73 | Metal_Rust_N.jpg | Metal_Rust_Normal.jpg |
| 74 | Metal_Rust_heavy_Green_col.tif | Metal_Rust_Heavy_Green_Color.tif |
| 75 | Metal_Rust_Heavy_N.tif | Metal_Rust_Heavy_Normal.tif |
| 76 | Metal_Rust_heavy_White_col.tif | Metal_Rust_Heavy_White_Color.tif |
| 77 | X3m_Metal_N.tif | X3m_Metal_Normal.tif |
| 78 | X3m_Metal_N.tif | X3m_Metal_Normal.tif |
| 79 | Bricks050_Col.jpg | Bricks050_Color.jpg |
| 80 | Bricks050_NormalGL.jpg | Bricks050_Normal.jpg |
| 81 | Bricks_Broken02_A.jpg | Bricks_Broken_02_Albedo.jpg |
| 82 | Bricks_Broken02_MS.png | Bricks_Broken_02_Mask.png |
| 83 | Bricks_Broken02_N.jpg | Bricks_Broken_02_Normal.jpg |
| 84 | brick_broken_A.png | Brick_Broken_Albedo.png |
| 85 | brick_broken_N.png | Brick_Broken_Normal.png |
| 86 | DBK_Trim_LayerMASK2.tif | DBK_Trim_LayerMASK_02.tif |
| 87 | DBK_Trim_N.tga | DBK_Trim_Normal.tga |
| 88 | PaintedPlaster014_Col.jpg | PaintedPlaster014_Color.jpg |
| 89 | PaintedPlaster014_Displacement.jpg | PaintedPlaster014_Height.jpg |
| 90 | PaintedPlaster014_NormalGL.jpg | PaintedPlaster014_Normal.jpg |
| 91 | PaintedPlaster014_RoughnessMask4.png | PaintedPlaster014_RoughnessMask_04.png |
| 92 | Line_A.png | Line_Albedo.png |
| 93 | Line_N.png | Line_Normal.png |
| 94 | Line_RMask7.png | Line_RMask_07.png |
| 95 | StripStone_ao2.jpg | StripStone_Ao_02.jpg |
| 96 | StripStone_curveMask1.png | StripStone_CurveMask_01.png |
| 97 | StripStone_curveMask2.png | StripStone_CurveMask_02.png |
| 98 | StripStone_N.jpg | StripStone_Normal.jpg |
| 99 | sandstone_brick_wall_01_diff_4k.jpg | Sandstone_Brick_Wall_01_Diffuse.jpg |
| 100 | sandstone_brick_wall_01_nor_gl_4k.jpg | Sandstone_Brick_Wall_01_Normal.jpg |
| 101 | sandstone_brick_wall_01_rough_4kMask15.png | Sandstone_Brick_Wall_01_RoughMask_15.png |
| 102 | TCom_Pavement_Regular19_1.8x1.6_Col.tif | Pavement_Regular_19_Color.tif |
| 103 | TCom_Pavement_Regular19_1.8x1.6_N.tif | Pavement_Regular_19_Normal.tif |
| 104 | TCom_Pavement_Regular19_1.8x1.6_RoughnessMask1.png | Pavement_Regular_19_RoughnessMask_01.png |
| 105 | TCom_Pavement_Regular23_1.9x1.9_Col.tif | Pavement_Regular_23_Color.tif |
| 106 | TCom_Pavement_Regular23_1.9x1.9_N.tif | Pavement_Regular_23_Normal.tif |
| 107 | TCom_Pavement_Regular23_1.9x1.9_RoughnessMask1.png | Pavement_Regular_23_RoughnessMask_01.png |
| 108 | TCom_Tiles_Floor11_1.8x1.8_Col.tif | Tiles_Floor_11_Color.tif |
| 109 | TCom_Tiles_Floor11_1.8x1.8_N.tif | Tiles_Floor_11_Normal.tif |
| 110 | TCom_Tiles_Floor11_1.8x1.8_RoughnessMask1.png | Tiles_Floor_11_RoughnessMask_01.png |
| 111 | Roofing_AsbestosOndulated_Col.tif | Roofing_AsbestosOndulated_Color.tif |
| 112 | Roofing_AsbestosOndulated_N.tif | Roofing_AsbestosOndulated_Normal.tif |
| 113 | Roofing_AsbestosOndulated_RoughnessMask1.png | Roofing_AsbestosOndulated_RoughnessMask_01.png |
| 114 | Roofing_BronzeOld_1.5x1.5_512_Col.tif | Roof_Bronze_Old_Color.tif |
| 115 | Roofing_BronzeOld_1.5x1.5_512_H.tif | Roof_Bronze_Old_Height.tif |
| 116 | Roofing_BronzeOld_1.5x1.5_512_N.tif | Roof_Bronze_Old_Normal.tif |
| 117 | Roofing_BronzeOld_1.5x1.5_512_RoughnessMask1.png | Roof_Bronze_Old_RoughnessMask_01.png |
| 118 | Roofing_ItalianNew_Col.tif | Roof_Italian_New_Color.tif |
| 119 | Roofing_ItalianNew_H.tif | Roof_Italian_New_Height.tif |
| 120 | Roofing_ItalianNew_N.tif | Roof_Italian_New_Normal.tif |
| 121 | Roofing_ItalianNew_RoughnessMask1.png | Roof_Italian_New_RoughnessMask_01.png |
| 122 | Roofing_ItalianOld_Col.tif | Roof_Italian_Old_Color.tif |
| 123 | Roofing_ItalianOld_H.tif | Roof_Italian_Old_Height.tif |
| 124 | Roofing_ItalianOld_N.tif | Roof_Italian_Old_Normal.tif |
| 125 | Roofing_ItalianOld_RoughnessMask1.png | Roof_Italian_Old_RoughnessMask_01.png |
| 126 | TCom_Metal_Corrugated3_Col.tif | Metal_Corrugated_03_Color.tif |
| 127 | TCom_Metal_Corrugated3_Albedo2.tif | Metal_Corrugated_03_Albedo.tif |
| 128 | TCom_Metal_Corrugated3_Ao.tif | Metal_Corrugated_03_AO.tif |
| 129 | TCom_Metal_Corrugated3_N.tif | Metal_Corrugated_03_Normal.tif |
| 130 | TCom_Metal_Corrugated3_Roughness.tif | Metal_Corrugated_03_Roughness.tif |
| 131 | TCom_Metal_Corrugated3_RoughnessMask1.png | Metal_Corrugated_03_RoughnessMask_01.png |
| 132 | TCom_MetalCorrugatedRusted_LightRust_Col.tif | MetalCorrugatedRusted_LightRust_Color.tif |
| 133 | TCom_MetalCorrugatedRusted_LightRust_Ao.tif | MetalCorrugatedRusted_LightRust_AO.tif |
| 134 | TCom_MetalCorrugatedRusted_LightRust_Metallic.tif | MetalCorrugatedRusted_LightRust_Metallic.tif |
| 135 | TCom_MetalCorrugatedRusted_LightRust_N.tif | MetalCorrugatedRusted_LightRust_Normal.tif |
| 136 | TCom_MetalCorrugatedRusted_LightRust_Roughness.tif | MetalCorrugatedRusted_LightRust_Roughness.tif |
| 137 | TCom_MetalCorrugatedRusted_LightRust_RoughnessMask1.png | MetalCorrugatedRusted_LightRust_RoughnessMask_01.png |
| 138 | Roofing_RoundOld_Col.tif | Roof_Round_Old_Color.tif |
| 139 | Roofing_RoundOld_Albedo_Grey.tif | Roof_Round_Old_Albedo_Grey.tif |
| 140 | Roofing_RoundOld_H.tif | Roof_Round_Old_Height.tif |
| 141 | Roofing_RoundOld_N.tif | Roof_Round_Old_Normal.tif |
| 142 | Roofing_RoundOld_RoughnessMask1.png | Roof_Round_Old_RoughnessMask_01.png |
| 143 | Roofing_Slate_Col.tif | Roof_Slate_Color.tif |
| 144 | Roofing_Slate_H.tif | Roof_Slate_Height.tif |
| 145 | Roofing_Slate_N.tif | Roof_Slate_Normal.tif |
| 146 | Roofing_Slate_RoughnessMask1.png | Roof_Slate_RoughnessMask_01.png |
| 147 | SmallWoodenShingles_0.6x0.6_512_Col.tif | Roof_Shingle_Wood_Color.tif |
| 148 | SmallWoodenShingles_0.6x0.6_512_H.tif | Roof_Shingle_Wood_Height.tif |
| 149 | SmallWoodenShingles_0.6x0.6_512_N.tif | Roof_Shingle_Wood_Normal.tif |
| 150 | SmallWoodenShingles_0.6x0.6_512_RoughnessMask1.png | Roof_Shingle_Wood_RoughnessMask_01.png |
| 151 | TCom_Roofing_SquareOld_Col.tif | Roof_Square_Old_Color.tif |
| 152 | TCom_Roofing_SquareOld_H.tif | Roof_Square_Old_Height.tif |
| 153 | TCom_Roofing_SquareOld_N.tif | Roof_Square_Old_Normal.tif |
| 154 | TCom_Roofing_SquareOld_RoughnessMask1.png | Roof_Square_Old_RoughnessMask_01.png |
| 155 | Roofing_SquareOld2_Col.tif | Roofing_SquareOld_02_Color.tif |
| 156 | Roofing_SquareOld2_Albedo_Grey.tif | Roofing_SquareOld_02_Albedo_Grey.tif |
| 157 | Roofing_SquareOld2_H.tif | Roofing_SquareOld_02_Height.tif |
| 158 | Roofing_SquareOld2_N.tif | Roofing_SquareOld_02_Normal.tif |
| 159 | Roofing_SquareOld2_RoughnessMask1.png | Roofing_SquareOld_02_RoughnessMask_01.png |
| 160 | Roofing_SquareOld2_RoughnessMask1副本.tif | Roofing_SquareOld_02_RoughnessMask_01副本.tif |
| 161 | RoofTilesSlate002_COL.jpg | RoofTilesSlate002_Color.jpg |
| 162 | RoofTilesSlate002_DISP.jpg | RoofTilesSlate002_Height.jpg |
| 163 | RoofTilesSlate002_GLOSSMask25.png | RoofTilesSlate002_Mask.png |
| 164 | RoofTilesSlate002_NRM.png | RoofTilesSlate002_Normal.png |
| 165 | grey_roof_tiles_diff_4k.jpg | Roof_Grey_Tile_Diffuse.jpg |
| 166 | grey_roof_tiles_disp_4k.png | Roof_Grey_Tile_Height.png |
| 167 | grey_roof_tiles_nor_gl_4k.exr | Roof_Grey_Tile_Normal.exr |
| 168 | grey_roof_tiles_rough_4kMask1.png | Roof_Grey_Tile_RoughMask_01.png |
| 169 | roof_07_diff_4k.jpg | Roof_07_Diffuse.jpg |
| 170 | roof_07_disp_4k.png | Roof_07_Height.png |
| 171 | roof_07_nor_gl_4k.exr | Roof_07_Normal.exr |
| 172 | roof_07_rough_4kMask1.png | Roof_07_RoughMask_01.png |
| 173 | TCom_Roofing_PantileOld_Col.tif | Roof_Pantile_Old_Color.tif |
| 174 | TCom_Roofing_PantileOld_H.tif | Roof_Pantile_Old_Height.tif |
| 175 | TCom_Roofing_PantileOld_N.tif | Roof_Pantile_Old_Normal.tif |
| 176 | TCom_Roofing_PantileOld_RoughnessMask1.png | Roof_Pantile_Old_RoughnessMask_01.png |
| 177 | TCom_Roofing_PantileOld_RoughnessMask1.tif | Roof_Pantile_Old_RoughnessMask_01.tif |
| 178 | TCom_Roofing_PantileOld_RoughnessMask1副本.tif | Roof_Pantile_Old_RoughnessMask_01副本.tif |
| 179 | Roof_Col.tif | Roof_Color.tif |
| 180 | Roof_H.tif | Roof_Height.tif |
| 181 | Roof_N.tif | Roof_Normal.tif |
| 182 | roof_roughnessMask1.png | Roof_RoughnessMask_01.png |
| 183 | TCom_Roofing_WoodPlanks_Col.tif | Roofing_WoodPlanks_Color.tif |
| 184 | TCom_Roofing_WoodPlanks_Albedo2.tif | Roofing_WoodPlanks_Albedo.tif |
| 185 | TCom_Roofing_WoodPlanks_H.tif | Roofing_WoodPlanks_Height.tif |
| 186 | TCom_Roofing_WoodPlanks_N.tif | Roofing_WoodPlanks_Normal.tif |
| 187 | TCom_Roofing_WoodPlanks_RoughnessMask2.png | Roofing_WoodPlanks_RoughnessMask_02.png |
| 188 | mask2.tif | Mask_02.tif |
| 189 | RidgeTille_Col.tga | Ridge_Tile_Color.tga |
| 190 | RidgeTille_glossMask1.png | Ridge_Tile_Mask.png |
| 191 | RidgeTille_N.tga | Ridge_Tile_Normal.tga |
| 192 | rusty_metal_02_diff_2k.jpg | Metal_Rusty_02_Diffuse.jpg |
| 193 | rusty_metal_02_nor_2k.jpg | Metal_Rusty_02_Normal.jpg |
| 194 | rusty_metal_02_rough_2kMask1.png | Metal_Rusty_02_RoughMask_01.png |
| 195 | Wall_ConcreteFenceSoviet2_4.5x2.25_Col.tif | Wall_ConcreteFenceSoviet_02_Color.tif |
| 196 | Wall_ConcreteFenceSoviet2_4.5x2.25_N.tif | Wall_ConcreteFenceSoviet_02_Normal.tif |
| 197 | Wall_ConcreteFenceSoviet2_4.5x2.25_RMask1.png | Wall_ConcreteFenceSoviet_02_RMask_01.png |
| 198 | Wall_ConcreteFenceSoviet2_4.30x2.15_Col.tif | Wall_ConcreteFenceSoviet_02_Color.tif |
| 199 | Wall_ConcreteFenceSoviet2_4.30x2.15_H.tif | Wall_ConcreteFenceSoviet_02_Height.tif |
| 200 | Wall_ConcreteFenceSoviet2_4.30x2.15_N.tif | Wall_ConcreteFenceSoviet_02_Normal.tif |
| 201 | Wall_ConcreteFenceSoviet2_4.30x2.15_RoughnessMask1.png | Wall_ConcreteFenceSoviet_02_RoughnessMask_01.png |
| 202 | Grout_Col.tif | Grout_Color.tif |
| 203 | Grout_N.tif | Grout_Normal.tif |
| 204 | Grout_RoughnessMask9.png | Grout_RoughnessMask_09.png |
| 205 | Plaster002_Col.jpg | Plaster002_Color.jpg |
| 206 | Plaster002_NormalGL.jpg | Plaster002_Normal.jpg |
| 207 | Bricks099-JPG_Col.jpg | Bricks099-JPG_Color.jpg |
| 208 | Bricks099-JPG_NormalGL.jpg | Bricks099-JPG_Normal.jpg |
| 209 | StoneBricksBeige001_DISP16_3K.tif | StoneBricksBeige001_DISP_16_3K.tif |
| 210 | StoneBricksBeige002_GLOSS_3KMask1.png | StoneBricksBeige002_GLOSS_3KMask_01.png |
| 211 | Bricks03_COL_VAR1.jpg | Bricks_03_COL_VAR_01.jpg |
| 212 | Bricks03_DISPMask3.png | Bricks_03_Mask.png |
| 213 | Bricks03_NRM.jpg | Bricks_03_Normal.jpg |
| 214 | whiteMask1.png | WhiteMask_01.png |
| 215 | BrownCastleBrickWall_Col.tif | BrownCastleBrickWall_Color.tif |
| 216 | BrownCastleBrickWall_Height2.tif | BrownCastleBrickWall_Height_02.tif |
| 217 | BrownCastleBrickWall_N.tif | BrownCastleBrickWall_Normal.tif |
| 218 | medieval_wall_02_diff_2k.jpg | Medieval_Wall_02_Diffuse.jpg |
| 219 | medieval_wall_02_nor_gl_2k.exr | Medieval_Wall_02_Normal.exr |
| 220 | medieval_wall_02_rough_2kMask1.png | Medieval_Wall_02_RoughMask_01.png |
| 221 | Wall_Stone2_3x3_Col.tif | Wall_Stone_02_Color.tif |
| 222 | Wall_Stone2_3x3_H.tif | Wall_Stone_02_Height.tif |
| 223 | Wall_Stone2_3x3_N.tif | Wall_Stone_02_Normal.tif |
| 224 | Wall_Stone2_3x3_RoughnessMask14.png | Wall_Stone_02_RoughnessMask_14.png |
| 225 | StoneBricksBeige001_GLOSS_3KMask1.png | StoneBricksBeige001_GLOSS_3KMask_01.png |
| 226 | Wall_BrickIndustrial2_2.5x2.5_Col.tif | Wall_BrickIndustrial_02_Color.tif |
| 227 | Wall_BrickIndustrial2_2.5x2.5_N.tif | Wall_BrickIndustrial_02_Normal.tif |
| 228 | Wall_BrickIndustrial2_2.5x2.5_RoughnessMask23.png | Wall_BrickIndustrial_02_RoughnessMask_23.png |
| 229 | Wall_BrickIndustrial6_4x4_Col.tif | Wall_BrickIndustrial_06_Color.tif |
| 230 | Wall_BrickIndustrial6_4x4_N.tif | Wall_BrickIndustrial_06_Normal.tif |
| 231 | Wall_BrickIndustrial6_4x4_RoughnessMask1.png | Wall_BrickIndustrial_06_RoughnessMask_01.png |
| 232 | Brick_Rustic2_Col.tif | Brick_Rustic_02_Color.tif |
| 233 | Brick_Rustic2_H.tif | Brick_Rustic_02_Height.tif |
| 234 | Brick_Rustic2_N.tif | Brick_Rustic_02_Normal.tif |
| 235 | Brick_Rustic2_RoughnessMask19.png | Brick_Rustic_02_RoughnessMask_19.png |
| 236 | church_bricks_03_diff_4k.jpg | Church_Bricks_03_Diffuse.jpg |
| 237 | church_bricks_03_nor_gl_4k.png | Church_Bricks_03_Normal.png |
| 238 | church_bricks_03_rough_4kMask10.png | Church_Bricks_03_RoughMask_10.png |
| 239 | church_bricks_02_diff_png_4k.jpg | Church_Bricks_02_Diff_Png.jpg |
| 240 | church_bricks_02_nor_gl_4k.jpg | Church_Bricks_02_Normal.jpg |
| 241 | church_bricks_02_rough_4kMask8.png | Church_Bricks_02_RoughMask_08.png |
| 242 | DBK_Doors_Col.tif | DBK_Doors_Color.tif |
| 243 | DBK_Doors_Damage_N.tga | DBK_Doors_Damage_Normal.tga |
| 244 | DBK_Doors_Good_N.tga | DBK_Doors_Good_Normal.tga |
| 245 | DBK_Doors_wenli2.tif | DBK_Doors_Wenli_02.tif |
| 246 | layer2.tif | Layer_02.tif |
| 247 | Door_pattern_OcclusionMask6.png | Door_Pattern_Mask.png |
| 248 | Gate_Blue_Col.tif | Gate_Blue_Color.tif |
| 249 | Gate_glossMask1.png | Gate_Mask.png |
| 250 | Gate_Green_Col.tif | Gate_Green_Color.tif |
| 251 | Gate_N.psd | Gate_Normal.psd |
| 252 | Gate_Red_Col.tif | Gate_Red_Color.tif |
| 253 | Gate_Wood_Col.tif | Gate_Wood_Color.tif |
| 254 | Gate_Green_Col.tif | Gate_Green_Color.tif |
| 255 | Gate_normal_1k.tif | Gate_Normal.tif |
| 256 | Gate_roughnessMask1.png | Gate_RoughnessMask_01.png |
| 257 | Gate_Wood_Col.tif | Gate_Wood_Color.tif |
| 258 | WindowsAndDoor_01_A#Wood2.tif | WindowsAndDoor_01_A#Wood_02.tif |
| 259 | WindowsAndDoor_01_glossMask5.png | WindowsAndDoor_01_Mask.png |
| 260 | WindowsAndDoor_01_N.tif | WindowsAndDoor_01_Normal.tif |
| 261 | WoodWall_Wood_N.tif | WoodWall_Wood_Normal.tif |
| 262 | Paintwood_Low_Wood_Paint_A_N.tif | Paintwood_Low_Wood_Paint_A_Normal.tif |
| 263 | Planks004_Col.png | Planks004_Color.png |
| 264 | Planks004_Color2.tif | Planks004_Color_02.tif |
| 265 | Planks004_N.png | Planks004_Normal.png |
| 266 | RoughGrungyWoodSurface_basecolor.png | RoughGrungyWoodSurface_Color.png |
| 267 | RoughGrungyWoodSurface_N.tif | RoughGrungyWoodSurface_Normal.tif |
