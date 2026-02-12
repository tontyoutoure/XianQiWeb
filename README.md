# XianQiWeb

网页端牌类游戏大厅（Vue 3 + TypeScript / FastAPI + SQLite）。本仓库包含前端 `FrontEnd` 与后端 `BackEnd`，默认在本地联调运行。

## 目录结构

- `FrontEnd/`：Vue 3 + Vite 前端
- `BackEnd/`：FastAPI 后端（WebSocket + HTTP API）

## 运行环境

- Node.js + npm
- Python 3.x

## 启动后端（BackEnd）

> 默认端口 `8000`，WebSocket 地址 `/ws/{player_name}`。

```bash
cd BackEnd
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

也可以直接运行：

```bash
python main.py
```

## 启动前端（FrontEnd）

> 默认端口 `5173`（Vite）。默认后端地址为 `http://localhost:8000`。

```bash
cd FrontEnd
npm install
npm run dev
```

### 配置后端地址（可选）

前端会读取 `VITE_API_URL`，可在 `FrontEnd/.env.local` 中配置：

```bash
VITE_API_URL=http://localhost:8000
```

如果不配置，代码会默认使用 `http://localhost:8000`。

## 生产构建（前端）

```bash
cd FrontEnd
npm run build
npm run preview
```

## 常见联调方式

1. 先启动后端（`8000`）
2. 再启动前端（`5173`）
3. 浏览器访问 `http://localhost:5173`

## 备注

- 后端已开启 CORS（允许所有来源），前后端可直接联调。
- WebSocket 会使用与 `VITE_API_URL` 相同的主机名进行连接。
