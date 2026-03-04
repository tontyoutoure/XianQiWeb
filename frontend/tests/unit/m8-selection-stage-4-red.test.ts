import { mount, type VueWrapper } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import type { Component } from 'vue'

import * as ingameActionsModule from '@/stores/ingame-actions'

type ActionType = 'BUCKLE' | 'PASS_BUCKLE' | 'REVEAL' | 'PASS_REVEAL' | 'PLAY' | 'COVER'
type SubmitActionType = 'PLAY' | 'COVER'
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

interface ActionBarModule {
  default?: Component
}

type GenericRecord = Record<string, unknown>

type SelectionControllerFactory = (input: GenericRecord) => unknown

const ACTION_BAR_CANDIDATE_PATHS = [
  '/src/components/ingame/ActionBar.vue',
  '/src/components/ActionBar.vue',
] as const

const SELECTION_FACTORY_EXPORT_CANDIDATES = [
  'createCardSelectionControllerForTest',
  'createHandSelectionControllerForTest',
  'createSelectionControllerForTest',
] as const

async function loadActionBarComponent(): Promise<Component> {
  const componentModules = import.meta.glob('/src/components/**/*.vue')

  for (const path of ACTION_BAR_CANDIDATE_PATHS) {
    const loader = componentModules[path]
    if (!loader) {
      continue
    }

    const module = (await loader()) as ActionBarModule
    if (module.default) {
      return module.default
    }
  }

  throw new Error(
    'M8-CT-05/06 requires an ActionBar component at "@/components/ingame/ActionBar.vue" or "@/components/ActionBar.vue".',
  )
}

function buildActionBarProps(actionType: SubmitActionType, hasLegalSelection: boolean): GenericRecord {
  const selectedCards = hasLegalSelection
    ? actionType === 'COVER'
      ? ['R_SHI', 'B_NIU']
      : ['R_SHI']
    : []
  const disabled = !hasLegalSelection
  const legalAction: LegalAction =
    actionType === 'PLAY'
      ? {
          type: 'PLAY',
          payload_cards: { R_SHI: 1 },
        }
      : {
          type: 'COVER',
          required_count: 2,
        }
  const legalActions: LegalActions = {
    seat: 0,
    actions: [legalAction],
  }

  return {
    phase: 'in_round',
    currentPhase: 'in_round',
    legalActions,
    legal_actions: legalActions,
    actionTypes: [actionType],
    availableActionTypes: [actionType],
    actionDisabledMap: { [actionType]: disabled },
    action_disabled_map: { [actionType]: disabled },
    actionButtonDisabledMap: { [actionType]: disabled },
    action_button_disabled_map: { [actionType]: disabled },
    submitDisabledMap: { [actionType]: disabled },
    submit_disabled_map: { [actionType]: disabled },
    hasLegalSelection,
    has_legal_selection: hasLegalSelection,
    isSelectionValid: hasLegalSelection,
    is_selection_valid: hasLegalSelection,
    selectedCards,
    selected_cards: selectedCards,
    selectedCardCount: selectedCards.length,
    selected_card_count: selectedCards.length,
    requiredCount: actionType === 'COVER' ? 2 : 1,
    required_count: actionType === 'COVER' ? 2 : 1,
  }
}

async function mountActionBar(actionType: SubmitActionType, hasLegalSelection: boolean): Promise<VueWrapper> {
  const ActionBar = await loadActionBarComponent()
  return mount(ActionBar, {
    props: buildActionBarProps(actionType, hasLegalSelection),
  })
}

function findActionButton(wrapper: VueWrapper, actionType: SubmitActionType) {
  const byTestId = wrapper.find(`[data-testid="action-btn-${actionType}"]`)
  if (byTestId.exists()) {
    return byTestId
  }

  const normalizedType = actionType.replace(/\s+/g, '').toUpperCase()
  const byText = wrapper
    .findAll('button')
    .find((button) => button.text().replace(/\s+/g, '').toUpperCase().includes(normalizedType))
  if (byText) {
    return byText
  }

  throw new Error(`Unable to locate ${actionType} button in ActionBar.`)
}

function expectButtonDisabledState(
  wrapper: VueWrapper,
  actionType: SubmitActionType,
  expectedDisabled: boolean,
) {
  const button = findActionButton(wrapper, actionType)
  const hasDisabledAttr = button.attributes('disabled') !== undefined
  const disabledProp = (button.element as HTMLButtonElement).disabled
  expect(hasDisabledAttr || disabledProp).toBe(expectedDisabled)
}

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

function asRecord(value: unknown): GenericRecord | null {
  if (value && typeof value === 'object') {
    return value as GenericRecord
  }
  return null
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

function readStringArray(record: GenericRecord, keys: string[]): string[] {
  for (const key of keys) {
    const value = record[key]
    if (Array.isArray(value) && value.every((item) => typeof item === 'string')) {
      return value as string[]
    }
  }
  return []
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
    if (nested) {
      const nestedState =
        normalizeCardUiState(nested.state) ??
        normalizeCardUiState(nested.status) ??
        normalizeCardUiState(nested.mode)
      if (nestedState) {
        return nestedState
      }
    }
  }

  const topSelected = new Set(readStringArray(snapshot, ['selectedCards', 'selected_cards']))
  const topInteractive = new Set(
    readStringArray(snapshot, ['interactiveCards', 'interactive_cards', 'clickableCards']),
  )

  const uiSelection = asRecord(snapshot.uiSelectionState) ?? asRecord(snapshot.ui_selection_state)
  if (uiSelection) {
    for (const card of readStringArray(uiSelection, ['selectedCards', 'selected_cards'])) {
      topSelected.add(card)
    }
    for (const card of readStringArray(uiSelection, ['interactiveCards', 'interactive_cards'])) {
      topInteractive.add(card)
    }
  }

  if (topSelected.has(cardId)) {
    return 'selected'
  }
  if (topInteractive.has(cardId)) {
    return 'interactive'
  }
  if (topSelected.size > 0 || topInteractive.size > 0) {
    return 'normal'
  }

  return null
}

function readCardUiState(controller: unknown, cardId: string, testId: string): CardUiState {
  const directGetter = findCallable(controller, ['getCardState', 'getCardUiState', 'readCardState'])
  if (directGetter) {
    const directState =
      normalizeCardUiState(directGetter(cardId)) ??
      normalizeCardUiState(asRecord(directGetter(cardId))?.state)
    if (directState) {
      return directState
    }
  }

  const snapshotGetter = findCallable(controller, ['getState', 'snapshot', 'getSnapshot'])
  if (snapshotGetter) {
    const snapshot = asRecord(snapshotGetter())
    if (snapshot) {
      const stateFromSnapshot = readCardStateFromSnapshot(snapshot, cardId)
      if (stateFromSnapshot) {
        return stateFromSnapshot
      }
    }
  }

  throw new Error(
    `${testId} requires selection controller to expose card UI state (normal/interactive/selected).`,
  )
}

describe('M8 Stage 4 Red - action submit enabling and card selection state machine', () => {
  it('M8-CT-05 PLAY/COVER 在未形成合法选择时按钮 disabled=true', async () => {
    for (const actionType of ['PLAY', 'COVER'] as const) {
      const wrapper = await mountActionBar(actionType, false)
      expectButtonDisabledState(wrapper, actionType, true)
    }
  })

  it('M8-CT-06 达成合法选择后 PLAY/COVER disabled=false', async () => {
    for (const actionType of ['PLAY', 'COVER'] as const) {
      const invalidWrapper = await mountActionBar(actionType, false)
      expectButtonDisabledState(invalidWrapper, actionType, true)

      const validWrapper = await mountActionBar(actionType, true)
      expectButtonDisabledState(validWrapper, actionType, false)
    }
  })

  it('M8-UT-04 手牌三态切换：普通/可交互/已选中，支持点击与取消点击', async () => {
    const controller = createCoverSelectionController('M8-UT-04', 1)

    expect(readCardUiState(controller, 'R_SHI', 'M8-UT-04')).toBe('interactive')
    expect(readCardUiState(controller, 'B_NIU', 'M8-UT-04')).toBe('interactive')

    await clickCard(controller, 'R_SHI', 'M8-UT-04')

    expect(readCardUiState(controller, 'R_SHI', 'M8-UT-04')).toBe('selected')
    expect(readCardUiState(controller, 'B_NIU', 'M8-UT-04')).toBe('normal')

    await clickCard(controller, 'R_SHI', 'M8-UT-04')

    expect(readCardUiState(controller, 'R_SHI', 'M8-UT-04')).toBe('interactive')
    expect(readCardUiState(controller, 'B_NIU', 'M8-UT-04')).toBe('interactive')
  })

  it('M8-UT-05 COVER 未满 required_count 时，未选中牌保持可交互', async () => {
    const controller = createCoverSelectionController('M8-UT-05', 2)

    await clickCard(controller, 'R_SHI', 'M8-UT-05')

    expect(readCardUiState(controller, 'R_SHI', 'M8-UT-05')).toBe('selected')
    expect(readCardUiState(controller, 'B_NIU', 'M8-UT-05')).toBe('interactive')
    expect(readCardUiState(controller, 'R_MA', 'M8-UT-05')).toBe('interactive')
  })
})
