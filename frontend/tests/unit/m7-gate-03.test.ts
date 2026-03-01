import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

const EXPECTED_M7_GREEN_IDS = [
  'M7-UT-01',
  'M7-UT-02',
  'M7-UT-03',
  'M7-UT-04',
  'M7-UT-05',
  'M7-UT-06',
  'M7-UT-07',
  'M7-CT-01',
  'M7-CT-02',
  'M7-CT-03',
  'M7-CT-04',
  'M7-CT-05',
  'M7-CT-06',
  'M7-CT-07',
  'M7-WS-01',
  'M7-WS-02',
  'M7-WS-03',
  'M7-WS-04',
  'M7-WS-05',
  'M7-WS-06',
  'M7-E2E-01',
  'M7-E2E-02',
  'M7-E2E-03',
]

function resolveM7TestsDocPath(): string {
  const candidates = [
    resolve(process.cwd(), 'memory-bank/tests/m7-tests.md'),
    resolve(process.cwd(), '../memory-bank/tests/m7-tests.md'),
  ]

  const path = candidates.find((candidate) => existsSync(candidate))
  if (!path) {
    throw new Error('cannot locate memory-bank/tests/m7-tests.md')
  }
  return path
}

describe('M7 Gate 03', () => {
  it('M7-GATE-03 M7-UT/CT/WS/E2E 在 m7-tests.md 中保持 Green', () => {
    const m7TestsDocPath = resolveM7TestsDocPath()
    const content = readFileSync(m7TestsDocPath, 'utf-8')

    const greenStatusById = new Map<string, boolean>()
    const rowMatcher = /^\|\s*(M7-(?:UT|CT|WS|E2E)-\d{2})\s*\|\s*(.+?)\s*\|/gm

    for (const match of content.matchAll(rowMatcher)) {
      const testId = match[1]
      const statusCell = match[2]
      greenStatusById.set(testId, statusCell.includes('✅ Green通过'))
    }

    const missingOrNotGreen = EXPECTED_M7_GREEN_IDS.filter((id) => !greenStatusById.get(id))
    expect(missingOrNotGreen).toEqual([])
  })
})
