---
name: setup-biome
description: 为新项目配置 Biome 代码检查与格式化，集成 git pre-commit 钩子。包括 biome.json 配置、package.json 脚本，以及 simple-git-hooks + lint-staged 集成。
---

# 配置 Biome

初始化 Biome 作为项目的统一代码格式化与检查工具，并通过 git 钩子实现提交前自动检查。

## 适用场景

在以下情况下使用：
- 用户说"配置 biome"、"安装 biome"、"初始化 biome"
- 需要为新建或现有项目添加代码检查/格式化
- 需要 git pre-commit 钩子用于代码质量检查
- 需要用 Biome 替代 ESLint + Prettier

## 前置条件

- 带有 `package.json` 的 Node.js 项目
- 已初始化的 Git 仓库

## 配置步骤

### 1. 选择包管理器

首先，检测项目使用的包管理器（优先看 lock 文件：`pnpm-lock.yaml` → pnpm，`yarn.lock` → yarn，`package-lock.json` → npm）。若无法判断，向用户询问选择 npm、pnpm 还是 yarn。

### 2. 安装依赖

确定包管理器后，执行对应的安装命令：

| 包管理器 | 安装命令 |
|---------|---------|
| npm     | `npm install -D @biomejs/biome simple-git-hooks lint-staged` |
| pnpm    | `pnpm add -D @biomejs/biome simple-git-hooks lint-staged` |
| yarn    | `yarn add -D @biomejs/biome simple-git-hooks lint-staged` |

### 3. 创建 `biome.json`

**在创建 `biome.json` 之前**，先从 `node_modules/@biomejs/biome/package.json` 读取实际安装的 Biome 版本号，然后将 `$schema` 字段中的版本替换为该版本号。例如安装的是 `1.9.4`，则 `$schema` 应为：

```
https://biomejs.dev/schemas/1.9.4/schema.json
```

在项目根目录创建 `biome.json`，使用以下配置。请根据项目的源码目录调整 `files.includes`。

```json
{
  "$schema": "https://biomejs.dev/schemas/<VERSION>/schema.json",
  "vcs": {
    "enabled": true,
    "clientKind": "git",
    "useIgnoreFile": true
  },
  "files": {
    "ignoreUnknown": false,
    "includes": [
      "src/**/*.ts",
      "src/**/*.vue",
      "src/**/*.json",
      "package.json"
    ]
  },
  "formatter": {
    "enabled": true,
    "indentStyle": "tab",
    "indentWidth": 2,
    "lineWidth": 100,
    "lineEnding": "lf"
  },
  "linter": {
    "enabled": true,
    "rules": {
      "recommended": true,
      "correctness": {
        "noUnusedVariables": "error",
        "noUnusedImports": "error"
      },
      "suspicious": {
        "noDebugger": "error",
        "noConsole": "warn"
      },
      "style": {
        "useConst": "error",
        "useTemplate": "warn"
      }
    }
  },
  "javascript": {
    "formatter": {
      "quoteStyle": "single",
      "semicolons": "always",
      "trailingCommas": "all",
      "arrowParentheses": "always"
    }
  },
  "json": {
    "formatter": {
      "trailingCommas": "none"
    }
  },
  "html": {
    "experimentalFullSupportEnabled": true
  },
  "overrides": [
    {
      "includes": ["**/*.vue"],
      "linter": {
        "rules": {
          "style": {
            "useConst": "off",
            "useImportType": "off"
          },
          "correctness": {
            "noUnusedVariables": "off",
            "noUnusedImports": "off"
          }
        }
      }
    }
  ],
  "assist": {
    "enabled": true,
    "actions": {
      "source": {
        "organizeImports": "on"
      }
    }
  }
}
```

**需要关注的关键自定义项：**
- `files.includes`：更新 glob 模式以匹配你的源码文件（例如 React 项目用 `src/**/*.tsx`，monorepo 用 `packages/*/src/**/*.ts`）
- `formatter.indentStyle`：`"tab"` 或 `"space"`
- `formatter.lineWidth`：默认 `100`，可按团队偏好调整
- `javascript.formatter.quoteStyle`：`"single"` 或 `"double"`

### 4. 添加 npm 脚本

在 `package.json` 中添加以下脚本：

```json
{
  "scripts": {
    "check": "biome check",
    "fix": "biome check --write",
    "format": "biome format --write",
    "lint": "biome lint --write"
  }
}
```

- `check`：检查代码质量，不修改文件（CI 中复用此命令）
- `fix`：自动修复所有可修复的问题
- `format`：仅格式化，不运行 lint 规则
- `lint`：仅运行 lint 并修复

### 5. 配置 Git 钩子

在 `package.json` 中添加以下内容以启用 pre-commit 钩子：

```json
{
  "simple-git-hooks": {
    "pre-commit": "npx lint-staged"
  },
  "lint-staged": {
    "src/**/*.{ts,vue,json}": [
      "biome check --write --no-errors-on-unmatched"
    ]
  }
}
```

**重要提示：** 修改 `simple-git-hooks` 配置后，请运行：

```bash
npx simple-git-hooks
```

此命令会将实际的钩子文件安装到 `.git/hooks/` 中。

### 6. 验证配置

运行检查以确保 Biome 正常工作：

```bash
npm run check
```

进行一次小改动并运行以下命令来测试 pre-commit 钩子：

```bash
git add .
git commit -m "test: 验证 biome pre-commit 钩子"
```

## 项目特定覆盖配置

### Vue 项目
基础配置已包含 Vue 覆盖规则（`**/*.vue`），其中禁用了某些与 Vue 单文件组件不兼容的规则。如果使用 React，请移除 Vue 覆盖规则，并根据需要添加 React 专属规则。

### Monorepo 项目
对于 monorepo，可以选择：
- 使用根目录的 `biome.json`，设置 `"includes": ["packages/*/src/**/*"]`
- 或在各个 package 中创建独立的 `biome.json`，从每个 package 目录运行 Biome

### CI 集成
`check` 脚本同时适用于本地开发和 CI 流水线。它只检查不写入，在有违规时使构建失败：

```yaml
# GitHub Actions 步骤示例
- name: 代码检查与格式检查
  run: npm run check
```

## 常见问题

**钩子未触发：** 修改 `simple-git-hooks` 配置后，务必重新运行 `npx simple-git-hooks`。

**文件未被检查：** 验证 `lint-staged` 中的 glob 模式是否匹配你的文件路径。可使用 `npx lint-staged --debug` 进行排查。

**Biome 版本不匹配：** `biome.json` 中的 `$schema` 版本必须与安装的 `@biomejs/biome` 版本一致。遇到 schema 校验错误时，检查 `node_modules/@biomejs/biome/package.json` 中的 `version` 字段，确保 schema URL 中的版本号与之匹配。
