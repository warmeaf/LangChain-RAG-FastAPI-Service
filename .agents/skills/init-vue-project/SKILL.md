---
name: init-vue-project
description: 使用 pnpm create vite 初始化 Vue 3 + TypeScript 前端项目。固定技术栈为 Vue 3、TypeScript、Vite，包管理器为 pnpm。适用于用户说"创建vue项目"、"初始化vue项目"、"新建一个vue3项目"等场景。
---

# 初始化 Vue 3 + TypeScript 项目

使用 `pnpm create vite` 快速初始化一个 Vue 3 + TypeScript 前端项目，技术栈和包管理器均已固定，无需用户选择。

## 前置条件

- 系统已安装 Node.js（≥18）
- 已全局安装 pnpm

## 执行步骤

### 1. 获取项目名称（必须）

**首先向用户询问项目名称。** 在获得项目名称之前，不得进行任何后续操作。

```
请问项目名称是什么？
```

用户提供的名称将直接作为：
- 项目目录名
- `package.json` 中的 `name` 字段

项目将在当前工作目录下创建。若同名目录已存在，提示用户重新输入。

### 2. 执行脚手架命令

在目标目录下运行：

```bash
pnpm create vite <项目名称> --template vue-ts
```

此命令使用官方 `vue-ts` 模板，固定携带：
- Vue 3（SFC + Composition API）
- TypeScript（含 `vue-tsc` 类型检查）
- Vite（开发服务器 + 构建）

### 3. 安装依赖

进入项目目录安装依赖：

```bash
cd <项目名称>
pnpm install
```

### 4. 验证构建

安装完成后运行构建以验证项目完整性：

```bash
pnpm build
```

此命令会先执行 `vue-tsc -b` 进行类型检查，再执行 `vite build` 进行生产构建。两者均通过即表示项目初始化成功。

### 5. 报告结果

向用户汇报：

- 项目路径
- 脚手架生成的核心文件结构
- 构建验证结果
- 启动开发服务器的命令：`cd <项目名称> && pnpm dev`

## 生成的项目结构

```
<项目名称>/
  src/
    App.vue          # 根组件
    main.ts          # 入口文件
    style.css        # 全局样式
    components/      # 组件目录
    assets/          # 静态资源
  public/            # 公共资源（不经过编译）
  vite.config.ts     # Vite 配置
  tsconfig.json      # TypeScript 根配置
  tsconfig.app.json  # 应用 TypeScript 配置
  tsconfig.node.json # Node 端 TypeScript 配置
  package.json       # 项目元信息与依赖
  index.html         # HTML 入口
```

## 注意事项

- 技术栈已完全固定，**不得**询问用户选择框架、语言或包管理器。
- 唯一需要用户输入的是项目名称，**必须**在开始任何操作前获取。
- 若项目名称包含空格或特殊字符，建议用户使用短横线连接的小写形式（如 `my-vue-app`）。
- 此 skill 仅负责项目初始化，不包含 Tailwind CSS、Biome、路由、状态管理等后续配置。用户可另行使用其他 skill 添加这些工具。
