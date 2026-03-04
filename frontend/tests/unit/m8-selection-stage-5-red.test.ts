import { describe, expect, it } from 'vitest'

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

const SELECTION_FACTORY_EXPORT_CANDIDATES = [
  'createCardSelectionControllerForTest',
  'createHandSelectionControllerForTest',
  'createSelectionControllerForTest',
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

function createCoverSelectionController(testId: string, requiredCount: number) {
  const factory = requireSelectionControllerFactory(testId)
  const handCards = ['R_SHI', 'B_NIU', 'R_MA']
  const legalActions: LegalActions = {
    seat: 0,
    actions: [{ type: 'COVER', required_count: requiredCount }],
  }

  return factory({
    actionType: 'COVER',
    action_type: 'COVER',
    requiredCount,
    required_count: requiredCount,
    handCards,
    hand_cards: handCards,
    legalActions,
    legal_actions: legalActions,
  })
}

function createPlaySelectionController(testId: string) {
  const factory = requireSelectionControllerFactory(testId)
  const handCards = ['R_SHI', 'B_SHI', 'R_MA', 'B_MA']
  const legalActions: LegalActions = {
    seat: 0,
    actions: [
      { type: 'PLAY', payload_cards: { R_SHI: 1, B_SHI: 1 } },
      { type: 'PLAY', payload_cards: { R_MA: 1, B_MA: 1 } },
    ],
  }

  return factory({
    actionType: 'PLAY',
    action_type: 'PLAY',
    handCards,
    hand_cards: handCards,
    legalActions,
    legal_actions: legalActions,
    isRoundStarter: false,
    is_round_starter: false,
    isFirstPlayOfRound: false,
    is_first_play_of_round: false,
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

describe('M8 Stage 5 Red - selection state machine for COVER/PLAY advanced cases', () => {
  it('M8-UT-06 COVER 达到 required_count 后锁定其余手牌（其余 normal），且提交可用', async () => {
    const controller = createCoverSelectionController('M8-UT-06', 2)

    await clickCard(controller, 'R_SHI', 'M8-UT-06')
    await clickCard(controller, 'B_NIU', 'M8-UT-06')

    expect(readCardUiState(controller, 'R_SHI', 'M8-UT-06')).toBe('selected')
    expect(readCardUiState(controller, 'B_NIU', 'M8-UT-06')).toBe('selected')
    expect(readCardUiState(controller, 'R_MA', 'M8-UT-06')).toBe('normal')
    expect(readSubmitEnabled(controller, 'M8-UT-06', 'COVER')).toBe(true)
  })

  it('M8-UT-07 COVER 取消一张后重新开放可交互集合', async () => {
    const controller = createCoverSelectionController('M8-UT-07', 2)

    await clickCard(controller, 'R_SHI', 'M8-UT-07')
    await clickCard(controller, 'B_NIU', 'M8-UT-07')
    await clickCard(controller, 'B_NIU', 'M8-UT-07')

    expect(readCardUiState(controller, 'R_SHI', 'M8-UT-07')).toBe('selected')
    expect(readCardUiState(controller, 'B_NIU', 'M8-UT-07')).toBe('interactive')
    expect(readCardUiState(controller, 'R_MA', 'M8-UT-07')).toBe('interactive')
    expect(readSubmitEnabled(controller, 'M8-UT-07', 'COVER')).toBe(false)
  })

  it('M8-UT-08 PLAY（非首位）单击后收敛到唯一合法 payload_cards（仅该组合 selected，其余 normal）', async () => {
    const controller = createPlaySelectionController('M8-UT-08')

    await clickCard(controller, 'R_SHI', 'M8-UT-08')

    const selectedCards = readSelectedCards(controller, 'M8-UT-08')
    expect(new Set(selectedCards)).toEqual(new Set(['R_SHI', 'B_SHI']))
    expect(selectedCards).toHaveLength(2)

    expect(readCardUiState(controller, 'R_SHI', 'M8-UT-08')).toBe('selected')
    expect(readCardUiState(controller, 'B_SHI', 'M8-UT-08')).toBe('selected')
    expect(readCardUiState(controller, 'R_MA', 'M8-UT-08')).toBe('normal')
    expect(readCardUiState(controller, 'B_MA', 'M8-UT-08')).toBe('normal')
    expect(readSubmitEnabled(controller, 'M8-UT-08', 'PLAY')).toBe(true)
  })

  it('M8-UT-09 PLAY（非首位）取消组合后回到初始可选集', async () => {
    const controller = createPlaySelectionController('M8-UT-09')

    await clickCard(controller, 'R_SHI', 'M8-UT-09')

    expect(new Set(readSelectedCards(controller, 'M8-UT-09'))).toEqual(new Set(['R_SHI', 'B_SHI']))

    await clickCard(controller, 'R_SHI', 'M8-UT-09')

    expect(readSelectedCards(controller, 'M8-UT-09')).toEqual([])
    expect(readCardUiState(controller, 'R_SHI', 'M8-UT-09')).toBe('interactive')
    expect(readCardUiState(controller, 'B_SHI', 'M8-UT-09')).toBe('interactive')
    expect(readCardUiState(controller, 'R_MA', 'M8-UT-09')).toBe('interactive')
    expect(readCardUiState(controller, 'B_MA', 'M8-UT-09')).toBe('interactive')
    expect(readSubmitEnabled(controller, 'M8-UT-09', 'PLAY')).toBe(false)
  })
})
