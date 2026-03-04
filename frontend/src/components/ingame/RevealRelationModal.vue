<script setup lang="ts">
import { computed } from 'vue'

interface RelationLike {
  relation_id?: unknown
  relationId?: unknown
  revealer_seat?: unknown
  revealerSeat?: unknown
  buckler_seat?: unknown
  bucklerSeat?: unknown
  invalid?: unknown
  is_invalid?: unknown
}

interface PublicStateLike {
  reveal?: unknown
}

interface RevealLike {
  relations?: unknown
}

const props = defineProps<{
  open?: boolean | null
  visible?: boolean | null
  show?: boolean | null
  modelValue?: boolean | null
  relations?: unknown
  revealRelations?: unknown
  reveal_relations?: unknown
  publicState?: PublicStateLike | null
  public_state?: PublicStateLike | null
}>()

const emit = defineEmits<{
  close: []
  'update:modelValue': [value: boolean]
  'update:open': [value: boolean]
  'update:visible': [value: boolean]
}>()

const isOpen = computed<boolean>(() => {
  return Boolean(props.open || props.visible || props.show || props.modelValue)
})

const resolvedRelations = computed<RelationLike[]>(() => {
  const candidates: unknown[] = [
    props.relations,
    props.revealRelations,
    props.reveal_relations,
    readRevealRelations(props.publicState),
    readRevealRelations(props.public_state),
  ]

  for (const candidate of candidates) {
    if (Array.isArray(candidate)) {
      return candidate.filter((relation): relation is RelationLike => !!relation && typeof relation === 'object')
    }
  }

  return []
})

function readRevealRelations(publicState: PublicStateLike | null | undefined): unknown {
  if (!publicState || !publicState.reveal || typeof publicState.reveal !== 'object') {
    return undefined
  }

  return (publicState.reveal as RevealLike).relations
}

function relationId(relation: RelationLike, index: number): string {
  const id = relation.relation_id ?? relation.relationId
  if (typeof id === 'string' && id.length > 0) {
    return id
  }
  return `relation-${index}`
}

function readSeat(value: unknown): string {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return String(value)
  }
  if (typeof value === 'string' && value.trim() !== '' && Number.isFinite(Number(value))) {
    return String(Number(value))
  }
  return '-'
}

function isInvalidRelation(relation: RelationLike): boolean {
  return relation.invalid === true || relation.is_invalid === true
}

function closeModal(): void {
  emit('close')
  emit('update:modelValue', false)
  emit('update:open', false)
  emit('update:visible', false)
}
</script>

<template>
  <section v-if="isOpen" class="reveal-relation-modal" data-testid="reveal-relation-modal">
    <button type="button" data-testid="reveal-relation-close" aria-label="close reveal relation modal" @click="closeModal">
      Close
    </button>

    <ul class="reveal-relation-list" data-testid="reveal-relation-list">
      <li
        v-for="(relation, index) in resolvedRelations"
        :key="relationId(relation, index)"
        class="reveal-relation-item"
        :class="{
          'reveal-relation-item-invalid text-muted line-through': isInvalidRelation(relation),
        }"
        :data-testid="isInvalidRelation(relation) ? 'reveal-relation-item-invalid' : 'reveal-relation-item'"
        :data-invalid="isInvalidRelation(relation) ? 'true' : 'false'"
        :aria-disabled="isInvalidRelation(relation) ? 'true' : 'false'"
      >
        <span class="relation-text">
          {{ readSeat(relation.revealer_seat ?? relation.revealerSeat) }} -> {{ readSeat(relation.buckler_seat ?? relation.bucklerSeat) }}
        </span>
        <span v-if="isInvalidRelation(relation)" class="relation-invalid-marker" data-testid="reveal-relation-invalid-marker">
          invalid
        </span>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.text-muted {
  color: gray;
  opacity: 0.7;
}

.line-through {
  text-decoration: line-through;
}
</style>
