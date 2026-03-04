<script setup lang="ts">
import { computed } from 'vue'

interface TurnPlayLike {
  seat?: unknown
  payload_cards?: unknown
  payloadCards?: unknown
}

interface TurnLike {
  plays?: unknown
}

interface PublicStateLike {
  turn?: unknown
}

const props = defineProps<{
  plays?: unknown
  turnPlays?: unknown
  turn_plays?: unknown
  turn?: unknown
  publicState?: unknown
  public_state?: unknown
}>()

const plays = computed<TurnPlayLike[]>(() => {
  const candidates: unknown[] = [
    props.plays,
    readPlaysFromTurn(props.turn),
    readPlaysFromPublicState(props.publicState),
    readPlaysFromPublicState(props.public_state),
    props.turnPlays,
    props.turn_plays,
  ]

  for (const candidate of candidates) {
    if (Array.isArray(candidate)) {
      return candidate.filter((play): play is TurnPlayLike => !!play && typeof play === 'object')
    }
  }

  return []
})

function readPlaysFromPublicState(value: unknown): unknown {
  if (!value || typeof value !== 'object') {
    return undefined
  }

  return readPlaysFromTurn((value as PublicStateLike).turn)
}

function readPlaysFromTurn(value: unknown): unknown {
  if (!value || typeof value !== 'object') {
    return undefined
  }

  return (value as TurnLike).plays
}

function readSeat(play: TurnPlayLike): number | null {
  const seat = play.seat
  if (typeof seat === 'number' && Number.isFinite(seat)) {
    return seat
  }

  if (typeof seat === 'string' && Number.isFinite(Number(seat))) {
    return Number(seat)
  }

  return null
}

function formatPayload(play: TurnPlayLike): string {
  const rawPayload = play.payload_cards ?? play.payloadCards
  if (!rawPayload || typeof rawPayload !== 'object') {
    return ''
  }

  return Object.entries(rawPayload as Record<string, unknown>)
    .filter((entry): entry is [string, number] => typeof entry[1] === 'number' && entry[1] > 0)
    .map(([card, count]) => `${card}x${count}`)
    .join(', ')
}
</script>

<template>
  <div class="turn-plays-panel" data-testid="turn-plays-panel">
    <div
      v-for="(play, index) in plays"
      :key="index"
      class="turn-play-item"
      data-testid="turn-play-item"
      :data-seat="readSeat(play) ?? undefined"
    >
      <span class="turn-play-seat" data-testid="turn-play-seat">Seat {{ readSeat(play) ?? '-' }}</span>
      <span class="turn-play-cards">{{ formatPayload(play) }}</span>
    </div>
  </div>
</template>
