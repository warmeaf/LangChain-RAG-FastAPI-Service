<script setup lang="ts">
import { CheckCircleOutlined, ClusterOutlined, ThunderboltOutlined } from '@ant-design/icons-vue';
import { ref } from 'vue';

// 技术栈数据
const techStacks = ref([
  {
    id: 'component',
    icon: ClusterOutlined,
    title: '组件库与图标方案',
    description:
      '项目组件库采用 ant-design-vue，基于 Ant Design 设计体系，提供高质量的企业级 Vue 3 组件。图标采用 @ant-design/icons-vue，提供与 Ant Design 视觉风格统一的海量图标资源。',
    accent: 'blue',
    subtitle: 'ant-design-vue、@ant-design/icons-vue',
  },
  {
    id: 'style',
    icon: ThunderboltOutlined,
    title: '样式约束方案',
    description:
      '组件库以外的样式约束采用 Tailwind CSS。通过原子化 CSS 类名进行布局、间距、颜色、响应式等样式控制，避免编写自定义 CSS，保持样式的一致性与可维护性。',
    accent: 'emerald',
    subtitle: 'Tailwind CSS v4、Ant Design token',
  },
  {
    id: 'commit',
    icon: CheckCircleOutlined,
    title: '代码提交校验',
    description:
      '代码提交时自动校验，通过 simple-git-hooks 在 pre-commit 阶段触发 lint-staged，对暂存文件执行 Biome 代码检查与格式化。',
    accent: 'amber',
    subtitle: 'Biome、simple-git-hooks、lint-staged',
  },
]);

// 获取 accent 颜色映射
const accentMap: Record<string, { bg: string; text: string }> = {
  blue: { bg: 'var(--colorPrimaryBg)', text: 'var(--colorPrimary)' },
  emerald: { bg: 'var(--colorSuccessBg)', text: 'var(--colorSuccess)' },
  amber: { bg: 'var(--colorWarningBg)', text: 'var(--colorWarning)' },
};
</script>

<template>
    <div class="min-h-screen bg-(--colorBgLayout)">
      <main class="max-w-5xl mx-auto px-(--paddingLG) py-(--marginXXL)">
        <div class="text-center mb-(--marginXXL)">
          <ATypographyTitle :level="2"
            class="tracking-[-0.8px]"
          >
            企业级 Vue3 项目模版
          </ATypographyTitle>
          <ATypographyText
            type="secondary"
            class="!block !text-[length:var(--fontSizeLG)] !mb-(--marginXS) !tracking-widest"
          >
            Ant Design Vue + Tailwind CSS + Ant Design token + TypeScript
          </ATypographyText>
          <ATypographyText
            class="!block !text-(--colorTextTertiary) !text-[length:var(--fontSize)] !tracking-widest"
          >
            适用于快速交付项目
          </ATypographyText>
        </div>
        <ARow :gutter="[24, 24]">
          <ACol
            v-for="stack in techStacks"
            :key="stack.id"
            :xs="24"
            :md="12"
            :lg="8"
          >
            <ACard
              class="!h-full !rounded-(--borderRadiusLG) !shadow-(--boxShadow) !transition-all !duration-300 !ease-(--motionEaseOut)"
              :body-style="{ padding: 'var(--paddingLG)', height: '100%' }"
              :bordered="false"
            >
              <div class="flex flex-col h-full">
                <div class="flex items-start gap-(--margin) !mb-(--marginMD)">
                  <div
                    class="flex items-center justify-center flex-shrink-0 rounded-(--borderRadiusLG) w-(--sizeXXL) h-(--sizeXXL)"
                    :style="{ backgroundColor: accentMap[stack.accent].bg }"
                  >
                    <component
                      :is="stack.icon"
                      class="!text-[length:var(--fontSizeHeading3)]"
                      :style="{ color: accentMap[stack.accent].text }"
                    />
                  </div>
                  <div class="flex-1 min-w-0 !overflow-hidden">
                    <ATypographyText strong class="!block !text-(--colorTextHeading) !text-[length:var(--fontSizeLG)]">
                      {{ stack.title }}
                    </ATypographyText>
                    <ATypographyText
                      v-if="stack.subtitle"
                      block
                      ellipsis
                      class="!text-(--colorTextTertiary) !text-[length:var(--fontSize)] !leading-(--lineHeight)"
                    >
                      {{ stack.subtitle }}
                    </ATypographyText>
                  </div>
                </div>
                <ATypographyParagraph
                  class="!flex-1 !text-(--colorTextSecondary) !text-[length:var(--fontSize)] !leading-(--lineHeight) !mb-0"
                >
                  {{ stack.description }}
                </ATypographyParagraph>
              </div>
            </ACard>
          </ACol>
        </ARow>
      </main>
    </div>
</template>
