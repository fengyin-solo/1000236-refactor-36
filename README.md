# 影视剧组拍摄制作管理平台

面向剧本分场、选角档期、拍摄通告、场地器材、后期特效与杀青结算的一体化剧组管理后台。

这是一个前后端分离的管理平台：前端 Vue 3 + Vite + TypeScript，后端 FastAPI（Python）。
两边各自独立启动，前端 dev server 已关掉自动打开页面，启动后按终端打印的地址手工打开。

## 目录结构

```text
.
├── frontend/                 Vue 3 + Vite + TypeScript 前端
│   ├── src/views/            每个业务模块一个页面
│   ├── src/api/              统一请求封装
│   ├── src/stores/           会话与筛选状态
│   └── vite.config.ts        dev server 配置（open: false）
├── backend/                  FastAPI（Python） 后端
│   ├── app/routers/          每个业务模块一组接口
│   ├── app/services/         业务规则与状态流转
│   └── app/store.py          内存数据仓库与示例数据
├── .gitignore
└── docker-compose.yml
```

## 启动

### 后端

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
./run.sh
```

健康检查：`curl http://127.0.0.1:8000/api/health`

### 启动链路（环境校验 → 数据准备 → 启动检查）

`./run.sh` 在启动 uvicorn 前会先执行 `python -m app.bootstrap`（也可用 `make check`
单独运行），按顺序完成三步，任一步失败都会打印具体原因并以非 0 退出，服务不会带病启动：

1. **环境校验**：`APP_ENV`、`APP_PORT`、`APP_ALLOWED_ORIGINS`、分页配置等是否合法，
   一次列出全部问题；可用变量见根目录 `.env.example`。
2. **数据准备**：幂等灌入 `app/seed.py` 示例数据，只补缺失 id，**不覆盖**已有单据和
   列表结果；灌入前先校验种子库存口径（道具的 `status` / 「使用状态」 / pending / abnormal）。
3. **启动检查**：关键路由是否注册、道具借出/归还/损毁流转口径是否自洽、库存数据是否合法。

整条链路只读 + 幂等补数，修复后可安全反复重跑。

### 前端

```bash
cd frontend
npm install
npm run dev
```

前端默认监听 `http://127.0.0.1:5173/`，dev server 不会自动打开浏览器，
需要自己访问。`/api` 由 vite 代理到后端 `http://127.0.0.1:8000`。

## 业务模块

| 模块 | 目录 | 业务对象 | 主要字段 |
| --- | --- | --- | --- |
| 剧本管理 | `script` | 剧本 | 剧本编号、剧本名称、题材类型 |
| 分场大纲 | `scene` | 分场表 | 场次编号、所属剧本、场景地点 |
| 角色选角 | `casting` | 角色 | 角色编号、角色名称、角色类型 |
| 剧组人员 | `crew` | 剧组成员 | 成员编号、姓名、岗位职务 |
| 拍摄通告 | `notice` | 拍摄通告单 | 通告编号、拍摄日期、集合时间 |
| 场地租用 | `location` | 拍摄场地 | 场地编号、场地名称、场地类型 |
| 道具管理 | `prop` | 道具 | 道具编号、道具名称、道具类别 |
| 服装造型 | `costume` | 戏服 | 服装编号、服装名称、角色归属 |
| 化妆造型 | `makeup` | 妆造方案 | 方案编号、角色名称、造型风格 |
| 器材管理 | `equipment` | 拍摄器材 | 器材编号、器材名称、器材类别 |
| 拍摄进度 | `shooting` | 拍摄日 | 拍摄日编号、拍摄日期、拍摄地点 |
| 素材管理 | `footage` | 拍摄素材 | 素材编号、素材类型、拍摄日期 |
| 后期剪辑 | `edit` | 剪辑任务 | 任务编号、所属集数、剪辑师 |
| 特效制作 | `vfx` | 特效镜头 | 镜头编号、所属集数、特效类型 |
| 审片意见 | `review` | 审片记录 | 审片编号、审片轮次、审片人 |
| 预算科目 | `budget` | 预算科目 | 科目编号、科目名称、费用类别 |
| 费用报销 | `expense` | 报销单 | 报销单号、报销人、费用类别 |
| 档期协调 | `schedule` | 演员档期 | 档期编号、演员姓名、经纪公司 |
| 外景许可 | `permit` | 拍摄许可 | 许可编号、许可类型、申请地点 |
| 杀青结算 | `wrap` | 结算单 | 结算单号、结算对象、结算周期 |

## 约定

- 每个模块的前端页面在 `frontend/src/views/<模块>/index.vue`，后端接口在
  `backend/app/routers/<模块>.py`，业务规则在 `backend/app/services/<模块>.py`。
- 列表接口统一返回 `{ items, total, page, size }`，动作接口统一返回 `{ ok, message }`。
- 状态流转只允许在 `app/services` 里改，路由层不做业务判断。
- 道具库存口径只有一个出处 `app/services/prop.py`：在库 → 已借出 → 已归还 → 已损毁。
  在库可借出、已借出可归还/损毁、已归还/已损毁为终态；「使用状态」是 `status` 的读时
  镜像，按钮以后端下发的 `actions` 为准，统计卡取自 `/api/prop/stats`，前端不再各写一份。
