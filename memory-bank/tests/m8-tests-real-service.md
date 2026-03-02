# M8 阶段真实后端收口测试设计草案（In-game + Settlement + Seed Hunter）

> 目标：在真实启动的后端服务上完成 M8 对局与结算联调收口，并先冻结“种子注入 + Seed Hunter”的测试设计口径。
> 依据文档：`memory-bank/implementation-plan.md`（M8）、`memory-bank/design/backend_design.md`、`memory-bank/design/frontend_ingame_design.md`、`memory-bank/interfaces/frontend-backend-interfaces.md`、`memory-bank/interfaces/backend-engine-interface.md`。
> 口径声明：本文件当前只保留“测试设计草案”，不包含测试用例 ID、Red/Green 执行记录与通过结果。
> 当前状态：等待测试设计评审确认。

## 0) 测试环境与执行约定（真实服务）

- 建议环境：
  - 后端：conda `XQB`
  - 前端：Node.js `22.x`
- 后端启动（推荐）：
  - `XQWEB_APP_ENV=test`
  - `XQWEB_APP_HOST=127.0.0.1`
  - `XQWEB_APP_PORT=18080`
  - `XQWEB_TEST_DB_DIR=/tmp/xqweb-test`（可选）
  - `XQWEB_JWT_SECRET=<at-least-32-byte-secret>`
  - `bash scripts/start-backend-test.sh`
- 前端环境变量（`frontend/.env.test` 或命令行覆盖）：
  - `VITE_API_BASE_URL=http://127.0.0.1:18080`
  - `VITE_WS_BASE_URL=ws://127.0.0.1:18080`
- e2e 执行建议：
  - `cd frontend && npm run test:e2e -- --project=chromium --workers=1`
- 数据隔离约定：
  - 每轮测试使用唯一用户名前缀。
  - 每轮测试使用全新后端实例（避免跨用例房间污染）。

## 1) 启动参数注入设计（Seed Inject by Startup Options）

> 本节口径以 `memory-bank/design/backend_design.md` 的 `4. M8 Seed Hunter 与启动注入设计` 为准。
> 本文不重复定义后端接口细节，只保留测试关注点。

### 1.1 测试关注点

- 启动参数是否正确生效（环境变量入口）。
- 首局种子一次性消费语义是否可验证。
- 未暴露 REST 注入接口时，e2e 是否仍可稳定复现。

## 2) Seed Hunter 设计（基于台账文件）

> 流程与行为约束以 `memory-bank/design/backend_design.md` 的 `4.4 ~ 4.8` 为准。

### 2.1 标准流程

1. 按目录加载台账并选定目标 case。
2. 先复用 `seed_current` 做快速验证。
3. 失效后进入 `search_range` 搜索。
4. 命中后回填 `seed_current` 与 `updated_at`。
5. 搜索耗尽按启动失败口径处理。

### 2.2 命中判定口径

- 只在“开局可直接观测”的字段上判定。
- 当前冻结匹配维度：
  - 首位出牌座次（`first_turn_seat`）
  - 每位玩家手牌约束（`hands_at_least_by_seat`，子集匹配）

## 3) Seed 台账字段口径（M8-SEED-CATALOG）

JSON 路径：
- `frontend/tests/e2e/seed-catalog/`（目录；M8 台账允许拆分为多个文件）

字段约束：
- `test_id`：测试 ID，必须唯一。
- `enabled`：是否启用该条配置。
- `seed_required`：是否依赖种子。
- `seed_current`：当前可复现 seed；`seed_required=false` 时必须为 `null`。
- `seed_requirement`：命中条件对象（见下方结构）。
- `fallback_policy.search_range`：搜索区间 `[start,end)`。
- `updated_at`：台账最近更新日期（`YYYY-MM-DD`）。

说明：
- 默认 case 选择、跨文件唯一性与启动失败语义以 `backend_design.md` 第 4 章为准。

`seed_requirement` 结构（冻结草案）：

```json
{
  "first_turn_seat": 0,
  "hands_at_least_by_seat": {
    "0": {"R_SHI": 1},
    "1": {"B_XIANG": 1},
    "2": {}
  }
}
```

匹配语义：
- `first_turn_seat`：必须等于开局后首帧中的当前行动 seat。
- `hands_at_least_by_seat`：按 seat 分别做“至少包含”匹配（台账给出的牌张数必须都满足，允许存在额外牌）。

## 4) 测试设计部分（待敲定）

> 本节只保留设计主题，不写测试 ID、不写通过结果、不写 Red/Green 记录。

- 设计主题 A：启动参数注入的一次性消费口径。
- 设计主题 B：台账 case 选择策略（显式 `case_id` 与默认选择）。
- 设计主题 C：`seed_requirement` 两个字段的命中判定细则。
- 设计主题 D：搜索失败时的状态回填与失败可观测性。
- 设计主题 E：台账回填的原子性与并发保护。

## 5) 已冻结决策（与后端设计对齐）

- 后端默认 case 选择：未指定 `case_id` 时按目录顺序取首个 `enabled=true && seed_required=true` 条目。
- 搜索失败口径：启动失败（fail-fast），不带着无效种子继续执行 e2e。
- 台账回填字段：仅回填 `seed_current`、`updated_at`。
