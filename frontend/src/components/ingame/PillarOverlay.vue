<script setup lang="ts">
import { computed, ref } from 'vue'

interface PillarLike {
  pillar_id?: unknown
  pillarId?: unknown
  owner_seat?: unknown
  ownerSeat?: unknown
  cards?: unknown
  covered_count?: unknown
  coveredCount?: unknown
}

interface TurnPlayLike {
  cards?: unknown
}

interface TurnLike {
  plays?: unknown
}

interface PublicStateLike {
  pillars?: unknown
  pillar_list?: unknown
  turn?: unknown
}

interface PrivateStateLike {
  hand?: unknown
}

const props = defineProps<{
  open?: boolean | null
  visible?: boolean | null
  show?: boolean | null
  modelValue?: boolean | null
  viewMode?: string | null
  view_mode?: string | null
  mode?: string | null
  displayMode?: string | null
  publicState?: PublicStateLike | null
  public_state?: PublicStateLike | null
  privateState?: PrivateStateLike | null
  private_state?: PrivateStateLike | null
  pillars?: unknown
  pillarList?: unknown
  pillar_list?: unknown
  includeOutsideCards?: boolean | null
  include_outside_cards?: boolean | null
  includeOuterCards?: boolean | null
}>()

const isOpen = computed<boolean>(() => {
  return Boolean(props.open || props.visible || props.show || props.modelValue)
})

const currentMode = computed<string>(() => {
  return props.viewMode ?? props.view_mode ?? props.mode ?? props.displayMode ?? 'ownership'
})

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

const ownerGroups = computed<Array<{ owner: number; pillars: PillarLike[] }>>(() => {
  const grouped = new Map<number, PillarLike[]>()

  for (const pillar of resolvedPillars.value) {
    const owner = readOwnerSeat(pillar)
    const existing = grouped.get(owner) ?? []
    existing.push(pillar)
    grouped.set(owner, existing)
  }

  return Array.from(grouped.entries())
    .sort((a, b) => a[0] - b[0])
    .map(([owner, pillars]) => ({ owner, pillars }))
})

const includeOutsideCards = ref<boolean>(readIncludeOutsideCardsDefault())

const publicCardsBySize = computed<string[]>(() => {
  return resolvedPillars.value
    .flatMap((pillar) => readCards(pillar))
    .map((card, index) => ({ card, index }))
    .sort((a, b) => {
      const powerDiff = readPower(b.card) - readPower(a.card)
      if (powerDiff !== 0) {
        return powerDiff
      }
      return a.index - b.index
    })
    .map((entry) => entry.card)
})

const coveredCountItems = computed<Array<{ key: string; label: string }>>(() => {
  return resolvedPillars.value
    .map((pillar, index) => {
      const count = readCoveredCount(pillar)
      return {
        key: `covered-count-${pillarId(pillar, index)}`,
        label: `covered_count=${count}`,
        count,
      }
    })
    .filter((entry) => entry.count > 0)
    .map((entry) => ({ key: entry.key, label: entry.label }))
})

const outsideCards = computed<string[]>(() => {
  const handCards = readHandCards(props.privateState) ?? readHandCards(props.private_state) ?? []
  const turnCards =
    readTurnPlayCards(props.publicState) ??
    readTurnPlayCards(props.public_state) ??
    []

  return [...handCards, ...turnCards]
})

const sizeItems = computed<Array<{ key: string; label: string }>>(() => {
  const base = publicCardsBySize.value.map((card, index) => ({
    key: `public-card-${index}`,
    label: card,
  }))

  if (includeOutsideCards.value) {
    outsideCards.value.forEach((card, index) => {
      base.push({
        key: `outside-card-${index}`,
        label: card,
      })
    })
  }

  coveredCountItems.value.forEach((item) => {
    base.push(item)
  })

  return base
})

function readOwnerSeat(pillar: PillarLike): number {
  const value = pillar.owner_seat ?? pillar.ownerSeat
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }
  if (typeof value === 'string' && value.trim() !== '' && Number.isFinite(Number(value))) {
    return Number(value)
  }
  return -1
}

function readCards(pillar: PillarLike): string[] {
  if (!Array.isArray(pillar.cards)) {
    return []
  }
  return pillar.cards.filter((card): card is string => typeof card === 'string')
}

function readIncludeOutsideCardsDefault(): boolean {
  const candidates = [props.includeOutsideCards, props.include_outside_cards, props.includeOuterCards]
  for (const value of candidates) {
    if (typeof value === 'boolean') {
      return value
    }
  }
  return false
}

function readPower(card: string): number {
  const match = card.match(/POWER_(\d+)/i)
  if (!match) {
    return -1
  }
  return Number(match[1])
}

function readCoveredCount(pillar: PillarLike): number {
  const candidates = [pillar.covered_count, pillar.coveredCount]
  for (const value of candidates) {
    if (typeof value === 'number' && Number.isFinite(value)) {
      return value
    }
    if (typeof value === 'string' && value.trim() !== '' && Number.isFinite(Number(value))) {
      return Number(value)
    }
  }
  return 0
}

function readHandCards(privateState: PrivateStateLike | null | undefined): string[] | null {
  if (!privateState || !Array.isArray(privateState.hand)) {
    return null
  }
  return privateState.hand.filter((card): card is string => typeof card === 'string')
}

function readTurnPlayCards(publicState: PublicStateLike | null | undefined): string[] | null {
  if (!publicState || !publicState.turn || typeof publicState.turn !== 'object') {
    return null
  }

  const plays = (publicState.turn as TurnLike).plays
  if (!Array.isArray(plays)) {
    return null
  }

  return plays
    .filter((play): play is TurnPlayLike => !!play && typeof play === 'object')
    .flatMap((play) => {
      if (!Array.isArray(play.cards)) {
        return []
      }
      return play.cards.filter((card): card is string => typeof card === 'string')
    })
}

function pillarId(pillar: PillarLike, index: number): string {
  const id = pillar.pillar_id ?? pillar.pillarId
  if (typeof id === 'string' && id.length > 0) {
    return id
  }
  return `pillar-${index}`
}
</script>

<template>
  <div v-if="isOpen" class="pillar-overlay" data-testid="pillar-overlay">
    <template v-if="currentMode === 'ownership'">
      <section
        v-for="group in ownerGroups"
        :key="`owner-${group.owner}`"
        class="pillar-owner-group"
        data-testid="pillar-owner-group"
        :data-owner-seat="group.owner"
      >
        <header :data-testid="`pillar-owner-group-${group.owner}`">Owner {{ group.owner }}</header>
        <div
          v-for="(pillar, pillarIndex) in group.pillars"
          :key="pillarId(pillar, pillarIndex)"
          class="pillar-overlay-item"
          :data-testid="`pillar-overlay-item-${pillarId(pillar, pillarIndex)}`"
        >
          <span
            v-for="(card, cardIndex) in readCards(pillar)"
            :key="`${pillarId(pillar, pillarIndex)}-${cardIndex}`"
            class="pillar-overlay-card"
            data-testid="pillar-overlay-card"
          >
            {{ card }}
          </span>
        </div>
      </section>
    </template>
    <template v-else-if="currentMode === 'size'">
      <label class="pillar-include-outside-toggle" data-testid="pillar-include-outside-toggle-label">
        <input
          v-model="includeOutsideCards"
          type="checkbox"
          name="include-outside-cards"
          data-testid="pillar-include-outside-toggle"
          aria-label="包含柱外牌"
          @click="includeOutsideCards = !includeOutsideCards"
        />
        包含柱外牌
      </label>

      <ul class="pillar-size-list" data-testid="pillar-size-list">
        <li
          v-for="(item, index) in sizeItems"
          :key="item.key"
          data-testid="pillar-size-item"
          :data-size-index="index"
        >
          {{ item.label }}
        </li>
      </ul>
    </template>
  </div>
</template>
