# {{ projectName }}

## 技术栈

| 类别 | 方案 |
|------|------|
| 框架 | Vue 3 + TypeScript |
| 构建 | Vite |
| 组件库 | ant-design-vue |
| 图标 | @ant-design/icons-vue |
| 样式 | Tailwind CSS v4 |
| 代码校验 | Biome |
| 提交钩子 | simple-git-hooks + lint-staged |

## 快速开始

```bash
pnpm install
pnpm dev
```

## 代码提交规范

提交时 `pre-commit` 钩子会自动对暂存区的 `.ts`、`.vue`、`.css`、`.json` 文件执行 Biome 检查与格式化，校验通过后方可提交。

```bash
# 手动执行检查
pnpm check

# 自动修复
pnpm fix
```
