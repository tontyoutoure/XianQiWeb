<script setup lang="ts">
import { computed } from 'vue'

interface SettlementEntry {
  seat: number | null
  username: string
  delta: number
  deltaEnough: number
  deltaReveal: number
  deltaCeramic: number
}

interface SettlementRecord {
  players?: unknown
  player_results?: unknown
  details?: unknown
  entries?: unknown
}

const props = defineProps<{
  open?: boolean | null
  visible?: boolean | null
  show?: boolean | null
  modelValue?: boolean | null
  settlement?: unknown
  settlementResult?: unknown
  settlement_result?: unknown
  players?: unknown
  entries?: unknown
}>()

const emit = defineEmits<{
  (event: 'close'): void
  (event: 'update:modelValue', value: boolean): void
  (event: 'update:open', value: boolean): void
  (event: 'update:visible', value: boolean): void
  (event: 'update:show', value: boolean): void
}>()

const isOpen = computed<boolean>(() => {
  const booleanFlags = [props.modelValue, props.open, props.visible, props.show].filter(
    (value): value is boolean => typeof value === 'boolean',
  )

  if (booleanFlags.length === 0) {
    return false
  }

  return booleanFlags.some((value) => value)
})

const normalizedEntries = computed<SettlementEntry[]>(() => {
  const candidates: unknown[] = [
    props.entries,
    props.players,
    readEntriesFromSettlement(props.settlement),
    readEntriesFromSettlement(props.settlementResult),
    readEntriesFromSettlement(props.settlement_result),
  ]

  for (const candidate of candidates) {
    if (!Array.isArray(candidate)) {
      continue
    }

    return candidate
      .filter((entry): entry is Record<string, unknown> => !!entry && typeof entry === 'object')
      .map((entry, index) => normalizeEntry(entry, index))
  }

  return []
})

const normalizedEntriesDigest = computed<string>(() => {
  return normalizedEntries.value
    .map((entry) => {
      return [
        entry.username,
        entry.seat ?? '-',
        entry.delta,
        entry.deltaEnough,
        entry.deltaReveal,
        entry.deltaCeramic,
      ].join(' ')
    })
    .join(' | ')
})

function readEntriesFromSettlement(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value
  }

  if (!value || typeof value !== 'object') {
    return null
  }

  const settlement = value as SettlementRecord
  const candidates: unknown[] = [settlement.players, settlement.player_results, settlement.details, settlement.entries]
  for (const candidate of candidates) {
    if (Array.isArray(candidate)) {
      return candidate
    }
  }

  return null
}

function normalizeEntry(entry: Record<string, unknown>, index: number): SettlementEntry {
  const seat = readNumber(entry.seat)
  const username = typeof entry.username === 'string' && entry.username.trim().length > 0
    ? entry.username
    : `Seat ${seat ?? index}`

  return {
    seat,
    username,
    delta: readNumber(entry.delta) ?? 0,
    deltaEnough: readNumber(entry.delta_enough) ?? 0,
    deltaReveal: readNumber(entry.delta_reveal) ?? 0,
    deltaCeramic: readNumber(entry.delta_ceramic) ?? 0,
  }
}

function readNumber(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }

  if (typeof value === 'string' && value.trim() !== '' && Number.isFinite(Number(value))) {
    return Number(value)
  }

  return null
}

function formatSigned(value: number): string {
  return value > 0 ? `+${value}` : String(value)
}

function handleClose(): void {
  emit('close')
  emit('update:modelValue', false)
  emit('update:open', false)
  emit('update:visible', false)
  emit('update:show', false)
}
</script>

<template>
  <section
    v-if="isOpen"
    class="settlement-modal"
    data-testid="settlement-modal"
    role="dialog"
    aria-label="结算弹层"
  >
    <header class="settlement-header">
      <h2>结算</h2>
      <button type="button" data-testid="settlement-close" aria-label="关闭结算" @click="handleClose">
        关闭
      </button>
    </header>

    <div class="settlement-columns">
      <span>delta</span>
      <span>delta_enough</span>
      <span>delta_reveal</span>
      <span>delta_ceramic</span>
    </div>

    <div
      v-for="(entry, index) in normalizedEntries"
      :key="`${entry.username}-${index}`"
      class="settlement-player-row"
      data-testid="settlement-player-row"
    >
      <span>{{ entry.username }} (seat {{ entry.seat ?? '-' }})</span>
      <span>delta {{ formatSigned(entry.delta) }}</span>
      <span>delta_enough {{ formatSigned(entry.deltaEnough) }}</span>
      <span>delta_reveal {{ formatSigned(entry.deltaReveal) }}</span>
      <span>delta_ceramic {{ formatSigned(entry.deltaCeramic) }}</span>
      <span>{{ normalizedEntriesDigest }}</span>
    </div>
  </section>
</template>
