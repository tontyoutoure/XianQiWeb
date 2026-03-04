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
