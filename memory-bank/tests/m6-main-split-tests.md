# M6 main.py 拆分测试设计与TDD记录

> 目标：在不改变外部行为的前提下拆分 `backend/app/main.py`，验证 REST/WS 主链路、心跳与重连关键语义不回退。
> 范围：结构重构（routers/ws/runtime 模块化），不新增业务功能。

## 1) 测试用例列表

| 测试ID | 描述 | 通过条件 |
|---|---|---|
| M6-MAIN-SPLIT-01 | M6 心跳回归 | `pytest backend/tests/integration/real_service/test_m6_rs_hb_01_03_red.py -q` 全通过 |
| M6-MAIN-SPLIT-02 | M6 重连回归 | `pytest backend/tests/integration/real_service/test_m6_rs_rc_01_08_red.py -q` 全通过 |
| M6-MAIN-SPLIT-03 | M6 WS 推送回归 | `pytest backend/tests/integration/real_service/test_m6_rs_ws_01_08_red.py -q` 全通过 |
| M6-MAIN-SPLIT-04 | M2 WS 心跳兼容回归 | `pytest backend/tests/integration/real_service/test_m2_rs_ws_06_10_red.py::test_m2_rs_ws_10_server_ping_and_client_pong_keeps_connection_alive -q` 通过 |
| M6-MAIN-SPLIT-05 | 旧单测入口兼容（startup/me/register/login） | `pytest backend/tests/api/auth -q` 全通过，且 `app.main` 导出接口保持可用 |

## 2) TDD执行记录

| 测试ID | 当前状态 | 阶段 | 执行日期 | 备注 |
|---|---|---|---|---|
| M6-MAIN-SPLIT-01 | ✅ 已通过 | Green（回归通过） | 2026-02-24 | 执行 `pytest backend/tests/integration/real_service/test_m6_rs_hb_01_03_red.py -q`，结果 `3 passed`。 |
| M6-MAIN-SPLIT-02 | ✅ 已通过 | Green（回归通过） | 2026-02-24 | 执行 `pytest backend/tests/integration/real_service/test_m6_rs_rc_01_08_red.py -q`，结果 `8 passed`。 |
| M6-MAIN-SPLIT-03 | ✅ 已通过 | Green（回归通过） | 2026-02-24 | 执行 `pytest backend/tests/integration/real_service/test_m6_rs_ws_01_08_red.py -q`，结果 `8 passed`。 |
| M6-MAIN-SPLIT-04 | ✅ 已通过 | Green（回归通过） | 2026-02-24 | 执行 `pytest backend/tests/integration/real_service/test_m2_rs_ws_06_10_red.py::test_m2_rs_ws_10_server_ping_and_client_pong_keeps_connection_alive -q`，结果 `1 passed`。 |
| M6-MAIN-SPLIT-05 | ✅ 已通过 | Green（回归通过） | 2026-02-24 | 执行 `pytest backend/tests/api/auth -q`，结果 `12 passed`，验证 `app.main` 旧导出入口兼容。 |

补充回归（非主清单）：
- `pytest backend/tests/integration/ws/test_m2_ws_01_06_rooms.py -q` => `6 passed`
- `pytest backend/tests/integration/concurrency/test_m2_cc_01_03_rooms.py -q` => `3 passed`
- `pytest backend/tests/api/games/test_m5_api_01_05_settlement_red.py backend/tests/api/games/test_m5_api_06_10_ready_reopen_red.py -q` => `10 passed`
