# Unity 资产路径过长 — 风险分析与应对方案

> 适用机器：公司（Linux）→ 但分析结论适用于最终部署的 Windows Unity 环境
> 生成时间：2026-06-09
> 触发：用户担心 rename 后文件名+路径可能超过 Windows 260 字符限制

---

## 一、风险判定：会，而且比你担心的更严重

### 1.1 Windows 硬限制

| 限制 | 值 | 说明 |
|------|-----|------|
| MAX_PATH（传统） | 260 字符 | 包括盘符+路径+文件名+扩展名 |
| 扩展前缀 `\\?\` | 32767 字符 | 需要应用层面显式支持，Unity 默认不启用 |
| Unity 内部 AssetDatabase | ~260 字符 | Unity 对长路径的兼容性因版本而异，不保证 |

**结论**：0-260 字符是「安全区」；260-32767 是「灰色地带」（取决于 Unity 版本和 Windows 注册表设置）；>260 在大多数场景下会直接报错。

### 1.2 当前项目实测数据

扫描了 `/Assets/AssetScene/SceneModels/` 下约 1,900+ 文件：

```
当前 Linux 路径最长 225 字符:
  .../Building_unx/Military_Hangar_group_RAF_A_库房待更新/
      Materails/Workroom_Roof_Metal_CorrugatedBare/
      WorkRoom_Roof_Metal_CorrugatedBare_Normal.tif
```

| Windows 安装路径 | 最长 Linux→Win | 距 260 余量 | 风险 |
|-----------------|---------------|:----------:|:----:|
| `G:/Project_amend_01/` | ~209 字符 | 51 字符 | ✅ 安全 |
| `C:/Users/YuanWentao/Documents/Unity/` | ~256 字符 | **4 字符** | ⚠️ 临界 |
| 加 prefix 8 字符后 | ~264 字符 | **-4** | ❌ 超限 |

### 1.3 三大风险源（严重度从高到低）

| # | 风险源 | 示例 | 最多吞噬字符 |
|---|--------|------|:----------:|
| 🔴 | **深层目录嵌套** | `Military_Hangar_group_RAF_A_库房待更新/Materails/Workroom_Roof_Metal_CorrugatedBare/` — 4层深度 + 长英文名 | 80-100 |
| 🔴 | **工作备注混入目录名** | `Watch_Tower_Battlefield_V 比例有问题 得拆改模型`（中文+空格） | 30-50 |
| 🟡 | **rename 加前缀** | `Road_`→`RoadSide_` 在深层嵌套中 +8 字符 | 8-15 |
| 🟡 | **材质名本身过长** | `WorkRoom_Roof_Metal_CorrugatedBare_Albedo.tif`（43字符） | 自带 |

### 1.4 发现的其他隐患

| 隐患 | 位置 | 影响 |
|------|------|------|
| `库房待更新` | `Military_Hangar_group_RAF_A_` 目录名 | 中文占 3 字节/字符，某些工具可能乱码；持续占用 5 个字符 |
| `比例有问题 得拆改模型` | Watch Tower 子目录 | 含空格，跨工具引用可能断裂 |
| `淘汰` | Railway_CrossingRailing 目录 | 语义不清（淘汰还是待淘汰？） |
| `Materails` | Building_unx 拼写错误 | 不是 "Materials"，但改名会联动破坏 Unity 引用 |

---

## 二、全局应对策略（从预防到修复）

### 2.1 预防层：设计阶段就控制（优先级最高）

```
📐 所有 plan 命令输出映射表后，自动检查 Windows 路径长度

规则：
  1. 映射表中每条 change，计算 after.path 在 Windows 下完整路径长度
  2. 超过 240 字符 → ⚠️ 警告
  3. 超过 255 字符 → ❌ 标记 conflict，不入执行表
  4. 超过 260 字符 → 🚫 拒绝生成，要求用户先缩短目录/文件名

实现位置：unity-file-manager.py plan 命令 → 内部 step 4.5
```

### 2.2 缓解层：目录结构优化（改造源头）

**目标**：把最深嵌套的目录路径缩短 30-50 字符。

#### 2.2.1 优先处理：去掉中文备注（省 10-30 字符）

| 当前路径 | 建议 |
|---------|------|
| `Military_Hangar_group_RAF_A_库房待更新/` | `Military_Hangar_RAF_A/`（去掉中文+group） |
| `Watch_Tower_Battlefield_V 比例有问题 得拆改模型/` | 挪到 scratch 或单独标注，不要留在 Assets 内 |

#### 2.2.2 其次：拼写修正（省 0 字符，但保证可读性）

| 当前 | 修正 |
|------|------|
| `Materails/` | `Materials/` ⚠️ 改名会触发 Unity 引用丢失，必须在 plan→apply 工作流内通过 `.meta` 配对同步修复；不可手动直接改名 |

#### 2.2.3 最后手段：缩写约定（每处省 5-15 字符）

| 原词 | 缩写 | 省 |
|------|------|:--:|
| `Materials` | `Mats` | 6 |
| `Prefab` | `Pfb` | 3 |
| `Textures` | `Tex` | 5 |
| `WorkRoom_Roof_Metal_CorrugatedBare` | `WrRm_Roof_Metal_CorrugBare` | 8 |

> ⚠️ 缩写是最后手段：降低可读性，不建议常态化使用。只在路径确实>250 时针对性应用。

### 2.3 修复层：已超限时的应急处理

| 场景 | 处理 |
|------|------|
| 路径长度 255-260 | ⚠️ 警告 + 建议缩短 |
| 路径长度 >260，但 Unity 可用 | 在 Windows 上启用长路径支持（注册表 `LongPathsEnabled=1` + 应用 manifest） |
| 路径长度 >260，Unity 不可用 | 必须缩短路径（移目录/改名/减少嵌套层） |

### 2.4 自动化：集成到 unity-file-manager

在 `plan` 命令的检查流程中自动加入路径长度检查：

```
plan 输出流程（修订后）：

1. 扫描目录 → 收集所有文件
2. 应用规则 → 生成 before→after 映射
3. 冲突检测 → 同名不同源检查
4. 🆕 路径长度检测 → 模拟 Windows 路径，标记超标条目
5. 输出映射表 → 终端摘要 + JSON + 🆕 路径超标报告
```

---

## 三、当前项目专项评估

### 3.1 各子目录风险排序

| 目录 | 最长路径 | Windows (G:) | Windows (C:\Users\...) | 风险 |
|------|:-----:|:-----:|:-----:|:--:|
| Building_unx | 225 | 209 | ~256 | 🔴 最高 |
| Military | 222 | 206 | ~253 | 🟡 |
| Wall | 157 | 141 | ~188 | 🟢 |
| RoadSide | 143 | 127 | ~174 | 🟢 |
| Railway | — | — | — | 🟡 (含中文"淘汰") |

### 3.2 最危险文件 TOP 5

```
1. WorkRoom_Roof_Metal_CorrugatedBare_Normal.tif  ← 225 字符 (Linux)
2. WorkRoom_Roof_Metal_CorrugatedBare_Height.tif   ← 225 字符
3. WorkRoom_Roof_Metal_CorrugatedBare_Albedo.tif   ← 225 字符
4. Factory_Roof_Metal_CorrugatedBare_Normal.tif    ← 223 字符
5. Factory_Roof_Metal_CorrugatedBare_Albedo.tif    ← 223 字符

共同特征：
  • 都位于 Building_unx/Military_Hangar_group_RAF_A_库房待更新/ 下
  • 目录名含中文+拼写错误(Materails)
  • 材质名超过 40 字符
  • 如果安装到 C:\Users 默认路径 → 全部临界或超限
```

---

## 四、给用户的建议（按优先级）

| # | 操作 | 省字符 | 风险 | 推荐 |
|---|------|:--:|------|:--:|
| 1 | 去掉 `Military_Hangar_group_RAF_A_库房待更新` 的中文部分 → `Military_Hangar_RAF_A` | 12 | 低（仅改目录名，Unity 引用可通过 plan→apply 同步修复） | ✅ 强烈建议 |
| 2 | 安装项目到 G: 盘或短路径（如 `G:/P01/`）而非默认用户目录 | 30+ | 无 | ✅ 强烈建议 |
| 3 | 清理含备注的目录名（中文+空格） | 20-50 | 中（需要同步修复引用） | ✅ 建议 |
| 4 | plan 命令加 Windows 路径检查 | — | 无 | ✅ 立即实施 |
| 5 | rename 时优先缩短而非加长名称 | 不定 | 视具体规则 | ⚠️ 妥协方案 |
