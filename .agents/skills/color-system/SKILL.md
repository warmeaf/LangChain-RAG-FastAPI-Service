---
name: color-system
description: 从用户提供的主色调（支持 HSL 或十六进制 hex 色值）生成完整的设计系统配色方案，输出 tokens.json + tokens.css + tokens.js + index.html 可视化演示页到工作目录的 color-system/ 文件夹下。当用户说"生成配色"、"创建配色系统"、"配色方案"、"设计系统颜色"、"color system"、"design tokens"、"根据这个颜色生成"时使用。
---

# 配色系统生成器

从单一主色自动推导出完整的设计系统配色方案，包含 5 个模块（主色系 / 辅助色 & 强调色 / 中性色 / 语义色 / 背景 & 文字 & 边框），支持明暗双主题。

**推导方式**：基于模板 + 大模型自主推导。读取颜色理论指南和结构模板后，大模型自主计算所有 HSL 色值并直接写入 `tokens.json`（不依赖外部脚本生成）。

## 工作流

### Step 1：收集主色

向用户询问主色调。接受以下格式：

- **HSL 格式**：`hsl(H, S%, L%)` 如 `hsl(41, 61%, 56%)`
- **十六进制 hex**：`#RRGGBB` 如 `#D4A845`
- **直接报数值**：H=41, S=61, L=56

🔴 **CHECKPOINT**：确认主色的 H/S/L 值无误后再进入 Step 2。如果用户提供的是模糊描述（如"紫色系""暖色调"），根据色相范围列出 2-3 个示例色值供用户选择，不要直接编造。

### Step 2：hex 转 HSL（如需要）

如果用户输入的是 hex，用以下算法转换为 HSL：

```javascript
// 在 Node.js 中可直接执行此代码块进行转换
function hexToHSL(hex) {
  let r = parseInt(hex.slice(1,3), 16) / 255;
  let g = parseInt(hex.slice(3,5), 16) / 255;
  let b = parseInt(hex.slice(5,7), 16) / 255;
  const max = Math.max(r, g, b), min = Math.min(r, g, b);
  const l = (max + min) / 2;
  let h = 0, s = 0;
  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    switch (max) {
      case r: h = ((g - b) / d + (g < b ? 6 : 0)) / 6; break;
      case g: h = ((b - r) / d + 2) / 6; break;
      case b: h = ((r - g) / d + 4) / 6; break;
    }
  }
  return { h: Math.round(h * 360), s: Math.round(s * 100), l: Math.round(l * 100) };
}
```

### Step 3：确定名称和风格

**由大模型自主确定**，不依赖固定映射表。根据主色的 HSL 值，结合色彩感知和文化联想，自主为以下内容命名：

1. **主色中文名**：从中国传统色或自然意象中提炼一个富有诗意的中文色名（2-3 字），如"靛青""暖金""苔绿""暮紫"等
2. **风格描述**：为配色系统赋予一个风格名，格式为「中文意境词 + 英文意象词」，如"暮光之城 Twilight""自然萃取 Nature Distilled"
3. **辅助色系列名称**（3 个）：
   - **辅助色**：H-5 偏移的邻近类似色，自主命名
   - **强调色**：H-23 偏移向红色方向的强调色，自主命名
   - **互补色**：H+47 偏移的对比色，自主命名

**命名原则**：贴合色相感受，避免机械套用模板。如果不确定，可以用功能名作为兜底（"辅助色""强调色""互补色"）。

将推荐名称展示给用户，允许用户修改。

🔴 **CHECKPOINT**：确认色名和风格描述后再进入核心推导。Step 4 是最大步骤，名称更改后需重新推导，在此确认可避免返工。

### Step 4：读取模板 + 大模型自主推导 tokens.json

这是核心步骤。**不要运行任何脚本**，而是由大模型自主完成颜色推导。

#### 4.1 读取模板文件

同时读取两个模板文件：

```
skill://color-system/templates/color-theory.md    — 颜色推导指南（规则、参考值、公式）
skill://color-system/templates/tokens-schema.json  — 结构模板（完整示例，展示精确的 JSON 格式）
```

#### 4.2 按模块依次推导

对照 `color-theory.md` 中的 5 个模块，逐一计算所有 token 的 HSL 值：

1. **主色系 Primary**（10 步：50-900）— 以用户主色为 step 400 锚点，按 H/S/L 偏移表向亮暗两端延展。明暗模式值相同。
2. **辅助色系列 Secondary Set**（3 行 × 5 步）— 按色相偏移计算三个子系列，S 值按比例缩放（基准 Sref=61），L 值使用固定参考表。明暗模式各有独立值。
3. **中性色 Neutral**（11 步：0-900）— 亮色模式按暖度混合系数（冷色 H>180 → 0.2，暖色 H≤180 → 0.5）混合主色与参考暖灰；暗色模式使用固定值。step 0 和 900 需附加 border 元数据。
4. **语义色 Semantic**（4 行 × 2 步）— **完全使用固定值**，不从主色推导。成功/警告/错误/信息四组，各有 step 50 和 400。
5. **背景 & 文字 & 边框 Surface/Text/Border** — 基于主色 H/S 按比例推导，L 值使用固定参考或直接使用主色值。

#### 4.3 编写 tokens.json

严格参照 `tokens-schema.json` 的结构，将推导出的色值填入，写入 `color-system/tokens.json`。

**关键约束：**
- 所有 H 归一化到 0-360
- S 限制在 1-100，L 限制在 3-98
- `meta.name` 固定为 `"设计系统 — 颜色"`
- `meta.description` 格式：`"主色调：{色名} hsl({H}, {S}%, {L}%) · 风格：{风格中文} {风格英文}"`
- sections 数组恰好 5 个元素，按 01-05 顺序排列
- 每个 section 的 `id` 和 `renderType` 必须与模板一致
- Token key 命名规则：`color-{模块id}-{step}`（如 `color-primary-400`）
- 主色系 row 需含 `showStepNumbers: true` 和 `accentStep: 400`
- 辅助色系列每个 row 需含 `accentStep: 400`
- 语义色的 `steps` 仅为 `[50, 400]`（不是完整色阶）

#### 4.4 备选方案

如果模板文件不可用或推导卡住：

1. **模板不可用**：参考本文件末尾「颜色系统架构」章节的核心规则，5 个模块的约束已在此概括，可据此手动推导
2. **推导卡住（某个模块公式不生效）**：打开 `tokens-schema.json`，从参考暖金主题的已有色值反推 ΔH/ΔS/ΔL 偏移量，再应用到新主色
3. **始终无法完成**：告知用户当前遇到的问题（哪个模块、什么偏差），请用户提供方向或接受部分结果

### Step 5：复制模板文件

```bash
cp skill://color-system/templates/export-tokens.mjs color-system/
cp skill://color-system/templates/index.html color-system/
```

### Step 6：构建 CSS 和 JS

```bash
node color-system/export-tokens.mjs
```

这会读取 `color-system/tokens.json`，在同目录下生成 `tokens.css` 和 `tokens.js`。

### Step 7：验证输出

确认 `color-system/` 目录下存在所有 6 个文件：

| 文件 | 说明 |
|------|------|
| `tokens.json` | 配色数据源（唯一可手动编辑的文件） |
| `export-tokens.mjs` | 构建脚本（修改 JSON 后运行此脚本重新生成 CSS/JS） |
| `tokens.css` | CSS 自定义属性（明暗双主题） |
| `tokens.js` | JS 运行时数据（`window.__TOKENS__`） |
| `README.md` | 使用说明文档（配色系统使用指南） |
| `index.html` | 可视化演示页（可直接在浏览器中打开） |

向用户报告生成的 token 数量和输出目录。建议用户在浏览器中打开 `index.html` 预览配色系统。

### Step 8：复制 README.md

```bash
cp skill://color-system/templates/README.md color-system/
```

### 异常处理

| 步骤 | 触发条件 | 处理动作 | 仍失败则 |
|------|---------|---------|---------|
| Step 1 | 用户输入非标准格式（如"金色"、"偏蓝"） | 根据色相常识自主判断推荐 H 值，列出 2-3 个示例 HSL/hex 供用户选择 | 请用户提供任意格式的具体色值 |
| Step 2 | hex 字符串无效（长度≠7、含非十六进制字符） | 提示格式错误，展示正确示例 `#RRGGBB` | 请用户直接提供 HSL 数值 |
| Step 4 | 模板文件读取失败 | 使用本文件「颜色系统架构」章节的核心规则手动推导 | 告知用户模板缺失，建议检查 skill 安装 |
| Step 5 | `cp` 命令失败 | 手动 Read 模板源文件内容，Write 到 `color-system/` 目标目录 | 检查目标目录权限，告知用户 |
| Step 6 | `node export-tokens.mjs` 报错 | 先验证 JSON 有效性：`node -e "require('./color-system/tokens.json')"`，根据报错修正 | 手动生成 tokens.css（直接拼接 CSS `var()` 语法）和 tokens.js |
| Step 7 | 输出文件缺失 | 回溯缺失文件对应的步骤重新生成（缺 JSON→Step 4，缺 CSS/JS→Step 6，缺 HTML→Step 5，缺 README→Step 8） | 告知用户具体缺失了哪个文件及原因 |

## 使用说明（给用户）

生成完成后，`color-system/` 目录是一个完整的配色系统包：

- **在项目中使用**：引入 `tokens.css`，通过 CSS 变量使用颜色（如 `var(--color-primary-400)`）
- **切换暗色模式**：给 `<html>` 添加 `data-theme="dark"` 属性
- **在 JS 中使用**：引入 `tokens.js`，通过 `window.__TOKENS__` 访问所有颜色数据
- **修改配色**：编辑 `tokens.json`，然后运行 `node export-tokens.mjs` 重新构建 CSS/JS
- **预览配色**：在浏览器中打开 `index.html`

## 颜色系统架构

系统在 HSL 色彩空间中运行，每个颜色存储为 `{ h, s, l }` 对象，包含 `light`（亮色模式）和 `dark`（暗色模式）两套值。

### 5 个模块

1. **主色系**（10 步：50-900）— 从用户提供的主色（step 400）向亮/暗两端延展
2. **辅助色 & 强调色 & 互补色**（各 5 步：50-400）— 色轮上的和声关系色
3. **中性色**（11 步：0-900）— 带暖色调的灰度色板
4. **语义色**（成功/警告/错误/信息）— 标准化的状态色彩，不随主色变化
5. **背景 & 文字 & 边框**— 基于中性色推导的应用层颜色

### 主题切换

CSS 输出三层级联：
- `:root` — 亮色模式（默认值）
- `[data-theme="dark"]` — JS 手动切换暗色模式
- `@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) }` — 跟随系统偏好

## 反例清单（禁止操作）

| # | 不要做 | 原因 | 正确做法 |
|---|--------|------|---------|
| 1 | 跳过 Step 1 直接编造主色 | 配色起点是用户指定的主色，编造产出用户不想要的方案 | 用户未给具体色值时，根据其色相倾向列出 2-3 个示例值供选择 |
| 2 | 不读模板凭记忆推导 | color-theory.md 的偏移表经校准，凭记忆推导必然产生偏差 | 每次推导前先 Read 两个模板文件 |
| 3 | 仅复制亮色的 dark 值 | 暗色模式需独立调整 S/L，复用亮色值导致刺眼或沉闷 | 按 color-theory.md 中明暗模式规则独立计算每 token 的 dark 值 |
| 4 | 修改语义色的色值 | 语义色（成功/警告/错误/信息）是标准化固定值，不从主色推导 | 直接使用 color-theory.md 语义色模块的固定值表 |
| 5 | 在 HSL 外使用其他色彩空间 | 整套推导规则以 HSL 为基础，HEX/RGB 无法直接应用偏移表 | Step 2 先将 HEX 转 HSL，所有推导在 HSL 空间完成 |
| 6 | 跳过 Step 7 验证 | 未验证导致缺失文件或 JSON 格式错误未被发现 | 完成所有步骤后逐项确认 6 个输出文件存在 |

## 模板文件

| 文件 | 用途 |
|------|------|
| `templates/color-theory.md` | 颜色推导指南：5 个模块的推导规则、参考值表、公式和约束条件 |
| `templates/tokens-schema.json` | 结构模板：完整的 tokens.json 示例（暖金主题），展示精确的 JSON 格式 |
| `templates/export-tokens.mjs` | 构建脚本：读取 tokens.json 生成 tokens.css 和 tokens.js |
| `templates/index.html` | 可视化演示页：单文件 HTML，在浏览器中预览完整配色系统 |
| `templates/README.md` | 使用说明模板：复制到 color-system/ 目录作为配色系统使用指南 |
