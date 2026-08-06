# media/unity/ 素材说明

> 2026-08-06 Unity 火焰特效工作产出。
> 完整过程见 `docs/案例-Unity-UI火焰特效全流程复盘-20260806.md`

## 视频（最终成果）

| 文件 | 内容 |
|------|------|
| `fire_edge_full.mp4` | 全屏版，30 帧 @12fps = 2.5s，看整体效果 |
| `fire_edge_card.mp4` | 卡片特写版，裁切坐标来自 `GetWorldCorners` 实测 |

## 截图（关键节点）

| 文件 | 内容 |
|------|------|
| `hover_campaign_20260806.png` | CAMPAIGN hover 展开态复现（第一次成功截到 UI） |
| `fire_v4.png` | 铺满版火焰（8×8 切帧修正后，第一次看起来正常） |
| `fire_edge.png` | **最终交付态**：边缘燃烧，占卡片底部 1/3，三束火苗 |

## 图集参考（实测导出，用于确认网格行列）

| 文件 | 结论 |
|------|------|
| `atlas_AF_Fire_Sequence_01.png` | **8×8**，小火星生灭，占单格 10-25% |
| `atlas_AF_Fire_Sequence_02.png` | **8×8**，竖直摇曳火苗，占单格 30-50% ← 最终选用 |
| `atlas_AF_Fire_Sequence_06.png` | **8×8**（2048²），大火球+浓烟，后期占格 80%+ |

🔴 这三张是用 `Graphics.Blit` → `ReadPixels` 从项目里导出、
并把透明区合成到深色底上生成的**参考图**，不是项目资产本身。
原始资产在 `Assets/AB/Pool/Material/Type_Fire/` 下。

导出它们的原因：我一开始猜图集是 4×4，导致 `uvRect` 切错、
火焰只显示中心一小块（表现为「火焰太小」）。**网格行列必须实测，不能猜。**

## 已清理的中间产物

以下文件已删除（合成视频后不再需要，共省 94M）：
- `seqframe_001~030.png` —— 录制用的 30 帧原始截图（84M）
- `fire_v2.png` / `fire_v3.png` / `fire_overlay_1.png` —— 迭代过程截图
- `verify*.png` / `verify*.jpg` —— 抽帧自检拼图
- `verify_receiver.png` —— 截图回传通道验证图

需要重录时跑 `bash scripts/unity-record-ui-effect.sh 30`（脚本仍在）。
