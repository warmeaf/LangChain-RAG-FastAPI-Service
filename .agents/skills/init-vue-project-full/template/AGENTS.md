# Agent Guide

此文件是当前项目的权威 Agent 指南。CLAUDE.md 是指向该文件的符号链接，因此 Claude Code 与 Codex 会看到完全相同的内容。请编辑此文件，不要编辑 CLAUDE.md。

## 编码规范 —— 每次改动必须执行

```bash
pnpm check       # Biome 检查
pnpm fix         # Biome 自动修复
pnpm build       # 构建项目，包含类型检查
```

每次修改完成后必须依次运行 `pnpm fix` 和 `pnpm build`，两道都通过才算完成。`pnpm build` 包含 `vue-tsc -b` 类型检查，类型错误会阻止构建。

## 组件使用规范

**组件一律使用 Ant Design Vue，禁止自行实现已有的通用组件。**

### 命名约定：统一使用 `A` 前缀

`app.use(Antd)` 以 `A` 前缀全局注册所有 ant-design-vue 组件（如 `AButton`、`ACard`、`AAvatar`）。
**模板中必须使用 `A` 前缀名，无需在 `<script>` 中手动 import。**

图标由 unplugin-vue-components 自动按需加载，同样无需手动 import。

```html
<template>
  <!-- ant-design-vue 组件：A 前缀，零导入 -->
  <AButton type="primary">提交</AButton>
  <ACard>内容</ACard>

  <!-- 图标：直接使用，零导入 -->
  <DownloadOutlined />
</template>
```

### 禁止在 ant-design-vue 组件上叠加默认 token

ant-design-vue 组件已经内置了 Ant Design 设计规范，**不要在组件上重复添加与其默认值相同的 token class**。

| 冗余写法 | 正确写法 | 原因 |
|---|---|---|
| `<ATypographyText class="text-(--colorText)! text-[length:var(--fontSize)]!">` | `<ATypographyText>` | 组件默认就是 `--colorText` + `--fontSize` |
| `<ATypographyText class="text-(--colorTextSecondary)!">` | `<ATypographyText type="secondary">` | 有 prop 就用 prop，不要用 token 复述 |
| `<ATypographyText strong class="text-(--colorText)! text-[length:var(--fontSize)]!">` | `<ATypographyText strong>` | `strong` 已处理加粗和颜色 |
| `<ADescriptions :label-style="{ color: 'var(--colorTextSecondary)', fontSize: 'var(--fontSize)' }">` | `<ADescriptions>` | 全部是默认值 |

**允许叠加 token 的情况**：
- 组件 prop 无法表达的值（如 `--colorTextTertiary`，没有对应的 `type`）
- 组件不提供的样式维度（间距 `mb-*!`、阴影差异 `shadow-*!`、背景覆盖等）
- 非 ant-design-vue 原生元素（`div`、`p`、`span`、图标等）

## 样式规范

### 核心原则：优先使用设计 token

**样式优先使用 `src/style.css` 的 `@theme` 块中定义的 Ant Design token；仅当 token 体系中不存在合适值时，才使用 Tailwind 内置工具类。**

`src/style.css` 的 `@theme` 块包含 362 个设计 token，涵盖色板（15 色各 10 级）、语义色、中性色、排版、圆角、尺寸、间距、阴影、动效、断点等类别。

### Tailwind CSS v4 引用 token 的语法

```html
<!-- 正确：使用 var(--tokenName) 引用设计 token -->
<div class="bg-(--colorBgLayout) text-(--colorTextSecondary) rounded-(--borderRadiusLG)">
```

```html
<!-- 错误：不要直接写色值或使用 Tailwind 内置颜色（除非 token 中没有对应的） -->
<div class="bg-gray-100 text-gray-500">           <!-- 禁止：浪费 token 体系 -->
<div class="bg-[#f5f5f5] text-[#666]">            <!-- 禁止：魔法值 -->
```

### 特殊情况：length 修饰符

部分 token（如 `--fontSize`、`--marginXS` 等）代表 CSS 长度值。当使用 `[]` 任意值语法且 Tailwind 无法自动推断值类型时，需用 `length:` 前缀显式标注：

```html
<!-- 需要 length 修饰符：字体大小、间距等长度类 token -->
<span class="text-[length:var(--fontSize)]">
<div class="p-[length:var(--paddingXS)]">
```

```html
<!-- 不需要 length 修饰符：颜色、阴影等非长度 token -->
<div class="bg-(--colorBgLayout) text-(--colorText)">
```

> **经验法则**：使用 `()` 简写语法（如 `text-(--fontSize)`）优先；若样式不生效，改用 `[length:var(--token)]` 语法。

### 降级规则

仅当以下情况使用 Tailwind 内置工具类：

1. Token 中无对应值（如 `flex`、`grid`、`gap-4`、`items-center` 等布局类）
2. Token 中不存在所需的特定值
```html
<!-- 正确：在 ant-design-vue 组件上必须加 ! 后缀来提升优先级 -->
<ACard class="rounded-(--borderRadiusLG)! shadow-(--boxShadow)!">
<AButton class="bg-(--colorPrimary)! text-(--colorWhite)!">
```

```html
<!-- 错误：不加 ! 后缀可能被组件内部样式覆盖 -->
<ACard class="rounded-(--borderRadiusLG)">
```

### 禁止事项

- 禁止在 `<style>` 块或 `style.css` 中编写自定义 CSS 类（Tailwind 工具类和 token 变量已覆盖所有需求）
- 禁止使用内联 `style` 属性（除非绑定了动态计算值）
- 禁止使用 `@apply` 抽取自定义类
