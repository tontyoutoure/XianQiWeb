import { expect, test, type Browser, type BrowserContext, type Page } from '@playwright/test'

interface AuthApiSession {
  accessToken: string
  refreshToken: string
  userId: number
  username: string
}

interface RoomSummary {
  room_id: number
  status: 'waiting' | 'playing' | 'settlement'
  player_count: number
  ready_count: number
}

interface RoomDetail {
  room_id: number
  status: 'waiting' | 'playing' | 'settlement'
  owner_id: number
  members: Array<{
    user_id: number
    username: string
    seat: number
    ready: boolean
    chips: number
  }>
  current_game_id: number | null
}

interface GameStateResponse {
  game_id: number
  self_seat: number
  public_state: {
    phase?: string
    version?: number
  }
  private_state: Record<string, unknown>
  legal_actions:
    | {
        seat?: number
        actions?: Array<{
          type?: string
          payload_cards?: Record<string, number>
          required_count?: number
        }>
      }
    | null
}

interface PlayerRuntime {
  session: AuthApiSession
  context: BrowserContext
  page: Page
}

const apiBaseUrl = process.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:18080'
const appBaseUrl = process.env.PLAYWRIGHT_BASE_URL ?? 'http://127.0.0.1:5173'

function randomUsername(prefix: string): string {
  const suffix = Math.random().toString(36).slice(2, 8)
  return `${prefix}${suffix}`.slice(0, 10)
}

async function registerAndGetSession(username: string, password: string): Promise<AuthApiSession> {
  const response = await fetch(`${apiBaseUrl}/api/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  if (!response.ok) {
    throw new Error(`register failed: ${response.status}`)
  }

  const payload = (await response.json()) as {
    access_token: string
    refresh_token: string
    user: { id: number; username: string }
  }

  return {
    accessToken: payload.access_token,
    refreshToken: payload.refresh_token,
    userId: payload.user.id,
    username: payload.user.username,
  }
}

async function loginInUi(page: Page, username: string, password: string): Promise<void> {
  await page.goto('/login')
  await page.getByTestId('login-username').fill(username)
  await page.getByTestId('login-password').fill(password)
  await page.getByTestId('login-submit').click()
  await expect(page).toHaveURL(/\/lobby$/)
}

async function listRoomsByApi(accessToken: string): Promise<RoomSummary[]> {
  const response = await fetch(`${apiBaseUrl}/api/rooms`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  })
  if (!response.ok) {
    throw new Error(`list rooms failed: ${response.status}`)
  }
  return (await response.json()) as RoomSummary[]
}

async function getRoomDetailByApi(accessToken: string, roomId: number): Promise<RoomDetail> {
  const response = await fetch(`${apiBaseUrl}/api/rooms/${roomId}`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  })
  if (!response.ok) {
    throw new Error(`get room detail failed: ${response.status}`)
  }
  return (await response.json()) as RoomDetail
}

async function leaveRoomByApi(accessToken: string, roomId: number): Promise<void> {
  const response = await fetch(`${apiBaseUrl}/api/rooms/${roomId}/leave`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${accessToken}` },
  })
  if (!response.ok) {
    throw new Error(`leave room failed: ${response.status}`)
  }
}

async function getGameStateByApi(accessToken: string, gameId: number): Promise<GameStateResponse> {
  const response = await fetch(`${apiBaseUrl}/api/games/${gameId}/state`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  })
  if (!response.ok) {
    throw new Error(`get game state failed: ${response.status}`)
  }
  return (await response.json()) as GameStateResponse
}

async function submitGameActionByApi(input: {
  accessToken: string
  gameId: number
  actionIdx: number
  clientVersion: number
  coverList?: Record<string, number> | null
}): Promise<void> {
  const response = await fetch(`${apiBaseUrl}/api/games/${input.gameId}/actions`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${input.accessToken}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      action_idx: input.actionIdx,
      client_version: input.clientVersion,
      cover_list: input.coverList ?? null,
    }),
  })

  if (response.status !== 204) {
    throw new Error(`submit action failed: ${response.status}`)
  }
}

async function joinRoomInUi(page: Page, roomId: number): Promise<void> {
  await page.getByTestId(`lobby-join-room-${roomId}`).click()
  await expect(page).toHaveURL(new RegExp(`/rooms/${roomId}$`))
}

function readActionTypes(state: GameStateResponse): string[] {
  const actions = state.legal_actions?.actions
  if (!Array.isArray(actions)) {
    return []
  }
  return actions
    .map((action) => action.type)
    .filter((actionType): actionType is string => typeof actionType === 'string')
}

function hasExactActionTypes(state: GameStateResponse, expectedTypes: string[]): boolean {
  const actual = [...readActionTypes(state)].sort()
  const expected = [...expectedTypes].sort()
  if (actual.length !== expected.length) {
    return false
  }
  return actual.every((value, index) => value === expected[index])
}

function findActionIndexByType(state: GameStateResponse, actionType: string): number {
  const actions = state.legal_actions?.actions
  if (!Array.isArray(actions)) {
    return -1
  }
  return actions.findIndex((action) => action.type === actionType)
}

async function createThreePlayersAndStartGame(browser: Browser, testTag: string): Promise<{
  roomId: number
  gameId: number
  players: PlayerRuntime[]
}> {
  const password = '123'
  const sessions = await Promise.all([
    registerAndGetSession(randomUsername(`${testTag}a`), password),
    registerAndGetSession(randomUsername(`${testTag}b`), password),
    registerAndGetSession(randomUsername(`${testTag}c`), password),
  ])

  const players: PlayerRuntime[] = []
  for (const session of sessions) {
    const context = await browser.newContext({ baseURL: appBaseUrl })
    const page = await context.newPage()
    await loginInUi(page, session.username, password)
    players.push({ session, context, page })
  }

  const rooms = await listRoomsByApi(players[0].session.accessToken)
  const roomId = (rooms.find((room) => room.player_count === 0) ?? rooms[0]).room_id

  for (const player of players) {
    await joinRoomInUi(player.page, roomId)
  }
  for (const player of players) {
    await player.page.getByTestId('room-ready-toggle').click()
  }

  let gameId: number | null = null
  await expect
    .poll(async () => {
      const detail = await getRoomDetailByApi(players[0].session.accessToken, roomId)
      if (detail.status !== 'playing' || detail.current_game_id === null) {
        gameId = null
        return null
      }
      gameId = detail.current_game_id
      return gameId
    })
    .not.toBeNull()

  if (gameId === null) {
    throw new Error('game id was not resolved after room entered playing')
  }

  return {
    roomId,
    gameId,
    players,
  }
}

async function cleanupPlayers(players: PlayerRuntime[], roomId: number): Promise<void> {
  await Promise.all(
    players.map(async (player) => {
      try {
        await leaveRoomByApi(player.session.accessToken, roomId)
      } catch {
        // ignore cleanup failures in red-phase E2E
      }
    }),
  )

  await Promise.all(
    players.map(async (player) => {
      await player.context.close()
    }),
  )
}

test.describe('M8 RS E2E 01-03', () => {
  test('M8-RS-E2E-01 主流程入局', async ({ browser }) => {
    const runtime = await createThreePlayersAndStartGame(browser, 'm8e1')
    try {
      const actorPage = runtime.players[0].page
      await expect(actorPage.getByTestId('ingame-hand-cards')).toBeVisible()
      await expect(actorPage.getByTestId('ingame-action-bar')).toBeVisible()
    } finally {
      await cleanupPlayers(runtime.players, runtime.roomId)
    }
  })

  test('M8-RS-E2E-02 buckle_flow 按钮映射', async ({ browser }) => {
    const runtime = await createThreePlayersAndStartGame(browser, 'm8e2')
    try {
      const stateByIndex = await Promise.all(
        runtime.players.map((player) => getGameStateByApi(player.session.accessToken, runtime.gameId)),
      )

      const buckleActorIndex = stateByIndex.findIndex((state) => hasExactActionTypes(state, ['BUCKLE', 'PASS_BUCKLE']))
      expect(buckleActorIndex).toBeGreaterThanOrEqual(0)

      const page = runtime.players[buckleActorIndex].page
      await expect(page.getByTestId('action-btn-BUCKLE')).toBeVisible()
      await expect(page.getByTestId('action-btn-PASS_BUCKLE')).toBeVisible()
      await expect(page.getByTestId('action-btn-REVEAL')).toHaveCount(0)
      await expect(page.getByTestId('action-btn-PASS_REVEAL')).toHaveCount(0)

      await page.getByTestId('action-btn-BUCKLE').click()
      await expect
        .poll(async () => {
          const nextState = await getGameStateByApi(
            runtime.players[buckleActorIndex].session.accessToken,
            runtime.gameId,
          )
          return nextState.public_state.phase
        })
        .toBe('in_round')
    } finally {
      await cleanupPlayers(runtime.players, runtime.roomId)
    }
  })

  test('M8-RS-E2E-03 扣后掀棋决策映射（命中 REVEAL 立即短路）', async ({ browser }) => {
    const runtime = await createThreePlayersAndStartGame(browser, 'm8e3')
    try {
      const stateBeforeBuckle = await Promise.all(
        runtime.players.map((player) => getGameStateByApi(player.session.accessToken, runtime.gameId)),
      )
      const bucklerIndex = stateBeforeBuckle.findIndex((state) => hasExactActionTypes(state, ['BUCKLE', 'PASS_BUCKLE']))
      expect(bucklerIndex).toBeGreaterThanOrEqual(0)

      const bucklerState = stateBeforeBuckle[bucklerIndex]
      const buckleActionIdx = findActionIndexByType(bucklerState, 'BUCKLE')
      expect(buckleActionIdx).toBeGreaterThanOrEqual(0)

      await submitGameActionByApi({
        accessToken: runtime.players[bucklerIndex].session.accessToken,
        gameId: runtime.gameId,
        actionIdx: buckleActionIdx,
        clientVersion: Number(bucklerState.public_state.version ?? 0),
      })

      let revealAskerIndex = -1
      await expect
        .poll(async () => {
          const stateAfterBuckle = await Promise.all(
            runtime.players.map((player) => getGameStateByApi(player.session.accessToken, runtime.gameId)),
          )
          revealAskerIndex = stateAfterBuckle.findIndex((state) => hasExactActionTypes(state, ['REVEAL', 'PASS_REVEAL']))
          return revealAskerIndex
        })
        .toBeGreaterThanOrEqual(0)

      const revealPage = runtime.players[revealAskerIndex].page
      await expect(revealPage.getByTestId('action-btn-REVEAL')).toBeVisible()
      await expect(revealPage.getByTestId('action-btn-PASS_REVEAL')).toBeVisible()
      await expect(revealPage.getByTestId('action-btn-BUCKLE')).toHaveCount(0)
      await expect(revealPage.getByTestId('action-btn-PASS_BUCKLE')).toHaveCount(0)

      await revealPage.getByTestId('action-btn-REVEAL').click()
      await expect
        .poll(async () => {
          const statesAfterReveal = await Promise.all(
            runtime.players.map((player) => getGameStateByApi(player.session.accessToken, runtime.gameId)),
          )
          return statesAfterReveal.some((state) => {
            const actionTypes = readActionTypes(state)
            return actionTypes.includes('REVEAL') || actionTypes.includes('PASS_REVEAL')
          })
        })
        .toBe(false)
    } finally {
      await cleanupPlayers(runtime.players, runtime.roomId)
    }
  })
})
