# DMS 忘记密码与顶部闹铃提醒功能 - 系统设计文档

**文档版本**: v1.0
**作者**: 高见远（架构师）
**日期**: 2025-01-13
**状态**: 待评审

---

## 1. 功能概述

本设计文档涵盖 DMS 设备管理系统的两项功能增强：

| 功能 | 描述 | 优先级 |
|------|------|--------|
| 忘记密码 | 用户可通过邮箱/用户名申请密码重置，通知管理员处理 | P1 |
| 顶部闹铃提醒 | 导航栏顶部显示待审批数量徽章，仅管理员可见 | P1 |

---

## 2. 功能设计方案

### 2.1 忘记密码功能

#### 2.1.1 业务流程

```
┌─────────────┐     点击"忘记密码"      ┌─────────────────┐
│   用户登录页  │ ──────────────────────▶  │ 忘记密码表单页   │
└─────────────┘                         └────────┬────────┘
                                                │
                                    输入用户名/邮箱
                                                │
                                                ▼
                                       ┌─────────────────┐
                                       │ 发送重置请求通知 │
                                       │ 记录到数据库     │
                                       └────────┬────────┘
                                                │
                               ┌────────────────┼────────────────┐
                               │                │                │
                               ▼                ▼                ▼
                        ┌──────────┐    ┌───────────┐    ┌──────────────┐
                        │ email通知 │    │ 管理员后台 │    │ 用户收到确认  │
                        │ (如配置)  │    │ 待办列表   │    │ 等待邮件/消息 │
                        └──────────┘    └───────────┘    └──────────────┘
```

#### 2.1.2 角色可见性

| 角色 | 可申请重置 | 可处理重置请求 |
|------|-----------|---------------|
| admin | ✅ | ✅ |
| qa_manager | ✅ | ❌ |
| equipment_engineer | ✅ | ❌ |
| validation_engineer | ✅ | ❌ |
| archivist | ✅ | ❌ |
| production_supervisor | ✅ | ❌ |
| metrology_engineer | ✅ | ❌ |

#### 2.1.3 设计决策

**方案 A: 邮件通知 + 数据库记录（推荐）**
- 用户输入用户名/邮箱
- 系统记录重置请求到 `password_reset_requests` 表
- 可选：发送邮件通知管理员
- 管理员在用户列表页面处理重置请求

**方案 B: 即时通知 + 管理员弹窗**
- 用户提交后弹出提示
- 管理员登录后自动弹出待处理通知
- 优点：无需邮件配置
- 缺点：管理员必须在线才能看到

**选择方案 A**，理由：
- 支持异步处理，管理员无需实时在线
- 数据库记录便于审计和追踪
- 邮件通知为可选功能，可渐进增强

---

### 2.2 顶部闹铃提醒功能

#### 2.2.1 业务流程

```
┌─────────────────────────────────────────────────────────┐
│                     Context Processor                    │
│  (app.py inject_global_vars)                            │
│                                                          │
│  1. 检查 current_user 是否已认证                         │
│  2. 检查用户角色是否具有审批权限                         │
│  3. 查询 pending_count                                  │
│  4. 注入到模板变量                                       │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                     base.html 顶部栏                     │
│                                                          │
│  <div class="topbar-right">                              │
│    <!-- 仅管理员可见 -->                                  │
│    {% if can_view_approvals %}                          │
│    <button class="topbar-icon-btn" aria-label="通知">    │
│      <i data-lucide="bell"></i>                         │
│      {% if pending_count > 0 %}                         │
│      <span class="notification-badge">{{ pending_count }}</span>
│      {% endif %}                                        │
│    </button>                                             │
│    {% endif %}                                          │
│  </div>                                                 │
└─────────────────────────────────────────────────────────┘
```

#### 2.2.2 角色可见性

根据 `config.py` 中的 `ROLE_PERMISSIONS`，具有 `document_approval` 权限的角色可以查看待审批数量：

| 角色 | 可见性 | 权限说明 |
|------|--------|----------|
| admin | ✅ | document_approval |
| qa_manager | ✅ | document_approval |
| equipment_engineer | ❌ | - |
| validation_engineer | ✅ | document_approval |
| archivist | ❌ | - |
| production_supervisor | ✅ | document_approval |
| metrology_engineer | ❌ | - |

---

## 3. 数据库变更

### 3.1 新增表：password_reset_requests

```sql
CREATE TABLE password_reset_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    username TEXT NOT NULL,
    email TEXT,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending, completed, expired, cancelled
    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP,
    processed_by TEXT,
    new_password_hint TEXT,  -- 记录新密码设置方式
    ip_address TEXT,
    user_agent TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 索引
CREATE INDEX idx_password_reset_status ON password_reset_requests(status);
CREATE INDEX idx_password_reset_user ON password_reset_requests(user_id);
```

### 3.2 新增字段：users.email（可选）

```sql
ALTER TABLE users ADD COLUMN email TEXT;
```

### 3.3 现有数据查询

**待审批数量查询（已存在于 app.py）：**
```sql
SELECT COUNT(*) as total FROM approval_requests WHERE status = 'pending'
```

---

## 4. API 接口列表

### 4.1 忘记密码相关

| 路由 | 方法 | 描述 | 权限 |
|------|------|------|------|
| `/forgot-password` | GET | 显示忘记密码表单 | 公开 |
| `/forgot-password` | POST | 提交重置请求 | 公开 |
| `/admin/password-resets` | GET | 管理员查看重置请求列表 | admin |
| `/admin/password-resets/<id>/reset` | POST | 管理员执行密码重置 | admin |

#### 4.1.1 POST /forgot-password

**请求参数：**
```json
{
  "username": "string (必填)"
}
```

**成功响应 (200)：**
```json
{
  "success": true,
  "message": "密码重置请求已提交，管理员将处理您的请求。"
}
```

**失败响应 (404)：**
```json
{
  "success": false,
  "message": "未找到该用户名，请联系管理员。"
}
```

#### 4.1.2 POST /admin/password-resets/<id>/reset

**请求参数：**
```json
{
  "password": "string (必填, 最小8位)"
}
```

**成功响应 (200)：**
```json
{
  "success": true,
  "message": "密码已重置，用户可使用新密码登录。"
}
```

---

### 4.2 审批数量 API（可选，用于前端轮询）

| 路由 | 方法 | 描述 | 权限 |
|------|------|------|------|
| `/api/pending-count` | GET | 获取待审批数量 | 已登录且有审批权限 |

**响应：**
```json
{
  "pending_count": 5
}
```

---

## 5. 文件修改清单

### 5.1 新增文件

| 文件路径 | 描述 |
|----------|------|
| `templates/forgot_password.html` | 忘记密码表单页面 |
| `templates/admin_password_resets.html` | 管理员密码重置列表页面 |
| `blueprints/password.py` | 密码重置 Blueprint |
| `docs/design-forget-password-alert.md` | 本设计文档 |

### 5.2 修改文件

| 文件路径 | 修改内容 |
|----------|----------|
| `app.py` | 注册 password Blueprint；增强 Context Processor 注入 `can_view_approvals` |
| `templates/login.html` | 添加"忘记密码"链接（第64行后） |
| `templates/base.html` | 顶部栏闹铃图标添加动态徽章和角色权限控制 |
| `database.py` | 添加 `password_reset_requests` 表创建逻辑 |
| `models/user.py` | 添加 `can_view_approvals` 属性方法 |
| `static/css/login.css` | 添加忘记密码链接样式 |

### 5.3 依赖 Blueprint 注册顺序

```python
# app.py 中添加
from blueprints.password import password_bp
app.register_blueprint(password_bp)  # 密码相关路由
```

---

## 6. 实现顺序

### Phase 1: 忘记密码功能

```
阶段1.1: 数据库变更
├── 修改 database.py 添加表结构
└── 运行数据库迁移

阶段1.2: 后端 API
├── 创建 blueprints/password.py
├── 实现 /forgot-password GET/POST
├── 实现 /admin/password-resets 列表
└── 实现 /admin/password-resets/<id>/reset

阶段1.3: 前端页面
├── 创建 templates/forgot_password.html
├── 创建 templates/admin_password_resets.html
└── 修改 templates/login.html 添加链接

阶段1.4: 用户模型增强
└── models/user.py 添加 email 字段支持
```

### Phase 2: 顶部闹铃提醒

```
阶段2.1: Context Processor 增强
├── 修改 app.py inject_global_vars
├── 添加 can_view_approvals 判断
└── 传递 pending_count 仅给有权限用户

阶段2.2: 顶部栏模板修改
├── templates/base.html 第148-152行
├── 添加条件渲染
└── 添加徽章样式
```

### Phase 3: 样式与测试

```
阶段3.1: 样式完善
├── static/css/login.css 添加忘记密码链接样式
└── 徽章徽章动画效果

阶段3.2: 功能测试
├── 忘记密码流程测试
├── 管理员重置密码测试
├── 闹铃提醒权限测试
└── 边界条件测试
```

---

## 7. 待明确事项

### 7.1 忘记密码通知方式

- **邮件通知**：是否需要配置 SMTP？如需，邮件模板格式？
- **站内通知**：是否需要新增"通知"功能模块？
- **当前建议**：先实现数据库记录 + 管理员手动处理，邮件通知作为后续增强

### 7.2 管理员重置密码方式

- **自动生成**：系统自动生成随机密码，通过邮件/站内消息发给用户
- **手动设置**：管理员手动设置新密码
- **当前建议**：采用"手动设置"方式，管理员与用户当面或通过安全渠道确认

### 7.3 "高级管理员"角色定义

需求中提到"admin 和高级管理员"可见闹铃，但当前系统中：
- `admin` 角色已定义
- "高级管理员"未明确定义

**可能的解释：**
1. 仅 `admin` 可见（最简单）
2. `admin` + `qa_manager`（质量相关审批角色）
3. `admin` + 所有具有 `document_approval` 权限的角色

**建议**：采用方案3，与权限系统保持一致

### 7.4 徽章数字上限

当待审批数量超过99时：
- **方案 A**：显示 "99+"（推荐）
- **方案 B**：显示实际数字

### 7.5 闹铃点击行为

点击顶部闹铃图标后的行为：
- **方案 A**：跳转至 `/approvals` 待审批列表
- **方案 B**：显示下拉菜单列出最近待审批项
- **方案 C**：无操作，仅作为状态指示

---

## 8. 风险与约束

### 8.1 安全考虑

| 风险 | 缓解措施 |
|------|----------|
| 暴力破解重置请求 | 添加请求频率限制（同一IP 5分钟内最多3次） |
| 枚举用户名 | 返回相同提示信息，不论成功或失败 |
| 密码重置链接泄露 | 使用一次性令牌，不暴露用户原密码 |

### 8.2 兼容性

- 现有 `users` 表无 `email` 字段，需向后兼容无邮箱用户
- 忘记密码功能应允许仅凭用户名申请

---

## 9. 验收标准

### 9.1 忘记密码功能

- [ ] 用户可在登录页点击"忘记密码"进入表单
- [ ] 输入有效用户名可提交重置请求
- [ ] 数据库正确记录重置请求
- [ ] 管理员可查看待处理重置请求列表
- [ ] 管理员可成功重置用户密码
- [ ] 重置后用户可使用新密码登录

### 9.2 顶部闹铃提醒

- [ ] 仅具有审批权限的角色可见闹铃图标
- [ ] 闹铃徽章正确显示待审批数量
- [ ] 数量为0时隐藏徽章
- [ ] 页面刷新后数据正确更新

---

## 10. 附录

### A. 相关文件路径

```
D:\EquipmentManagement\
├── app.py
├── database.py
├── config.py
├── models/user.py
├── blueprints/
│   ├── auth.py
│   ├── approvals.py
│   ├── users.py
│   └── password.py  [新增]
├── templates/
│   ├── login.html
│   ├── base.html
│   ├── forgot_password.html  [新增]
│   └── admin_password_resets.html  [新增]
├── static/
│   └── css/login.css
└── docs/
    └── design-forget-password-alert.md  [本文档]
```

### B. 参考现有代码

- 忘记密码表单参考：`templates/login.html`（第50-65行表单结构）
- 管理员列表参考：`templates/users.html`
- Context Processor 参考：`app.py`（第64-80行）
- 审计日志参考：`utils/audit.py`

---

**文档结束**
