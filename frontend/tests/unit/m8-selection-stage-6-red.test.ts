import { mount, type VueWrapper } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import type { Component } from 'vue'

import * as ingameActionsModule from '@/stores/ingame-actions'

type ActionType = 'BUCKLE' | 'PASS_BUCKLE' | 'REVEAL' | 'PASS_REVEAL' | 'PLAY' | 'COVER'
type CardUiState = 'normal' | 'interactive' | 'selected'

interface LegalAction {
  type: ActionType
  payload_cards?: Record<string, number>
  required_count?: number
}

interface LegalActions {
  seat: number
  actions: LegalAction[]
}

type GenericRecord = Record<string, unknown>
type SelectionControllerFactory = (input: GenericRecord) => unknown

interface TurnPlaysComponentModule {
  default?: Component
}

const SELECTION_FACTORY_EXPORT_CANDIDATES = [
  'createCardSelectionControllerForTest',
  'createHandSelectionControllerForTest',
  'createSelectionControllerForTest',
] as const

const TURN_PLAYS_COMPONENT_PATH_CANDIDATES = [
  '/src/components/ingame/TurnPlaysPanel.vue',
  '/src/components/ingame/GameTurnPlays.vue',
  '/src/components/TurnPlaysPanel.vue',
  '/src/components/GameTurnPlays.vue',
] as const

function requireSelectionControllerFactory(testId: string): SelectionControllerFactory {
  const moduleExports = ingameActionsModule as unknown as Record<string, unknown>

  for (const exportName of SELECTION_FACTORY_EXPORT_CANDIDATES) {
    const factory = moduleExports[exportName]
    if (typeof factory === 'function') {
      return factory as SelectionControllerFactory
    }
  }

  throw new Error(
    `${testId} requires one of ${SELECTION_FACTORY_EXPORT_CANDIDATES.join(', ')} in @/stores/ingame-actions`,
  )
}

function createRoundStarterPlaySelectionController(testId: string) {
  const factory = requireSelectionControllerFactory(testId)
  const handCards = ['R_SHI', 'B_SHI', 'R_NIU', 'B_NIU', 'R_XIANG', 'R_MA']
  const legalActions: LegalActions = {
    seat: 0,
    actions: [
      { type: 'PLAY', payload_cards: { R_SHI: 1, B_SHI: 1 } },
      { type: 'PLAY', payload_cards: { R_NIU: 1, B_NIU: 1, R_XIANG: 1 } },
      { type: 'PLAY', payload_cards: { R_MA: 1 } },
    ],
  }

  return factory({
    actionType: 'PLAY',
    action_type: 'PLAY',
    handCards,
    hand_cards: handCards,
    legalActions,
    legal_actions: legalActions,
    isRoundStarter: true,
    is_round_starter: true,
    isFirstPlayOfRound: true,
    is_first_play_of_round: true,
  })
}

function asRecord(value: unknown): GenericRecord | null {
  if (value && typeof value === 'object') {
    return value as GenericRecord
  }
  return null
}

function readStringArray(record: GenericRecord, keys: string[]): string[] {
  for (const key of keys) {
    const value = record[key]
    if (Array.isArray(value) && value.every((item) => typeof item === 'string')) {
      return value as string[]
    }
  }
  return []
}

function normalizeCardUiState(rawState: unknown): CardUiState | null {
  if (typeof rawState !== 'string') {
    return null
  }

  const token = rawState.trim().toLowerCase()
  if (token === 'selected' || token === 'picked' || token === 'active') {
    return 'selected'
  }
  if (
    token === 'interactive' ||
    token === 'interactable' ||
    token === 'clickable' ||
    token === 'available' ||
    token === 'legal'
  ) {
    return 'interactive'
  }
  if (token === 'normal' || token === 'inactive' || token === 'disabled' || token === 'none') {
    return 'normal'
  }
  return null
}

function findCallable(controller: unknown, methodNames: string[]) {
  const record = asRecord(controller)
  if (!record) {
    return null
  }

  for (const methodName of methodNames) {
    const method = record[methodName]
    if (typeof method === 'function') {
      return method as (...args: unknown[]) => unknown
    }
  }

  return null
}

async function clickCard(controller: unknown, cardId: string, testId: string): Promise<void> {
  const clickMethod = findCallable(controller, [
    'clickCard',
    'toggleCard',
    'toggleCardSelection',
    'onCardClick',
    'handleCardClick',
    'selectCard',
  ])

  if (!clickMethod) {
    throw new Error(
      `${testId} requires selection controller to expose clickCard/toggleCard style method.`,
    )
  }

  const result = clickMethod(cardId)
  if (result instanceof Promise) {
    await result
  }
}

function readStateSnapshot(controller: unknown, testId: string): GenericRecord {
  const snapshotGetter = findCallable(controller, ['getState', 'snapshot', 'getSnapshot'])
  if (!snapshotGetter) {
    throw new Error(`${testId} requires getState/snapshot/getSnapshot method.`)
  }

  const snapshot = asRecord(snapshotGetter())
  if (!snapshot) {
    throw new Error(`${testId} requires state snapshot object.`)
  }

  return snapshot
}

function readSelectedCardsFromSnapshot(snapshot: GenericRecord): string[] {
  const topLevel = readStringArray(snapshot, ['selectedCards', 'selected_cards'])
  if (topLevel.length > 0) {
    return topLevel
  }

  const uiSelection = asRecord(snapshot.uiSelectionState) ?? asRecord(snapshot.ui_selection_state)
  if (!uiSelection) {
    return []
  }

  return readStringArray(uiSelection, ['selectedCards', 'selected_cards'])
}

function readInteractiveCardsFromSnapshot(snapshot: GenericRecord): string[] {
  const topLevel = readStringArray(snapshot, ['interactiveCards', 'interactive_cards', 'clickableCards'])
  if (topLevel.length > 0) {
    return topLevel
  }

  const uiSelection = asRecord(snapshot.uiSelectionState) ?? asRecord(snapshot.ui_selection_state)
  if (!uiSelection) {
    return []
  }

  return readStringArray(uiSelection, ['interactiveCards', 'interactive_cards', 'clickableCards'])
}

function readSelectedCards(controller: unknown, testId: string): string[] {
  return readSelectedCardsFromSnapshot(readStateSnapshot(controller, testId))
}

function readCardStateFromSnapshot(snapshot: GenericRecord, cardId: string): CardUiState | null {
  const stateMaps = [
    snapshot.cardStates,
    snapshot.card_states,
    snapshot.handCardStates,
    snapshot.hand_card_states,
  ]

  for (const stateMapCandidate of stateMaps) {
    const stateMap = asRecord(stateMapCandidate)
    if (!stateMap) {
      continue
    }

    const value = stateMap[cardId]
    const normalized = normalizeCardUiState(value)
    if (normalized) {
      return normalized
    }

    const nested = asRecord(value)
    if (!nested) {
      continue
    }

    const nestedState =
      normalizeCardUiState(nested.state) ?? normalizeCardUiState(nested.status) ?? normalizeCardUiState(nested.mode)
    if (nestedState) {
      return nestedState
    }
  }

  const selectedSet = new Set(readSelectedCardsFromSnapshot(snapshot))
  const interactiveSet = new Set(readInteractiveCardsFromSnapshot(snapshot))

  if (selectedSet.has(cardId)) {
    return 'selected'
  }
  if (interactiveSet.has(cardId)) {
    return 'interactive'
  }
  if (selectedSet.size > 0 || interactiveSet.size > 0) {
    return 'normal'
  }

  return null
}

function readCardUiState(controller: unknown, cardId: string, testId: string): CardUiState {
  const directGetter = findCallable(controller, ['getCardState', 'getCardUiState', 'readCardState'])
  if (directGetter) {
    const directState = normalizeCardUiState(directGetter(cardId))
    if (directState) {
      return directState
    }
  }

  const snapshot = readStateSnapshot(controller, testId)
  const snapshotState = readCardStateFromSnapshot(snapshot, cardId)
  if (snapshotState) {
    return snapshotState
  }

  throw new Error(`${testId} requires card UI state (normal/interactive/selected).`)
}

function normalizeBooleanLike(value: unknown): boolean | null {
  if (typeof value === 'boolean') {
    return value
  }
  if (typeof value === 'number') {
    if (value === 0) {
      return false
    }
    if (value === 1) {
      return true
    }
  }
  if (typeof value === 'string') {
    const token = value.trim().toLowerCase()
    if (token === 'true' || token === 'enabled' || token === 'valid') {
      return true
    }
    if (token === 'false' || token === 'disabled' || token === 'invalid') {
      return false
    }
  }

  return null
}

function readSubmitEnabled(controller: unknown, testId: string, actionType: 'PLAY' | 'COVER'): boolean {
  const methodGetter = findCallable(controller, [
    'canSubmit',
    'isSubmitEnabled',
    'hasLegalSelection',
    'isSelectionValid',
  ])
  if (methodGetter) {
    const direct = normalizeBooleanLike(methodGetter(actionType)) ?? normalizeBooleanLike(methodGetter())
    if (direct !== null) {
      return direct
    }
  }

  const snapshot = readStateSnapshot(controller, testId)
  const directCandidates = [
    snapshot.canSubmit,
    snapshot.submitEnabled,
    snapshot.hasLegalSelection,
    snapshot.has_legal_selection,
    snapshot.isSelectionValid,
    snapshot.is_selection_valid,
  ]

  for (const candidate of directCandidates) {
    const normalized = normalizeBooleanLike(candidate)
    if (normalized !== null) {
      return normalized
    }
  }

  const mapCandidates = [
    snapshot.submitEnabledMap,
    snapshot.submit_enabled_map,
    snapshot.actionDisabledMap,
    snapshot.action_disabled_map,
    snapshot.actionButtonDisabledMap,
    snapshot.action_button_disabled_map,
  ]

  for (const mapCandidate of mapCandidates) {
    const map = asRecord(mapCandidate)
    if (!map) {
      continue
    }

    const value = normalizeBooleanLike(map[actionType])
    if (value === null) {
      continue
    }

    if (mapCandidate === snapshot.actionDisabledMap || mapCandidate === snapshot.action_disabled_map) {
      return !value
    }

    if (mapCandidate === snapshot.actionButtonDisabledMap || mapCandidate === snapshot.action_button_disabled_map) {
      return !value
    }

    if (mapCandidate === snapshot.submitEnabledMap || mapCandidate === snapshot.submit_enabled_map) {
      return value
    }

    return !value
  }

  throw new Error(
    `${testId} requires selection controller state to expose submit availability for ${actionType}.`,
  )
}

async function loadTurnPlaysComponent(): Promise<Component> {
  const componentModules = import.meta.glob('/src/components/**/*.vue')

  for (const path of TURN_PLAYS_COMPONENT_PATH_CANDIDATES) {
    const loader = componentModules[path]
    if (!loader) {
      continue
    }

    const componentModule = (await loader()) as TurnPlaysComponentModule
    if (componentModule.default) {
      return componentModule.default
    }
  }

  throw new Error(
    'M8-CT-07 requires a turn plays component at "@/components/ingame/TurnPlaysPanel.vue" or "@/components/ingame/GameTurnPlays.vue".',
  )
}

function buildTurnPlaysProps(): GenericRecord {
  const plays = [
    { seat: 2, payload_cards: { R_SHI: 1, B_SHI: 1 } },
    { seat: 0, payload_cards: { R_MA: 1 } },
  ]
  const turn = { plays }
  const publicState = { version: 41, turn }

  return {
    plays,
    turnPlays: plays,
    turn_plays: plays,
    turn,
    publicState,
    public_state: publicState,
  }
}

async function mountTurnPlaysComponent(): Promise<VueWrapper> {
  const TurnPlaysComponent = await loadTurnPlaysComponent()
  return mount(TurnPlaysComponent, {
    props: buildTurnPlaysProps(),
  })
}

function readSeatFromRow(row: VueWrapper): number | null {
  const attrSeat = row.attributes('data-seat') || row.attributes('data-seat-index') || row.attributes('seat')
  if (attrSeat && Number.isFinite(Number(attrSeat))) {
    return Number(attrSeat)
  }

  const seatNode = row.find('[data-testid="turn-play-seat"]')
  if (seatNode.exists()) {
    const match = seatNode.text().match(/(\d+)/)
    if (match) {
      return Number(match[1])
    }
  }

  const textMatch = row.text().match(/(?:seat|座位|位)\s*([0-9]+)/i)
  if (textMatch) {
    return Number(textMatch[1])
  }

  return null
}

function findTurnPlayRows(wrapper: VueWrapper): VueWrapper[] {
  const selectors = [
    '[data-testid="turn-play-item"]',
    '[data-testid="turn-play-row"]',
    '[data-testid^="turn-play-item-"]',
    '[data-testid^="turn-play-row-"]',
  ]

  for (const selector of selectors) {
    const rows = wrapper.findAll(selector)
    if (rows.length > 0) {
      return rows
    }
  }

  throw new Error('M8-CT-07 requires turn plays rows with data-testid "turn-play-item"/"turn-play-row".')
}

describe('M8 Stage 6 Red - round starter PLAY selection and turn plays rendering', () => {
  it('M8-UT-10 PLAY 首位对子/三牛部分选中时仅同组合可继续选', async () => {
    const pairController = createRoundStarterPlaySelectionController('M8-UT-10')
    await clickCard(pairController, 'R_SHI', 'M8-UT-10')

    expect(readCardUiState(pairController, 'R_SHI', 'M8-UT-10')).toBe('selected')
    expect(readCardUiState(pairController, 'B_SHI', 'M8-UT-10')).toBe('interactive')
    expect(readCardUiState(pairController, 'R_NIU', 'M8-UT-10')).toBe('normal')
    expect(readCardUiState(pairController, 'B_NIU', 'M8-UT-10')).toBe('normal')
    expect(readCardUiState(pairController, 'R_XIANG', 'M8-UT-10')).toBe('normal')
    expect(readCardUiState(pairController, 'R_MA', 'M8-UT-10')).toBe('normal')
    expect(readSubmitEnabled(pairController, 'M8-UT-10', 'PLAY')).toBe(false)

    const tripleController = createRoundStarterPlaySelectionController('M8-UT-10')
    await clickCard(tripleController, 'R_NIU', 'M8-UT-10')

    expect(readCardUiState(tripleController, 'R_NIU', 'M8-UT-10')).toBe('selected')
    expect(readCardUiState(tripleController, 'B_NIU', 'M8-UT-10')).toBe('interactive')
    expect(readCardUiState(tripleController, 'R_XIANG', 'M8-UT-10')).toBe('interactive')
    expect(readCardUiState(tripleController, 'R_SHI', 'M8-UT-10')).toBe('normal')
    expect(readCardUiState(tripleController, 'B_SHI', 'M8-UT-10')).toBe('normal')
    expect(readCardUiState(tripleController, 'R_MA', 'M8-UT-10')).toBe('normal')
    expect(readSubmitEnabled(tripleController, 'M8-UT-10', 'PLAY')).toBe(false)
  })

  it('M8-UT-11 PLAY 首位满足合法组合后 PLAY 可提交', async () => {
    const controller = createRoundStarterPlaySelectionController('M8-UT-11')

    await clickCard(controller, 'R_SHI', 'M8-UT-11')
    expect(readSubmitEnabled(controller, 'M8-UT-11', 'PLAY')).toBe(false)

    await clickCard(controller, 'B_SHI', 'M8-UT-11')
    expect(new Set(readSelectedCards(controller, 'M8-UT-11'))).toEqual(new Set(['R_SHI', 'B_SHI']))
    expect(readSubmitEnabled(controller, 'M8-UT-11', 'PLAY')).toBe(true)

    const tripleController = createRoundStarterPlaySelectionController('M8-UT-11')
    await clickCard(tripleController, 'R_NIU', 'M8-UT-11')
    await clickCard(tripleController, 'B_NIU', 'M8-UT-11')
    expect(readSubmitEnabled(tripleController, 'M8-UT-11', 'PLAY')).toBe(false)

    await clickCard(tripleController, 'R_XIANG', 'M8-UT-11')
    expect(new Set(readSelectedCards(tripleController, 'M8-UT-11'))).toEqual(
      new Set(['R_NIU', 'B_NIU', 'R_XIANG']),
    )
    expect(readSubmitEnabled(tripleController, 'M8-UT-11', 'PLAY')).toBe(true)
  })

  it('M8-UT-12 PLAY 首位撤销后重算可交互集合', async () => {
    const controller = createRoundStarterPlaySelectionController('M8-UT-12')

    await clickCard(controller, 'R_NIU', 'M8-UT-12')
    await clickCard(controller, 'B_NIU', 'M8-UT-12')
    await clickCard(controller, 'R_XIANG', 'M8-UT-12')

    expect(new Set(readSelectedCards(controller, 'M8-UT-12'))).toEqual(
      new Set(['R_NIU', 'B_NIU', 'R_XIANG']),
    )
    expect(readSubmitEnabled(controller, 'M8-UT-12', 'PLAY')).toBe(true)

    await clickCard(controller, 'B_NIU', 'M8-UT-12')

    expect(new Set(readSelectedCards(controller, 'M8-UT-12'))).toEqual(new Set(['R_NIU', 'R_XIANG']))
    expect(readCardUiState(controller, 'B_NIU', 'M8-UT-12')).toBe('interactive')
    expect(readCardUiState(controller, 'R_SHI', 'M8-UT-12')).toBe('normal')
    expect(readCardUiState(controller, 'B_SHI', 'M8-UT-12')).toBe('normal')
    expect(readCardUiState(controller, 'R_MA', 'M8-UT-12')).toBe('normal')
    expect(readSubmitEnabled(controller, 'M8-UT-12', 'PLAY')).toBe(false)
  })

  it('M8-CT-07 出棋状况区正确渲染 public_state.turn.plays（含顺序与 seat 标识）', async () => {
    const wrapper = await mountTurnPlaysComponent()
    const rows = findTurnPlayRows(wrapper)

    expect(rows).toHaveLength(2)

    const seatOrder = rows.map((row) => readSeatFromRow(row))
    expect(seatOrder).toEqual([2, 0])
  })
})
