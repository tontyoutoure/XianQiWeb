import { mount, type VueWrapper } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import type { Component } from 'vue'

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

interface ActionBarModule {
  default?: Component
}

const ACTION_TYPES: ActionType[] = ['BUCKLE', 'PASS_BUCKLE', 'REVEAL', 'PASS_REVEAL', 'PLAY', 'COVER']
const ACTION_BAR_CANDIDATE_PATHS = [
  '/src/components/ingame/ActionBar.vue',
  '/src/components/ActionBar.vue',
] as const

const ACTION_LABELS: Record<ActionType, string[]> = {
  BUCKLE: ['BUCKLE', '扣棋'],
  PASS_BUCKLE: ['PASS_BUCKLE', '不扣'],
  REVEAL: ['REVEAL', '掀棋'],
  PASS_REVEAL: ['PASS_REVEAL', '不掀'],
  PLAY: ['PLAY', '出棋'],
  COVER: ['COVER', '垫棋'],
}

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
    'M8-CT-01~04 requires an ActionBar component at "@/components/ingame/ActionBar.vue" or "@/components/ActionBar.vue".',
  )
}

async function mountActionBar(phase: string, legalActions: LegalActions): Promise<VueWrapper> {
  const ActionBar = await loadActionBarComponent()
  return mount(ActionBar, {
    props: {
      phase,
      currentPhase: phase,
      legalActions,
      legal_actions: legalActions,
      actionTypes: legalActions.actions.map((action) => action.type),
      availableActionTypes: legalActions.actions.map((action) => action.type),
    },
  })
}

function normalizeLabel(label: string): string {
  return label.replace(/\s+/g, '').toUpperCase()
}

function collectVisibleActionTypes(wrapper: VueWrapper): ActionType[] {
  const visibleActions = new Set<ActionType>()
  const buttons = wrapper.findAll('button')

  for (const button of buttons) {
    if (!button.isVisible()) {
      continue
    }

    const testId = normalizeLabel(button.attributes('data-testid') ?? '')
    const buttonText = normalizeLabel(button.text())

    for (const actionType of ACTION_TYPES) {
      if (testId.includes(actionType)) {
        visibleActions.add(actionType)
        continue
      }

      const labels = ACTION_LABELS[actionType]
      if (labels.some((label) => buttonText.includes(normalizeLabel(label)))) {
        visibleActions.add(actionType)
      }
    }
  }

  return ACTION_TYPES.filter((actionType) => visibleActions.has(actionType))
}

function expectOnlyVisibleActions(wrapper: VueWrapper, expected: ActionType[]) {
  const visible = collectVisibleActionTypes(wrapper)
  expect(visible).toEqual(expected)
}

describe('M8 Stage 3 Red - action bar button visibility', () => {
  it('M8-CT-01 buckle_flow 起始决策仅显示 BUCKLE/PASS_BUCKLE', async () => {
    const wrapper = await mountActionBar('buckle_flow', {
      seat: 0,
      actions: [{ type: 'BUCKLE' }, { type: 'PASS_BUCKLE' }],
    })

    expectOnlyVisibleActions(wrapper, ['BUCKLE', 'PASS_BUCKLE'])
  })

  it('M8-CT-02 掀棋询问仅显示 REVEAL/PASS_REVEAL', async () => {
    const wrapper = await mountActionBar('buckle_flow', {
      seat: 1,
      actions: [{ type: 'REVEAL' }, { type: 'PASS_REVEAL' }],
    })

    expectOnlyVisibleActions(wrapper, ['REVEAL', 'PASS_REVEAL'])
  })

  it('M8-CT-03 in_round 可压制时仅显示 PLAY（无 COVER）', async () => {
    const wrapper = await mountActionBar('in_round', {
      seat: 2,
      actions: [{ type: 'PLAY', payload_cards: { R_SHI: 1 } }],
    })

    expectOnlyVisibleActions(wrapper, ['PLAY'])
  })

  it('M8-CT-04 in_round 无法压制时仅显示 COVER（无 PLAY）', async () => {
    const wrapper = await mountActionBar('in_round', {
      seat: 2,
      actions: [{ type: 'COVER', required_count: 1 }],
    })

    expectOnlyVisibleActions(wrapper, ['COVER'])
  })
})
