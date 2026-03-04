<script setup lang="ts">
import { computed } from 'vue'

interface PillarLike {
  pillar_id?: unknown
  pillarId?: unknown
  owner_seat?: unknown
  ownerSeat?: unknown
  cards?: unknown
  max_card?: unknown
  maxCard?: unknown
  covered_count?: unknown
  coveredCount?: unknown
}

interface CoveredEntryLike {
  seat?: unknown
  cards?: unknown
  covered_count?: unknown
  coveredCount?: unknown
}

interface PublicStateLike {
  pillars?: unknown
  pillar_list?: unknown
}

interface PrivateStateLike {
  covered?: unknown
}

const props = defineProps<{
  currentSeat?: number | string | null
  selfSeat?: number | string | null
  seat?: number | string | null
  publicState?: PublicStateLike | null
  public_state?: PublicStateLike | null
  privateState?: PrivateStateLike | null
  private_state?: PrivateStateLike | null
  pillars?: unknown
  pillarList?: unknown
  pillar_list?: unknown
}>()

const resolvedPillars = computed<PillarLike[]>(() => {
  const candidates: unknown[] = [
    props.pillars,
    props.pillarList,
    props.pillar_list,
    props.publicState?.pillars,
    props.publicState?.pillar_list,
    props.public_state?.pillars,
    props.public_state?.pillar_list,
  ]

  for (const candidate of candidates) {
    if (Array.isArray(candidate)) {
      return candidate.filter((pillar): pillar is PillarLike => !!pillar && typeof pillar === 'object')
    }
  }

  return []
})

const selfSeatValue = computed<number | null>(() => {
  return readSeat([props.selfSeat, props.currentSeat, props.seat])
})

const selfCoveredCards = computed<string[]>(() => {
  const coveredEntries = readCoveredEntries(props.privateState) ?? readCoveredEntries(props.private_state) ?? []
  const selfSeat = selfSeatValue.value

  return coveredEntries
    .filter((entry) => selfSeat === null || readSeat([entry.seat]) === selfSeat)
    .flatMap((entry) => readStringArray(entry.cards))
})

function readCoveredEntries(privateState: PrivateStateLike | null | undefined): CoveredEntryLike[] | null {
  if (!privateState || !Array.isArray(privateState.covered)) {
    return null
  }

  return privateState.covered.filter((entry): entry is CoveredEntryLike => !!entry && typeof entry === 'object')
}

function readSeat(values: unknown[]): number | null {
  for (const value of values) {
    if (typeof value === 'number' && Number.isFinite(value)) {
      return value
    }
    if (typeof value === 'string' && value.trim() !== '' && Number.isFinite(Number(value))) {
      return Number(value)
    }
  }
  return null
}

function readStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return []
  }

  return value.filter((card): card is string => typeof card === 'string')
}

function pillarId(pillar: PillarLike, index: number): string {
  const id = pillar.pillar_id ?? pillar.pillarId
  if (typeof id === 'string' && id.length > 0) {
    return id
  }
  return `pillar-${index}`
}

function visibleMaxCard(pillar: PillarLike): string {
  const maxCard = pillar.max_card ?? pillar.maxCard
  if (typeof maxCard === 'string' && maxCard.length > 0) {
    return maxCard
  }

  const cards = readStringArray(pillar.cards)
  return cards[0] ?? ''
}

function coveredCount(pillar: PillarLike): number {
  const candidateValues = [pillar.covered_count, pillar.coveredCount]
  for (const value of candidateValues) {
    if (typeof value === 'number' && Number.isFinite(value)) {
      return value
    }
    if (typeof value === 'string' && value.trim() !== '' && Number.isFinite(Number(value))) {
      return Number(value)
    }
  }
  return 0
}

function maskedCardCount(pillar: PillarLike): number {
  const cards = readStringArray(pillar.cards)
  if (cards.length > 1) {
    return cards.length - 1
  }
  return Math.max(0, coveredCount(pillar))
}
</script>

<template>
  <div class="pillar-board" data-testid="pillar-board">
    <section
      v-for="(pillar, index) in resolvedPillars"
      :key="pillarId(pillar, index)"
      class="pillar-item"
      :data-testid="`pillar-${pillarId(pillar, index)}`"
    >
      <div class="pillar-main-card" data-testid="pillar-max-card">{{ visibleMaxCard(pillar) }}</div>
      <div class="pillar-masked-list">
        <span
          v-for="maskedIndex in maskedCardCount(pillar)"
          :key="`${pillarId(pillar, index)}-masked-${maskedIndex}`"
          class="card-back"
          data-testid="pillar-masked-card"
          aria-label="hidden card"
        >
          ## 
        </span>
      </div>
      <div
        data-testid="pillar-covered-count"
        :data-count="String(coveredCount(pillar))"
        :aria-label="`covered-count-${coveredCount(pillar)}`"
      >
        covered: {{ coveredCount(pillar) }}
      </div>
    </section>

    <section class="self-covered-cards" data-testid="self-covered-cards">
      <div v-for="(card, index) in selfCoveredCards" :key="`self-covered-${index}`" data-testid="self-covered-card">
        {{ card }}
      </div>
    </section>
  </div>
</template>
