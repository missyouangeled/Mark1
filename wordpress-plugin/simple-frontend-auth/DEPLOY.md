# Deploy Simple Frontend Auth

## 当前状态

插件代码已经在工作区准备好，但还没有写入线上 WordPress 目录。

目标线上目录：

```text
/var/www/html/wordpress/wp-content/plugins/simple-frontend-auth
```

## 部署步骤

### 方案 A：手动复制

把工作区目录：

```text
/home/missyouangeled/.openclaw/workspace/wordpress-plugin/simple-frontend-auth
```

复制到：

```text
/var/www/html/wordpress/wp-content/plugins/
```

然后去 WordPress 后台启用插件。

### 方案 B：拿到写权限后直接部署

如果之后给贾维斯相应写权限，就可以直接同步过去并继续开发。

## 页面接入示例

- 登录页：`[sfa_login_form show_register_link="true" register_url="register"]`
- 注册页：`[sfa_register_form auto_login="true" show_login_link="true" login_url="login"]`
- 合并页：`[sfa_auth_forms]`

## 推荐页面结构

- `/login` → 放 `[sfa_login_form show_register_link="true" register_url="register"]`
- `/register` → 放 `[sfa_register_form auto_login="true" show_login_link="true" login_url="login"]`
- `/member-center` → 登录后跳转页，未登录时自动跳转到登录页
