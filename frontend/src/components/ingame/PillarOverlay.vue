<script setup lang="ts">
import { computed } from 'vue'

interface PillarLike {
  pillar_id?: unknown
  pillarId?: unknown
  owner_seat?: unknown
  ownerSeat?: unknown
  cards?: unknown
}

interface PublicStateLike {
  pillars?: unknown
  pillar_list?: unknown
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
  pillars?: unknown
  pillarList?: unknown
  pillar_list?: unknown
}>()

const isOpen = computed<boolean>(() => {
  return Boolean(props.open ?? props.visible ?? props.show ?? props.modelValue)
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
  </div>
</template>
