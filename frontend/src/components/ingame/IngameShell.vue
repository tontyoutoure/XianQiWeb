<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import ActionBar from './ActionBar.vue'
import SettlementModal from './SettlementModal.vue'

interface GenericRecord {
  [key: string]: unknown
}

interface TurnPlay {
  seat?: unknown
  cards?: unknown
  payload_cards?: unknown
}

const props = defineProps<{
  phase?: string | null
  roomStatus?: string | null
  room_status?: string | null
  status?: string | null
  publicState?: unknown
  public_state?: unknown
  privateState?: unknown
  private_state?: unknown
  latestGameEvent?: unknown
  latest_game_event?: unknown
  settlement?: unknown
  settlementResult?: unknown
  settlement_result?: unknown
  legalActions?: unknown
  legal_actions?: unknown
  actionDisabledMap?: unknown
  action_disabled_map?: unknown
  submitDisabledMap?: unknown
  submit_disabled_map?: unknown
}>()
const emit = defineEmits<{
  (event: 'action-click', actionType: string): void
}>()

const settlementVisible = ref(false)
const showReadyNotice = ref(false)
const showColdEndNotice = ref(false)

const resolvedRoomStatus = computed<string>(() => {
  return firstNonEmptyString([props.roomStatus, props.room_status, props.status]) ?? ''
})

const resolvedPublicState = computed<GenericRecord | null>(() => {
  return asRecord(props.publicState) ?? asRecord(props.public_state)
})

const resolvedPrivateState = computed<GenericRecord | null>(() => {
  return asRecord(props.privateState) ?? asRecord(props.private_state)
})

const resolvedPhase = computed<string>(() => {
  return firstNonEmptyString([props.phase, resolvedPublicState.value?.phase]) ?? ''
})

const resolvedLatestEvent = computed<GenericRecord | null>(() => {
  return asRecord(props.latestGameEvent) ?? asRecord(props.latest_game_event)
})

const resolvedLatestEventType = computed<string>(() => {
  return firstNonEmptyString([resolvedLatestEvent.value?.type]) ?? ''
})

const resolvedSettlement = computed<unknown>(() => {
  const directSettlement = firstDefined([props.settlement, props.settlementResult, props.settlement_result])
  if (directSettlement !== null && directSettlement !== undefined) {
    return directSettlement
  }

  if (normalizeToken(resolvedLatestEventType.value) === 'settlement') {
    return resolvedLatestEvent.value?.payload ?? null
  }

  return null
})

const resolvedLegalActions = computed<GenericRecord | null>(() => {
  return asRecord(props.legalActions) ?? asRecord(props.legal_actions)
})

const resolvedActionDisabledMap = computed<GenericRecord | null>(() => {
  return (
    asRecord(props.actionDisabledMap) ??
    asRecord(props.action_disabled_map) ??
    asRecord(props.submitDisabledMap) ??
    asRecord(props.submit_disabled_map)
  )
})

const hasSettlementData = computed<boolean>(() => {
  return resolvedSettlement.value !== null && resolvedSettlement.value !== undefined
})

const showIngameArea = computed<boolean>(() => {
  return normalizeToken(resolvedRoomStatus.value) === 'playing' && !showColdEndNotice.value
})

const ingamePlaySummary = computed<string>(() => {
  const turn = asRecord(resolvedPublicState.value?.turn)
  const plays = Array.isArray(turn?.plays) ? turn.plays : []

  return plays
    .filter((play): play is TurnPlay => !!play && typeof play === 'object')
    .map((play) => {
      const seat = firstNonEmptyString([play.seat]) ?? String(play.seat ?? '-')
      const cards = readCardList(play.cards)
      if (cards.length > 0) {
        return `seat ${seat}: ${cards.join(',')}`
      }

      const payloadCards = asRecord(play.payload_cards)
      if (payloadCards) {
        const payloadText = Object.entries(payloadCards)
          .filter((entry): entry is [string, number] => typeof entry[1] === 'number' && entry[1] > 0)
          .map(([card, count]) => `${card}x${count}`)
          .join(',')
        if (payloadText.length > 0) {
          return `seat ${seat}: ${payloadText}`
        }
      }

      return `seat ${seat}`
    })
    .join(' | ')
})

const ingameHandSummary = computed<string>(() => {
  const hand = resolvedPrivateState.value?.hand
  const handAsArray = readCardList(hand)
  if (handAsArray.length > 0) {
    return handAsArray.join(',')
  }

  const handAsRecord = asRecord(hand)
  if (!handAsRecord) {
    return ''
  }

  return Object.entries(handAsRecord)
    .filter((entry): entry is [string, number] => typeof entry[1] === 'number' && entry[1] > 0)
    .map(([card, count]) => `${card}x${count}`)
    .join(',')
})

watch(
  resolvedPhase,
  (newPhase, oldPhase) => {
    if (normalizeToken(newPhase) === 'settlement' && normalizeToken(oldPhase) !== 'settlement') {
      settlementVisible.value = true
      showReadyNotice.value = false
      showColdEndNotice.value = false
    }
  },
  { immediate: true },
)

watch(
  resolvedLatestEvent,
  (newEvent, oldEvent) => {
    const newType = normalizeToken(firstNonEmptyString([newEvent?.type]) ?? '')
    const oldType = normalizeToken(firstNonEmptyString([oldEvent?.type]) ?? '')
    if (newType === 'settlement' && newType !== oldType) {
      settlementVisible.value = true
      showReadyNotice.value = false
      showColdEndNotice.value = false
    }
  },
  { immediate: true },
)

watch(
  resolvedRoomStatus,
  (newStatus, oldStatus) => {
    const fromStatus = normalizeToken(oldStatus)
    const toStatus = normalizeToken(newStatus)
    const hasSettlementContext = hasSettlementData.value || normalizeToken(resolvedPhase.value) === 'settlement'

    if (fromStatus === 'playing' && toStatus === 'waiting' && !hasSettlementContext) {
      settlementVisible.value = false
      showReadyNotice.value = false
      showColdEndNotice.value = true
      return
    }

    if (toStatus === 'playing') {
      showColdEndNotice.value = false
    }
  },
  { immediate: true },
)

function handleSettlementClose(): void {
  settlementVisible.value = false
  showReadyNotice.value = true
  showColdEndNotice.value = false
}

function handleSettlementModelUpdate(value: boolean): void {
  settlementVisible.value = value
  if (!value) {
    showReadyNotice.value = true
    showColdEndNotice.value = false
  }
}

function handleActionClick(actionType: string): void {
  emit('action-click', actionType)
}

function firstDefined(values: unknown[]): unknown {
  for (const value of values) {
    if (value !== undefined) {
      return value
    }
  }
  return undefined
}

function firstNonEmptyString(values: unknown[]): string | null {
  for (const value of values) {
    if (typeof value === 'string' && value.trim().length > 0) {
      return value
    }

    if (typeof value === 'number' && Number.isFinite(value)) {
      return String(value)
    }
  }

  return null
}

function normalizeToken(value: unknown): string {
  if (typeof value !== 'string') {
    return ''
  }

  return value.trim().toLowerCase()
}

function asRecord(value: unknown): GenericRecord | null {
  if (value && typeof value === 'object') {
    return value as GenericRecord
  }
  return null
}

function readCardList(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return []
  }

  return value.filter((card): card is string => typeof card === 'string')
}
</script>

<template>
  <section class="ingame-shell" data-testid="game-shell">
    <SettlementModal
      v-if="settlementVisible"
      :model-value="settlementVisible"
      :settlement="resolvedSettlement"
      @close="handleSettlementClose"
      @update:model-value="handleSettlementModelUpdate"
    />

    <p v-if="showReadyNotice">已进入准备阶段，请重新 ready 开新局</p>
    <p v-if="showColdEndNotice">对局结束</p>

    <section v-if="showIngameArea" data-testid="ingame-area">
      <div data-testid="ingame-action-bar">
        <ActionBar
          :phase="resolvedPhase"
          :legal-actions="resolvedLegalActions"
          :legal_actions="resolvedLegalActions"
          :action-disabled-map="resolvedActionDisabledMap"
          :actionDisabledMap="resolvedActionDisabledMap"
          :submit-disabled-map="resolvedActionDisabledMap"
          :submitDisabledMap="resolvedActionDisabledMap"
          @action-click="handleActionClick"
        />
      </div>
      <div data-testid="turn-plays-panel">{{ ingamePlaySummary }}</div>
      <div data-testid="ingame-hand-cards">{{ ingameHandSummary }}</div>
    </section>
  </section>
</template>
