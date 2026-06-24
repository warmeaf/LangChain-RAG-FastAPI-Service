#!/usr/bin/env node
/**
 * export-tokens.mjs — 读取 tokens.json，生成 tokens.css 和 tokens.js
 *
 * 用法: node export-tokens.mjs
 * 零外部依赖，仅使用 Node.js 内置模块。
 */

import { readFileSync, writeFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

// ── 1. 读取 tokens.json ──────────────────────────────────────────────
const json = JSON.parse(readFileSync(join(__dirname, 'tokens.json'), 'utf-8'));

// ── 2. 递归收集所有 token ────────────────────────────────────────────
// 返回有序数组 [{ name: "color-primary-50", light: {h,s,l}, dark: {h,s,l} }, ...]
function collectAllTokens(sections) {
  const result = [];
  for (const sec of sections) {
    if (sec.rows) {
      for (const row of sec.rows) {
        if (row.tokens) {
          // 按 steps 顺序收集
          for (const step of row.steps) {
            const key = `color-${row.id}-${step}`;
            const t = row.tokens[key];
            if (t) {
              result.push({ name: key, light: t.light, dark: t.dark });
            }
          }
        }
      }
    }
    if (sec.blocks) {
      for (const block of sec.blocks) {
        if (block.items) {
          for (const item of block.items) {
            result.push({ name: item.name, light: item.light, dark: item.dark });
          }
        }
      }
    }
  }
  return result;
}

const allTokens = collectAllTokens(json.sections);

// ── 3. 辅助：格式化 HSL ──────────────────────────────────────────────
function formatHSL(hsl) {
  return `hsl(${hsl.h}, ${hsl.s}%, ${hsl.l}%)`;
}

// ── 4. 生成 tokens.css ───────────────────────────────────────────────
const CSS_HEADER = `/* ========================================
   设计系统 — 颜色 Tokens
   由 export-tokens.mjs 自动生成
   请勿手动编辑 — 修改 tokens.json 后运行: node export-tokens.mjs
   ======================================== */`;

function generateCSS(tokens) {
  let css = CSS_HEADER + '\n\n';

  // Light mode（默认值）
  css += '/* ---- Light 模式（默认） ---- */\n';
  css += ':root {\n';
  for (const t of tokens) {
    css += `  --${t.name}: ${formatHSL(t.light)};\n`;
  }
  css += '}\n\n';

  // Dark mode（JS 切换）
  css += '/* ---- Dark 模式（JS 手动切换） ---- */\n';
  css += '[data-theme="dark"] {\n';
  for (const t of tokens) {
    css += `  --${t.name}: ${formatHSL(t.dark)};\n`;
  }
  css += '}\n\n';

  // Dark mode（系统偏好，仅在无明确 light 选择时生效）
  css += '/* ---- Dark 模式（系统偏好，无手动选择时自动跟随） ---- */\n';
  css += '@media (prefers-color-scheme: dark) {\n';
  css += '  :root:not([data-theme="light"]) {\n';
  for (const t of tokens) {
    css += `    --${t.name}: ${formatHSL(t.dark)};\n`;
  }
  css += '  }\n';
  css += '}\n';

  return css;
}

writeFileSync(join(__dirname, 'tokens.css'), generateCSS(allTokens), 'utf-8');

// ── 5. 生成 tokens.js ────────────────────────────────────────────────
const JS_HEADER = `// tokens.js — 由 export-tokens.mjs 自动生成，请勿手动编辑`;

function generateJS(meta, sections) {
  // 直接嵌入 sections 数据（包含完整的 token 定义）
  let js = JS_HEADER + '\n';
  js += '(function() {\n';
  js += '  var data = ' + JSON.stringify({ meta: meta, sections: sections }) + ';\n';
  js += '\n';
  js += '  // 辅助方法\n';
  js += '  data.formatHSL = function(hsl) {\n';
  js += '    return \'hsl(\' + hsl.h + \', \' + hsl.s + \'%, \' + hsl.l + \'%)\';\n';
  js += '  };\n';
  js += '\n';
  js += '  // 按 CSS 变量名查找 token 的当前模式色值\n';
  js += '  data.getTokenValue = function(cssVarName, mode) {\n';
  js += '    mode = mode || \'light\';\n';
  js += '    for (var si = 0; si < data.sections.length; si++) {\n';
  js += '      var sec = data.sections[si];\n';
  js += '      // 检查 rows\n';
  js += '      if (sec.rows) {\n';
  js += '        for (var ri = 0; ri < sec.rows.length; ri++) {\n';
  js += '          var row = sec.rows[ri];\n';
  js += '          if (row.tokens && row.tokens[cssVarName]) {\n';
  js += '            return row.tokens[cssVarName][mode];\n';
  js += '          }\n';
  js += '        }\n';
  js += '      }\n';
  js += '      // 检查 blocks\n';
  js += '      if (sec.blocks) {\n';
  js += '        for (var bi = 0; bi < sec.blocks.length; bi++) {\n';
  js += '          var block = sec.blocks[bi];\n';
  js += '          if (block.items) {\n';
  js += '            for (var ii = 0; ii < block.items.length; ii++) {\n';
  js += '              if (block.items[ii].name === cssVarName) {\n';
  js += '                return block.items[ii][mode];\n';
  js += '              }\n';
  js += '            }\n';
  js += '          }\n';
  js += '        }\n';
  js += '      }\n';
  js += '    }\n';
  js += '    return null;\n';
  js += '  };\n';
  js += '\n';
  js += '  window.__TOKENS__ = data;\n';
  js += '})();\n';

  return js;
}

writeFileSync(join(__dirname, 'tokens.js'), generateJS(json.meta, json.sections), 'utf-8');

// ── 6. 输出统计 ──────────────────────────────────────────────────────
console.log(`✅ 已生成 tokens.css（${allTokens.length} 个 token）`);
console.log(`✅ 已生成 tokens.js`);
