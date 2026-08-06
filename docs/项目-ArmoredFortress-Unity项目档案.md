# ArmoredFortress 项目档案（Unity 工作前必读）

> 建立：2026-08-06
> 用途：任何 Unity 工作开工前先读本文，**不要靠猜管线和场景**
> 数据来源：全部为 Bridge / MCP **实测取回**，非文档抄录
> 复验命令见文末（配置可能被人改，隔久了要复验）

---

## 一、渲染管线：**HDRP**（已钉死，非推测）

| 证据 | 结果 |
|------|------|
| 场景内活组件 `component.get` | `fullType: UnityEngine.Rendering.HighDefinition.StaticLightingSky` ✅ |
| `reflect search HDRenderPipelineAsset` | count **1** ✅ |
| `reflect search HDAdditionalCameraData` | count **10** ✅ |
| `reflect search UniversalRenderPipelineAsset` | count **0** ❌ 不是 URP |

⚠️ **判据分强弱，别只看 reflect。**
`reflect` 只证明「程序集里有这个类型」，**不等于它是当前激活管线**（装了包没启用也会有）。
真正的硬证据是**场景里存在一个活的 HDRP 专属组件** —— 本项目根节点 `StaticLightingSky`
就是 HDRP 独有物件，这条才是决定性的。

### HDRP 对做特效的直接影响（这是为什么必须先查管线）

- ❌ **Standard / URP 的 Shader 不能直接用**，材质会变粉红
- ❌ 网上大量 Unity 特效教程默认 Built-in 管线，**照抄必翻车**
- ✅ 后处理走 **Volume + VolumeProfile**（已确认 `VolumeProfile` 存在），不是老的 PostProcessing Stack
- ✅ 自定义 Shader 走 **Shader Graph / HDRP Lit**，不写 Built-in 的 surface shader
- ⚠️ HDRP 里 UI 特效尤其要小心：Canvas 默认不吃 Volume 后处理

---

## 二、Unity 版本与环境

| 项 | 值 |
|---|---|
| Unity 版本 | **2021.3.32f1c1** |
| 平台 | WindowsEditor（宿主机） |
| 工程路径 | `E:/Unity/2026-04-28/Assets` |
| productName | ArmoredFortress |

⚠️ **2021.3 是老版本**，很多新 API 不存在。
写 C# 前**先 `reflect search` 验证 API 真实存在**，别凭训练数据编造（这是 MCP 最大的增益）。
实测例：`HDRenderPipelineGlobalSettings` 在本项目 **count=0**（那是更高版本才有的类），
`HDRPDefaultSettings` 也是 **count=0**。要是照新版教程写就直接编译不过。

---

## 三、场景清单（7 个）

| # | 名称 | 路径 |
|---|------|------|
| 0 | Splash | `Assets/Scenes/Splash.unity` |
| **1** | **Main** ← 截图里的主菜单 | `Assets/Scenes/Interface/Main.unity` |
| 2 | Campaign | `Assets/Scenes/Interface/Campaign.unity` |
| 3 | Scene_Switch | `Assets/Scenes/Game/Scene_Switch.unity` |
| 4 | Scene_Airfield | `Assets/Scenes/Mission/Scene_Airfield/Scene_Airfield.unity` |
| 5 | Scene_Village | `Assets/Scenes/Mission/Scene_Village/Scene_Village.unity` |
| 6 | Scene_Town | `Assets/Scenes/Mission/Scene_Town/Scene_Town.unity` |

### Main.unity 结构（截图已对照一致）

根节点 7 个，其中两个主要：

```
▶ Canvas [Canvas, CanvasScaler, GraphicRaycaster]
  ├─ Menu Manager          [MainPanelManager]           ← 左侧导航
  ├─ CAMPAIGN Manager      [Main_Campaign_UI_Manager]
  ├─ SKIRMISH Manager      [Skirmish_Manager]
  ├─ Multiplayer Manager   （下含 Lobby/CreatRoom/Chat/Room/Commander/Account 六个子 Manager）
  ├─ Settings Manager      [UI_Settings_Manager]
  ├─ EventSystem           [StandaloneInputModule]
  ├─ Main_Panels           [CanvasGroup, Animator]       ← 面板切换靠 Animator
  │   ├─ HOME / CAMPAIGN / SKIRMISH ... [PanelBrushManager]
  └─ Modal Windows         [BlurManager]                 ← ⭐ 已有的 UI 模糊特效手段
▶ SingleMode_Room_01       [MeshFilter, MeshRenderer]    ← 菜单背景 3D 场景（机库）
▶ StaticLightingSky                                      ← HDRP 专属，管线判据
```

**做 UI 特效前先看这几个已有件**，别重复造轮子：
- `BlurManager`（Modal Windows 上）—— 弹窗背景模糊已经有了
- `PanelBrushManager`（各面板上）
- `Animator` + `CanvasGroup`（Main_Panels）—— 面板转场是 Animator 驱动的

---

## 四、做特效可用的技术栈（已实测存在）

| 能力 | 类型 | count | 备注 |
|------|------|-------|------|
| VFX Graph | `VisualEffect` / `VisualEffectAsset` / `VisualEffectObject` | 3 | ✅ 可用 |
| 老粒子系统 | `ParticleSystemRenderer` | 1 | ✅ 可用（Shuriken） |
| 后处理 | `VolumeProfile` / `VolumeProfileFactory` | 3 | ✅ HDRP Volume 体系 |
| 文字 | `TMP_Text` 等 | 9 | ✅ TextMeshPro 在用 |

---

## 五、复验命令（配置会变，隔久了要重查）

```bash
# 0) 先确认两条通道活着
bash ~/.openclaw/workspace/scripts/unity-stack-patch.sh verify

# 1) 管线（硬判据：场景里的活组件）
curl -s -X POST http://localhost:27182/unity/tool -H "Content-Type: application/json" \
  -d '{"tool":"component.get","arguments":{"gameObject":"StaticLightingSky","type":"UnityEngine.Rendering.HighDefinition.StaticLightingSky"}}'

# 2) 当前场景 + 全部场景
curl -s -X POST http://localhost:27182/unity/tool -H "Content-Type: application/json" \
  -d '{"tool":"scene.getActive","arguments":{}}'
curl -s -X POST http://localhost:27182/unity/tool -H "Content-Type: application/json" \
  -d '{"tool":"scene.list","arguments":{}}'

# 3) 版本 / 工程路径
curl -s -X POST http://localhost:27182/unity/tool -H "Content-Type: application/json" \
  -d '{"tool":"editor.getState","arguments":{}}'

# 4) 写 C# 前验 API 真实存在（防幻觉）
cd ~/.openclaw/workspace/tools/unity-mcp-coplay/Server
.venv/bin/unity-mcp --host 127.0.0.1 --port 8080 reflect search "<类名>"
```

### ⚠️ `component.get` 的参数名（2026-08-06 实测纠错）

指南原先写的 `{"name":..., "componentType":...}` 是**错的**，会返回
`GameObject '' not found`。**正确是 `gameObject` + `type`**：

```json
{"gameObject":"Canvas","type":"Transform"}
```

且 **HDRP 等带命名空间的类型必须写全名**，否则报 `Type 'X' not found`：

```json
{"gameObject":"StaticLightingSky","type":"UnityEngine.Rendering.HighDefinition.StaticLightingSky"}
```
