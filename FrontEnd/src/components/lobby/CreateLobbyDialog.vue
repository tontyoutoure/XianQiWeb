# components/lobby/CreateLobbyDialog.vue
<template>
  <div v-if="isOpen" class="fixed inset-0 flex items-center justify-center z-50">
    <!-- Backdrop -->
    <div class="absolute inset-0 bg-black bg-opacity-50" @click="close"></div>
    
    <!-- Dialog -->
    <div class="bg-white rounded-lg p-6 w-full max-w-md relative z-10">
      <h2 class="text-xl font-bold mb-4">Create New Lobby</h2>
      
      <div class="mb-6">
        <label class="block text-sm font-medium mb-2">Initial Chip Count</label>
        <div class="grid grid-cols-3 gap-2">
          <button
            v-for="count in chipCounts"
            :key="count"
            @click="selectedChips = count"
            :class="[
              'p-3 text-center rounded-lg border',
              selectedChips === count
                ? 'bg-blue-500 text-white border-blue-600'
                : 'border-gray-300 hover:border-blue-500'
            ]"
          >
            {{ count }}
          </button>
        </div>
      </div>
      
      <div class="flex justify-end space-x-3">
        <button
          @click="close"
          class="px-4 py-2 border rounded-lg hover:bg-gray-50 active:bg-gray-100"
        >
          Cancel
        </button>
        <button
          @click="createLobby"
          :disabled="!selectedChips"
          class="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 active:bg-blue-700 disabled:bg-gray-300"
        >
          Create
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{
  isOpen: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'create', chipCount: number): void
}>()

const chipCounts = [10, 15, 20, 25, 30]
const selectedChips = ref<number>()

function close() {
  selectedChips.value = undefined
  emit('close')
}

function createLobby() {
  if (selectedChips.value) {
    emit('create', selectedChips.value)
    close()
  }
}
</script>