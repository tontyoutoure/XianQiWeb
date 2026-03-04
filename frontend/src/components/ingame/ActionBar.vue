<script setup lang="ts">
import { computed } from 'vue'

type ActionType = 'BUCKLE' | 'PASS_BUCKLE' | 'REVEAL' | 'PASS_REVEAL' | 'PLAY' | 'COVER'

interface LegalActionLike {
  type?: unknown
}

interface LegalActionsLike {
  actions?: unknown
}

const VALID_ACTION_TYPES: readonly ActionType[] = [
  'BUCKLE',
  'PASS_BUCKLE',
  'REVEAL',
  'PASS_REVEAL',
  'PLAY',
  'COVER',
]

const props = defineProps<{
  phase?: string
  currentPhase?: string
  legalActions?: LegalActionsLike | null
  legal_actions?: LegalActionsLike | null
  actionTypes?: string[] | null
  availableActionTypes?: string[] | null
}>()

const visibleActionTypes = computed<ActionType[]>(() => {
  const fromCamel = readActionTypesFromLegalActions(props.legalActions)
  if (fromCamel.length > 0) {
    return dedupeActionTypes(fromCamel)
  }

  const fromSnake = readActionTypesFromLegalActions(props.legal_actions)
  if (fromSnake.length > 0) {
    return dedupeActionTypes(fromSnake)
  }

  const fallbackTypes = Array.isArray(props.actionTypes)
    ? props.actionTypes
    : Array.isArray(props.availableActionTypes)
      ? props.availableActionTypes
      : []

  return dedupeActionTypes(fallbackTypes)
})

function readActionTypesFromLegalActions(legalActions: LegalActionsLike | null | undefined): string[] {
  if (!legalActions || !Array.isArray(legalActions.actions)) {
    return []
  }

  return legalActions.actions
    .map((action) => (action as LegalActionLike)?.type)
    .filter((type): type is string => typeof type === 'string')
}

function dedupeActionTypes(actionTypes: readonly string[]): ActionType[] {
  const deduped: ActionType[] = []
  const seen = new Set<ActionType>()

  for (const actionType of actionTypes) {
    if (!isActionType(actionType) || seen.has(actionType)) {
      continue
    }
    deduped.push(actionType)
    seen.add(actionType)
  }

  return deduped
}

function isActionType(value: string): value is ActionType {
  return (VALID_ACTION_TYPES as readonly string[]).includes(value)
}
</script>

<template>
  <div class="action-bar" data-testid="action-bar">
    <button
      v-for="actionType in visibleActionTypes"
      :key="actionType"
      type="button"
      :data-testid="`action-btn-${actionType}`"
    >
      {{ actionType }}
    </button>
  </div>
</template>
