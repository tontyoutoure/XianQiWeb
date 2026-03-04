export type ActionType = 'BUCKLE' | 'PASS_BUCKLE' | 'REVEAL' | 'PASS_REVEAL' | 'PLAY' | 'COVER'

export interface LegalAction {
  type: ActionType
  payload_cards?: Record<string, number>
  required_count?: number
}

export interface LegalActions {
  seat: number
  actions: LegalAction[]
}

export interface BuildActionSubmitPayloadInput {
  legalActions: LegalActions
  actionType: ActionType
  payloadCards?: Record<string, number>
  coverList?: Record<string, number>
  publicStateVersion: number
}

export interface ActionSubmitPayload {
  action_idx: number
  client_version: number
  cover_list?: Record<string, number> | null
}

interface ControllerPendingAction {
  actionType: ActionType
  payloadCards?: Record<string, number>
  coverList?: Record<string, number>
}

interface IngameActionControllerState {
  publicState: Record<string, unknown>
  privateState: Record<string, unknown> | null
  legalActions: Record<string, unknown> | null
  uiSelectionState: {
    selectedCards: string[]
  }
  pendingAction: ControllerPendingAction | null
}

interface RecoverStatePayload {
  public_state: Record<string, unknown>
  private_state: Record<string, unknown> | null
  legal_actions: Record<string, unknown> | null
}

interface IngameActionControllerServices {
  submitAction: (payload: Record<string, unknown>) => Promise<{
    status: number
    body?: { code?: string }
  }>
  fetchLatestState: () => Promise<RecoverStatePayload>
  notifySubmitError: (message: string) => void
}

interface CreateIngameActionControllerForTestInput {
  gameId: number
  initialState: IngameActionControllerState
  services: IngameActionControllerServices
}

interface SubmitControllerActionInput {
  actionType: ActionType
  payloadCards?: Record<string, number>
  coverList?: Record<string, number>
}

export function mapLegalActionsToButtonTypes(legalActions: LegalActions | null | undefined): ActionType[] {
  if (!legalActions || !Array.isArray(legalActions.actions)) {
    return []
  }

  const seenTypes = new Set<ActionType>()
  const buttonTypes: ActionType[] = []
  for (const action of legalActions.actions) {
    if (seenTypes.has(action.type)) {
      continue
    }
    seenTypes.add(action.type)
    buttonTypes.push(action.type)
  }
  return buttonTypes
}

export function buildActionSubmitPayload(input: BuildActionSubmitPayloadInput): ActionSubmitPayload {
  const actionIdx = findActionIndex(input.legalActions.actions, input.actionType, input.payloadCards)
  if (actionIdx < 0) {
    throw new Error(`Unable to find legal action index for action type ${input.actionType}`)
  }

  if (input.actionType === 'COVER') {
    return {
      action_idx: actionIdx,
      client_version: input.publicStateVersion,
      cover_list: input.coverList ?? null,
    }
  }

  return {
    action_idx: actionIdx,
    client_version: input.publicStateVersion,
  }
}

function findActionIndex(
  actions: LegalAction[],
  actionType: ActionType,
  payloadCards: Record<string, number> | undefined,
): number {
  return actions.findIndex((action) => {
    if (action.type !== actionType) {
      return false
    }

    if (actionType !== 'PLAY') {
      return true
    }

    if (payloadCards === undefined) {
      return true
    }

    return isSameCardCountMap(action.payload_cards, payloadCards)
  })
}

function isSameCardCountMap(
  left: Record<string, number> | undefined,
  right: Record<string, number> | undefined,
): boolean {
  if (!left || !right) {
    return !left && !right
  }

  const leftEntries = Object.entries(left)
  const rightEntries = Object.entries(right)
  if (leftEntries.length !== rightEntries.length) {
    return false
  }

  for (const [card, count] of leftEntries) {
    if (right[card] !== count) {
      return false
    }
  }

  return true
}

type CardUiState = 'normal' | 'interactive' | 'selected'

interface CardSelectionControllerState {
  selectedCards: string[]
  interactiveCards: string[]
  cardStates: Record<string, CardUiState>
  uiSelectionState: {
    selectedCards: string[]
    interactiveCards: string[]
  }
}

export function createCardSelectionControllerForTest(input: Record<string, unknown>) {
  const handCards = normalizeHandCards(input.handCards ?? input.hand_cards)
  const requiredCount = normalizeRequiredCount(
    input.requiredCount ?? input.required_count ?? readRequiredCountFromLegalActions(input),
  )
  const selectedCards: string[] = []
  const handCardSet = new Set(handCards)

  function toggleCard(cardId: string): void {
    if (!handCardSet.has(cardId)) {
      return
    }

    const selectedIndex = selectedCards.indexOf(cardId)
    if (selectedIndex >= 0) {
      selectedCards.splice(selectedIndex, 1)
      return
    }

    if (selectedCards.length < requiredCount) {
      selectedCards.push(cardId)
      return
    }

    if (requiredCount === 1) {
      selectedCards[0] = cardId
    }
  }

  function getState(): CardSelectionControllerState {
    const interactiveCards = computeInteractiveCards(handCards, selectedCards, requiredCount)
    const interactiveSet = new Set(interactiveCards)
    const selectedSet = new Set(selectedCards)
    const cardStates: Record<string, CardUiState> = {}

    for (const handCard of handCards) {
      if (selectedSet.has(handCard)) {
        cardStates[handCard] = 'selected'
        continue
      }

      cardStates[handCard] = interactiveSet.has(handCard) ? 'interactive' : 'normal'
    }

    return {
      selectedCards: [...selectedCards],
      interactiveCards,
      cardStates,
      uiSelectionState: {
        selectedCards: [...selectedCards],
        interactiveCards: [...interactiveCards],
      },
    }
  }

  function getCardState(cardId: string): CardUiState {
    return getState().cardStates[cardId] ?? 'normal'
  }

  return {
    toggleCard,
    clickCard: toggleCard,
    getState,
    getCardState,
  }
}

function computeInteractiveCards(
  handCards: string[],
  selectedCards: string[],
  requiredCount: number,
): string[] {
  if (selectedCards.length === 0) {
    return [...handCards]
  }

  if (selectedCards.length >= requiredCount) {
    return []
  }

  const selectedSet = new Set(selectedCards)
  return handCards.filter((card) => !selectedSet.has(card))
}

function normalizeHandCards(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return []
  }

  const uniqueCards: string[] = []
  const seen = new Set<string>()
  for (const item of value) {
    if (typeof item !== 'string' || seen.has(item)) {
      continue
    }
    uniqueCards.push(item)
    seen.add(item)
  }

  return uniqueCards
}

function normalizeRequiredCount(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) && value > 0 ? Math.floor(value) : 1
}

function readRequiredCountFromLegalActions(input: Record<string, unknown>): unknown {
  const legalActions = input.legalActions ?? input.legal_actions
  if (!legalActions || typeof legalActions !== 'object') {
    return undefined
  }

  const actions = (legalActions as { actions?: unknown }).actions
  if (!Array.isArray(actions)) {
    return undefined
  }

  for (const action of actions) {
    if (!action || typeof action !== 'object') {
      continue
    }

    const typedAction = action as { type?: unknown; required_count?: unknown }
    if (typedAction.type === 'COVER') {
      return typedAction.required_count
    }
  }

  return undefined
}

const DEFAULT_SUBMIT_ERROR_MESSAGE = '动作提交失败，请稍后重试'

export function createIngameActionControllerForTest(input: CreateIngameActionControllerForTestInput) {
  const state: IngameActionControllerState = {
    publicState: input.initialState.publicState,
    privateState: input.initialState.privateState,
    legalActions: input.initialState.legalActions,
    uiSelectionState: {
      selectedCards: [...(input.initialState.uiSelectionState?.selectedCards ?? [])],
    },
    pendingAction: input.initialState.pendingAction,
  }

  async function submitAction(actionInput: SubmitControllerActionInput): Promise<void> {
    state.pendingAction = {
      actionType: actionInput.actionType,
      payloadCards: actionInput.payloadCards,
      coverList: actionInput.coverList,
    }

    let submitResponse: { status: number; body?: { code?: string } }
    try {
      submitResponse = await input.services.submitAction(
        buildSubmitPayloadForController(actionInput, state),
      )
    } catch {
      state.pendingAction = null
      input.services.notifySubmitError(DEFAULT_SUBMIT_ERROR_MESSAGE)
      return
    }

    if (submitResponse.status === 204) {
      state.pendingAction = null
      return
    }

    if (submitResponse.status === 409 && submitResponse.body?.code === 'GAME_VERSION_CONFLICT') {
      try {
        const latestState = await input.services.fetchLatestState()
        state.publicState = latestState.public_state
        state.privateState = latestState.private_state
        state.legalActions = latestState.legal_actions
        state.uiSelectionState.selectedCards = []
        state.pendingAction = null
      } catch {
        state.pendingAction = null
        input.services.notifySubmitError(DEFAULT_SUBMIT_ERROR_MESSAGE)
      }
      return
    }

    state.pendingAction = null
    input.services.notifySubmitError(DEFAULT_SUBMIT_ERROR_MESSAGE)
  }

  return {
    submitAction,
    getState: (): IngameActionControllerState => state,
  }
}

function buildSubmitPayloadForController(
  actionInput: SubmitControllerActionInput,
  state: IngameActionControllerState,
): ActionSubmitPayload {
  return buildActionSubmitPayload({
    legalActions: state.legalActions as LegalActions,
    actionType: actionInput.actionType,
    payloadCards: actionInput.payloadCards,
    coverList: actionInput.coverList,
    publicStateVersion: readPublicStateVersion(state.publicState),
  })
}

function readPublicStateVersion(publicState: Record<string, unknown>): number {
  const version = publicState.version
  return typeof version === 'number' ? version : 0
}
