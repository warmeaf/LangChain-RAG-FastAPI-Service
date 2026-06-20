---
name: setup-ant-design-vue
description: 在 Vue 3 + TypeScript + Vite 项目中集成最新版 ant-design-vue（v4），配置 unplugin-vue-components 实现自动按需加载。组件和图标在模板中直接使用，无需手动 import。当用户说"集成 ant-design-vue"、"安装 antd vue"、"按需加载 ant-design-vue"、"添加 ant-design-vue"时使用。
---

# 集成 ant-design-vue（v4）+ 自动按需加载

在现有 Vue 3 + TypeScript + Vite 项目中安装 ant-design-vue v4，通过 `unplugin-vue-components` 实现组件和图标的自动按需导入。

## 适用场景

- 用户说"集成 ant-design-vue"、"安装 antd vue"
- 需要为 Vue 3 项目添加 ant-design-vue 组件库
- 要求按需加载，不引入全量组件
- 图标也需要自动按需导入

## 前置条件

- Vue 3 + TypeScript + Vite 项目（包管理器为 pnpm）
- 已配置好的 `vite.config.ts` 和 `tsconfig.app.json`

## 集成步骤

### 1. 确认包管理器

检查项目 lock 文件。若存在 `pnpm-lock.yaml`，使用 pnpm；若无法判断，向用户确认。

以下步骤以 pnpm 为例。若为 npm/yarn，替换对应命令即可。

### 2. 安装依赖

```bash
pnpm add ant-design-vue @ant-design/icons-vue
pnpm add -D unplugin-vue-components
```

### 3. 配置 Vite 插件

编辑 `vite.config.ts`，添加 `Components` 插件和 `AntDesignVueResolver`：

```ts
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import Components from 'unplugin-vue-components/vite'
import { AntDesignVueResolver } from 'unplugin-vue-components/resolvers'

export default defineConfig({
  plugins: [
    vue(),
    Components({
      resolvers: [AntDesignVueResolver({ importStyle: false, resolveIcons: true })],
    }),
  ],
})
```

两个关键配置项：

| 选项 | 值 | 原因 |
|------|-----|------|
| `importStyle` | `false` | ant-design-vue v4 使用 CSS-in-JS 运行时注入样式，无需单独导入组件 CSS 文件。设为 `true`（默认）会尝试从 `ant-design-vue/es/<comp>/style/css` 路径引入，该路径在 v4 中不存在，导致构建失败 |
| `resolveIcons` | `true` | 从 `@ant-design/icons-vue` 自动解析图标组件。默认值 `false`，仅解析 `A` 前缀的组件（`AButton`、`AInput` 等），不解析图标（`SearchOutlined` 等） |

### 4. 导入 base 样式

在入口文件（通常是 `src/main.ts`）中引入 ant-design-vue 的样式重置文件，**放在项目自身样式之前**：

```ts
import { createApp } from 'vue'
import 'ant-design-vue/dist/reset.css'  // 新增：ant-design-vue 样式归一化
import './style.css'
import App from './App.vue'

createApp(App).mount('#app')
```

`reset.css` 的作用：统一各浏览器的默认样式（`box-sizing`、表单元素外观、margin/padding 等），保证 ant-design-vue 组件跨浏览器渲染一致。类似于 `normalize.css`，但是 ant-design-vue 组件库的配套版本。

### 5. 更新 TypeScript 配置

编辑 `tsconfig.app.json`，将自动生成的 `components.d.ts` 加入 `include`：

```json
{
  "include": ["src/**/*.ts", "src/**/*.tsx", "src/**/*.vue", "components.d.ts"]
}
```

`unplugin-vue-components` 首次构建或启动 dev server 时会在项目根目录生成 `components.d.ts`，声明所有用到的组件为 `GlobalComponents`，提供完整的 TypeScript 类型提示。

### 6. 验证集成

运行类型检查和构建：

```bash
pnpm build
```

此命令会先执行 `vue-tsc -b` 进行类型检查，再执行 `vite build`。两者均通过即表示集成成功。

验证 `components.d.ts` 已生成，且包含了 `GlobalComponents` 类型声明。

## 用法（给用户）

集成完成后，模板中直接使用组件，无需手动 import：

```vue
<template>
  <!-- 组件：A 前缀 -->
  <AButton type="primary">按钮</AButton>
  <AInput placeholder="请输入" />
  <AModal v-model:open="visible" title="标题" />

  <!-- 图标：直接在模板中使用 -->
  <SearchOutlined />
  <DownloadOutlined />

  <!-- 按钮中使用图标 -->
  <AButton>
    <template #icon><SearchOutlined /></template>
    搜索
  </AButton>
</template>
```

- 仅实际使用到的组件和图标会被打包，无关代码自动 tree-shake
- 组件样式由 CSS-in-JS 运行时自动注入，无需额外配置
- 图标通过 `@ant-design/icons-vue` 按需加载

## 异常处理

| 现象 | 原因 | 修复 |
|------|------|------|
| 构建报错 `Failed to resolve import "ant-design-vue/es/button/style/css"` | `importStyle` 未设为 `false`，v4 无独立的 `style/css` 路径 | 设置 `importStyle: false`（见步骤 3） |
| 控制台警告 `Failed to resolve component: SearchOutlined` | `resolveIcons` 未设为 `true`，图标组件未被自动解析 | 设置 `resolveIcons: true`（见步骤 3） |
| 组件样式缺失或异常 | `reset.css` 未导入 | 在 `main.ts` 中导入 `ant-design-vue/dist/reset.css`（见步骤 4） |
| 模板中使用组件无 TypeScript 类型提示 | `components.d.ts` 未加入 tsconfig | 将其加入 `tsconfig.app.json` 的 `include`（见步骤 5） |
