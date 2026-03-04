import { describe, expect, it } from 'vitest'

type ActionType = 'BUCKLE' | 'PASS_BUCKLE' | 'REVEAL' | 'PASS_REVEAL' | 'PLAY' | 'COVER'

interface LegalAction {
  type: ActionType
  payload_cards?: Record<string, number>
  required_count?: number
}

interface LegalActions {
  seat: number
  actions: LegalAction[]
}

interface BuildActionSubmitPayloadInput {
  legalActions: LegalActions
  actionType: ActionType
  payloadCards?: Record<string, number>
  coverList?: Record<string, number>
  publicStateVersion: number
}

interface ActionSubmitPayload {
  action_idx: number
  client_version: number
  cover_list?: Record<string, number> | null
}

interface InGameActionModuleExports {
  mapLegalActionsToButtonTypes?: (legalActions: LegalActions | null | undefined) => ActionType[]
  buildActionSubmitPayload?: (input: BuildActionSubmitPayloadInput) => ActionSubmitPayload
}

async function loadInGameActionModule(): Promise<InGameActionModuleExports> {
  try {
    return (await import('@/stores/ingame-actions')) as InGameActionModuleExports
  } catch {
    return {}
  }
}

describe('M8 Stage 1 Red - actions mapping and submit payload', () => {
  it('M8-UT-01 legal_actions 到按钮能力映射仅来自后端动作集合，不做额外推断', async () => {
    const actionModule = await loadInGameActionModule()

    if (typeof actionModule.mapLegalActionsToButtonTypes !== 'function') {
      throw new Error(
        'M8-UT-01 requires mapLegalActionsToButtonTypes in @/stores/ingame-actions',
      )
    }

    const legalActions: LegalActions = {
      seat: 1,
      actions: [{ type: 'REVEAL' }, { type: 'PASS_REVEAL' }],
    }

    const buttonTypes = actionModule.mapLegalActionsToButtonTypes(legalActions)
    expect(buttonTypes).toEqual(['REVEAL', 'PASS_REVEAL'])
    expect(buttonTypes).not.toContain('BUCKLE')
    expect(buttonTypes).not.toContain('PLAY')
    expect(buttonTypes).not.toContain('COVER')
  })

  it('M8-UT-02 action_idx 按 legal_actions.actions 顺序', async () => {
    const actionModule = await loadInGameActionModule()

    if (typeof actionModule.buildActionSubmitPayload !== 'function') {
      throw new Error(
        'M8-UT-02 requires buildActionSubmitPayload in @/stores/ingame-actions',
      )
    }

    const legalActions: LegalActions = {
      seat: 0,
      actions: [{ type: 'REVEAL' }, { type: 'PASS_REVEAL' }, { type: 'BUCKLE' }],
    }

    const payload = actionModule.buildActionSubmitPayload({
      legalActions,
      actionType: 'BUCKLE',
      publicStateVersion: 12,
    })

    expect(payload.action_idx).toBe(2)
  })

  it('M8-UT-03 COVER 提交携带 cover_list，非 COVER 不携带 cover_list', async () => {
    const actionModule = await loadInGameActionModule()

    if (typeof actionModule.buildActionSubmitPayload !== 'function') {
      throw new Error(
        'M8-UT-03 requires buildActionSubmitPayload in @/stores/ingame-actions',
      )
    }

    const legalActions: LegalActions = {
      seat: 2,
      actions: [{ type: 'COVER', required_count: 2 }, { type: 'PASS_BUCKLE' }],
    }
    const coverList = { R_SHI: 1, B_NIU: 1 }

    const coverPayload = actionModule.buildActionSubmitPayload({
      legalActions,
      actionType: 'COVER',
      coverList,
      publicStateVersion: 21,
    })
    const passPayload = actionModule.buildActionSubmitPayload({
      legalActions,
      actionType: 'PASS_BUCKLE',
      coverList,
      publicStateVersion: 21,
    })

    expect(coverPayload.cover_list).toEqual(coverList)
    expect(
      Object.prototype.hasOwnProperty.call(passPayload, 'cover_list')
        ? passPayload.cover_list
        : null,
    ).toBeNull()
  })

  it('M8-IT-01 所有动作提交携带 client_version=public_state.version', async () => {
    const actionModule = await loadInGameActionModule()

    if (typeof actionModule.buildActionSubmitPayload !== 'function') {
      throw new Error(
        'M8-IT-01 requires buildActionSubmitPayload in @/stores/ingame-actions',
      )
    }

    const legalActions: LegalActions = {
      seat: 0,
      actions: [
        { type: 'BUCKLE' },
        { type: 'PASS_BUCKLE' },
        { type: 'REVEAL' },
        { type: 'PASS_REVEAL' },
        { type: 'PLAY', payload_cards: { R_SHI: 1 } },
        { type: 'COVER', required_count: 1 },
      ],
    }
    const publicStateVersion = 88

    const payloads = [
      actionModule.buildActionSubmitPayload({
        legalActions,
        actionType: 'BUCKLE',
        publicStateVersion,
      }),
      actionModule.buildActionSubmitPayload({
        legalActions,
        actionType: 'PASS_BUCKLE',
        publicStateVersion,
      }),
      actionModule.buildActionSubmitPayload({
        legalActions,
        actionType: 'REVEAL',
        publicStateVersion,
      }),
      actionModule.buildActionSubmitPayload({
        legalActions,
        actionType: 'PASS_REVEAL',
        publicStateVersion,
      }),
      actionModule.buildActionSubmitPayload({
        legalActions,
        actionType: 'PLAY',
        payloadCards: { R_SHI: 1 },
        publicStateVersion,
      }),
      actionModule.buildActionSubmitPayload({
        legalActions,
        actionType: 'COVER',
        coverList: { B_NIU: 1 },
        publicStateVersion,
      }),
    ]

    for (const payload of payloads) {
      expect(payload.client_version).toBe(publicStateVersion)
    }
  })
})
