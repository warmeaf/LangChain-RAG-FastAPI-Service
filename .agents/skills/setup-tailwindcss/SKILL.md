---
name: setup-tailwindcss
description: 在 Vue 3 + TypeScript + Vite 项目中集成最新版 Tailwind CSS（v4），通过 @tailwindcss/vite 插件实现零配置集成。当用户说"集成 tailwind"、"安装 tailwind css"、"添加 tailwind"、"配置 tailwind"时使用。
---

# 集成 Tailwind CSS v4

在现有 Vue 3 + TypeScript + Vite 项目中安装 Tailwind CSS v4，通过官方 `@tailwindcss/vite` 插件实现零配置集成。v4 无需 `tailwind.config.js` 或 `postcss.config.js`，所有配置通过 CSS 完成。

## 适用场景

- 用户说"集成 tailwindcss"、"安装 tailwind css"、"添加 tailwind"
- 需要为 Vue 3 项目添加 Utility-First CSS 框架
- 需要零配置的 CSS 方案

## 前置条件

- Vue 3 + TypeScript + Vite 项目（包管理器为 pnpm）
- 已配置的 `vite.config.ts`

## 集成步骤

### 1. 确认包管理器

检查项目 lock 文件。若存在 `pnpm-lock.yaml`，使用 pnpm；若无法判断，向用户确认。

以下步骤以 pnpm 为例。若为 npm/yarn，替换对应命令即可。

### 2. 安装依赖

```bash
pnpm add -D tailwindcss @tailwindcss/vite
```

Tailwind CSS v4 拆分为两个包：

| 包 | 作用 |
|---|------|
| `tailwindcss` | CSS 框架本体，包含所有 utility class 和引擎 |
| `@tailwindcss/vite` | Vite 插件，在构建时通过 Lightning CSS 编译 Tailwind，替代 PostCSS |

### 3. 配置 Vite 插件

编辑 `vite.config.ts`，导入并添加 `tailwindcss` 插件，**放在 `vue()` 插件之前**：

```ts
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [
    tailwindcss(),  // 必须在 vue() 之前
    vue(),
  ],
})
```

**插件顺序说明**：`tailwindcss()` 需要最先处理 CSS，确保 Tailwind 的 `@import` 和 `@theme` 指令在其他 CSS 处理器之前被解析。

### 4. 导入 Tailwind

在项目的主 CSS 文件（通常是 `src/style.css`）**最顶部**添加：

```css
@import "tailwindcss";
```

这一行会注入 Tailwind 的所有 utility class、base 样式和 variant。放在最顶部确保它作为基础层，项目自定义样式可以覆盖 Tailwind 默认值。

### 5. 验证集成

运行构建以验证一切正常：

```bash
pnpm build
```

此命令会先执行 `vue-tsc -b` 进行类型检查，再执行 `vite build`。两者均通过即表示集成成功。

**验证要点**：
- 构建输出 CSS 文件大小应比集成前明显增大（包含 Tailwind utilities）
- 开发服务器启动时无 CSS 相关报错

## 使用（给用户）

集成完成后，在 Vue 组件的 `class` 属性中直接使用 Tailwind utility classes：

```vue
<template>
  <div class="flex items-center gap-4 p-6 bg-gray-100 rounded-lg">
    <span class="text-lg font-bold text-blue-600">Hello Tailwind</span>
  </div>
</template>
```

- Tailwind v4 的 JIT 引擎仅生成实际使用到的 utility class，无需配置 `content` 路径
- 无需 `tailwind.config.js`——自定义 theme 通过 CSS `@theme` 指令完成（见下方）

### 自定义 Theme

在 `src/style.css` 中使用 `@theme` 指令扩展默认设计系统：

```css
@import "tailwindcss";

@theme {
  --color-primary: #6b5ce7;
  --color-secondary: #a78bfa;
  --font-sans: 'Inter', system-ui, sans-serif;
}
```

自定义 token 会与 Tailwind 默认 token 合并，自定义优先。直接在 class 中使用：`bg-primary text-secondary font-sans`。

### 暗色模式

v4 默认启用 `prefers-color-scheme` 媒体查询暗色模式变体：

```vue
<div class="bg-white dark:bg-gray-900 text-black dark:text-white">
```

无需额外配置。

## 异常处理

| 现象 | 原因 | 修复 |
|------|------|------|
| 构建报错 `Unknown at rule @tailwind` | 项目中残留 v3 的 `@tailwind base/components/utilities` 指令 | 将所有 `@tailwind` 指令替换为 `@import "tailwindcss"` |
| 构建报错 `Could not resolve "tailwindcss"` | `tailwindcss` 包未安装到 `dependencies` 或 `devDependencies` | 执行 `pnpm add -D tailwindcss @tailwindcss/vite` |
| Tailwind classes 不生效 | `@import "tailwindcss"` 未添加到主 CSS 文件，或未放在最顶部 | 将 `@import "tailwindcss"` 作为 `style.css` 的第一行 |
| 开发服务器报 CSS 解析错误 | 其他 Vite 插件在 Tailwind 之前处理了 CSS | 将 `tailwindcss()` 移到 plugins 数组首位 |
| 自定义颜色/token 不生效 | `@theme` 块放在了 `@import` 之前 | 将 `@theme` 放在 `@import "tailwindcss"` 之后 |

## 与 PostCSS 的关系

Tailwind CSS v4 **不依赖 PostCSS**。`@tailwindcss/vite` 使用 Lightning CSS 直接编译，速度更快。如果项目中存在 `postcss.config.js`，它不会影响 Tailwind 的工作，但 Tailwind 也不会经过 PostCSS 管线。

如果项目同时需要 PostCSS 处理其他 CSS（如 autoprefixer），可以保留 `postcss.config.js`——两者互不干扰。
