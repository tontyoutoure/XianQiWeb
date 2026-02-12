<!-- src/components/common/Input.vue -->
<template>
    <div class="input-container">
      <input
        :value="modelValue"
        @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
        :placeholder="placeholder"
        :type="type"
        class="custom-input"
        :class="{ 'error': error }"
      />
      <span v-if="error" class="error-message">{{ error }}</span>
    </div>
  </template>
  
  <script lang="ts">
  import { defineComponent } from 'vue'
  
  export default defineComponent({
    name: 'Input',
    props: {
      modelValue: {
        type: String,
        required: true
      },
      placeholder: {
        type: String,
        default: ''
      },
      type: {
        type: String,
        default: 'text'
      },
      error: {
        type: String,
        default: ''
      }
    },
    emits: ['update:modelValue']
  })
  </script>
  
  <style scoped>
  .input-container {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  
  .custom-input {
    padding: 10px;
    border: 1px solid #ddd;
    border-radius: 4px;
    font-size: 16px;
    width: 100%;
    box-sizing: border-box;
  }
  
  .custom-input.error {
    border-color: #ff4444;
  }
  
  .error-message {
    color: #ff4444;
    font-size: 12px;
  }
  </style>