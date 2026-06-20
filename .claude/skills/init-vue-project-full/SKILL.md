---
name: init-vue-project-full
description: 完整初始化一个工程化 Vue 3 + TypeScript + Vite 项目，依次集成 Tailwind CSS v4、ant-design-vue v4、Biome 代码校验与自动提交钩子，并生成技术栈展示页。适用于用户说"完整初始化vue项目"、"初始化工程化vue项目"、"创建完整的vue项目"、"初始化vue工程化项目"、"从零搭建vue项目"等场景。
---

# 完整初始化工程化 Vue 3 项目

按顺序执行以下五个阶段，每个阶段依赖前一阶段的产出，**必须严格按序执行，不得跳过或并行**。

---

## 阶段一：项目脚手架（init-vue-project）

执行 `skill://init-vue-project` 的全部步骤：

1. 向用户询问项目名称
2. 在用户指定的工作目录下运行 `pnpm create vite <名称> --template vue-ts`
3. `cd <名称> && pnpm install`
4. 运行 `pnpm build` 验证

**阶段一成功标志**：`vue-tsc -b` 和 `vite build` 均通过。

---

## 阶段二：代码校验（setup-biome）

在阶段一创建的项目目录内，执行 `skill://setup-biome` 的全部步骤：

1. 确认包管理器为 pnpm
2. `pnpm add -D @biomejs/biome simple-git-hooks lint-staged`
3. 从 `node_modules/@biomejs/biome/package.json` 读取实际版本号，创建 `biome.json`，`$schema` 使用该版本号
4. `biome.json` 中 `files.includes` 设为 `["src/**/*.ts", "src/**/*.vue", "src/**/*.css", "src/**/*.json", "package.json"]`
5. 在 `package.json` 中添加脚本：`check`、`fix`、`format`、`lint`
6. 在 `package.json` 中添加 `simple-git-hooks` 和 `lint-staged` 配置，`lint-staged` 的 glob 包含 `src/**/*.{ts,vue,css,json}`
7. 运行 `npx simple-git-hooks` 安装钩子
8. 运行 `pnpm check` 验证

**阶段二成功标志**：`biome check` 通过。

---

## 阶段三：组件库（setup-ant-design-vue）

在项目目录内，执行 `skill://setup-ant-design-vue` 的全部步骤：

1. `pnpm add ant-design-vue @ant-design/icons-vue && pnpm add -D unplugin-vue-components`
2. 编辑 `vite.config.ts`，在 `plugins` 数组中**追加** `Components({ resolvers: [AntDesignVueResolver({ importStyle: false, resolveIcons: true })] })`
3. 在 `src/main.ts` 中新增 `import 'ant-design-vue/dist/reset.css'`（放在 `import './style.css'` 之前）
4. 编辑 `tsconfig.app.json`，将 `"components.d.ts"` 加入 `include` 数组
5. 运行 `pnpm build` 验证

**阶段三成功标志**：构建通过，根目录生成 `components.d.ts`。

---

## 阶段四：样式框架（setup-tailwindcss）

在项目目录内，执行 `skill://setup-tailwindcss` 的全部步骤：

1. `pnpm add -D tailwindcss @tailwindcss/vite`
2. 编辑 `vite.config.ts`，**在 `plugins` 数组最前面**插入 `tailwindcss()`
3. 确保 `vite.config.ts` 最终 plugins 顺序为：`tailwindcss()` → `vue()` → `Components(...)`
4. 在 `src/style.css` 最顶部添加 `@import "tailwindcss";`
5. 运行 `pnpm build` 验证

**阶段四成功标志**：构建通过，构建输出 CSS 包含 Tailwind utilities。

---

## 阶段五：清理与展示

阶段一到四全部成功后，执行以下清理和内容替换。

### 5.1 删除官方模板文件

```bash
rm -f src/components/HelloWorld.vue \
      src/assets/vite.svg \
      src/assets/vue.svg \
      src/assets/hero.png \
      public/icons.svg \
      public/favicon.svg \
      README.md \
      components.d.ts
```

`components.d.ts` 会在下次构建时由 `unplugin-vue-components` 自动重新生成。

### 5.2 使用模板 `src/style.css`

用本 skill 的 `template/style.css` 覆盖项目中的 `src/style.css`：

```bash
cp template/style.css src/style.css
```

### 5.3 更新 `src/main.ts`

确保 `src/main.ts` 的最终内容为：

```ts
import { createApp } from 'vue';
import Antd from 'ant-design-vue';
import 'ant-design-vue/dist/reset.css';
import App from './App.vue';
import './style.css';

const app = createApp(App);
app.use(Antd);
app.mount('#app');
```

### 5.4 更新 `index.html`

将 `index.html` 中的 `<html lang="en">` 改为 `<html lang="zh-CN">`，删除 `<link rel="icon" ... />` 行（favicon.svg 已删除）。

### 5.5 使用模板 `src/App.vue`

用本 skill 的 `template/App.vue` 覆盖项目中的 `src/App.vue`：

```bash
cp template/App.vue src/App.vue
```

### 5.6 复制 Agent 指南模板

将本 skill 的 `template/AGENTS.md` 和 `template/CLAUDE.md` 复制到项目根目录：

```bash
cp template/AGENTS.md AGENTS.md
cp template/CLAUDE.md CLAUDE.md
```

### 5.7 使用模板 `README.md`

用本 skill 的 `template/README.md` 覆盖项目根目录的 `README.md`，并将其中的 `{{ projectName }}` 替换为阶段一中用户输入的项目名称：

```bash
cp template/README.md README.md
```

然后编辑 `README.md`，将 `{{ projectName }}` 替换为实际项目名称。

### 5.8 最终验证

依次执行：

```bash
pnpm check    # Biome 校验通过
pnpm build    # vue-tsc + vite build 均通过
```

两项均通过后，向用户报告：

- 项目路径
- 集成的工具链清单
- 启动命令：`pnpm dev`
- 提交代码时 pre-commit 钩子会自动检查

---

## 注意事项

- **严格顺序**：五个阶段必须依次执行，后一阶段依赖前一阶段的产出。
- **单一工作目录**：所有操作都在阶段一创建的项目目录内进行。
- **错误即停**：任一阶段失败（构建不通过、校验报错），立即向用户报告错误信息，不得继续后续阶段。
- **不跳过**：即使用户说"我已经装了 XXX"，也按完整流程执行，确保配置一致。
- **pnpm 固定**：包管理器固定为 pnpm，不与 npm/yarn 混用。
