<!-- src/components/common/Button.vue -->
<template>
    <button 
      class="custom-button" 
      :class="{ 'disabled': disabled }"
      :disabled="disabled"
      @click="$emit('click')"
    >
      {{ text }}
    </button>
  </template>
  
  <script lang="ts">
  import { defineComponent } from 'vue'
  
  export default defineComponent({
    name: 'Button',
    props: {
      text: {
        type: String,
        required: true
      },
      disabled: {
        type: Boolean,
        default: false
      }
    },
    emits: ['click']
  })
  </script>
  
  <style scoped>
  .custom-button {
    padding: 10px 20px;
    border: none;
    border-radius: 4px;
    background-color: #4CAF50;
    color: white;
    font-size: 16px;
    cursor: pointer;
    transition: background-color 0.3s;
  }
  
  .custom-button:hover:not(.disabled) {
    background-color: #45a049;
  }
  
  .custom-button.disabled {
    background-color: #cccccc;
    cursor: not-allowed;
  }
  </style>