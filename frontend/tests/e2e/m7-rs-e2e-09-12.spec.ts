import { expect, test, type BrowserContext, type Page } from '@playwright/test'

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

async function pickFirstRoomIdFromLobby(page: Page): Promise<number> {
  const firstJoinButton = page.locator('[data-testid^="lobby-join-room-"]').first()
  await expect(firstJoinButton).toBeVisible()
  const testId = await firstJoinButton.getAttribute('data-testid')
  if (!testId) {
    throw new Error('missing room join test id')
  }
  const roomId = Number.parseInt(testId.replace('lobby-join-room-', ''), 10)
  if (Number.isNaN(roomId)) {
    throw new Error(`invalid room id in test id: ${testId}`)
  }
  return roomId
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

async function joinRoomByApi(accessToken: string, roomId: number): Promise<void> {
  const response = await fetch(`${apiBaseUrl}/api/rooms/${roomId}/join`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${accessToken}` },
  })
  if (!response.ok) {
    throw new Error(`join room failed: ${response.status}`)
  }
}

async function setReadyByApi(accessToken: string, roomId: number, ready: boolean): Promise<void> {
  const response = await fetch(`${apiBaseUrl}/api/rooms/${roomId}/ready`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ ready }),
  })
  if (!response.ok) {
    throw new Error(`set ready failed: ${response.status}`)
  }
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

async function installRoomSocketTracker(context: BrowserContext): Promise<void> {
  await context.addInitScript(() => {
    const trackedSockets: WebSocket[] = []
    const NativeWebSocket = window.WebSocket

    class TrackedWebSocket extends NativeWebSocket {
      constructor(url: string | URL, protocols?: string | string[]) {
        if (protocols === undefined) {
          super(url)
        } else {
          super(url, protocols)
        }
        trackedSockets.push(this)
      }
    }

    ;(TrackedWebSocket as unknown as Record<string, number>).CONNECTING = NativeWebSocket.CONNECTING
    ;(TrackedWebSocket as unknown as Record<string, number>).OPEN = NativeWebSocket.OPEN
    ;(TrackedWebSocket as unknown as Record<string, number>).CLOSING = NativeWebSocket.CLOSING
    ;(TrackedWebSocket as unknown as Record<string, number>).CLOSED = NativeWebSocket.CLOSED

    ;(window as unknown as { __xqTrackedSockets?: WebSocket[] }).__xqTrackedSockets = trackedSockets
    window.WebSocket = TrackedWebSocket as unknown as typeof WebSocket
  })
}

test.describe('M7 RS E2E 09-12', () => {
  test.describe.configure({ mode: 'serial' })

  test('M7-RS-E2E-09 token 过期自动 refresh 并重放请求', async ({ page }) => {
    const username = randomUsername('r9')
    const password = '123'
    await registerAndGetSession(username, password)

    await loginInUi(page, username, password)
    const roomId = await pickFirstRoomIdFromLobby(page)
    await page.getByTestId(`lobby-join-room-${roomId}`).click()
    await expect(page).toHaveURL(new RegExp(`/rooms/${roomId}$`))
    await expect(page.getByTestId('room-ready-count')).toContainText('ready 0/1')

    await page.evaluate(() => {
      const key = 'xianqi.auth.session'
      const raw = window.localStorage.getItem(key)
      if (!raw) {
        throw new Error('missing auth session')
      }
      const session = JSON.parse(raw) as {
        accessToken: string
        refreshToken: string
        accessExpireAt: number
      }
      session.accessToken = 'expired-token-simulated'
      session.accessExpireAt = Date.now() + 3_600_000
      window.localStorage.setItem(key, JSON.stringify(session))
    })

    await page.reload()
    await expect(page).toHaveURL(new RegExp(`/rooms/${roomId}$`))
    await page.getByTestId('room-ready-toggle').click()

    await expect(page.getByTestId('room-ready-count')).toContainText('ready 1/1')
  })

  test('M7-RS-E2E-10 WS 断线重连 + 拉态兜底', async ({ browser }) => {
    const password = '123'
    const userA = await registerAndGetSession(randomUsername('r10a'), password)
    const userB = await registerAndGetSession(randomUsername('r10b'), password)

    const contextA = await browser.newContext({ baseURL: appBaseUrl })
    const contextB = await browser.newContext({ baseURL: appBaseUrl })
    await installRoomSocketTracker(contextA)

    try {
      const pageA = await contextA.newPage()
      const pageB = await contextB.newPage()
      await loginInUi(pageA, userA.username, password)
      await loginInUi(pageB, userB.username, password)

      const rooms = await listRoomsByApi(userA.accessToken)
      const roomId = (rooms.find((room) => room.player_count === 0) ?? rooms[0]).room_id
      await joinRoomByApi(userA.accessToken, roomId)
      await joinRoomByApi(userB.accessToken, roomId)

      await pageA.goto(`/rooms/${roomId}`)
      await pageB.goto(`/rooms/${roomId}`)
      await expect(pageA.getByTestId('room-ready-count')).toContainText('ready 0/2')

      const closedSocketCount = await pageA.evaluate(() => {
        const tracked = (window as unknown as { __xqTrackedSockets?: WebSocket[] }).__xqTrackedSockets ?? []
        let closed = 0
        for (const socket of tracked) {
          if (socket.url.includes('/ws/rooms/')) {
            socket.close(4000, 'M7-RS-E2E-10-forced-disconnect')
            closed += 1
          }
        }
        return closed
      })
      expect(closedSocketCount).toBeGreaterThan(0)

      await setReadyByApi(userB.accessToken, roomId, true)
      await expect
        .poll(async () => (await pageA.getByTestId('room-ready-count').innerText()).trim())
        .toContain('ready 1/2')
    } finally {
      await contextA.close()
      await contextB.close()
    }
  })

  test('M7-RS-E2E-11 服务端重启边界提示', async ({ page }) => {
    const password = '123'
    const user = await registerAndGetSession(randomUsername('r11'), password)

    await loginInUi(page, user.username, password)
    const roomId = await pickFirstRoomIdFromLobby(page)
    await page.getByTestId(`lobby-join-room-${roomId}`).click()
    await expect(page).toHaveURL(new RegExp(`/rooms/${roomId}$`))

    await leaveRoomByApi(user.accessToken, roomId)
    await page.reload()

    await expect(page.getByText('服务已重置，请重新入房')).toBeVisible()
    await expect(page).toHaveURL(/\/lobby$/)
  })

  test('M7-RS-E2E-12 冷结束提示', async ({ page }) => {
    const password = '123'
    const userA = await registerAndGetSession(randomUsername('r12a'), password)
    const userB = await registerAndGetSession(randomUsername('r12b'), password)
    const userC = await registerAndGetSession(randomUsername('r12c'), password)

    const rooms = await listRoomsByApi(userA.accessToken)
    const roomId = (rooms.find((room) => room.player_count === 0) ?? rooms[0]).room_id
    await joinRoomByApi(userA.accessToken, roomId)
    await joinRoomByApi(userB.accessToken, roomId)
    await joinRoomByApi(userC.accessToken, roomId)

    await setReadyByApi(userA.accessToken, roomId, true)
    await setReadyByApi(userB.accessToken, roomId, true)
    await setReadyByApi(userC.accessToken, roomId, true)

    await expect
      .poll(async () => {
        const detail = await getRoomDetailByApi(userA.accessToken, roomId)
        return detail.status
      })
      .toBe('playing')

    await loginInUi(page, userA.username, password)
    await page.goto(`/rooms/${roomId}`)
    await expect(page.getByTestId('room-ready-count')).toBeVisible()

    await leaveRoomByApi(userB.accessToken, roomId)

    await expect(page.getByText('对局结束')).toBeVisible()
  })
})
