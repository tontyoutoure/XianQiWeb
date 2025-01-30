<!-- src/views/NameInputPage.vue -->
<template>
    <div class="name-input-container">
      <h1>掀棋</h1>
      <div class="input-wrapper">
        <Input
          v-model="playerName"
          placeholder="请输入姓名"
          :error="errorMessage"
        />
        <Button
          text="继续"
          :disabled="!playerName.trim()"
          @click="handleSubmit"
        />
      </div>
    </div>
  </template>
  
  <script lang="ts">
  import { defineComponent, ref } from 'vue'
  import { useStore } from 'vuex'
  import { useRouter } from 'vue-router'
  import Button from '@/components/common/Button.vue'
  import Input from '@/components/common/Input.vue'
  
  export default defineComponent({
    name: 'NameInputPage',
    components: {
      Button,
      Input
    },
    setup() {
      const store = useStore()
      const router = useRouter()
      const playerName = ref('')
      const errorMessage = ref('')
  
      const handleSubmit = async () => {
        try {    
          const apiUrl = import.meta.env.VITE_API_URL || ''  // Use environment variable
          const response = await fetch(`${apiUrl}/api/player/name`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({ name: playerName.value.trim() })
          })
  
          if (!response.ok) {
            throw new Error('Failed to submit name')
          }
  
          // Store the name in Vuex
          await store.dispatch('user/setPlayerName', playerName.value.trim())
          
          // TODO: Navigate to lobby list page once it's created
          // router.push('/lobby-list')
        } catch (error) {
          errorMessage.value = 'Failed to submit name. Please try again.'
          console.error('Error:', error)
        }
      }
  
      return {
        playerName,
        errorMessage,
        handleSubmit
      }
    }
  })
  </script>
  
  <style scoped>
  .name-input-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    padding: 20px;
  }
  
  h1 {
    margin-bottom: 2rem;
    color: #333;
  }
  
  .input-wrapper {
    width: 100%;
    max-width: 400px;
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }
  </style>