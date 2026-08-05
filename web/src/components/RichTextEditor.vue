<!--
  Love Journal - a private journal + blog + real-time interaction platform for couples.
  Copyright (C) 2026 Love Journal Contributors

  This program is free software: you can redistribute it and/or modify
  it under the terms of the GNU Affero General Public License as published
  by the Free Software Foundation, version 3 of the License.

  This program is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU Affero General Public License for more details.

  You should have received a copy of the GNU Affero General Public License
  along with this program.  If not, see <https://www.gnu.org/licenses/>.
-->

<template>
  <div class="rich-editor-wrapper">
    <div ref="editorRef" class="vditor-container"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue';
import Vditor from 'vditor';
import 'vditor/dist/index.css';
import { useI18n } from 'vue-i18n';

const { t } = useI18n();

const props = defineProps({
  modelValue: {
    type: String,
    default: ''
  },
  placeholder: {
    type: String,
    default: ''
  },
  height: {
    type: String,
    default: '500px'
  },
  mode: {
    type: String,
    default: 'wysiwyg', // wysiwyg, ir (即时渲染), sv (分屏预览)
    validator: (value) => ['wysiwyg', 'ir', 'sv'].includes(value)
  },
  toolbar: {
    type: Array,
    default: () => [
      'emoji',
      'headings',
      'bold',
      'italic',
      'strike',
      '|',
      'line',
      'quote',
      'list',
      'ordered-list',
      'check',
      '|',
      'code',
      'inline-code',
      'link',
      'table',
      '|',
      'upload',
      '|',
      'undo',
      'redo',
      '|',
      'edit-mode',
      'fullscreen',
      'preview',
      'outline',
      'help'
    ]
  },
  uploadUrl: {
    type: String,
    default: null
  }
});

const emit = defineEmits(['update:modelValue', 'change', 'upload']);

const editorRef = ref(null);
let vditor = null;

onMounted(() => {
  if (!editorRef.value) return;

  const options = {
    height: props.height,
    placeholder: props.placeholder || t("richTextEditor.placeholder"),
    mode: props.mode,
    toolbar: props.toolbar,
    cache: {
      enable: false
    },
    counter: {
      enable: true,
      type: 'markdown'
    },
    preview: {
      theme: {
        current: 'light'
      },
      hljs: {
        enable: true,
        style: 'github'
      },
      markdown: {
        toc: true,
        mark: true,
        footnotes: true,
        autoSpace: true
      }
    },
    hint: {
      emoji: {
        '+1': '👍',
        '-1': '👎',
        'heart': '❤️',
        'smile': '😊',
        'tada': '🎉',
        'thinking': '🤔',
        'cry': '😢',
        'laughing': '😆'
      },
      extend: [
        {
          key: '@',
          hint: () => {
            return [];
          }
        }
      ]
    },
    tab: '\t',
    typewriterMode: false,
    toolbarConfig: {
      pin: true // 固定工具栏
    },
    input: (value) => {
      emit('update:modelValue', value);
      emit('change', value);
    },
    after: () => {
      if (props.modelValue) {
        vditor.setValue(props.modelValue);
      }
      
      // 修复工具提示被遮盖的问题
      setTimeout(() => {
        // 添加全局样式来修复工具提示
        const style = document.createElement('style');
        style.id = 'vditor-tooltip-fix';
        style.textContent = `
          .vditor-tooltipped::before,
          .vditor-tooltipped::after {
            z-index: 999999 !important;
          }
          .vditor-toolbar {
            z-index: 999998 !important;
          }
        `;
        
        // 如果样式还不存在，则添加
        if (!document.getElementById('vditor-tooltip-fix')) {
          document.head.appendChild(style);
        }
        
        // 监听工具栏按钮的鼠标事件，动态调整提示位置
        const toolbarItems = document.querySelectorAll('.vditor-toolbar__item');
        toolbarItems.forEach(item => {
          item.addEventListener('mouseenter', () => {
            // 确保工具提示在最上层
            const tooltipped = item.querySelector('.vditor-tooltipped');
            if (tooltipped) {
              tooltipped.style.zIndex = '999999';
            }
          });
        });
      }, 100);
    }
  };

  // 如果提供了上传 URL，配置上传功能
  if (props.uploadUrl) {
    options.upload = {
      url: props.uploadUrl,
      max: 10 * 1024 * 1024, // 10MB
      accept: 'image/*',
      fieldName: 'file',
      format: (files, responseText) => {
        try {
          const response = JSON.parse(responseText);
          if (response.url) {
            return JSON.stringify({
              msg: '',
              code: 0,
              data: {
                errFiles: [],
                succMap: {
                  [files[0].name]: response.url
                }
              }
            });
          }
        } catch (_error) {
          // Preserve the editor response when it is not valid JSON.
        }
        return responseText;
      },
      error: (msg) => {
        emit('upload', { success: false, error: msg });
      },
      success: (editor, msg) => {
        emit('upload', { success: true, data: msg });
      }
    };
  }

  vditor = new Vditor(editorRef.value, options);
});

// 监听外部值变化
watch(() => props.modelValue, (newValue) => {
  if (vditor && vditor.getValue() !== newValue) {
    vditor.setValue(newValue || '');
  }
});

onBeforeUnmount(() => {
  if (vditor) {
    vditor.destroy();
    vditor = null;
  }
});

// 暴露方法给父组件
defineExpose({
  getValue: () => vditor?.getValue() || '',
  setValue: (value) => vditor?.setValue(value || ''),
  focus: () => vditor?.focus(),
  blur: () => vditor?.blur(),
  disabled: () => vditor?.disabled(),
  enable: () => vditor?.enable(),
  getHTML: () => vditor?.getHTML() || ''
});
</script>

<style scoped>
.rich-editor-wrapper {
  width: 100%;
  border-radius: 8px;
  overflow: visible;
  position: relative;
  background: white;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.vditor-container {
  width: 100%;
  position: relative;
}

/* 自定义 Vditor 主题以匹配项目风格 */
:deep(.vditor) {
  border: 1px solid rgba(148, 163, 184, 0.3);
  border-radius: 8px;
  overflow: visible;
}

:deep(.vditor-toolbar) {
  background: linear-gradient(to bottom, #fafbfc, #f6f8fa);
  border-bottom: 1px solid rgba(148, 163, 184, 0.3);
  padding: 8px;
}

:deep(.vditor-toolbar__item) {
  border-radius: 6px;
  transition: all 0.2s ease;
}

:deep(.vditor-toolbar__item:hover) {
  background: rgba(143, 155, 255, 0.1);
}

:deep(.vditor-toolbar__item--current) {
  background: rgba(143, 155, 255, 0.2);
}

:deep(.vditor-content) {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', sans-serif;
}

:deep(.vditor-reset) {
  font-size: 16px;
  line-height: 1.8;
  color: #1e293b;
}

:deep(.vditor-reset h1),
:deep(.vditor-reset h2),
:deep(.vditor-reset h3) {
  color: #0f172a;
  font-weight: 700;
  margin-top: 1.5em;
  margin-bottom: 0.5em;
}

:deep(.vditor-reset blockquote) {
  border-left: 4px solid #8f9bff;
  background: rgba(143, 155, 255, 0.08);
  padding: 0.8rem 1.2rem;
  border-radius: 0 8px 8px 0;
  color: #3730a3;
}

:deep(.vditor-reset code) {
  background: rgba(143, 155, 255, 0.1);
  color: #6366f1;
  padding: 0.2em 0.4em;
  border-radius: 4px;
  font-size: 0.9em;
}

:deep(.vditor-reset pre) {
  background: #1e293b;
  border-radius: 8px;
  padding: 1rem;
}

:deep(.vditor-reset pre code) {
  background: transparent;
  color: #e2e8f0;
  padding: 0;
}

:deep(.vditor-reset a) {
  color: #8f9bff;
  text-decoration: none;
  border-bottom: 1px solid rgba(143, 155, 255, 0.3);
  transition: all 0.2s ease;
}

:deep(.vditor-reset a:hover) {
  color: #6366f1;
  border-bottom-color: #6366f1;
}

:deep(.vditor-reset img) {
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  max-width: 100%;
}

:deep(.vditor-reset table) {
  border-collapse: collapse;
  width: 100%;
  margin: 1em 0;
}

:deep(.vditor-reset th),
:deep(.vditor-reset td) {
  border: 1px solid rgba(148, 163, 184, 0.3);
  padding: 0.6em 1em;
}

:deep(.vditor-reset th) {
  background: rgba(143, 155, 255, 0.1);
  font-weight: 600;
  color: #0f172a;
}

:deep(.vditor-counter) {
  color: #94a3b8;
  font-size: 0.85rem;
}

/* 修复工具栏浮窗被遮盖的问题 */
:deep(.vditor-panel) {
  z-index: 2000 !important;
}

:deep(.vditor-hint) {
  z-index: 2000 !important;
}

:deep(.vditor-tooltipped) {
  z-index: 2000 !important;
}

:deep(.vditor-menu) {
  z-index: 2000 !important;
}

:deep(.vditor-panel--none) {
  z-index: 2000 !important;
}

/* 重点修复：工具提示（tooltip）的伪元素 */
:deep(.vditor-tooltipped::before),
:deep(.vditor-tooltipped::after) {
  z-index: 10000 !important;
  position: absolute !important;
}

/* 确保所有弹出层都在最上层 */
:deep(.vditor-toolbar__item--current .vditor-panel) {
  z-index: 2000 !important;
}

/* 工具提示的所有方向 */
:deep(.vditor-toolbar__item .vditor-tooltipped__s::before),
:deep(.vditor-toolbar__item .vditor-tooltipped__s::after),
:deep(.vditor-toolbar__item .vditor-tooltipped__n::before),
:deep(.vditor-toolbar__item .vditor-tooltipped__n::after),
:deep(.vditor-toolbar__item .vditor-tooltipped__w::before),
:deep(.vditor-toolbar__item .vditor-tooltipped__w::after),
:deep(.vditor-toolbar__item .vditor-tooltipped__e::before),
:deep(.vditor-toolbar__item .vditor-tooltipped__e::after) {
  z-index: 10000 !important;
}

/* 表情选择器 */
:deep(.vditor-panel--emoji) {
  z-index: 2000 !important;
}

/* 标题选择器 */
:deep(.vditor-panel--headings) {
  z-index: 2000 !important;
}

/* 帮助面板 */
:deep(.vditor-panel--help) {
  z-index: 2000 !important;
}

/* 上传面板 */
:deep(.vditor-upload) {
  z-index: 2000 !important;
}

/* 链接输入框 */
:deep(.vditor-link) {
  z-index: 2000 !important;
}

/* 所有 vditor 相关的浮动元素 */
:deep(.vditor) .vditor-panel,
:deep(.vditor) .vditor-hint,
:deep(.vditor) .vditor-menu {
  z-index: 2000 !important;
}
</style>
