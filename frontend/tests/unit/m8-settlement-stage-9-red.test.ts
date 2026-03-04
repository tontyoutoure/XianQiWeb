import { mount, type DOMWrapper, type VueWrapper } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import type { Component } from 'vue'

type GenericRecord = Record<string, unknown>

interface ComponentModule {
  default?: Component
}

interface SettlementPlayerEntry {
  seat: number
  username: string
  delta: number
  delta_enough: number
  delta_reveal: number
  delta_ceramic: number
}

const SETTLEMENT_MODAL_CANDIDATE_PATHS = [
  '/src/components/ingame/SettlementModal.vue',
  '/src/components/ingame/GameSettlementModal.vue',
  '/src/components/SettlementModal.vue',
  '/src/components/GameSettlementModal.vue',
] as const

const INGAME_SHELL_CANDIDATE_PATHS = [
  '/src/components/ingame/IngameShell.vue',
  '/src/components/ingame/GameIngameShell.vue',
  '/src/components/IngameShell.vue',
  '/src/components/GameIngameShell.vue',
] as const

const SETTLEMENT_MODAL_SELECTOR_CANDIDATES = [
  '[data-testid="settlement-modal"]',
  '[data-testid="game-settlement-modal"]',
  '[data-testid*="settlement-modal"]',
  '[aria-label*="结算"]',
]

const SETTLEMENT_CLOSE_BUTTON_SELECTOR_CANDIDATES = [
  '[data-testid="settlement-close"]',
  '[data-testid="game-settlement-close"]',
  '[data-testid*="settlement-close"]',
  'button[aria-label*="close"]',
  'button[aria-label*="关闭"]',
]

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

    const module = (await loader()) as ComponentModule
    if (module.default) {
      return module.default
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

function buildSettlementEntries(): SettlementPlayerEntry[] {
  return [
    {
      seat: 0,
      username: 'alice',
      delta: 8,
      delta_enough: 5,
      delta_reveal: 2,
      delta_ceramic: 1,
    },
    {
      seat: 1,
      username: 'bob',
      delta: -5,
      delta_enough: -3,
      delta_reveal: -1,
      delta_ceramic: -1,
    },
    {
      seat: 2,
      username: 'carol',
      delta: -3,
      delta_enough: -2,
      delta_reveal: -1,
      delta_ceramic: 0,
    },
  ]
}

async function mountSettlementModal(extraProps: GenericRecord = {}): Promise<VueWrapper> {
  const SettlementModal = await loadComponentFromCandidates(
    SETTLEMENT_MODAL_CANDIDATE_PATHS,
    'M8-CT-16',
    'a settlement modal component at "@/components/ingame/SettlementModal.vue" (or equivalent candidate path)',
  )

  const players = buildSettlementEntries()
  const settlement = {
    players,
    player_results: players,
    details: players,
  }

  return mount(SettlementModal, {
    props: {
      open: true,
      visible: true,
      show: true,
      modelValue: true,
      settlement,
      settlementResult: settlement,
      settlement_result: settlement,
      players,
      entries: players,
      ...extraProps,
    },
  })
}

async function mountIngameShell(extraProps: GenericRecord = {}): Promise<VueWrapper> {
  const IngameShell = await loadComponentFromCandidates(
    INGAME_SHELL_CANDIDATE_PATHS,
    'M8-IT-06/M8-IT-07/M8-IT-08',
    'an ingame shell component at "@/components/ingame/IngameShell.vue" (or equivalent candidate path)',
  )

  const settlementEntries = buildSettlementEntries()

  const publicState = {
    version: 901,
    phase: 'in_round',
    turn: {
      plays: [{ seat: 0, cards: ['CARD_A'] }],
    },
    pillars: [
      {
        pillar_id: 'pillar-1',
        owner_seat: 0,
        cards: ['PILLAR_CARD_A', 'PILLAR_CARD_B'],
      },
    ],
  }

  const settlementPayload = {
    players: settlementEntries,
    player_results: settlementEntries,
    details: settlementEntries,
  }

  return mount(IngameShell, {
    props: {
      roomStatus: 'playing',
      room_status: 'playing',
      status: 'playing',
      publicState,
      public_state: publicState,
      privateState: {
        hand: ['HAND_CARD_A', 'HAND_CARD_B'],
      },
      private_state: {
        hand: ['HAND_CARD_A', 'HAND_CARD_B'],
      },
      settlement: null,
      settlementResult: null,
      settlement_result: null,
      latestGameEvent: null,
      latest_game_event: null,
      ...extraProps,
      settlementPayload,
    },
  })
}

function assertSettlementModalVisible(wrapper: VueWrapper, testId: string): void {
  const modalNodes = findBySelectorCandidates(wrapper, SETTLEMENT_MODAL_SELECTOR_CANDIDATES)

  if (modalNodes.length === 0) {
    throw new Error(
      `${testId} requires settlement modal root node and auto-open behavior when receiving SETTLEMENT or phase=settlement.`,
    )
  }

  expect(modalNodes.some((node) => node.isVisible())).toBe(true)
}

function containsSignedNumber(text: string, value: number): boolean {
  const valueAsString = String(value)
  if (text.includes(valueAsString)) {
    return true
  }

  const valueWithPlus = value > 0 ? `+${value}` : valueAsString
  return text.includes(valueWithPlus)
}

describe('M8 Stage 9 Red - settlement and stage transition', () => {
  it('M8-IT-06 收到 SETTLEMENT 或 phase=settlement 自动弹结算层', async () => {
    const wrapper = await mountIngameShell()

    await wrapper.setProps({
      phase: 'settlement',
      roomStatus: 'settlement',
      room_status: 'settlement',
      publicState: {
        version: 902,
        phase: 'settlement',
      },
      public_state: {
        version: 902,
        phase: 'settlement',
      },
      latestGameEvent: {
        type: 'SETTLEMENT',
        payload: {
          players: buildSettlementEntries(),
        },
      },
      latest_game_event: {
        type: 'SETTLEMENT',
        payload: {
          players: buildSettlementEntries(),
        },
      },
    })
    await wrapper.vm.$nextTick()

    assertSettlementModalVisible(wrapper, 'M8-IT-06')
  })

  it('M8-CT-16 结算弹层展示 delta/delta_enough/delta_reveal/delta_ceramic 且总和正确', async () => {
    const wrapper = await mountSettlementModal()
    const players = buildSettlementEntries()

    const rows = findBySelectorCandidates(wrapper, [
      '[data-testid="settlement-player-row"]',
      '[data-testid^="settlement-player-row-"]',
      '[data-testid*="settlement-row"]',
      '[data-testid="settlement-item"]',
      '[data-testid^="settlement-item-"]',
    ])

    if (rows.length === 0) {
      throw new Error('M8-CT-16 requires settlement row nodes for each player entry.')
    }

    const pageText = wrapper.text().toLowerCase()
    expect(pageText.includes('delta') || pageText.includes('总计')).toBe(true)
    expect(pageText.includes('delta_enough') || pageText.includes('够')).toBe(true)
    expect(pageText.includes('delta_reveal') || pageText.includes('掀')).toBe(true)
    expect(pageText.includes('delta_ceramic') || pageText.includes('瓷')).toBe(true)

    for (const player of players) {
      const expectedTotal = player.delta_enough + player.delta_reveal + player.delta_ceramic
      expect(expectedTotal).toBe(player.delta)

      const matchedRow = rows.find((row) => row.text().includes(player.username) || row.text().includes(String(player.seat)))
      if (!matchedRow) {
        throw new Error(`M8-CT-16 requires settlement row for player ${player.username}.`)
      }

      const rowText = matchedRow.text()
      expect(containsSignedNumber(rowText, player.delta)).toBe(true)
      expect(containsSignedNumber(rowText, player.delta_enough)).toBe(true)
      expect(containsSignedNumber(rowText, player.delta_reveal)).toBe(true)
      expect(containsSignedNumber(rowText, player.delta_ceramic)).toBe(true)
    }
  })

  it('M8-IT-07 关闭结算弹层后出现“已进入准备阶段，请重新 ready 开新局”', async () => {
    const wrapper = await mountIngameShell({
      phase: 'settlement',
      roomStatus: 'settlement',
      room_status: 'settlement',
      publicState: {
        version: 903,
        phase: 'settlement',
      },
      public_state: {
        version: 903,
        phase: 'settlement',
      },
      latestGameEvent: {
        type: 'SETTLEMENT',
        payload: {
          players: buildSettlementEntries(),
        },
      },
      latest_game_event: {
        type: 'SETTLEMENT',
        payload: {
          players: buildSettlementEntries(),
        },
      },
    })

    assertSettlementModalVisible(wrapper, 'M8-IT-07')

    const closeButtons = findBySelectorCandidates(wrapper, SETTLEMENT_CLOSE_BUTTON_SELECTOR_CANDIDATES)
    if (closeButtons.length === 0) {
      throw new Error('M8-IT-07 requires close button in settlement modal.')
    }

    await closeButtons[0].trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('已进入准备阶段，请重新 ready 开新局')
  })

  it('M8-IT-08 房间冷结束（playing->waiting 且无结算）时清空对局 UI并显示“对局结束”', async () => {
    const wrapper = await mountIngameShell({
      roomStatus: 'playing',
      room_status: 'playing',
      status: 'playing',
      settlement: null,
      settlementResult: null,
      settlement_result: null,
      publicState: {
        version: 904,
        phase: 'in_round',
        turn: {
          plays: [{ seat: 0, cards: ['HOT_GAME_CARD'] }],
        },
      },
      public_state: {
        version: 904,
        phase: 'in_round',
        turn: {
          plays: [{ seat: 0, cards: ['HOT_GAME_CARD'] }],
        },
      },
      privateState: {
        hand: ['HOT_HAND_CARD'],
      },
      private_state: {
        hand: ['HOT_HAND_CARD'],
      },
    })

    await wrapper.setProps({
      roomStatus: 'waiting',
      room_status: 'waiting',
      status: 'waiting',
      phase: 'waiting',
      settlement: null,
      settlementResult: null,
      settlement_result: null,
      latestGameEvent: {
        type: 'ROOM_UPDATE',
        payload: {
          room: {
            status: 'waiting',
          },
        },
      },
      latest_game_event: {
        type: 'ROOM_UPDATE',
        payload: {
          room: {
            status: 'waiting',
          },
        },
      },
    })
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('对局结束')

    const staleIngameNodes = findBySelectorCandidates(wrapper, [
      '[data-testid="ingame-action-bar"]',
      '[data-testid="turn-plays-panel"]',
      '[data-testid="pillar-board"]',
      '[data-testid="ingame-hand-cards"]',
      '[data-testid*="ingame-"]',
    ])

    expect(staleIngameNodes.filter((node) => node.isVisible()).length).toBe(0)
    expect(wrapper.text()).not.toContain('HOT_GAME_CARD')
    expect(wrapper.text()).not.toContain('HOT_HAND_CARD')
  })
})
