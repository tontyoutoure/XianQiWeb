import { mount, type DOMWrapper, type VueWrapper } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import type { Component } from 'vue'

type GenericRecord = Record<string, unknown>

interface ComponentModule {
  default?: Component
}

const PILLAR_BOARD_CANDIDATE_PATHS = [
  '/src/components/ingame/PillarBoard.vue',
  '/src/components/ingame/GamePillarBoard.vue',
  '/src/components/PillarBoard.vue',
  '/src/components/GamePillarBoard.vue',
] as const

const PILLAR_OVERLAY_CANDIDATE_PATHS = [
  '/src/components/ingame/PillarOverlay.vue',
  '/src/components/ingame/GamePillarOverlay.vue',
  '/src/components/PillarOverlay.vue',
  '/src/components/GamePillarOverlay.vue',
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

function buildPillarFixture() {
  const publicPillar = {
    pillar_id: 'pillar-1',
    pillarId: 'pillar-1',
    owner_seat: 1,
    ownerSeat: 1,
    cards: ['PILLAR_MAX_VISIBLE_CARD', 'PILLAR_HIDDEN_CARD_1', 'PILLAR_HIDDEN_CARD_2'],
    max_card: 'PILLAR_MAX_VISIBLE_CARD',
    maxCard: 'PILLAR_MAX_VISIBLE_CARD',
    covered_count: 2,
    coveredCount: 2,
    covered_cards: ['OPP_COVER_SECRET_A', 'OPP_COVER_SECRET_B'],
    coveredCards: ['OPP_COVER_SECRET_A', 'OPP_COVER_SECRET_B'],
  }

  const publicState = {
    version: 88,
    pillars: [publicPillar],
    pillar_list: [publicPillar],
    covered: [{ seat: 1, covered_count: 2, coveredCount: 2 }],
  }

  const privateState = {
    covered: [
      {
        seat: 0,
        cards: ['SELF_COVER_CARD_A', 'SELF_COVER_CARD_B'],
        covered_count: 2,
      },
    ],
  }

  return { publicState, privateState }
}

async function mountPillarBoard(extraProps: GenericRecord = {}): Promise<VueWrapper> {
  const PillarBoard = await loadComponentFromCandidates(
    PILLAR_BOARD_CANDIDATE_PATHS,
    'M8-CT-08~10',
    'a pillar board component at "@/components/ingame/PillarBoard.vue" (or equivalent candidate path)',
  )

  const { publicState, privateState } = buildPillarFixture()
  return mount(PillarBoard, {
    props: {
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

async function mountPillarOverlay(extraProps: GenericRecord = {}): Promise<VueWrapper> {
  const PillarOverlay = await loadComponentFromCandidates(
    PILLAR_OVERLAY_CANDIDATE_PATHS,
    'M8-CT-11',
    'a pillar overlay component at "@/components/ingame/PillarOverlay.vue" (or equivalent candidate path)',
  )

  const overlayPillar = {
    pillar_id: 'overlay-pillar-1',
    pillarId: 'overlay-pillar-1',
    owner_seat: 0,
    ownerSeat: 0,
    cards: ['OVERLAY_CARD_A', 'OVERLAY_CARD_B', 'OVERLAY_CARD_C'],
  }

  const publicState = {
    version: 89,
    pillars: [overlayPillar],
    pillar_list: [overlayPillar],
  }

  return mount(PillarOverlay, {
    props: {
      open: true,
      visible: true,
      show: true,
      modelValue: true,
      viewMode: 'ownership',
      view_mode: 'ownership',
      mode: 'ownership',
      displayMode: 'ownership',
      currentSeat: 0,
      selfSeat: 0,
      seat: 0,
      publicState,
      public_state: publicState,
      pillars: publicState.pillars,
      pillarList: publicState.pillars,
      pillar_list: publicState.pillars,
      ...extraProps,
    },
  })
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

function nodeContainsCount(node: DOMWrapper<Element>, expectedCount: number): boolean {
  const expected = String(expectedCount)
  if (node.text().includes(expected)) {
    return true
  }

  const dataCount = node.attributes('data-count')
  if (dataCount === expected) {
    return true
  }

  const ariaLabel = node.attributes('aria-label') ?? ''
  return ariaLabel.includes(expected)
}

describe('M8 Stage 7 Red - pillar covered information and overlay views', () => {
  it('M8-CT-08 公共区垫牌仅显示 covered_count（不展示对手垫牌牌面）', async () => {
    const wrapper = await mountPillarBoard()

    const coveredCountNodes = findBySelectorCandidates(wrapper, [
      '[data-testid="pillar-covered-count"]',
      '[data-testid^="pillar-covered-count-"]',
      '[data-testid*="covered-count"]',
    ])

    if (coveredCountNodes.length === 0) {
      throw new Error('M8-CT-08 requires covered-count marker in pillar board.')
    }

    expect(coveredCountNodes.some((node) => node.isVisible())).toBe(true)
    expect(coveredCountNodes.some((node) => nodeContainsCount(node, 2))).toBe(true)

    const content = wrapper.text()
    expect(content).not.toContain('OPP_COVER_SECRET_A')
    expect(content).not.toContain('OPP_COVER_SECRET_B')
  })

  it('M8-CT-09 己方垫牌可由 private_state.covered 补全本地牌面（仅自己视角）', async () => {
    const wrapper = await mountPillarBoard()
    const content = wrapper.text()

    expect(content).toContain('SELF_COVER_CARD_A')
    expect(content).toContain('SELF_COVER_CARD_B')
    expect(content).not.toContain('OPP_COVER_SECRET_A')
    expect(content).not.toContain('OPP_COVER_SECRET_B')
  })

  it('M8-CT-10 主界面棋柱“最大牌完整 + 其余遮挡”展示', async () => {
    const wrapper = await mountPillarBoard()
    const content = wrapper.text()

    expect(content).toContain('PILLAR_MAX_VISIBLE_CARD')
    expect(content).not.toContain('PILLAR_HIDDEN_CARD_1')
    expect(content).not.toContain('PILLAR_HIDDEN_CARD_2')

    const maskedNodes = findBySelectorCandidates(wrapper, [
      '[data-testid="pillar-masked-card"]',
      '[data-testid^="pillar-masked-card-"]',
      '[data-testid*="card-back"]',
      '.card-back',
      '[aria-label*="hidden"]',
      '[aria-label*="遮挡"]',
    ])

    if (maskedNodes.length === 0) {
      throw new Error('M8-CT-10 requires masked/covered card rendering for non-max cards.')
    }

    expect(maskedNodes.length).toBeGreaterThanOrEqual(1)
  })

  it('M8-CT-11 棋柱弹层按归属视图全展开三枚牌', async () => {
    const wrapper = await mountPillarOverlay()
    const content = wrapper.text()

    expect(content).toContain('OVERLAY_CARD_A')
    expect(content).toContain('OVERLAY_CARD_B')
    expect(content).toContain('OVERLAY_CARD_C')

    const ownerGroups = findBySelectorCandidates(wrapper, [
      '[data-testid="pillar-owner-group"]',
      '[data-testid^="pillar-owner-group-"]',
      '[data-testid*="owner-group"]',
    ])

    if (ownerGroups.length === 0) {
      throw new Error('M8-CT-11 requires ownership-group sections in pillar overlay.')
    }

    expect(ownerGroups.length).toBeGreaterThanOrEqual(1)
  })
})
