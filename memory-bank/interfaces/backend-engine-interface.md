# 后端对局引擎接口

## 1. 逻辑引擎接口设计

### 1.1 基本约定
- 引擎是一个对象，内部维护当前对局状态（state），对外暴露明确的方法。
- 所有校验在引擎完成（手牌合法性、轮次、必须压制/垫棋等）。
- 引擎内部只使用座次（seat）标识玩家；用户 id 与座次映射由后端维护。
- “当前谁在决策（谁的计时在走）”属于一等状态；最少应可由 `turn.current_seat` 表达，推荐额外显式输出 `decision` 字段。

引擎对象建议提供的方法：
- `init_game(config, rng_seed?) -> output`：初始化新局并返回一次输出快照（见 1.5）。
- `apply_action(action_idx, cover_list=None, client_version=None) -> output`：按 `legal_actions` 列表序号执行动作并推进状态，返回输出快照（见 1.5）。
- `settle() -> output`：在 `phase = settlement` 时计算结算并推进到 `finished`，返回输出快照（见 1.5）。
- `get_public_state() -> public_state`：获取当前公共状态（脱敏）。
- `get_private_state(seat) -> private_state`：获取指定 seat 的私有状态。
- `get_legal_actions(seat) -> legal_actions`：获取指定 seat 的合法动作列表（通常为当前行动玩家）。
- `dump_state() -> state`：导出完整内部状态用于持久化/重连。
- `load_state(state)`：从持久化状态恢复引擎。

### 1.2 卡牌与组合表示（不区分实例）
- card_type：如 `R_SHI`, `B_SHI`, `R_XIANG`, `B_XIANG`, `R_MA`, `B_MA`, `R_CHE`, `B_CHE`, `R_GOU`, `B_GOU`, `R_NIU`, `B_NIU`。
- hand 表示为计数表（多重集合）：`{\"R_SHI\": 2, \"B_NIU\": 1, ...}`。
- combo（出棋/垫棋的具体牌面，不含“本轮牌型”）：
  - power: int（按规则计算；垫棋固定为 -1）
  - cards: [{type, count}]
- round_kind（本轮牌型/张数）：
  - 1：single（单张）
  - 2：pair / dog_pair（对子/狗脚对）
  - 3：triple（三牛）

卡牌牌力（单张，数值越大越强）：
|卡牌类型|描述|牌力|
|---|---|---|
|R_SHI|红士|9|
|B_SHI|黑士|8|
|R_XIANG|红相|7|
|B_XIANG|黑象|6|
|R_MA|红马|5|
|B_MA|黑马|4|
|R_CHE|红车|3|
|B_CHE|黑车|2|
|R_GOU|红狗/炮|3（与红车同级）|
|B_GOU|黑狗/炮|2（与黑车同级）|
|R_NIU|红牛/兵|1|
|B_NIU|黑牛/卒|0|
一轮出牌是牌力为-1的时候，代表该轮是垫牌的。

### 1.3 引擎状态结构（建议）
说明：引擎状态为内部完整记录，包含垫棋牌面；对外 public_state 由后端脱敏处理。
补充：`buckle_decision` 阶段视为新一轮开始，`round_kind` 应置为 0（表示尚未出牌确定牌型）。
```jsonc
{
  "version": 12, // 状态版本号，单调递增，用于乐观锁与重连校验（每次动作被接受并更新状态后 +1）
  "phase": "in_round", // 对局阶段（init / buckle_decision / in_round / reveal_decision / settlement / finished）
  "players": [
    {
      "seat": 0, // 座次（0/1/2，逆时针）
      "hand": {"R_SHI": 2} // 手牌计数表：card_type -> count
    },
    {"seat": 1, "hand": {"B_NIU": 1}},
    {"seat": 2, "hand": {}}
  ],
  "turn": {
    "current_seat": 0, // 当前该行动/当前决策（当前烧时间）的座次
    "round_index": 2, // 第几回合（从0开始）
    "round_kind": 1, // 本轮牌型/张数（1/2/3）
    "last_combo": {
      "power": 9, // 组合强度（按规则计算，垫棋不会改写 last_combo）
      "cards": [{"type": "R_SHI", "count": 1}], // 组合内牌的类型与数量
      "owner_seat": 1 // 当前最大组合所属座次
    },
    "plays": [
      {
        "seat": 1,
        "power": 9,
        "cards": [{"type": "R_SHI", "count": 1}]
      },
      {
        "seat": 2,
        "power": -1,
        "cards": [{"type": "B_NIU", "count": 1}]
      }
    ]
  },
  "decision": {
    "seat": 0, // 当前决策座次（与 turn.current_seat 一致）
    "context": "in_round", // buckle_decision / in_round / reveal_decision
    "started_at_ms": 1739600000, // 进入该决策位时间
    "timeout_at_ms": null // MVP 可为空；后续支持超时时填截止时间
  },
  "pillar_groups": [
    {
      "round_index": 1, // 本棋柱组来源的回合序号（从0开始）
      "winner_seat": 1, // 获得本棋柱组的玩家座次
      "round_kind": 2, // 1/2/3
      "plays": [
        {
          "seat": 1, // 出棋者座次
          "power": 9,
          "cards": [{"type": "R_SHI", "count": 2}] // 出棋的牌
        },
        {
          "seat": 2, // 垫棋者座次
          "power": -1,
          "cards": [{"type": "B_NIU", "count": 2}] // 垫棋牌面（内部记录）
        },
        {
          "seat": 0,
          "power": -1,
          "cards": [{"type": "R_NIU", "count": 2}]
        }
      ]
    }
  ],
  "reveal": {
    "buckler_seat": 0, // 本次扣棋发起人
    "pending_order": [2], // 待决策掀棋的座次顺序
    "relations": [
      {
        "revealer_seat": 1,
        "buckler_seat": 0,
        "revealer_enough_at_time": false // 掀棋当刻是否已够棋
      }
    ] // 掀扣关系（按时间追加）
  }
}
```

### 1.4 动作输入（ActionIndex）
```json
{
  "action_idx": 0,
  "client_version": 12,
  "cover_list": [{"type": "B_NIU", "count": 1}]
}
```
说明：
- `action_idx` 为当前 `legal_actions.actions` 的下标（从 0 开始）。
- `cover_list` 仅在 `action_idx` 指向 COVER 时需要，表示实际垫牌牌面；其他动作传 `null`。允许任意组合，但引擎必须校验该玩家是否持有这些牌。
- `client_version` 为客户端认为的当前版本号（可选）；引擎必须校验并在不匹配时拒绝该动作。

### 1.5 引擎输出
- new_state（完整状态，内部用）
- public_state（完整公共快照，前端可直接渲染）
- private_state_by_seat（每个座次的私有快照，仅向本人发送）
- legal_actions（当前应行动玩家的全部合法动作）
- settlement（结算结果，仅在 `phase = settlement / finished` 时提供；包含完整状态与每个玩家筹码变更）

#### 1.5.1 public_state（脱敏）
```jsonc
{
  "version": 12,
  "phase": "in_round",
  "players": [
    {"seat": 0, "hand_count": 6, "captured_pillar_count": 2},
    {"seat": 1, "hand_count": 6, "captured_pillar_count": 3},
    {"seat": 2, "hand_count": 6, "captured_pillar_count": 3}
  ],
  "turn": {
    "current_seat": 0,
    "round_index": 2,
    "round_kind": 1,
    "last_combo": {
      "power": 9,
      "cards": [{"type": "R_SHI", "count": 1}],
      "owner_seat": 1
    },
    "plays": [
      {"seat": 1, "power": 9, "cards": [{"type": "R_SHI", "count": 1}]},
      {"seat": 2, "power": -1, "covered_count": 1}
    ]
  },
  "decision": {
    "seat": 0,
    "context": "in_round",
    "timeout_at_ms": null
  },
  "pillar_groups": [
    {
      "round_index": 1,
      "winner_seat": 1,
      "round_kind": 2,
      "plays": [
        {"seat": 1, "power": 9, "cards": [{"type": "R_SHI", "count": 2}]},
        {"seat": 2, "power": -1, "covered_count": 2},
        {"seat": 0, "power": -1, "covered_count": 2}
      ]
    }
  ],
  "reveal": {
    "buckler_seat": 0,
    "pending_order": [2],
    "relations": [{"revealer_seat": 1, "buckler_seat": 0, "revealer_enough_at_time": false}]
  }
}
```
- `hand_count`、`captured_pillar_count` 为公开信息；`captured_pillar_count` 可由 `pillar_groups` 推导，但为前端便利提供且必须由引擎计算输出。
- 垫棋在公共视图中不暴露牌面，使用 `covered_count` 代替 `cards`。
- `decision` 用于明确“当前轮到谁决策/谁的时钟在走”；与 `turn.current_seat` 必须一致。

#### 1.5.2 private_state_by_seat
```jsonc
{
  "0": {"hand": {"R_SHI": 2, "B_NIU": 1}, "covered": {"R_NIU": 1}},
  "1": {"hand": {"B_NIU": 1}, "covered": {}},
  "2": {"hand": {}, "covered": {"B_NIU": 2}}
}
```
- 后端仅将对应 seat 的私有状态下发给本人。
- `covered` 为该玩家已垫棋子的计数表（card_type -> count），仅本人可见。

#### 1.5.3 legal_actions（仅当前行动玩家）
同一状态下 `actions` 只包含当前阶段合法动作：`in_round` 阶段 PLAY 与 COVER 互斥；`buckle_decision` 阶段仅 PLAY 或 BUCKLE；REVEAL / PASS_REVEAL 仅在 `phase = reveal_decision` 出现。`actions` 的顺序按引擎输出顺序，后端与前端不做额外排序；`action_idx` 以该顺序为准。同一状态下无牌面动作（BUCKLE / REVEAL / PASS_REVEAL）各最多 1 个。
所有动作都需要引擎校验；若校验失败，引擎应返回错误，后端需向客户端返回非 204 的错误码（MVP 阶段即可）。

buckle_decision 阶段示例（起始玩家可出棋或扣棋）：
```jsonc
{
  "seat": 0,
  "actions": [
    {
      "type": "PLAY",
      "payload_cards": [{"type": "R_SHI", "count": 1}]
    },
    {
      "type": "PLAY",
      "payload_cards": [{"type": "B_NIU", "count": 1}]
    },
    {"type": "BUCKLE"},
  ]
}
```

in_round 阶段示例（可压制）：
```jsonc
{
  "seat": 1,
  "actions": [
    {
      "type": "PLAY",
      "payload_cards": [{"type": "R_SHI", "count": 1}]
    }
  ]
}
```

in_round 阶段示例（只能垫牌）：
```jsonc
{
  "seat": 1,
  "actions": [
    {
      "type": "COVER",
      "required_count": 1
    }
  ]
}
```

掀棋决策示例：
```jsonc
{
  "seat": 2,
  "actions": [
    {"type": "REVEAL"},
    {"type": "PASS_REVEAL"}
  ]
}
```
- COVER 仅给出 `required_count`，由前端在手牌中选择任意同张数牌面并通过 `cover_list` 传回，最终由引擎校验合法性。

#### 1.5.4 settlement（结算结果）
```jsonc
{
  "final_state": { /* 完整对局状态（未脱敏） */ },
  "chip_delta_by_seat": [
    {
      "seat": 0,
      "delta": -1,
      "delta_enough": 0,
      "delta_reveal": -1,
      "delta_ceramic": 0
    },
    {
      "seat": 1,
      "delta": 2,
      "delta_enough": 1,
      "delta_reveal": 0,
      "delta_ceramic": 1
    },
    {
      "seat": 2,
      "delta": -1,
      "delta_enough": -1,
      "delta_reveal": 0,
      "delta_ceramic": 0
    }
  ]
}
```
- 结算时下发完整状态，便于结果解释（“输家做个明白鬼”）。
- `delta_enough / delta_reveal / delta_ceramic` 分别表示够棋、掀棋、瓷棋导致的筹码变更（加和为 `delta`）。若玩家已够但未瓷且因掀棋而不赢够棋筹码，则 `delta_enough = 0`。
