# Unity 实操手册（实测版）

> 建立：2026-08-06
> 用途：**动手前必读。** 这里全是实测踩出来的正确用法，不是 README 抄的。
> 定位：`docs/通用-Unity-Bridge-连接指南.md` 讲怎么连，
> `docs/项目-ArmoredFortress-Unity项目档案.md` 讲这个项目是什么，
> **本文讲怎么真正把活干成。**
>
> ⚠️ 凡本文标 🔴 的，都是**文档/help 写错或有坑、我实际踩过**的地方。

---

## 一、两条通道怎么选

| 需求 | 用哪条 | 理由 |
|------|--------|------|
| 读场景、查物件、截图、控制台 | **Bridge** `:27182` | 快，返回干净 JSON |
| 建物件 / 加组件 / 改 Transform | **MCP** `:8080` | Bridge 的 transform 参数名是坏的（见下） |
| 调粒子参数 | **MCP** `vfx raw` | Bridge 没有 |
| 查 API 是否存在 | **MCP** `reflect` | ⭐ 防幻觉，最大增益 |
| 找资产 / 查材质 shader | **MCP** `asset` / `material` | Bridge 没有 |
| **在 Unity 里跑 C#** | **MCP** `code execute` | ⭐ 万能出口，下面详述 |

启动：`bash scripts/unity-stack-patch.sh start --apply`（两条一起，systemd 托管）

MCP 命令前缀（下文统一简写为 `$M`）：
```bash
cd ~/.openclaw/workspace/tools/unity-mcp-coplay/Server
M=".venv/bin/unity-mcp --host 127.0.0.1 --port 8080"
```

---

## 二、🔴 参数名纠错表（血泪）

### Bridge 侧

| 工具 | 文档写的（错） | 实测正确 |
|------|--------------|---------|
| `component.get` | `name` + `componentType` | **`gameObject` + `type`** |
| `transform.setPosition` | `objectName` | 🔴 **两种写法都报 `GameObject '' not found`，这工具是坏的 → 改用 MCP `gameobject modify`** |

带命名空间的类型**必须写全名**，否则 `Type 'X' not found`：
```bash
# ✅
-d '{"tool":"component.get","arguments":{"gameObject":"FX_Fire_Test_Light","type":"UnityEngine.Rendering.HighDefinition.HDAdditionalLightData"}}'
# ❌ 报 Type not found
-d '{"...":"HDAdditionalLightData"}'
```

### MCP 侧

| 命令 | 坑 |
|------|-----|
| `material assign` | 🔴 **材质路径在前，目标物件在后**。反了报 `Could not find target GameObject: Assets/...` |
| `gameobject create --components "X"` | 🔴 **不生效**，报 success 但 componentNames 只有 Transform → 必须事后单独 `component add` |
| `gameobject create --position` | 🔴 **有 parent 时被当 local 叠加**。父在 x=-20，传 -20 → 实际 -40。解法：传 local 值（0），或建完用 `gameobject modify --position` 修 |
| `component add` | 报 `Failed to add component... Unity may restrict` 时**先去查物件**，可能已经加上了（重复调用的误报） |
| `lighting create` | 🔴 **报 success 但 Light 组件根本没建上**，只有 Transform → 必须 `component add <名> Light` 补 |

---

## 三、🔴 「报 success 其实没成」清单

这是最危险的一类：**返回 `status: success` 但事情没做成。**

1. **`lighting create`** → 光建了个空物件，Light 组件没有
2. **`gameobject create --components`** → 组件列表被忽略
3. **粒子 `playOnAwake`** → 编辑器里 `isPlaying: True`，一进 Play 变 False（详见第五节）
4. **`editor play`** → 报 success ≠ 已进入，必须回读 `isPlaying`，且等 12-15 秒
5. **`script create`** → 文件已存在时报 `Script already exists`，不覆盖（绕法见第四节）

**通用防御：每一步做完，回读实际状态确认，不看返回值。**

```bash
# 回读组件（唯一可信）
curl -s -X POST http://localhost:27182/unity/tool -H "Content-Type: application/json" \
  -d '{"tool":"gameobject.find","arguments":{"name":"<物件名>"}}' | python3 -c "
import sys,json;d=json.load(sys.stdin)['result'][0]
print('组件:',d['components']);print('坐标:',d['position'])
for c in d.get('children',[]): print('  └',c['name'],c['components'])"
```

### 🔴 UI 专项：`activeInHierarchy=True` 不代表看得见

2026-08-06 实测踩坑：UI 整个消失，但数据层全部正常 ——
`Canvas` / `Main_Panels` / `HOME` / `SliderInfo` 全是 `active=True`。
真因是 **`HOME` 的 `CanvasGroup.alpha = 0`**（assembly reload 把 Animator 驱动的
运行时状态打回初始值，重新播放的逻辑没跑）。

**查 UI 可见性要逐级看四样：**
```csharp
activeInHierarchy   // 物件激活
CanvasGroup.alpha   // ⭐ 最容易漏
Image.enabled / color.a
RectTransform.localScale / lossyScale
```

**修法**：不要手改 alpha 糊过去，**干净重启 Play** 让 UI 走自己的初始化逻辑。

---

## 四、⭐ `code execute` —— 万能出口

CLI 覆盖不到的都走它。**代码作为方法体执行**，能用 UnityEngine + UnityEditor，`return` 回传数据。

```bash
$M code execute 'return Application.unityVersion;'
$M code execute -f script.cs                      # 从文件读，长代码用这个
$M code execute --no-safety-checks '...'           # 放开 File.Delete / WebClient 等
```

**实测确认：`code execute` 不会踢掉 Play 模式**（三步验证 True→True→True）。
最初怀疑 codedom 编译触发 assembly reload 踢掉 Play，实测排除了。

能干的事：
- 遍历场景找东西（`Resources.FindObjectsOfTypeAll<T>()`）
- 直接调项目自己的脚本方法（比 ExecuteEvents 可靠）
- 读私有/序列化字段的真实值
- 截图 + **把文件传回 Linux**（见第六节）
- **写脚本文件**（绕过 `script create` 不能覆盖的限制）

### 🔴 绕过 `script create` 不能覆盖

```csharp
var path = System.IO.Path.Combine(Application.dataPath, "相对Assets的路径.cs");
System.IO.File.WriteAllText(path, content, new System.Text.UTF8Encoding(false));
UnityEditor.AssetDatabase.ImportAsset("Assets/相对路径.cs");
```

长内容用 Python 生成 `.cs` 探针文件再 `-f` 传入，避免 shell 转义地狱
（**shell 会在逗号处截断参数**，实测 `code execute '...string.Join(",",x)...'` 报
`Got unexpected extra argument`）。

### 🔴 `reflect search` 查不到项目自己的脚本

`reflect` 扫的是 **Unity 内置程序集**，不含 `Assembly-CSharp`。
项目脚本编译成功也会 `count: 0`。验证项目类型要用：

```csharp
var t = System.Type.GetType("你的类名, Assembly-CSharp");
if (t == null) return "NOT COMPILED";
foreach (var f in t.GetFields()) sb.Append(f.Name + " ");   // 顺便验字段真在
```

### 🔴 assembly reload 会断开 MCP session

改脚本触发编译时，MCP 报
`Unity plugin session ... disconnected while awaiting command_result`，
**这是正常现象**，等 20 秒左右自动重连。同时 Play 模式会被强制退出。

---

## 五、粒子 / 特效怎么做（HDRP）

### 完整可用流程

```bash
# 1) 建空物件（位置注意 local 叠加坑）
$M gameobject create "FX_Fire_Test" --position 0 0.5 2 --parent "SingleMode_Room_01"

# 2) 单独加组件（--components 不生效）
$M component add "FX_Fire_Test" ParticleSystem

# 3) 主模块（🔴 playOnAwake 必须显式开！）
$M vfx raw particle_set_main "FX_Fire_Test" --params '{"duration":5,"looping":true,
  "startLifetime":1.2,"startSpeed":1.5,"startSize":0.5,"maxParticles":200,
  "gravityModifier":-0.15,"playOnAwake":true,
  "startColor":{"r":1.0,"g":0.55,"b":0.15,"a":1.0}}'

# 4) 发射 / 形状
$M vfx raw particle_set_emission "FX_Fire_Test" --params '{"enabled":true,"rateOverTime":45}'
$M vfx raw particle_set_shape "FX_Fire_Test" --params '{"enabled":true,"shapeType":"Cone","angle":12,"radius":0.25}'
$M vfx raw particle_set_color_over_lifetime "FX_Fire_Test" --params '{"enabled":true}'
$M vfx raw particle_set_size_over_lifetime "FX_Fire_Test" --params '{"enabled":true}'

# 5) 材质（HDRP 关键，见下）
$M material assign "Assets/AB/Pool/Material/Type_Fire/Fire_01/AF_Fire_01.mat" "FX_Fire_Test"

# 6) 配光（两个组件都要加）
$M lighting create "FX_Fire_Test_Light" --type Point --position -20 0.9 2 --color 1.0 0.5 0.15 --intensity 2.5
$M component add "FX_Fire_Test_Light" Light --properties '{"type":2,"intensity":2.5,"range":8}'
$M component add "FX_Fire_Test_Light" "UnityEngine.Rendering.HighDefinition.HDAdditionalLightData"
$M gameobject modify "FX_Fire_Test_Light" --parent "FX_Fire_Test"
```

### 🔴 `playOnAwake` 是本轮最阴的坑

编辑器里 `vfx particle info` 显示 `isPlaying: True`，**一进 Play 模式变 False、particleCount 0**。
根因：`playOnAwake` 默认关着，编辑器预览是靠 `vfx particle play` 手动播的，运行时没人播它。

**判据：`particleCount > 0` 才是真在喷**，`isPlaying` 不够。

### 🔴 HDRP 材质：**用项目现成的，别自己建**

- `material create` 默认 shader 是 `Standard` → **HDRP 下必粉红**
- 本项目已有 1913 个材质，Fire 13 个 / Flame 8 个 / 整套序列帧
- 现成材质 shader 是 `Shader Graphs/ParticleUnlitEmission`（项目自制，带 `Emission_Color`/`Emission_Power`），已适配管线

```bash
$M asset search "Fire t:Material"                    # 先找现成的
$M -f json asset search "AF_Fire_01 t:Material"      # 🔴 要完整路径必须加 -f json
$M material info "<完整.mat路径>"                     # 看 shader 确认
```

⚠️ 联网查到的坑：**HDRP `_EmissiveIntensity` 用 C# 设置无效**（官方回复：GUI 代码额外设了 keyword/render state，没暴露运行时 API）。
用项目的 Shader Graph 材质天然绕开了这个问题。

### HDRP 灯光必须配 `HDAdditionalLightData`

只加 `Light` 组件，HDRP 下**不会按 HDRP 方式渲染**。这是"不查管线就动手"的典型翻车点。

---

## 六、Play 模式 + 截图回传

### Play 控制

```bash
$M editor play      # 进
$M editor stop      # 出
$M editor pause     # 暂停
```

🔴 **`editor play` 报 success ≠ 已进入**。必须回读，且要等 **12-15 秒**（编译 + 启动）：

```bash
curl -s -X POST http://localhost:27182/unity/tool -H "Content-Type: application/json" \
  -d '{"tool":"editor.getState","arguments":{}}'
# → isPlaying / isPaused / fps / time
```

⚠️ **进 Play 会丢未保存的改动**（Unity 退出 Play 时还原场景）。先存：
```bash
$M scene save
```

### 🔴 截图回传（Unity 在 Windows，我在 Linux VM，没有共享盘）

`debug.screenshot` 存到 `C:/Users/.../LocalLow/<公司>/<产品>/`，**我看不到**。
解法：VM 上起 HTTP 接收端，Unity 侧用 `WebClient` POST 回来。

```bash
# ① VM 起接收服务（默认落盘到 workspace/media/unity/，可直接给 image 工具看）
setsid nohup python3 ~/.openclaw/workspace/scripts/unity-shot-receiver.py \
  > /tmp/unity-shot-receiver.log 2>&1 < /dev/null & disown
curl -s http://127.0.0.1:28080/          # → unity-shot-receiver ok

# ② Unity 里截图（必须在 Play 模式！见下方红字）
$M code execute --no-safety-checks 'var p=System.IO.Path.Combine(Application.persistentDataPath,"shot.png");
if(System.IO.File.Exists(p)) System.IO.File.Delete(p);
ScreenCapture.CaptureScreenshot(p);
return "shot requested";'

# ③ 等 3-4 秒让 Unity 写盘，再传
$M code execute --no-safety-checks 'var p=System.IO.Path.Combine(Application.persistentDataPath,"shot.png");
if(!System.IO.File.Exists(p)) return "NOT READY (isPlaying="+Application.isPlaying+")";
var b=System.IO.File.ReadAllBytes(p);
var wc=new System.Net.WebClient(); wc.Headers.Add("X-Name","shot.png");
wc.UploadData("http://192.168.79.128:28080/", b);
return "UPLOADED "+b.Length;'
```

实测：2.6MB / 2005×1102 一次传成；脚本端到端复验 2538539 bytes 落盘成功。

### 🔴 `CaptureScreenshot` 在非 Play 模式下**根本不写盘**

实测（两轮对照）：

| 状态 | 结果 |
|------|------|
| `isPlaying=False` | 等 3s、再等 6s、共 9s+ → 文件**始终不存在** |
| `isPlaying=True` | 等 4s → ✅ 2538539 bytes |

原因：`ScreenCapture.CaptureScreenshot` 依赖**渲染帧循环**，非 Play 模式下
编辑器不跑连续帧，请求永远不会完成。
**要截图就先进 Play。** 不要把 `NOT READY` 当成“再等一下就好”。

⚠️ 另一条路：`debug.screenshot`（Bridge）在非 Play 模式下能出图，
因为它走的是 `mode: camera` 主动渲染，不依赖帧循环。
但它只返回 Windows 路径，仍需上面的 `code execute` 回传才能拿到图。

🔴 **`image` 工具只能读 workspace 下的路径**，`/tmp` 会被拒
（`Local media path is not under an allowed directory`）。
接收脚本已默认落盘到 `media/unity/`，无需再 cp。

---

## 七、UI 特效叠加（🔴 先查 Canvas 渲染模式）

> 完整案例：`docs/案例-Unity-UI火焰特效全流程复盘-20260806.md`

### 第一步必须查渲染模式 —— 它决定全部技术选型

```bash
$M code execute 'var c=GameObject.Find("Canvas").GetComponent<Canvas>();
return "renderMode="+c.renderMode+" sortingOrder="+c.sortingOrder;'
```

| Canvas 模式 | 渲染顺序 | 3D 粒子能盖在 UI 上？ |
|------------|---------|--------------------|
| **ScreenSpaceOverlay** | 场景物件先渲染 → Canvas 最后 | ❌ **永远不能** |
| ScreenSpaceCamera | Canvas → 粒子在其后 | ✅ 可以（需配 sortingLayer） |
| WorldSpace | 同上 | ✅ 可以 |

**本项目是 `ScreenSpaceOverlay`**（实测）。所以：
- ❌ 3D 粒子完全无效（上午那火焰 `particleCount: 54` 真在喷，但画面就是看不见）
- ⚠️ 不要为了特效改 Canvas 模式 —— 会变动整个菜单的缩放与布局
- ✅ **走 UI 层内部叠加**：`RawImage` + 序列帧 flipbook

### 序列帧图集：🔴 网格行列必须实测

**本轮最大的坑**：我猜 4×4，实际是 **8×8**。
`uvRect` 用 0.25 切 → 实际取到「4 格拼在一块」，火焰只占中心一小点，
表现为「火焰太小」—— **不是尺寸没调够，是切错了。**

实测方法（导出图集肘眼看）：
```csharp
var rtex = new RenderTexture(tex.width, tex.height, 0, RenderTextureFormat.ARGB32);
Graphics.Blit(tex, rtex);                    // 绕过 compressed/non-readable
RenderTexture.active = rtex;
var readable = new Texture2D(tex.width, tex.height, TextureFormat.RGBA32, false);
readable.ReadPixels(new Rect(0,0,tex.width,tex.height), 0, 0);
readable.Apply();
// 再把透明区合成到深色底上写 PNG，否则透明看不出格子
```

### flipbook UV 切帧公式

```csharp
float w = 1f / columns, h = 1f / rows;
int cx = idx % columns, cy = idx / columns;
float y = 1f - h * (cy + 1);        // 图集第0帧在左上，UV 原点在左下 → y 需翻转
raw.uvRect = new Rect(cx*w, y, w*tileX, h);   // tileX 横向平铺份数
```

可复用组件：`Assets/Scenes/Interface/UI/Scripts/UIFlipbookFire.cs`

### 必记的三个细节

- `raycastTarget = false` —— 否则挡住底下 UI 的鼠标事件
- `SetAsLastSibling()` —— 保证画在目标图像之上
- **编辑模式建 + `scene save`** —— 运行时建的物件退 Play 就没了

### 找目标物件：不要凭画面观感猜

本轮我先去查 `CAMPAIGN` 按钮内部，以为预览图在里面 ——
**按钮本身只有 70×25，里面只有文字图片**。真正的卡片是兄弟节点 `SliderInfo`。

**用户说的「选项卡展开后出现的东西」，不一定是那个按钮的子物件。**
先遍历兄弟节点看全局布局（带 y/x 范围），再定目标。

---

## 八、触发 UI 交互（hover / click）

### 找按钮

```bash
$M code execute 'var sb=new System.Text.StringBuilder();
foreach(var b in Resources.FindObjectsOfTypeAll<UnityEngine.UI.Button>()){
 if(b.gameObject.scene.name==null) continue;
 var p=b.transform; string path=b.name;
 while(p.parent!=null){p=p.parent;path=p.name+"/"+path;}
 sb.AppendLine(b.gameObject.activeInHierarchy+" | "+path);}
return sb.ToString();'
```

### 触发 hover —— 两条路

```bash
# 路 A：标准事件（需 Play 模式，EventSystem.current 才非 null）
$M code execute 'var go=GameObject.Find("<完整路径>");
var es=UnityEngine.EventSystems.EventSystem.current;
if(es==null) return "NO EVENTSYSTEM";   // 非 Play 模式必然 null
var ped=new UnityEngine.EventSystems.PointerEventData(es);
ped.position=new Vector2(138f,795f);
UnityEngine.EventSystems.ExecuteEvents.Execute(go,ped,
  UnityEngine.EventSystems.ExecuteEvents.pointerEnterHandler);
return "ok";'

# 路 B：直接调项目脚本方法（更可靠，绕过 EventTrigger 连线）
$M code execute 'var cu=GameObject.Find("<路径>").GetComponent<ChangeUIbim>();
cu.OnPointerEnter(); return cu.element.element.sizeDelta.y;'
```

⚠️ **非 Play 模式下 `EventSystem.current` 一定是 null**，即使场景里那个 EventSystem 物件 active。

### 🔴 验证 hover 生效：必须知道两端基准值

本轮我看到 `height 70 -> 70` 就判定"没生效"，**报了错结论**。
真相：前一发已经让它进展开态，第二次调用时本来就是 70。
读到脚本里 `heightold=25 / heightnew=70` 才看清 **70 就是 hover 后的值**。

**教训：单点采样看不出状态，必须先拿到「变化前」和「变化后」两个基准。**
（同今早误判 timer 的病：`SubState=running` 是正常中间态）

本项目 hover 实现：`ChangeUIbim.OnPointerEnter()` 改 `sizeDelta.y`（25→70）
+ `LayoutRebuilder.ForceRebuildLayoutImmediate`，靠 `EventTrigger` 连线调用。

---

## 九、录制动态效果视频（ffmpeg）

静态图看不出特效动态。完整脚本：`scripts/unity-record-ui-effect.sh`

### 三个关键点

1. **每帧都要重新锁 hover** —— UI 自身逻辑会把展开状态重置
2. **必须用 Bridge `debug.screenshot`** —— `CaptureScreenshot` 拓不到 Overlay UI
3. 截图落在 Windows，需 `code execute` + `WebClient` 回传

```bash
ffmpeg -y -framerate 12 -pattern_type glob -i 'seqframe_*.png' \
  -vf "scale=1400:-2:flags=lanczos" -c:v libx264 -pix_fmt yuv420p -crf 22 \
  -movflags +faststart out_full.mp4
```

⚠️ 接收端会把文件名里的 `/` 替掉（防目录穿越）→ 用扁平命名 `seqframe_001.png`

### 🔴 裁切坐标必须从 Unity 读，不要猜

本轮我猜了三次 crop、来回改了四遍。第四次才想到读真坐标：

```bash
$M code execute 'var rt=GameObject.Find("<路径>").GetComponent<RectTransform>();
Vector3[] c=new Vector3[4]; rt.GetWorldCorners(c);
return "x="+c[0].x+" y_top="+(Screen.height-c[2].y)+" w="+(c[2].x-c[0].x)+" h="+(c[2].y-c[0].y);'
```

实测 `y_top=707`，而我第一次猜的是 `130` —— **差了 577 像素**。

⚠️ **看图反馈前后矛盾时（先说上边切、后说下边切），说明诊断方向错了**，
要停下重新判断，不要接着调参数（真因是火焰被另一块 UI 挡住下半截）。

### 自检：发给用户前必须自己看过

```bash
ffmpeg -y -i out.mp4 -vf "select='eq(n\,0)+eq(n\,10)+eq(n\,20)',tile=3x1,scale=1100:-2" \
  -frames:v 1 verify.jpg
```

🔴 **`image` 工具对大图会超时**（1.3MB PNG 超 60s）→ 先转小 jpg 再看。

---

## 十、验收清单（别看灯）

| 验什么 | 怎么验 |
|--------|--------|
| 物件/组件真建上了 | `gameobject.find` 回读 `components` |
| 坐标对不对 | 回读 `position`（注意 local vs world） |
| 材质没坏 | `console.getErrors` → **count 0**（粉红材质会报错） |
| 粒子真在喷 | `vfx particle info` → **particleCount > 0** |
| Play 真进了 | `editor.getState` → `isPlaying: true` |
| 画面对不对 | **先进 Play**，再截图回传 + 自己用 `image` 工具看过再给用户 |
| API 真存在 | `reflect search`（写 C# 前） |

```bash
curl -s -X POST http://localhost:27182/unity/tool -H "Content-Type: application/json" \
  -d '{"tool":"console.getErrors","arguments":{"count":30}}'
```

---

## 十一、已知坏的 / 别用

| 东西 | 状态 |
|------|------|
| Bridge `transform.setPosition` | 🔴 参数名怎么写都报 not found → 用 MCP `gameobject modify` |
| `script validate` CLI | 🔴 上游 bug，换版本无解 → `$M raw manage_script '{"action":"validate",...}'` |
| `code search` 给目录 | 🔴 PATH 必须是**文件** |
| `resource read` | 🔴 子命令不存在，错误处理自身会崩 |
| Roslyn 精确校验 | 默认关，要加 `USE_ROSLYN` 编译符号（**影响全项目，别动**） |
| `asset info "<名字>"` | 只认完整路径；要拿路径用 `-f json asset search` |
| `reflect search` 查项目脚本 | 只扫 Unity 内置程序集 → `Type.GetType("X, Assembly-CSharp")` |
| `script create` 覆盖已存文件 | 报错不覆盖 → `code execute` 里 `File.WriteAllText` + `ImportAsset` |
| `code execute` 行内写带逗号的 C# | shell 在逗号处截断参数 → 写文件用 `-f` 传 |
| `ScreenCapture.CaptureScreenshot` | 非 Play 不写盘；**且拓不到 ScreenSpaceOverlay 的 UI** → 用 Bridge `debug.screenshot` |

---

## 十二、待改进

- hover 状态靠「每帧重新调 OnPointerEnter」锁住，更稳的做法是写协程在 N 帧内持续锁定
- 截图接收服务 `scripts/unity-shot-receiver.py` 目前手起，可并入 `openclaw-unity.target` 模块
- 2026-08-06 火焰位置放错了（放在常驻的 SliderInfo，而非 hover 真正展开的物件）——
  **下次应先做 hover 前后的 hierarchy diff**，看到底哪个物件是新出现/变化的
