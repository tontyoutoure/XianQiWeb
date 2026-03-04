import { describe, expect, it, vi } from 'vitest'

type GenericRecord = Record<string, unknown>
type ReconnectControllerFactory = (input: GenericRecord) => unknown

interface RecoverSnapshot {
  public_state: GenericRecord
  private_state: GenericRecord | null
  legal_actions: GenericRecord | null
}

const RECONNECT_FACTORY_EXPORT_CANDIDATES = [
  'createIngameReconnectControllerForTest',
  'createIngameSessionRecoveryForTest',
] as const

const RECONNECT_FACTORY_MODULE_CANDIDATES = [
  '/src/stores/ingame-actions.ts',
  '/src/stores/ingame-session.ts',
  '/src/stores/ingame-reconnect.ts',
  '/src/stores/ingame.ts',
  '/src/ws/ingame-channel.ts',
] as const

function asRecord(value: unknown): GenericRecord | null {
  if (value && typeof value === 'object') {
    return value as GenericRecord
  }
  return null
}

function findCallable(target: unknown, methodNames: readonly string[]) {
  const record = asRecord(target)
  if (!record) {
    return null
  }

  for (const methodName of methodNames) {
    const maybeMethod = record[methodName]
    if (typeof maybeMethod === 'function') {
      return maybeMethod as (...args: unknown[]) => unknown
    }
  }
  return null
}

async function invokeCallable(method: (...args: unknown[]) => unknown, ...args: unknown[]) {
  const result = method(...args)
  if (result instanceof Promise) {
    await result
  }
}

async function requireReconnectFactory(testId: string): Promise<ReconnectControllerFactory> {
  const modules = import.meta.glob('/src/**/*.ts')
  const fallbackPaths = Object.keys(modules)
    .filter((path) => path.startsWith('/src/stores/') || path.startsWith('/src/ws/'))
    .sort()
  const candidatePaths = [...RECONNECT_FACTORY_MODULE_CANDIDATES, ...fallbackPaths]
  const visited = new Set<string>()

  for (const path of candidatePaths) {
    if (visited.has(path)) {
      continue
    }
    visited.add(path)

    const loader = modules[path]
    if (!loader) {
      continue
    }

    const loadedModule = (await loader()) as GenericRecord
    for (const exportName of RECONNECT_FACTORY_EXPORT_CANDIDATES) {
      const candidate = loadedModule[exportName]
      if (typeof candidate === 'function') {
        return candidate as ReconnectControllerFactory
      }
    }
  }

  throw new Error(
    `${testId} requires one of ${RECONNECT_FACTORY_EXPORT_CANDIDATES.join(', ')} export for reconnect/recovery tests.`,
  )
}

function createInitialState(overrides: Partial<GenericRecord> = {}): GenericRecord {
  return {
    publicState: {
      version: 800,
      phase: 'in_round',
      turn: { current_seat: 0 },
    },
    privateState: {
      hand: { R_SHI: 1, B_NIU: 1 },
      covered: {},
    },
    legalActions: {
      seat: 0,
      actions: [{ type: 'PLAY', payload_cards: { R_SHI: 1 } }],
    },
    uiSelectionState: {
      selectedCards: ['R_SHI'],
    },
    pendingAction: {
      actionType: 'PLAY',
      payloadCards: { R_SHI: 1 },
    },
    ...overrides,
  }
}

function buildRecoveredSnapshot(version: number): RecoverSnapshot {
  return {
    public_state: {
      version,
      phase: 'buckle_flow',
      turn: { current_seat: 2 },
    },
    private_state: {
      hand: { B_SHI: 1, B_MA: 1 },
      covered: { R_SHI: 1 },
    },
    legal_actions: {
      seat: 2,
      actions: [{ type: 'REVEAL' }, { type: 'PASS_REVEAL' }],
    },
  }
}

async function createReconnectController(
  testId: string,
  input: {
    initialState?: GenericRecord
    snapshot?: RecoverSnapshot
    refreshResult?: boolean
  } = {},
) {
  const factory = await requireReconnectFactory(testId)
  const reconnectWs = vi.fn().mockResolvedValue(undefined)
  const fetchLatestState = vi.fn().mockResolvedValue(input.snapshot ?? buildRecoveredSnapshot(801))
  const refreshSession = vi.fn().mockResolvedValue(input.refreshResult ?? true)
  const navigateToLogin = vi.fn()

  const services = {
    reconnectWs,
    reconnectChannel: reconnectWs,
    reconnectRoomChannel: reconnectWs,
    reconnect: reconnectWs,
    fetchLatestState,
    fetchLatestSnapshot: fetchLatestState,
    fetchGameState: fetchLatestState,
    fetchGameSnapshot: fetchLatestState,
    refreshSession,
    refresh: refreshSession,
    navigateToLogin,
    redirectToLogin: navigateToLogin,
    goLogin: navigateToLogin,
  }

  const controller = factory({
    gameId: 19001,
    roomId: 2301,
    reconnectDelayMs: 0,
    restFallbackEnabled: true,
    initialState: input.initialState ?? createInitialState(),
    initial_state: input.initialState ?? createInitialState(),
    services,
    deps: services,
    options: {
      reconnectDelayMs: 0,
      restFallbackEnabled: true,
    },
  })

  const start = findCallable(controller, ['start', 'init', 'connect'])
  if (start) {
    await invokeCallable(start)
  }

  return {
    controller,
    spies: {
      reconnectWs,
      fetchLatestState,
      refreshSession,
      navigateToLogin,
    },
  }
}

async function triggerWsClose(controller: unknown, code: number, testId: string): Promise<void> {
  const closeHandler = findCallable(controller, [
    'onWsClose',
    'onSocketClose',
    'onChannelClose',
    'handleWsClose',
    'handleSocketClose',
    'handleChannelClose',
  ])
  if (!closeHandler) {
    throw new Error(`${testId} requires ws close handler for reconnect/recovery flow.`)
  }

  await invokeCallable(closeHandler, {
    code,
    reason: code === 4401 ? 'room-auth-closed' : 'network-disconnected',
  })
  await vi.runAllTimersAsync()
  await Promise.resolve()
}

function readControllerState(controller: unknown, testId: string): GenericRecord {
  const snapshotGetter = findCallable(controller, ['getState', 'snapshot', 'getSnapshot'])
  if (snapshotGetter) {
    const snapshot = asRecord(snapshotGetter())
    if (snapshot) {
      return snapshot
    }
  }

  const inlineState = asRecord(controller)
  if (inlineState) {
    return inlineState
  }

  throw new Error(`${testId} requires reconnect controller state snapshot.`)
}

function readStateSlice(state: GenericRecord, keys: readonly string[]): GenericRecord | null {
  for (const key of keys) {
    const value = asRecord(state[key])
    if (value) {
      return value
    }
  }
  return null
}

function readSelectedCards(state: GenericRecord): string[] {
  const uiSelection =
    asRecord(state.uiSelectionState) ??
    asRecord(state.ui_selection_state) ??
    asRecord(state.selectionState) ??
    asRecord(state.selection_state)
  if (!uiSelection) {
    return []
  }

  const selectedCards = uiSelection.selectedCards ?? uiSelection.selected_cards
  if (Array.isArray(selectedCards) && selectedCards.every((card) => typeof card === 'string')) {
    return selectedCards as string[]
  }
  return []
}

describe('M8 Stage 10 Red - reconnect and session recovery', () => {
  it('M8-IT-09 对局中 WS 断连后自动重连并 REST 拉态兜底，最终状态覆盖为最新快照', async () => {
    vi.useFakeTimers()
    try {
      const snapshot = buildRecoveredSnapshot(901)
      const { controller, spies } = await createReconnectController('M8-IT-09', { snapshot })

      await triggerWsClose(controller, 1006, 'M8-IT-09')

      const stateAfterRecover = readControllerState(controller, 'M8-IT-09')
      const publicState = readStateSlice(stateAfterRecover, ['publicState', 'public_state'])
      const privateState = readStateSlice(stateAfterRecover, ['privateState', 'private_state'])
      const legalActions = readStateSlice(stateAfterRecover, ['legalActions', 'legal_actions'])

      expect(spies.reconnectWs).toHaveBeenCalledTimes(1)
      expect(spies.fetchLatestState).toHaveBeenCalledTimes(1)
      expect(publicState).toEqual(snapshot.public_state)
      expect(privateState).toEqual(snapshot.private_state)
      expect(legalActions).toEqual(snapshot.legal_actions)
    } finally {
      vi.useRealTimers()
    }
  })

  it('M8-IT-10 重连后 legal_actions 与选择态一致重建（旧选择态清理）', async () => {
    vi.useFakeTimers()
    try {
      const snapshot = buildRecoveredSnapshot(902)
      const { controller, spies } = await createReconnectController('M8-IT-10', {
        snapshot,
        initialState: createInitialState({
          uiSelectionState: {
            selectedCards: ['R_SHI', 'B_NIU'],
          },
          pendingAction: {
            actionType: 'PLAY',
            payloadCards: { R_SHI: 1, B_NIU: 1 },
          },
        }),
      })

      await triggerWsClose(controller, 1006, 'M8-IT-10')

      const recoveredState = readControllerState(controller, 'M8-IT-10')
      const legalActions = readStateSlice(recoveredState, ['legalActions', 'legal_actions'])
      const selectedCards = readSelectedCards(recoveredState)

      expect(spies.reconnectWs).toHaveBeenCalledTimes(1)
      expect(spies.fetchLatestState).toHaveBeenCalledTimes(1)
      expect(legalActions).toEqual(snapshot.legal_actions)
      expect(selectedCards).toEqual([])
      expect(recoveredState.pendingAction ?? recoveredState.pending_action ?? null).toBeNull()
    } finally {
      vi.useRealTimers()
    }
  })

  it('M8-IT-11 收到房间鉴权关闭（4401）触发 refresh + 重连；refresh 失败回登录', async () => {
    vi.useFakeTimers()
    try {
      const successCase = await createReconnectController('M8-IT-11', {
        snapshot: buildRecoveredSnapshot(903),
        refreshResult: true,
      })
      await triggerWsClose(successCase.controller, 4401, 'M8-IT-11')

      expect(successCase.spies.refreshSession).toHaveBeenCalledTimes(1)
      expect(successCase.spies.reconnectWs).toHaveBeenCalledTimes(1)
      expect(successCase.spies.navigateToLogin).not.toHaveBeenCalled()

      const failCase = await createReconnectController('M8-IT-11', {
        snapshot: buildRecoveredSnapshot(904),
        refreshResult: false,
      })
      await triggerWsClose(failCase.controller, 4401, 'M8-IT-11')

      expect(failCase.spies.refreshSession).toHaveBeenCalledTimes(1)
      expect(failCase.spies.reconnectWs).not.toHaveBeenCalled()
      expect(failCase.spies.navigateToLogin).toHaveBeenCalledTimes(1)
    } finally {
      vi.useRealTimers()
    }
  })
})
