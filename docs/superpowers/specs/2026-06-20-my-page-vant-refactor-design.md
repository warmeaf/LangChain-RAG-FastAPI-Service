# My.vue Vant UI 重构设计

**日期**: 2026-06-20
**范围**: `front/src/views/My.vue` 单文件

## 目标

将 My.vue 页面中自定义 HTML 标签替换为 Vant UI 组件，与项目中 Profile.vue、Settings.vue 保持一致的组件使用模式。

## 改动

### 模板

| 当前（自定义标签） | 重构后（Vant 组件） |
|---|---|
| `div.user-info` (含 click/样式) | `van-cell-group inset` + `van-cell` (center, is-link) |
| `div.avatar` + `div.avatar-img` | `#icon` slot 内直接放 `van-image` |
| `div.avatar-letter` (v-else 兜底) | 保留 + `van-image` `#error` slot 增强兜底 |
| `div.info` / `div.username` / `div.desc` | `#title` / `#label` slot |
| `van-icon name="arrow"` | `is-link` 属性自带箭头 |

未登录态同理，但无 `is-link` 和 `@click`，`#label` 放登录/注册按钮。

### CSS

- 删除：`.user-info`、`.arrow-icon`、`.avatar`、`.avatar-img`、`.info`、`.username`、`.desc`
- 新增：`.user-info-group :deep(.van-cell)` — 渐变背景/圆角12px/阴影/padding
- 新增：`.user-info-group :deep(.van-cell__icon)` — 适配72px头像间距
- 新增：`.cell-username`、`.cell-bio` — 文字样式
- 保留：`.avatar-letter`、`.menu-list :deep(.van-cell)`、容器与导航栏样式

### 不变

- `<script setup>` 逻辑零改动
- `van-nav-bar`、`tab-bar`、菜单区 `van-cell-group` 不变
