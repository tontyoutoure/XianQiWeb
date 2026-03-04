import { mount, type DOMWrapper, type VueWrapper } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import type { Component } from 'vue'

type GenericRecord = Record<string, unknown>

interface ComponentModule {
  default?: Component
}

const PILLAR_OVERLAY_CANDIDATE_PATHS = [
  '/src/components/ingame/PillarOverlay.vue',
  '/src/components/ingame/GamePillarOverlay.vue',
  '/src/components/PillarOverlay.vue',
  '/src/components/GamePillarOverlay.vue',
] as const

const REVEAL_RELATION_MODAL_CANDIDATE_PATHS = [
  '/src/components/ingame/RevealRelationModal.vue',
  '/src/components/ingame/RevealRelationsModal.vue',
  '/src/components/RevealRelationModal.vue',
  '/src/components/RevealRelationsModal.vue',
] as const

const FORBIDDEN_REQUEST_EVENT_NAMES = [
  'refresh-state',
  'request-state',
  'sync-state',
  'submit-action',
  'fetch-state',
  'update:publicState',
  'update:public_state',
] as const

async function loadComponentFromCandidates(
  candidatePaths: readonly string[],
  testId: string,
  expectedHint: string,
): Promise<Component> {
  const componentModules = import.meta.glob('/src/components/**/*.vue')

  for (const path of candidatePaths) {
    const loader = componentModules[path]
    if (!loader) {
      continue
    }

    const componentModule = (await loader()) as ComponentModule
    if (componentModule.default) {
      return componentModule.default
    }
  }

  throw new Error(`${testId} requires ${expectedHint}.`)
}

function findBySelectorCandidates(
  wrapper: VueWrapper,
  selectors: readonly string[],
): DOMWrapper<Element>[] {
  for (const selector of selectors) {
    const nodes = wrapper.findAll(selector)
    if (nodes.length > 0) {
      return nodes
    }
  }
  return []
}

function textWithAttrs(node: DOMWrapper<Element>): string {
  const attrs = node.attributes()
  return [node.text(), ...Object.values(attrs)].join(' ')
}

function containsCount(node: DOMWrapper<Element>, expectedCount: number): boolean {
  const expected = String(expectedCount)
  const value = textWithAttrs(node)
  return value.includes(expected)
}

function hasGraySemantics(node: DOMWrapper<Element>): boolean {
  const className = node.attributes('class') ?? ''
  const style = node.attributes('style') ?? ''
  const combined = `${className} ${style}`.toLowerCase()

  if (combined.includes('gray') || combined.includes('grey')) {
    return true
  }

  if (combined.includes('text-muted') || combined.includes('muted')) {
    return true
  }

  return combined.includes('opacity')
}

function hasLineThroughSemantics(node: DOMWrapper<Element>): boolean {
  const className = node.attributes('class') ?? ''
  const style = node.attributes('style') ?? ''
  const combined = `${className} ${style}`.toLowerCase()

  return (
    combined.includes('line-through') ||
    combined.includes('strikethrough') ||
    combined.includes('strike') ||
    combined.includes('text-decoration')
  )
}

async function mountPillarOverlay(extraProps: GenericRecord = {}): Promise<VueWrapper> {
  const PillarOverlay = await loadComponentFromCandidates(
    PILLAR_OVERLAY_CANDIDATE_PATHS,
    'M8-CT-12/M8-CT-13',
    'a pillar overlay component at "@/components/ingame/PillarOverlay.vue" (or equivalent candidate path)',
  )

  const pillarA = {
    pillar_id: 'pillar-A',
    owner_seat: 0,
    cards: ['POWER_7_PUBLIC', 'POWER_1_PUBLIC'],
    max_card: 'POWER_7_PUBLIC',
    covered_count: 0,
  }
  const pillarB = {
    pillar_id: 'pillar-B',
    owner_seat: 1,
    cards: ['POWER_9_PUBLIC', 'POWER_3_PUBLIC'],
    max_card: 'POWER_9_PUBLIC',
    covered_count: 2,
    covered_cards: ['OPP_COVER_SECRET_A', 'OPP_COVER_SECRET_B'],
  }

  const publicState = {
    version: 208,
    pillars: [pillarA, pillarB],
    pillar_list: [pillarA, pillarB],
    turn: {
      plays: [
        { seat: 0, cards: ['OUTSIDE_TURN_PLAY_CARD'] },
        { seat: 1, covered_count: 1 },
      ],
    },
  }

  const privateState = {
    covered: [{ seat: 0, cards: ['SELF_COVER_FACE_POWER_5'], covered_count: 1 }],
    hand: ['OUTSIDE_HAND_CARD_A'],
  }

  return mount(PillarOverlay, {
    props: {
      open: true,
      visible: true,
      show: true,
      modelValue: true,
      viewMode: 'size',
      view_mode: 'size',
      mode: 'size',
      displayMode: 'size',
      includeOutsideCards: false,
      include_outside_cards: false,
      includeOuterCards: false,
      currentSeat: 0,
      selfSeat: 0,
      seat: 0,
      publicState,
      public_state: publicState,
      privateState,
      private_state: privateState,
      pillars: publicState.pillars,
      pillarList: publicState.pillars,
      pillar_list: publicState.pillars,
      ...extraProps,
    },
  })
}

async function mountRevealRelationModal(extraProps: GenericRecord = {}): Promise<VueWrapper> {
  const RevealRelationModal = await loadComponentFromCandidates(
    REVEAL_RELATION_MODAL_CANDIDATE_PATHS,
    'M8-CT-14/M8-CT-15',
    'a reveal relation modal component at "@/components/ingame/RevealRelationModal.vue" (or RevealRelationsModal.vue)',
  )

  const relations = [
    {
      relation_id: 'rel-valid',
      revealer_seat: 2,
      buckler_seat: 0,
      revealer_enough_at_time: false,
      active: true,
      invalid: false,
      is_invalid: false,
    },
    {
      relation_id: 'rel-invalid',
      revealer_seat: 1,
      buckler_seat: 2,
      revealer_enough_at_time: true,
      active: false,
      invalid: true,
      is_invalid: true,
    },
  ]

  const publicState = {
    reveal: {
      relations,
    },
  }

  return mount(RevealRelationModal, {
    props: {
      open: true,
      visible: true,
      show: true,
      modelValue: true,
      relations,
      revealRelations: relations,
      reveal_relations: relations,
      publicState,
      public_state: publicState,
      ...extraProps,
    },
  })
}

describe('M8 Stage 8 Red - overlay size view and reveal relation modal', () => {
  it('M8-CT-12 棋柱弹层“按大小”视图按牌力降序；对手垫牌仅数量化并在末尾', async () => {
    const wrapper = await mountPillarOverlay({
      includeOutsideCards: false,
      include_outside_cards: false,
      includeOuterCards: false,
    })

    const sizeItems = findBySelectorCandidates(wrapper, [
      '[data-testid="pillar-size-item"]',
      '[data-testid^="pillar-size-item-"]',
      '[data-testid="pillar-power-card"]',
      '[data-testid^="pillar-power-card-"]',
      '[data-testid*="size-card"]',
    ])

    if (sizeItems.length === 0) {
      throw new Error('M8-CT-12 requires size-view card list nodes in PillarOverlay.')
    }

    const content = wrapper.text()
    const idxPower9 = content.indexOf('POWER_9_PUBLIC')
    const idxPower7 = content.indexOf('POWER_7_PUBLIC')

    expect(idxPower9).toBeGreaterThanOrEqual(0)
    expect(idxPower7).toBeGreaterThanOrEqual(0)
    expect(idxPower9).toBeLessThan(idxPower7)

    expect(content).not.toContain('OPP_COVER_SECRET_A')
    expect(content).not.toContain('OPP_COVER_SECRET_B')

    const lastNode = sizeItems[sizeItems.length - 1]
    expect(containsCount(lastNode, 2)).toBe(true)
  })

  it('M8-CT-13 “包含柱外牌”开关仅影响本地展示集合（不触发后端请求/状态变更）', async () => {
    const originalFetch = globalThis.fetch
    const fetchSpy = vi.fn(async () => new Response(null, { status: 204 }))
    globalThis.fetch = fetchSpy as typeof fetch

    try {
      const wrapper = await mountPillarOverlay({
        includeOutsideCards: false,
        include_outside_cards: false,
        includeOuterCards: false,
      })

      const toggleCandidates = findBySelectorCandidates(wrapper, [
        '[data-testid="pillar-include-outside-toggle"]',
        '[data-testid^="pillar-include-outside-toggle-"]',
        'input[type="checkbox"][name="include-outside-cards"]',
        '[aria-label*="柱外牌"]',
      ])

      if (toggleCandidates.length === 0) {
        throw new Error('M8-CT-13 requires include-outside-cards toggle in size view.')
      }

      const before = wrapper.text()
      expect(before).not.toContain('OUTSIDE_HAND_CARD_A')
      expect(before).not.toContain('OUTSIDE_TURN_PLAY_CARD')

      await toggleCandidates[0].trigger('click')
      await wrapper.vm.$nextTick()

      const after = wrapper.text()
      expect(after).toContain('OUTSIDE_HAND_CARD_A')
      expect(after).toContain('OUTSIDE_TURN_PLAY_CARD')
      expect(fetchSpy).not.toHaveBeenCalled()

      for (const eventName of FORBIDDEN_REQUEST_EVENT_NAMES) {
        expect(wrapper.emitted(eventName)).toBeUndefined()
      }
    } finally {
      globalThis.fetch = originalFetch
    }
  })

  it('M8-CT-14 掀扣关系弹层可打开/关闭', async () => {
    const wrapper = await mountRevealRelationModal({
      open: true,
      visible: true,
      show: true,
      modelValue: true,
    })

    const modalNodes = findBySelectorCandidates(wrapper, [
      '[data-testid="reveal-relation-modal"]',
      '[data-testid="reveal-relations-modal"]',
      '[data-testid*="reveal-relation-modal"]',
    ])

    if (modalNodes.length === 0) {
      throw new Error('M8-CT-14 requires a reveal relation modal root node.')
    }

    const closeButtons = findBySelectorCandidates(wrapper, [
      '[data-testid="reveal-relation-close"]',
      '[data-testid="reveal-relations-close"]',
      'button[aria-label*="close"]',
      'button[aria-label*="关闭"]',
    ])

    if (closeButtons.length === 0) {
      throw new Error('M8-CT-14 requires a close button for reveal relation modal.')
    }

    await closeButtons[0].trigger('click')
    await wrapper.vm.$nextTick()

    const emitNames = ['close', 'update:modelValue', 'update:open', 'update:visible']
    const hasCloseSignal = emitNames.some((name) => (wrapper.emitted(name) ?? []).length > 0)
    const stillVisible = modalNodes.some((node) => node.isVisible())

    expect(hasCloseSignal || !stillVisible).toBe(true)
  })

  it('M8-CT-15 掀扣关系失效项样式正确（置灰 + 中划线）', async () => {
    const wrapper = await mountRevealRelationModal()

    const invalidRows = findBySelectorCandidates(wrapper, [
      '[data-testid="reveal-relation-item-invalid"]',
      '[data-testid^="reveal-relation-item-invalid-"]',
      '[data-testid="reveal-relations-item-invalid"]',
      '[data-testid*="relation-invalid"]',
      '[data-invalid="true"]',
      '[aria-disabled="true"]',
    ])

    if (invalidRows.length === 0) {
      throw new Error('M8-CT-15 requires invalid relation row markers.')
    }

    const hasGray = invalidRows.some((node) => hasGraySemantics(node))
    const hasLineThrough = invalidRows.some((node) => hasLineThroughSemantics(node))

    expect(hasGray).toBe(true)
    expect(hasLineThrough).toBe(true)
  })
})
