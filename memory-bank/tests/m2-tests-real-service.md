# M2 阶段真实服务收口测试清单（Rooms REST + WS）

> 目标：在真实启动的后端服务上完成 M2 全功能收口，覆盖房间大厅的所有关键能力（预设房间、成员管理、ready、跨房迁移、冷结束、WS 推送、并发一致性）。
> 参考文档：`memory-bank/tests/m1-tests-real-service.md`、`memory-bank/tests/m2-tests.md`、`memory-bank/implementation-plan.md`（M2）、`memory-bank/interfaces/frontend-backend-interfaces.md`（Rooms/WS）、`memory-bank/design/backend_design.md`（2.1~2.9）。

## 0) 测试环境与约定（真实服务）

- 建议环境：conda `XQB`。
- 服务启动（示例）：
  - `XQWEB_JWT_SECRET=<at-least-32-byte-secret>`
  - `XQWEB_SQLITE_PATH=/tmp/xqweb-m2-real-service.sqlite3`
  - `XQWEB_ROOM_COUNT=3`（并发/迁移用例至少需要 2 个房间）
  - `XQWEB_APP_PORT=18080`
  - `conda run -n XQB bash scripts/start-backend.sh`
- 基础地址：`BASE_URL=http://127.0.0.1:18080`
- WS 地址：
  - `ws://127.0.0.1:18080/ws/lobby?token=<access_token>`
  - `ws://127.0.0.1:18080/ws/rooms/{room_id}?token=<access_token>`
- 响应校验口径：
  - 成功响应结构与接口文档一致。
  - 失败响应统一为 `{code,message,detail}`。
  - Rooms REST 未授权状态码为 `401`。
  - WS 鉴权失败关闭码为 `4401`，reason=`UNAUTHORIZED`。
- 代理注意事项（与 M1 相同）：若存在 `HTTP_PROXY/HTTPS_PROXY`，本地联调需禁用代理（如 `curl --noproxy * ...`，脚本端 `trust_env=False`）。

## 1) REST 收口测试（Rooms）

| 测试ID | 场景 | 步骤（真实服务交互） | 预期结果 |
|---|---|---|---|
| M2-RS-REST-01 | 预设房间初始化正确 | 启动服务后，登录任意用户调用 `GET /api/rooms` | 返回房间数=`XQWEB_ROOM_COUNT`；`room_id` 连续为 `0..N-1`；初始 `status=waiting/player_count=0/ready_count=0` |
| M2-RS-REST-02 | `GET /api/rooms` 未授权拒绝 | 不带 token 调 `GET /api/rooms` | `401` |
| M2-RS-REST-03 | 房间详情成功 | 调 `GET /api/rooms/{room_id}`（合法 id） | `200`；返回 `room_detail` 结构完整 |
| M2-RS-REST-04 | 房间详情 404 | 调 `GET /api/rooms/9999` | `404 + ROOM_NOT_FOUND` |
| M2-RS-REST-05 | 首次 join 成功（owner/seat/chips） | 用户 A `POST /api/rooms/0/join` | `200`；A 成为 `owner_id`；A `seat=0`；A `chips=20` |
| M2-RS-REST-06 | 连续 join 座位分配 | 用户 B/C 依次 join 同房 | B/C 分别获得最小空闲 seat（通常 `1/2`） |
| M2-RS-REST-07 | 满员冲突 | 用户 D join 已满 3 人房间 | `409 + ROOM_FULL` |
| M2-RS-REST-08 | 同房重复 join 幂等 | A 对已加入房间再次调用 join | `200`；成员数不变、A seat 不变 |
| M2-RS-REST-09 | 跨房自动迁移成功 | A 先在房间 0，再 `join` 房间 1 | A 从房间 0 移除并加入房间 1；任一时刻仅在一个房间 |
| M2-RS-REST-10 | 跨房迁移失败回滚（原子性） | A 在房间 0；先填满房间 1；A 再 `join` 房间 1 | 返回 `409 + ROOM_FULL`；A 仍保留房间 0 成员身份与原 seat |
| M2-RS-REST-11 | leave 成功与 owner 转移 | owner 离开房间后查询详情 | `POST /leave` 返回 `{"ok":true}`；owner 转移为剩余最早加入者 |
| M2-RS-REST-12 | leave 非成员拒绝 | 非成员调用 `POST /leave` | `403 + ROOM_NOT_MEMBER` |
| M2-RS-REST-13 | ready 变更成功 | 成员在 waiting 房间调用 `POST /ready` true/false | `200`；`ready_count` 与成员 ready 状态一致 |
| M2-RS-REST-14 | ready 非成员拒绝 | 非成员调用 `POST /ready` | `403 + ROOM_NOT_MEMBER` |
| M2-RS-REST-15 | 三人全 ready 行为 | 三名成员均 `ready=true` | 请求全部成功；状态变更行为符合当前阶段约定（M2 占位 hook 或已接入开局逻辑）且不重复触发开局 |
| M2-RS-REST-16 | 冷结束规则（playing 中 leave） | 使房间进入 `playing` 后，任一成员调用 `POST /leave` | 房间回 `waiting`，`current_game_id=null`，剩余成员 `ready=false`，`chips` 保持不变 |
| M2-RS-REST-17 | ready 非 waiting 拒绝 | 使房间处于 `playing/settlement`，成员调用 `POST /ready` | `409 + ROOM_NOT_WAITING` |
| M2-RS-REST-18 | join/leave/ready 未授权拒绝 | 不带 token 分别调用 join/leave/ready | 均 `401` |

## 2) WebSocket 收口测试（Lobby + Room）

| 测试ID | 场景 | 步骤（真实服务交互） | 预期结果 |
|---|---|---|---|
| M2-RS-WS-01 | `/ws/lobby` 初始快照 | 有效 token 建连 lobby | 首包为 `ROOM_LIST`，内容与 `GET /api/rooms` 一致 |
| M2-RS-WS-02 | `/ws/rooms/{id}` 初始快照 | 有效 token 建连房间 WS | 首包为 `ROOM_UPDATE`，内容与 `GET /api/rooms/{id}` 一致 |
| M2-RS-WS-03 | lobby 无 token 拒绝 | 不带 token 建连 lobby | 关闭 `4401/UNAUTHORIZED` |
| M2-RS-WS-04 | room 无效 token 拒绝 | `token=invalid` 建连 room WS | 关闭 `4401/UNAUTHORIZED` |
| M2-RS-WS-05 | room 不存在拒绝 | 有效 token 建连 `/ws/rooms/9999` | 关闭 `4404/ROOM_NOT_FOUND` |
| M2-RS-WS-06 | join 触发双通道推送 | 建立 lobby+room 监听后执行 join | lobby 收到 `ROOM_LIST`；对应 room 收到 `ROOM_UPDATE` |
| M2-RS-WS-07 | ready 触发双通道推送 | 执行 ready 变更 | lobby 的 `ready_count` 更新；room 成员 ready 同步 |
| M2-RS-WS-08 | leave/owner 变更推送 | owner leave 后观察 WS | room `owner_id` 更新；lobby `player_count` 更新 |
| M2-RS-WS-09 | 跨房迁移双房间推送 | A 从房间 0 迁移到房间 1 | 房间 0 和房间 1 都收到 `ROOM_UPDATE`；lobby 收到 `ROOM_LIST` |
| M2-RS-WS-10 | 心跳 PING/PONG | 建连后等待服务端 PING 并回 PONG | 能持续保活；连接不异常断开 |

## 3) 并发收口测试（真实服务）

| 测试ID | 场景 | 步骤（真实服务交互） | 预期结果 |
|---|---|---|---|
| M2-RS-CC-01 | 并发 join 不超员 | 多用户并发 join 同一房间 | 最终成员数 `<=3`，seat 无重复 |
| M2-RS-CC-02 | 并发 ready 计数一致 | 多成员并发切换 ready | `ready_count` 与成员 ready 实际值一致 |
| M2-RS-CC-03 | 双向跨房迁移无死锁 | 两用户并发执行 A->B、B->A | 在超时前完成，无死锁，最终成员关系一致 |

## 4) 收口通过标准（M2 Exit Criteria）

- 上述 `M2-RS-REST-01~18`、`M2-RS-WS-01~10`、`M2-RS-CC-01~03` 全部通过。
- 房间核心契约完整通过：容量限制、seat 分配/回收、owner 规则、ready 规则、跨房迁移原子性、冷结束。
- WS 契约完整通过：初始快照、增量推送、鉴权拒绝、心跳。
- 并发一致性通过：不超员、无 seat 冲突、无迁移死锁。

## 5) 执行记录（TDD 红绿循环）

> 约定：每条用例先记录 Red 观察，再记录 Green 回归结果。

| 测试ID | 当前状态 | TDD阶段 | 执行日期 | 备注 |
|---|---|---|---|---|
| M2-RS-REST-01 | ⬜ 未执行 | 待执行 | - | - |
| M2-RS-REST-02 | ⬜ 未执行 | 待执行 | - | - |
| M2-RS-REST-03 | ⬜ 未执行 | 待执行 | - | - |
| M2-RS-REST-04 | ⬜ 未执行 | 待执行 | - | - |
| M2-RS-REST-05 | ⬜ 未执行 | 待执行 | - | - |
| M2-RS-REST-06 | ⬜ 未执行 | 待执行 | - | - |
| M2-RS-REST-07 | ⬜ 未执行 | 待执行 | - | - |
| M2-RS-REST-08 | ⬜ 未执行 | 待执行 | - | - |
| M2-RS-REST-09 | ⬜ 未执行 | 待执行 | - | - |
| M2-RS-REST-10 | ⬜ 未执行 | 待执行 | - | - |
| M2-RS-REST-11 | ⬜ 未执行 | 待执行 | - | - |
| M2-RS-REST-12 | ⬜ 未执行 | 待执行 | - | - |
| M2-RS-REST-13 | ⬜ 未执行 | 待执行 | - | - |
| M2-RS-REST-14 | ⬜ 未执行 | 待执行 | - | - |
| M2-RS-REST-15 | ⬜ 未执行 | 待执行 | - | - |
| M2-RS-REST-16 | ⬜ 未执行 | 待执行 | - | - |
| M2-RS-REST-17 | ⬜ 未执行 | 待执行 | - | - |
| M2-RS-REST-18 | ⬜ 未执行 | 待执行 | - | - |
| M2-RS-WS-01 | ⬜ 未执行 | 待执行 | - | - |
| M2-RS-WS-02 | ⬜ 未执行 | 待执行 | - | - |
| M2-RS-WS-03 | ⬜ 未执行 | 待执行 | - | - |
| M2-RS-WS-04 | ⬜ 未执行 | 待执行 | - | - |
| M2-RS-WS-05 | ⬜ 未执行 | 待执行 | - | - |
| M2-RS-WS-06 | ⬜ 未执行 | 待执行 | - | - |
| M2-RS-WS-07 | ⬜ 未执行 | 待执行 | - | - |
| M2-RS-WS-08 | ⬜ 未执行 | 待执行 | - | - |
| M2-RS-WS-09 | ⬜ 未执行 | 待执行 | - | - |
| M2-RS-WS-10 | ⬜ 未执行 | 待执行 | - | - |
| M2-RS-CC-01 | ⬜ 未执行 | 待执行 | - | - |
| M2-RS-CC-02 | ⬜ 未执行 | 待执行 | - | - |
| M2-RS-CC-03 | ⬜ 未执行 | 待执行 | - | - |
