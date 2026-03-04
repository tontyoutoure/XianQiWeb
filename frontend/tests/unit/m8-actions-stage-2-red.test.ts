import { describe, expect, it, vi } from 'vitest'

import * as ingameActionsModule from '@/stores/ingame-actions'

type ActionType = 'BUCKLE' | 'PASS_BUCKLE' | 'REVEAL' | 'PASS_REVEAL' | 'PLAY' | 'COVER'

interface ControllerState {
  publicState: Record<string, unknown>
  privateState: Record<string, unknown> | null
  legalActions: Record<string, unknown> | null
  uiSelectionState: {
    selectedCards: string[]
  }
  pendingAction: {
    actionType: ActionType
    payloadCards?: Record<string, number>
    coverList?: Record<string, number>
  } | null
}

interface RecoverStatePayload {
  public_state: Record<string, unknown>
  private_state: Record<string, unknown> | null
  legal_actions: Record<string, unknown> | null
}

interface IngameActionControllerForTest {
  submitAction: (input: {
    actionType: ActionType
    payloadCards?: Record<string, number>
    coverList?: Record<string, number>
  }) => Promise<void>
  getState: () => ControllerState
}

interface IngameActionControllerFactory {
  (input: {
    gameId: number
    initialState: ControllerState
    services: {
      submitAction: (payload: Record<string, unknown>) => Promise<{
        status: number
        body?: { code?: string }
      }>
      fetchLatestState: () => Promise<RecoverStatePayload>
      notifySubmitError: (message: string) => void
    }
  }): IngameActionControllerForTest
}

function requireControllerFactory(testId: string): IngameActionControllerFactory {
  const candidate = (ingameActionsModule as unknown as Record<string, unknown>)
    .createIngameActionControllerForTest
  if (typeof candidate !== 'function') {
    throw new Error(
      `${testId} requires createIngameActionControllerForTest in @/stores/ingame-actions`,
    )
  }

  return candidate as IngameActionControllerFactory
}

function createInitialState(overrides: Partial<ControllerState> = {}): ControllerState {
  return {
    publicState: {
      version: 11,
      phase: 'in_round',
      turn: { current_seat: 0 },
    },
    privateState: {
      hand: { R_SHI: 1, B_NIU: 1 },
      covered: {},
    },
    legalActions: {
      seat: 0,
      actions: [{ type: 'PLAY', payload_cards: { R_SHI: 1 } }, { type: 'PASS_BUCKLE' }],
    },
    uiSelectionState: {
      selectedCards: [],
    },
    pendingAction: null,
    ...overrides,
  }
}

describe('M8 Stage 2 Red - conflict recovery and submit error handling', () => {
  it('M8-IT-02 动作提交后收到 204 时，不做本地伪推进（state 不提前变化）', async () => {
    const createController = requireControllerFactory('M8-IT-02')
    const initialState = createInitialState()
    const submitAction = vi.fn().mockResolvedValue({ status: 204 })
    const fetchLatestState = vi.fn()
    const notifySubmitError = vi.fn()

    const controller = createController({
      gameId: 9527,
      initialState,
      services: {
        submitAction,
        fetchLatestState,
        notifySubmitError,
      },
    })

    await controller.submitAction({
      actionType: 'PLAY',
      payloadCards: { R_SHI: 1 },
    })

    const stateAfterSubmit = controller.getState()

    expect(fetchLatestState).not.toHaveBeenCalled()
    expect(stateAfterSubmit.publicState).toEqual(initialState.publicState)
    expect(stateAfterSubmit.privateState).toEqual(initialState.privateState)
    expect(stateAfterSubmit.legalActions).toEqual(initialState.legalActions)
  })

  it('M8-IT-03 409 且 code=GAME_VERSION_CONFLICT 时自动触发拉态并覆盖 public/private/legal_actions', async () => {
    const createController = requireControllerFactory('M8-IT-03')
    const initialState = createInitialState()
    const submitAction = vi.fn().mockResolvedValue({
      status: 409,
      body: { code: 'GAME_VERSION_CONFLICT' },
    })
    const recoveredSnapshot: RecoverStatePayload = {
      public_state: {
        version: 12,
        phase: 'buckle_flow',
        turn: { current_seat: 1 },
      },
      private_state: {
        hand: { B_SHI: 1 },
        covered: { R_SHI: 1 },
      },
      legal_actions: {
        seat: 1,
        actions: [{ type: 'REVEAL' }, { type: 'PASS_REVEAL' }],
      },
    }
    const fetchLatestState = vi.fn().mockResolvedValue(recoveredSnapshot)
    const notifySubmitError = vi.fn()

    const controller = createController({
      gameId: 9528,
      initialState,
      services: {
        submitAction,
        fetchLatestState,
        notifySubmitError,
      },
    })

    await controller.submitAction({
      actionType: 'PLAY',
      payloadCards: { R_SHI: 1 },
    })

    const stateAfterRecover = controller.getState()

    expect(fetchLatestState).toHaveBeenCalledTimes(1)
    expect(stateAfterRecover.publicState).toEqual(recoveredSnapshot.public_state)
    expect(stateAfterRecover.privateState).toEqual(recoveredSnapshot.private_state)
    expect(stateAfterRecover.legalActions).toEqual(recoveredSnapshot.legal_actions)
  })

  it('M8-IT-04 IT-03 恢复后清空手牌选中态与待提交动作', async () => {
    const createController = requireControllerFactory('M8-IT-04')
    const initialState = createInitialState({
      uiSelectionState: {
        selectedCards: ['R_SHI'],
      },
      pendingAction: {
        actionType: 'PLAY',
        payloadCards: { R_SHI: 1 },
      },
    })
    const submitAction = vi.fn().mockResolvedValue({
      status: 409,
      body: { code: 'GAME_VERSION_CONFLICT' },
    })
    const fetchLatestState = vi.fn().mockResolvedValue({
      public_state: {
        version: 13,
        phase: 'in_round',
      },
      private_state: {
        hand: { B_NIU: 1 },
        covered: {},
      },
      legal_actions: {
        seat: 2,
        actions: [{ type: 'COVER', required_count: 1 }],
      },
    })
    const notifySubmitError = vi.fn()

    const controller = createController({
      gameId: 9529,
      initialState,
      services: {
        submitAction,
        fetchLatestState,
        notifySubmitError,
      },
    })

    await controller.submitAction({
      actionType: 'PLAY',
      payloadCards: { R_SHI: 1 },
    })

    const recoveredState = controller.getState()
    expect(recoveredState.uiSelectionState.selectedCards).toEqual([])
    expect(recoveredState.pendingAction).toBeNull()
  })

  it('M8-IT-05 403/404/非版本409 统一错误提示并终止提交', async () => {
    const createController = requireControllerFactory('M8-IT-05')
    const errorCases = [
      { status: 403 },
      { status: 404 },
      { status: 409, body: { code: 'GAME_INVALID_ACTION' } },
    ]
    const messages: string[] = []

    for (const errorCase of errorCases) {
      const submitAction = vi.fn().mockResolvedValue(errorCase)
      const fetchLatestState = vi.fn()
      const notifySubmitError = vi.fn((message: string) => messages.push(message))

      const controller = createController({
        gameId: 9530,
        initialState: createInitialState(),
        services: {
          submitAction,
          fetchLatestState,
          notifySubmitError,
        },
      })

      await controller.submitAction({
        actionType: 'PLAY',
        payloadCards: { R_SHI: 1 },
      })

      const stateAfterError = controller.getState()
      expect(fetchLatestState).not.toHaveBeenCalled()
      expect(notifySubmitError).toHaveBeenCalledTimes(1)
      expect(stateAfterError.pendingAction).toBeNull()
    }

    expect(messages.length).toBe(errorCases.length)
    expect(messages.every((message) => message.trim().length > 0)).toBe(true)
    expect(new Set(messages).size).toBe(1)
  })
})
