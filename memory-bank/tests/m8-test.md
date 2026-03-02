# M8 阶段测试列表（后端种子注入与 Seed Hunting，TDD）

> 依据文档：
> - `memory-bank/implementation-plan.md`（M8）
> - `memory-bank/design/backend_design.md`（第 4 章：M8 Seed Hunter 与 REST 注入设计）
> - `memory-bank/interfaces/frontend-backend-interfaces.md`
> 目标：先冻结测试用例清单与通过条件，再由人类指定测试 ID 进入 Red -> Green。

## 0) 测试环境与执行策略

- 两种运行模式必须分开测：
  - Seed Hunting 模式：设置 `XQWEB_SEED_CATALOG_DIR`，进程仅遍历台账并退出。
  - 常规服务模式：不设置 `XQWEB_SEED_CATALOG_DIR`，按 `XQWEB_SEED_ENABLE_SEED_INJECTION` 决定是否开放注入 REST。
- 推荐分层：
  - 单元：配置解析、目录扫描顺序、匹配器判定。
  - 集成：seed hunting 主流程、台账回填、退出码。
  - API/真实服务：`POST /api/games/seed-injection` 与“下一局一次性消费”语义。
- TDD 流程：
  1. 人类先指定测试 ID。
  2. 先编写并执行 Red（按预期失败）。
  3. 再最小改动实现到 Green。
  4. 每个测试通过后更新本文档第 3 节记录。

## 1) 测试用例列表（含通过条件）

### 1.1 配置与模式路由

| 测试ID | 测试描述 | 通过条件 |
|---|---|---|
| M8-SEED-CFG-01 | `XQWEB_SEED_ENABLE_SEED_INJECTION` 非法布尔值启动失败 | 进程非 0 退出，日志包含配置错误原因 |
| M8-SEED-CFG-02 | 仅设置 `XQWEB_SEED_CATALOG_DIR` 时进入 seed hunting 模式 | 不启动常规 HTTP/WS 服务；执行台账遍历后退出 |
| M8-SEED-CFG-03 | 仅设置 `XQWEB_SEED_ENABLE_SEED_INJECTION=true` 时进入常规服务模式 | HTTP 服务可用；注入接口可访问（非 403） |
| M8-SEED-CFG-04 | 同时设置两个变量时，`XQWEB_SEED_CATALOG_DIR` 优先 | 进程进入 seed hunting 模式，不启动常规 HTTP/WS |
| M8-SEED-CFG-05 | `XQWEB_SEED_CATALOG_DIR` 不存在或不可读 | 进程非 0 退出，日志包含目录错误信息 |

### 1.2 Seed Hunting（离线批量）流程

| 测试ID | 测试描述 | 通过条件 |
|---|---|---|
| M8-SEED-HUNT-01 | 目录遍历顺序固定：文件名升序 + `cases` 数组顺序 | 实际处理顺序与文档约定一致 |
| M8-SEED-HUNT-02 | 仅处理 `enabled=true && seed_required=true` | 非候选 case 不参与验证和搜索 |
| M8-SEED-HUNT-03 | `seed_current` 快速验证命中时不进入搜索 | 不触发 `search_range` 遍历，case 标记成功 |
| M8-SEED-HUNT-04 | 快速验证失败后进入区间搜索并命中 | 命中后回填 `seed_current` 和 `updated_at` |
| M8-SEED-HUNT-05 | 搜索区间耗尽未命中 | 该 case 失败；最终进程非 0 退出 |
| M8-SEED-HUNT-06 | `search_range` 非法（`start<0` 或 `end<=start`） | 进程非 0 退出，日志可诊断 |
| M8-SEED-HUNT-07 | `test_id` 跨文件重复 | 进程非 0 退出，日志标注重复 `test_id` |
| M8-SEED-HUNT-08 | 全量候选 case 成功后退出码正确 | 输出 `total/success/fail` 汇总，且 `exit 0` |

### 1.3 REST 注入接口与“一次性消费”

| 测试ID | 测试描述 | 通过条件 |
|---|---|---|
| M8-SEED-API-01 | 注入开关关闭时调用接口 | 返回 `403` |
| M8-SEED-API-02 | 请求体缺失 `seed` | 返回 `400` |
| M8-SEED-API-03 | `seed` 类型错误或 `<0` | 返回 `400` |
| M8-SEED-API-04 | 合法注入请求 | `200`，响应含 `ok=true`、`injected_seed`、`apply_scope=next_game_once` |
| M8-SEED-API-05 | 重复注入覆盖语义 | 后一次注入覆盖前一次（下一局使用后写 seed） |
| M8-SEED-API-06 | 注入后仅下一局消费一次 | 第一个新局使用注入 seed；第二个新局不继承该 seed |
| M8-SEED-API-07 | 注入不影响已在进行中的对局 | 进行中对局的 seed/状态不被改写，仅影响后续新局 |
| M8-SEED-API-08 | 处于 seed hunting 模式时不可走 REST 注入链路 | 进程不提供常规 HTTP/WS，无法调用注入接口 |

## 2) 阶段通过判定（M8-Seed）

- 配置路由可稳定区分“离线 seed hunting 模式”与“常规服务模式”。
- Seed Hunting 可按台账批量执行、正确回填，并以退出码反映成败。
- REST 注入接口契约（200/400/403）稳定。
- “注入后仅下一局生效且只消费一次”被可重复验证。

## 3) TDD 执行记录

> 当前已完成 `M8-SEED-CFG-01~05` 的 Red->Green；其余测试待指定。

| 测试ID | 当前状态 | TDD阶段 | 执行日期 | 备注 |
|---|---|---|---|---|
| M8-SEED-CFG-01 | Green通过 | Green完成 | 2026-03-02 | 已先 Red 后 Green；`XQWEB_SEED_ENABLE_SEED_INJECTION=not-bool` 启动失败（非 0 退出）。 |
| M8-SEED-CFG-02 | Green通过 | Green完成 | 2026-03-02 | 已先 Red 后 Green；仅设置 `XQWEB_SEED_CATALOG_DIR` 时进入 catalog 模式并快速退出，HTTP 不可达。 |
| M8-SEED-CFG-03 | Green通过 | Green完成 | 2026-03-02 | 已先 Red 后 Green；`XQWEB_SEED_ENABLE_SEED_INJECTION=true` 时 `POST /api/games/seed-injection` 不再返回 `403/404`。 |
| M8-SEED-CFG-04 | Green通过 | Green完成 | 2026-03-02 | 已先 Red 后 Green；同时设置两个变量时由 `XQWEB_SEED_CATALOG_DIR` 优先并快速退出。 |
| M8-SEED-CFG-05 | Green通过 | Green完成 | 2026-03-02 | 已先 Red 后 Green；`XQWEB_SEED_CATALOG_DIR` 不存在时启动失败（非 0 退出）。 |
| M8-SEED-HUNT-01 | Pending | 未开始 | - | 待人类指定 |
| M8-SEED-HUNT-02 | Pending | 未开始 | - | 待人类指定 |
| M8-SEED-HUNT-03 | Pending | 未开始 | - | 待人类指定 |
| M8-SEED-HUNT-04 | Pending | 未开始 | - | 待人类指定 |
| M8-SEED-HUNT-05 | Pending | 未开始 | - | 待人类指定 |
| M8-SEED-HUNT-06 | Pending | 未开始 | - | 待人类指定 |
| M8-SEED-HUNT-07 | Pending | 未开始 | - | 待人类指定 |
| M8-SEED-HUNT-08 | Pending | 未开始 | - | 待人类指定 |
| M8-SEED-API-01 | Pending | 未开始 | - | 待人类指定 |
| M8-SEED-API-02 | Pending | 未开始 | - | 待人类指定 |
| M8-SEED-API-03 | Pending | 未开始 | - | 待人类指定 |
| M8-SEED-API-04 | Pending | 未开始 | - | 待人类指定 |
| M8-SEED-API-05 | Pending | 未开始 | - | 待人类指定 |
| M8-SEED-API-06 | Pending | 未开始 | - | 待人类指定 |
| M8-SEED-API-07 | Pending | 未开始 | - | 待人类指定 |
| M8-SEED-API-08 | Pending | 未开始 | - | 待人类指定 |
