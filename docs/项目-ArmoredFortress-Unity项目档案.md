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

## 五、🔴 UI 体系关键事实（做 UI 特效必读）

### Canvas 是 **ScreenSpaceOverlay**

```
Canvas.renderMode  = ScreenSpaceOverlay
Canvas.sortingOrder = 0
Canvas.worldCamera  = NULL
Canvas.scaleFactor  = 2.505625
Screen = 2005x1102
```

**直接后果：3D 粒子系统永远被 UI 盖住**（官方 frame debugger 结论 + 本机实测）。
要在 UI 上加特效，必须走 UI 层内部（`RawImage`/`Image` + 序列帧）。
⚠️ 不要为了特效把 Canvas 改成 ScreenSpaceCamera —— 会变动整个菜单缩放与布局。

### HOME 面板布局（屏幕坐标，已实测）

```
Canvas/Main_Panels/HOME/Content/
  [0] LOGO        y 901~1085   x 0~401
  [1] Image       y 942~1044   x 1097~1975
  [2] SliderInfo  y 119~930    x 1546~1990   ← 右侧竖版信息卡片（177×323）
  [3] Button List y 0~827      x 0~401       ← 左侧八个菜单按钮
```

⭐ **注意**：`SliderInfo` 是**一直都在**的面板，不是 hover 才出现的。
hover 真正改变的只是**左侧按钮自身的高度**（25→70）。

### 菜单按钮结构

```
CAMPAIGN [Button|Animator|EventTrigger|ChangeUIbim]  size=(70, 25)
  - Background [Image]
  - Normal [CanvasGroup] → Text(inactive) / CAMPAIGN(Image)
  - Highlighted [CanvasGroup] (inactive)
```

按钮很小，**里面没有任何大预览图**。

### hover 效果的实现：`ChangeUIbim`

`Assets/Scenes/Interface/UI/Scripts/ChangeUIbim.cs`

```csharp
public void OnPointerEnter() {
    element.element.sizeDelta = new Vector2(x, element.heightnew);   // 25 → 70
    LayoutRebuilder.ForceRebuildLayoutImmediate(verticalLayoutGroup.transform as RectTransform);
}
```

靠 `EventTrigger` 连线调用。**直接调这个方法比发 `ExecuteEvents` 可靠。**
判据：`heightold=25` / `heightnew=70`，当前值 70 就是 hover 态。

### 已有的 UI 特效手段（别重复造轮子）

| 组件 | 挂在哪 | 作用 |
|------|--------|------|
| `BlurManager` | `Canvas/Modal Windows` | 弹窗背景模糊 |
| `PanelBrushManager` | 各面板 | 面板笔刷效果 |
| `Animator` + `CanvasGroup` | `Main_Panels` | 面板转场淡入淡出 |
| `UIFlipbookFire` | （新增 08-06） | 序列帧火焰叠加，参数化可复用 |

---

## 六、现成火焰资产（已实测，优先复用）

项目共 **1913 个材质**，火焰相关：Fire 13 / Flame 8 / Smoke 13 / Explosion 4。

| 用途 | 资源 | 网格 |
|------|------|------|
| 竖直摇曳小火苗 | `Assets/AB/Pool/Material/Type_Fire/Fire_Sequence_02/AF_Fire_Sequence_02.png` | **8×8** |
| 小火星生灭 | `Fire_Sequence_01/AF_Fire_Sequence_01.png` | **8×8** |
| 大火球+浓烟（笼罩用） | `Fire_Sequence_06/AF_Fire_Sequence_06.png`（2048²） | **8×8** |
| 粒子材质（已适配 HDRP） | `Type_Fire/Fire_01/AF_Fire_01.mat` | shader `Shader Graphs/ParticleUnlitEmission` |

🔴 **图集都是 8×8，不是 4×4。** 切错会导致「火焰看起来很小」。
⚠️ 不要自建材质：`material create` 默认 shader 是 `Standard`，HDRP 下**必粉红**。

---

## 七、复验命令（配置会变，隔久了要重查）

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
