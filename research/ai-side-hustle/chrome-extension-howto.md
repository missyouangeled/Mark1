# 路线一：Chrome 插件 · 实操全流程

> 整理日期：2026-06-15
> 数据来源：Google 官方文档、Extension Radar、Fungies.io、ExtensionPay、CSDN、知乎

---

## 一、注册 Chrome Web Store 开发者账号

### 要准备什么？

| 项目 | 说明 |
|------|------|
| Google 账号 | 用你现有的 Gmail 即可 |
| **$5 美元** | 一次性注册费，终身有效 |
| Visa/Mastercard 卡 | ⚠️ **中国大陆银行卡不被 Chrome Web Store 表单接受** |

### ⚠️ 最大的坑：国内卡怎么付这 $5？

Chrome Web Store 的支付表单**不支持中国大陆银行卡**。你有几条路：

1. **招商银行/中国银行 Visa/Mastercard 信用卡**（实测可行）：卡面上有 Visa 或 Mastercard 标志的双币/全币信用卡可以通过
2. **虚拟 Visa 卡**：Depay、OneKey Card 等可以生成虚拟 Visa 卡，充 USDT 转美元
3. **找人代付**：找个有外币信用卡的朋友帮你付 $5（就五美元，不难开口）

### 注册步骤

1. 打开 https://chrome.google.com/webstore/devconsole
2. 登录你的 Google 账号
3. 同意开发者协议和隐私政策
4. 填地址信息（用拼音填中国地址即可，不需要国外地址）
5. 支付 $5 注册费
6. 完成！不会再重复收费

---

## 二、开发一个插件（最小流程）

### 最小文件结构

```
my-extension/
├── manifest.json    ← 插件配置文件（必需）
├── popup.html       ← 弹窗页面
├── popup.js         ← 弹窗逻辑
├── background.js    ← 后台运行脚本
├── content.js       ← 注入到页面的脚本
├── icon16.png       ← 图标
├── icon48.png
└── icon128.png
```

### manifest.json 最简模板

```json
{
  "manifest_version": 3,
  "name": "你的插件名",
  "version": "1.0.0",
  "description": "插件描述",
  "icons": {
    "16": "icon16.png",
    "48": "icon48.png",
    "128": "icon128.png"
  },
  "action": {
    "default_popup": "popup.html",
    "default_icon": "icon48.png"
  },
  "permissions": ["storage"],
  "background": {
    "service_worker": "background.js"
  }
}
```

### 本地测试

1. Chrome 地址栏输入 `chrome://extensions`
2. 打开右上角「开发者模式」
3. 点击「加载已解压的扩展程序」，选择你的文件夹
4. 测试功能 → 改代码 → 点刷新按钮

---

## 三、上传到 Chrome Web Store

### 上传步骤

1. 进入 https://chrome.google.com/webstore/devconsole
2. 点击「新增项」
3. 把你的插件文件夹打包成 `.zip` 上传
4. 填写商店信息：
   - **名称**：插件的显示名称
   - **描述**：用英文写（必须），也可以加中文
   - **类别**：选最贴近的
   - **截图**：至少 1 张 1280x800 的截图
   - **小图**：Icon 至少 128x128
5. 提交审核

### 审核时间

- 通常 **1-3 个工作日**
- 首次提交可能慢一些（Google 人工审核）
- 更新提交通常几小时内通过

### 常见审核被拒原因

| 原因 | 怎么避免 |
|------|---------|
| 权限声明过多但不必要 | 只申请你真正用到的权限 |
| 描述与实际功能不符 | 诚实描述，不要夸大 |
| 缺少隐私政策 | 如果你的插件收集任何数据，必须提供隐私政策链接 |
| Manifest V2（已废弃）| 必须使用 Manifest V3 |
| 图标尺寸不对 | 必须提供 128x128 图标 |

---

## 四、收款——怎么让用户付钱？

### 🔴 关键事实：Google 不提供支付系统！

Chrome Web Store Payments（Google 自带的支付服务，抽 5%）**已经关闭了**。现在你必须自己搞定支付。

### 你有三条路：

#### 方案 A：ExtensionPay（最省心，推荐新手）

| 项目 | 说明 |
|------|------|
| 是什么 | 专为 Chrome 插件开发者做的支付工具 |
| 费用 | 免费使用，**从交易中抽成**（比 Stripe 贵一点但省时间） |
| 功能 | 一次性购买 + 订阅 + License 管理 + 试用期 |
| 接入 | 几行代码，HTTP 请求即可 |
| 收款 | 打到你的银行/PayPal 账户 |
| 网址 | https://extensionpay.com |

```javascript
// ExtensionPay 接入示例
const extpay = new ExtPay('your-extension-id');
extpay.startBackground();

// 检查用户是否已付费
extpay.getUser().then(user => {
  if (user.paid) {
    // 解锁高级功能
  }
});

// 发起支付
extpay.openPaymentPage();
```

#### 方案 B：Paddle（MoR，全球税收合规）

| 项目 | 说明 |
|------|------|
| 是什么 | 全球 Merchant of Record，帮你处理 VAT/GST/销售税 |
| 费用 | 5% + $0.50/笔 |
| 优点 | 你完全不用管税，Paddle 代扣代缴 |
| 收款 | 电汇到国内银行/PayPal |
| 缺点 | 需要审核，不是所有人都能过 |
| 网址 | https://paddle.com |

#### 方案 C：Lemon Squeezy（轻量 MoR）

| 项目 | 说明 |
|------|------|
| 费用 | 5% + $0.50 + 1.5% 国际卡 |
| 优点 | 对个人开发者友好、自带邮件营销、PayPal 收款 |
| 缺点 | 2024 年被 Stripe 收购后更新变慢 |
| 收款 | PayPal 到国内账户 |
| 网址 | https://lemonsqueezy.com |

### ⚠️ 你不需要国外信用卡！

你只需要：
- 一个能收 PayPal 的账户（用国内身份证就能注册 PayPal 中国）
- 或者一张国内 Visa/Mastercard 借记卡来付 $5 注册费
- **不需要**国外信用卡、国外银行账户、国外公司

---

## 五、定价怎么设？

### 常见定价模型

| 模式 | 价格 | 适合 |
|------|------|------|
| 免费增值 | 基础免费 + Pro $4.99-9.99/月 | 功能型插件 |
| 一次性买断 | $2.99-19.99 | 简单工具 |
| 按次收费 | $0.5-2/次 | API 代调用类 |
| 企业版 | $29-99/月 | B 端专用 |

### 真实参考数据
- 1 万活跃用户 + 免费增值模式 = **$2,000-10,000/月**
- 一个开发者靠生产力插件：8,000 付费用户 × $4.99 = **$4,200/月**

---

## 六、全部成本一览

| 项目 | 金额 | 频率 |
|------|------|------|
| Chrome Web Store 注册 | $5 | 一次性 |
| ExtensionPay/Paddle/LemonSqueezy | 0 固定费 | 按交易抽 5% |
| 域名（做官网/隐私政策页） | ~$10/年 | 可选 |
| **总启动成本** | **$5-15** | — |

---

## 七、流程图

```
你有想法
  ↓
开发（AI 辅助 1-3 天写完）
  ↓
本地测试（chrome://extensions → 加载已解压）
  ↓
支付 $5 注册开发者
  ↓
上传 .zip → 填信息 → 提交审核
  ↓
等 1-3 天审核通过
  ↓
接入 ExtensionPay/LemonSqueezy
  ↓
上架 → 用户下载 → 你收款 💰
```
