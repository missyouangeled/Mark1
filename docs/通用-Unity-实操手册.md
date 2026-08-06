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

## 三、🔴 三条"报 success 其实没成"（本轮全踩了）

这是最危险的一类：**返回 `status: success` 但事情没做成。**

1. **`lighting create`** → 光建了个空物件，Light 组件没有
2. **`gameobject create --components`** → 组件列表被忽略
3. **粒子 `playOnAwake`** → 编辑器里 `isPlaying: True`，一进 Play 变 False（详见第五节）

**通用防御：每一步做完，回读实际状态确认，不看返回值。**

```bash
# 回读组件（唯一可信）
curl -s -X POST http://localhost:27182/unity/tool -H "Content-Type: application/json" \
  -d '{"tool":"gameobject.find","arguments":{"name":"<物件名>"}}' | python3 -c "
import sys,json;d=json.load(sys.stdin)['result'][0]
print('组件:',d['components']);print('坐标:',d['position'])
for c in d.get('children',[]): print('  └',c['name'],c['components'])"
```

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

## 七、触发 UI 交互（hover / click）

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

## 八、验收清单（别看灯）

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

## 九、已知坏的 / 别用

| 东西 | 状态 |
|------|------|
| Bridge `transform.setPosition` | 🔴 参数名怎么写都报 not found → 用 MCP `gameobject modify` |
| `script validate` CLI | 🔴 上游 bug，换版本无解 → `$M raw manage_script '{"action":"validate",...}'` |
| `code search` 给目录 | 🔴 PATH 必须是**文件** |
| `resource read` | 🔴 子命令不存在，错误处理自身会崩 |
| Roslyn 精确校验 | 默认关，要加 `USE_ROSLYN` 编译符号（**影响全项目，别动**） |
| `asset info "<名字>"` | 只认完整路径，不认资产名 |

---

## 十、待改进

- **hover 后没截到"变化过程"**，只有静态终态。已装 ffmpeg 6.1.1 + `video-frames` skill，
  下次可连续截帧合成短视频看动态（火苗窜动、hover 展开过程）
- 截图接收服务目前是手起的临时进程，可考虑并入 unity-stack 模块
- 本轮火焰放在 `(-20, 0.5, 2)`，被 UI Canvas 完全遮住，画面里看不见 → 位置要选镜头可见处
