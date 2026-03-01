import { expect, test, type Page } from '@playwright/test'

interface AuthSession {
  user: { id: number; username: string }
  accessToken: string
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

async function registerByApi(username: string, password: string): Promise<void> {
  const response = await fetch(`${apiBaseUrl}/api/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  if (!response.ok) {
    throw new Error(`register failed: ${response.status}`)
  }
}

async function loginInUi(page: Page, username: string, password: string): Promise<void> {
  await page.goto('/login')
  await page.getByTestId('login-username').fill(username)
  await page.getByTestId('login-password').fill(password)
  await page.getByTestId('login-submit').click()
  await expect(page).toHaveURL(/\/lobby$/)
}

async function getAuthSession(page: Page): Promise<AuthSession> {
  const raw = await page.evaluate(() => window.localStorage.getItem('xianqi.auth.session'))
  if (!raw) {
    throw new Error('missing auth session in localStorage')
  }
  const parsed = JSON.parse(raw) as {
    user?: { id?: number; username?: string }
    accessToken?: string
  }
  if (!parsed.user?.id || !parsed.user?.username || !parsed.accessToken) {
    throw new Error('invalid auth session payload')
  }
  return {
    user: {
      id: parsed.user.id,
      username: parsed.user.username,
    },
    accessToken: parsed.accessToken,
  }
}

async function listRoomsByApi(accessToken: string): Promise<RoomSummary[]> {
  const response = await fetch(`${apiBaseUrl}/api/rooms`, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  })
  if (!response.ok) {
    throw new Error(`list rooms failed: ${response.status}`)
  }
  return (await response.json()) as RoomSummary[]
}

async function getRoomByApi(accessToken: string, roomId: number): Promise<{ status: number; detail: RoomDetail | null }> {
  const response = await fetch(`${apiBaseUrl}/api/rooms/${roomId}`, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  })
  if (!response.ok) {
    return { status: response.status, detail: null }
  }
  return { status: response.status, detail: (await response.json()) as RoomDetail }
}

async function joinRoomByApi(accessToken: string, roomId: number): Promise<void> {
  const response = await fetch(`${apiBaseUrl}/api/rooms/${roomId}/join`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  })
  if (!response.ok) {
    throw new Error(`join room failed: ${response.status}`)
  }
}

async function pickFirstRoomIdFromLobby(page: Page): Promise<number> {
  const firstJoinButton = page.locator('[data-testid^="lobby-join-room-"]').first()
  await expect(firstJoinButton).toBeVisible()
  const testId = await firstJoinButton.getAttribute('data-testid')
  if (!testId) {
    throw new Error('missing join button data-testid')
  }
  const roomId = Number.parseInt(testId.replace('lobby-join-room-', ''), 10)
  if (Number.isNaN(roomId)) {
    throw new Error(`invalid room id test id: ${testId}`)
  }
  return roomId
}

async function readLobbyCounts(page: Page, roomId: number): Promise<{ playerCount: number; readyCount: number }> {
  const rowButton = page.getByTestId(`lobby-join-room-${roomId}`)
  const row = rowButton.locator('xpath=ancestor::tr')
  const playerCountText = (await row.locator('td').nth(2).innerText()).trim()
  const readyCountText = (await row.locator('td').nth(3).innerText()).trim()
  return {
    playerCount: Number.parseInt(playerCountText, 10),
    readyCount: Number.parseInt(readyCountText, 10),
  }
}

test.describe('M7 RS E2E 04-08', () => {
  test.describe.configure({ mode: 'serial' })

  test('M7-RS-E2E-04 入房主流程', async ({ page }) => {
    const username = randomUsername('r4')
    const password = '123'
    await registerByApi(username, password)
    await loginInUi(page, username, password)
    const auth = await getAuthSession(page)

    const roomId = await pickFirstRoomIdFromLobby(page)
    await page.getByTestId(`lobby-join-room-${roomId}`).click()

    await expect(page).toHaveURL(new RegExp(`/rooms/${roomId}$`))
    const roomFetch = await getRoomByApi(auth.accessToken, roomId)
    expect(roomFetch.status).toBe(200)
    expect(roomFetch.detail?.members.some((member) => member.user_id === auth.user.id)).toBe(true)
  })

  test('M7-RS-E2E-05 ready 切换（真实 REST + ROOM_UPDATE）', async ({ page }) => {
    const username = randomUsername('r5')
    const password = '123'
    await registerByApi(username, password)
    await loginInUi(page, username, password)

    const roomId = await pickFirstRoomIdFromLobby(page)
    await page.getByTestId(`lobby-join-room-${roomId}`).click()
    await expect(page).toHaveURL(new RegExp(`/rooms/${roomId}$`))

    await page.getByTestId('room-ready-toggle').click()
    await expect(page.getByTestId('room-ready-count')).toContainText('ready 1/1')

    await page.reload()
    await expect(page).toHaveURL(new RegExp(`/rooms/${roomId}$`))
    await expect(page.getByTestId('room-ready-count')).toContainText('ready 1/1')
  })

  test('M7-RS-E2E-06 leave 主流程', async ({ page }) => {
    const username = randomUsername('r6')
    const password = '123'
    await registerByApi(username, password)
    await loginInUi(page, username, password)
    const auth = await getAuthSession(page)

    const roomsBeforeJoin = await listRoomsByApi(auth.accessToken)
    const candidateRoom = roomsBeforeJoin.find((room) => room.player_count === 0) ?? roomsBeforeJoin[0]
    const roomId = candidateRoom.room_id
    const beforeCount = candidateRoom.player_count
    await joinRoomByApi(auth.accessToken, roomId)

    const afterJoin = await listRoomsByApi(auth.accessToken)
    const roomAfterJoin = afterJoin.find((room) => room.room_id === roomId)
    expect(roomAfterJoin?.player_count).toBe(beforeCount + 1)

    await page.goto(`/rooms/${roomId}`)
    await page.getByTestId('room-leave-button').click()
    await expect(page).toHaveURL(/\/lobby$/)

    const afterLeave = await listRoomsByApi(auth.accessToken)
    const roomAfterLeave = afterLeave.find((room) => room.room_id === roomId)
    expect(roomAfterLeave?.player_count).toBe(beforeCount)
  })

  test('M7-RS-E2E-07 大厅实时同步（双端）', async ({ browser }) => {
    const usernameA = randomUsername('r7a')
    const usernameB = randomUsername('r7b')
    const password = '123'
    await registerByApi(usernameA, password)
    await registerByApi(usernameB, password)

    const contextA = await browser.newContext({ baseURL: appBaseUrl })
    const contextB = await browser.newContext({ baseURL: appBaseUrl })
    try {
      const pageA = await contextA.newPage()
      const pageB = await contextB.newPage()

      await loginInUi(pageA, usernameA, password)
      await loginInUi(pageB, usernameB, password)

      const roomId = await pickFirstRoomIdFromLobby(pageB)
      const before = await readLobbyCounts(pageB, roomId)

      await pageA.getByTestId(`lobby-join-room-${roomId}`).click()
      await expect(pageA).toHaveURL(new RegExp(`/rooms/${roomId}$`))
      await expect
        .poll(async () => {
          const next = await readLobbyCounts(pageB, roomId)
          return next.playerCount
        })
        .toBe(before.playerCount + 1)

      await pageA.getByTestId('room-ready-toggle').click()
      await expect
        .poll(async () => {
          const next = await readLobbyCounts(pageB, roomId)
          return next.readyCount
        })
        .toBe(before.readyCount + 1)

      await pageA.getByTestId('room-leave-button').click()
      await expect(pageA).toHaveURL(/\/lobby$/)
      await expect
        .poll(async () => {
          const next = await readLobbyCounts(pageB, roomId)
          return `${next.playerCount}/${next.readyCount}`
        })
        .toBe(`${before.playerCount}/${before.readyCount}`)
    } finally {
      await contextA.close()
      await contextB.close()
    }
  })

  test('M7-RS-E2E-08 房间实时同步（双端）', async ({ browser }) => {
    const usernameA = randomUsername('r8a')
    const usernameB = randomUsername('r8b')
    const password = '123'
    await registerByApi(usernameA, password)
    await registerByApi(usernameB, password)

    const contextA = await browser.newContext({ baseURL: appBaseUrl })
    const contextB = await browser.newContext({ baseURL: appBaseUrl })
    try {
      const pageA = await contextA.newPage()
      const pageB = await contextB.newPage()

      await loginInUi(pageA, usernameA, password)
      await loginInUi(pageB, usernameB, password)

      const authA = await getAuthSession(pageA)
      const authB = await getAuthSession(pageB)
      const rooms = await listRoomsByApi(authA.accessToken)
      const roomId = rooms[0].room_id
      await joinRoomByApi(authA.accessToken, roomId)
      await joinRoomByApi(authB.accessToken, roomId)

      await pageA.goto(`/rooms/${roomId}`)
      await pageB.goto(`/rooms/${roomId}`)

      const before = (await pageB.getByTestId('room-ready-count').innerText()).trim()
      await pageA.getByTestId('room-ready-toggle').click()

      await expect
        .poll(async () => {
          const next = (await pageB.getByTestId('room-ready-count').innerText()).trim()
          return next === before ? 'unchanged' : 'changed'
        })
        .toBe('changed')
    } finally {
      await contextA.close()
      await contextB.close()
    }
  })
})
