# Simple Frontend Auth

一个最小可用版的 WordPress 前台登录/注册插件。

## 当前功能

- 前台登录表单
- 前台注册表单
- 注册时用户名/邮箱/密码校验
- 注册成功后可自动登录
- 登录后显示当前用户和退出按钮
- 短代码接入，无需改 WordPress 核心

## 文件结构

```text
simple-frontend-auth/
├── assets/
│   └── simple-frontend-auth.css
├── simple-frontend-auth.php
└── README.md
```

## 安装方法

把整个 `simple-frontend-auth` 文件夹放到：

```text
wp-content/plugins/
```

然后在 WordPress 后台启用插件。

## 短代码

### 1. 单独登录表单

```text
[sfa_login_form]
```

可选参数：

```text
[sfa_login_form redirect="/member-center" show_register_link="true" register_url="/register"]
```

### 2. 单独注册表单

```text
[sfa_register_form]
```

可选参数：

```text
[sfa_register_form redirect="/member-center" auto_login="true" show_login_link="true" login_url="/login"]
```

### 3. 登录 + 注册双栏

```text
[sfa_auth_forms]
```

可选参数：

```text
[sfa_auth_forms login_redirect="/member-center" register_redirect="/member-center" auto_login="true"]
```

## 下一步建议

下一版可以继续加：

- 邮箱验证
- 忘记密码 / 重置密码
- 自定义用户角色
- 登录后按角色跳转
- 防暴力破解 / 简单限流
- Google reCAPTCHA / 图形验证码
