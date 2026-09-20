# 版本更新说明（CHANGELOG）

> 本项目（QQ 群管机器人 · **SnowLuma + NoneBot** 版）的所有版本变更记录。新版本发布时在最上方追加。
> 格式参考：[Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)
> 当前版本：**v1.2.0**（见 `VERSION` 文件）

## 版本策略

- 本项目与原项目（`QQ群管机器人`，NapCat + NoneBot）**版本线相互独立**，各自演进、互不覆盖
- 每次发版 = 一个独立 commit，禁止 force push / 改写已推送历史，旧 tag 永不移动
- 发版三件套：本文件新增条目 + 更新 `VERSION` + 打 annotated tag 一并推送

---

## [1.2.0] - 2026-09-20

**全项目自检后的修复版：修掉 3 个会实际影响运行的缺陷，并把部署/维护文档对齐到真实状态。**

### 修正

- ⚠ **`bot_is_admin` 缓存被并发穿透**：NoneBot2 对同一个 matcher 的多个 rule checker 是
  `asyncio.gather` 并发求值的（`on_command` 的命令判断与自定义 rule 一起并发跑），叠加同优先级多个 matcher
  同时判定，一条群消息会让本函数被并发调用 15 次；缓存为空时全部穿透去打 API。
  **实测 SnowLuma 日志里单条消息打了 15 次 `get_group_member_info`。**
  改为 per-group `asyncio.Lock` + 双检，并发请求收敛为 1 次
- ⚠ **测试脚本会写穿线上配置**：`switch` 流程会写 `部署配置.json` 的 `snowluma_bot_qq`，
  而测试直接对着项目里的真实配置跑 → 跑一次测试就把正在部署的账号改成测试占位号。
  新增环境变量 `SNOWLUMA_CONFIG_PATH`，测试改写临时副本，并加断言锁死"真实配置不得被改动"
- ⚠ **`一键部署` 遇到绑死旧机器的 venv 会卡死**：项目自带的 `venv\` 里 `pyvenv.cfg` 绑着创建时的
  解释器路径，把项目拷到别的机器后 `venv\Scripts\python.exe` 根本起不来；原逻辑只判断"venv 存在"，
  于是跳过重建、直接 `pip install`（连解释器都跑不了），失败信息完全对不上病因。
  改为：探测到"venv 在但解释器跑不通"→ 自动改名 `venv.machine-bound\` 备份后重建
- `snowluma_account.py`：`unload` 增加**结果复核**。实测 SnowLuma 会"接口返回成功但 hook 没摘掉"
  （日志 `[Hook] unload verification failed: PID=xxx pipe still up`），旧账号仍占着 3100/3001；
  现在复核发现仍在加载会明确报出并返回失败码，不再误报"卸载成功"
- `snowluma_deploy.py`：写 OneBot 配置时，`wsClients` 清理范围从"只清 6199"扩大到
  **所有指向本机其它端口的旧客户端**（含老项目 NoneBot 的 8080）——残留会导致同一条消息被两个业务框架处理两遍
- `snowluma_deploy.py`：模块 docstring 里业务框架端口 8080 → 8081（与实际不符）
- `snowluma_ctl.py`：端口配置统一强转 `int`（`部署配置.json` 里写成字符串时不再抛 `TypeError`，改为回退默认值并告警）

### 文档

- `README.md`：删除过时的"本项目登小号、老项目登主号"；新增「账号怎么安排」一节，
  **要求动手前先核对两个项目 `部署配置.json` 里的 `bot_qq` / `snowluma_bot_qq` 是不是同一个号**
  （自检时实测两处确实同号，只是老项目 NapCat 当前登录失效才没冲突；它一旦重新登录成功就会与本项目互踢）；
  目录表补 `deploy\snowluma_account.py`、`logs\bot.log`，移除已删除的 `AstrBot\`
- `docs\部署说明.md`：第 3 节"登录小号"→"登录账号"；排障表新增 3 条
  （风控无关的重复 API 调用 / unload 未真正生效 / 换机器后 venv 坏掉）；
  **新增第 8 节「维护要点」**：业务插件改完必须重启才生效、自测命令、必须在 `qq-group-bot\` 目录下跑业务
  （否则 `.env` 读不到会落到 8080 与老项目撞车）、别把比对齐版本新的 QQ 安装包放在项目里、日志体积、发版三件套、敏感信息边界
- `docs\功能说明.md`：账号段改为"以各自 `部署配置.json` 为准"；切换主用流程补第 5 步收尾提醒（错开账号 / 停用一边）
- `部署配置.example.json` / `部署配置.json`：`snowluma_bot_qq_说明` 改为账号无关的表述

### 测试

- 新增 `.workbuddy/test_admin_cache.py`：5 组断言锁住并发去重行为
  （首次并发 15 次→1 次、缓存内→0 次、过期后→1 次、不同群各自查询、API 异常时降级且不重复打）
- `.workbuddy/test_account_switch.py` 扩展到 7 组：新增"接口成功但 hook 未摘掉必须报错"、
  "真实配置不得被测试污染"；夹具账号改为占位符（1000000001 / 2000000002）

### 内部

- `.workbuddy/gen_bats.py`：`BASE` 此前仍指向已改名的 `QQ机器人-SnowLuma-AstrBot`，且模板里还写着
  不存在的 `docs\部署说明-SnowLuma版.md`（重跑会写错目录、生成错引用），已修正并加"定位不到项目目录就报错"；
  重新生成的 4 个 bat 与仓库现有 4 个**逐字节一致**（确认生成器与产物已同步）

---

## [1.1.0] - 2026-09-20

**新增「账号切换」脚本：把 5099 网页上的「卸载 / 加载账号」变成一条命令。**

### 新增

- `切换账号.bat` —— 切换登录账号的入口（支持 `切换账号.bat list` 只看状态）
- `deploy/snowluma_account.py` —— 走 SnowLuma WebUI HTTP API 的账号管理脚本：
  - `list` / `list --raw`：列出 QQ 进程、账号、hook 加载状态（`--raw` 带服务端原始 JSON）
  - `switch <QQ>`：卸载其它账号的 hook → 校正目标账号协议端配置 → 重载目标账号 → 复核
  - `unload <QQ|PID>`：只卸载某个账号
  - `sync-config <QQ>`：只校正协议端配置（HTTP 3100 / WS 3001 / wsClient → 8081）
  - 密码来源：环境变量 `SNOWLUMA_WEBUI_PASSWORD` 或交互输入，**不落盘**

### 修正

- ⚠ **纠正切号方式**：之前"直接复制 `config/onebot_<新号>.json`"的做法会造成脏状态——SnowLuma 会同时为
  两个账号建立 session，抢 HTTP 3100 / WS 3001 端口，日志刷 `EADDRINUSE`。正确做法是「先卸载旧账号 hook、
  再加载目标账号」，即本版脚本所做
- 修正 3 处文档引用错误：`启动-SnowLuma版.bat`、`自检-SnowLuma版.bat`、`deploy/snowluma_ctl.py` 指向了
  不存在的 `docs\部署说明-SnowLuma版.md`，统一为 `docs\部署说明.md`

### 文档

- `docs/部署说明.md` 新增第 6 节「切换登录账号（脚本化）」：能/不能脚本化的边界、用法、正确顺序、反面教材；
  排障表新增"端口 EADDRINUSE"一条
- `README.md` 脚本表补充 `切换账号.bat`
- `docs/功能说明.md` 换号说明改为脚本口径

### 说明

- **不能脚本化的部分**：QQ 客户端退出旧号 / 登录新号需要账号密码与手机验证，QQ 客户端不提供稳定可用的
  命令行换号接口，必须人工。脚本要求目标账号已在桌面版 QQ 登录，未登录时只提示、不做任何破坏性操作

---

## [1.0.0] - 2026-09-20

**首个版本：SnowLuma 协议端 + NoneBot 业务框架，本机联调打通。**

### 新增

- **协议端 SnowLuma（hook 桌面版 QQ）**
  - 通过注入真实桌面版 QQ 客户端实现协议通信，规避 NapCat 类非官方协议端的风控特征
  - 输出标准 OneBot v11（WS 服务端 3001 / HTTP 3100），与 NapCat 口径一致
  - 对齐 QQ 版本 **9.9.28-46928**，版本不匹配时 hook 无法注入（自检脚本会校验）
- **业务框架 NoneBot（自带独立副本，端口 8081）**
  - `qq-group-bot\` 完整业务代码：11 个群管插件（admin / approval / blacklist / common / guard / help / inactive / settings / silence / status / welcome）
  - 自带 `venv`，依赖 nonebot2 + adapter-onebot 已装好
- **自动化脚本套件**
  - `一键部署-SnowLuma版.bat`：备 Python 环境 + 装依赖 → 解压协议端 → 写 OneBot 配置 → 体检
  - `启动-SnowLuma版.bat`：拉起协议端（独立窗口）+ 业务框架（8081，日志落 `logs\bot.log`）
  - `自检-SnowLuma版.bat`：目录 / QQ 版本匹配 / 端口占用 / hook 注入 / WS 连接 / 账号接入 全链路体检
  - `关闭-SnowLuma版.bat`：按端口属主 PID + 程序路径精确停止本项目，不影响另一个项目
  - 配套 `deploy\snowluma_deploy.py`（部署）、`deploy\snowluma_ctl.py`（自检/停止）
- **文档**
  - `README.md`：架构、目录、脚本、端口表、与老项目的边界红线
  - `docs\部署说明.md`：从零到跑通 + 常见故障排障对照表
  - `docs\功能说明.md`：11 个插件功能清单、完整命令表、配置项说明
  - `docs\框架调研与迁移决策.md`：换协议端的调研依据与决策落地记录
- **项目边界**
  - 与原项目（`D:\Desktop\QQ群管机器人`，NapCat 版）完全分离：独立目录、独立进程、独立端口（8080 vs 8081）
  - 红线：**同一个 QQ 号绝不能同时登录两个协议端**（会被互踢）

### 说明

- 本版本为**独立项目起始版本**，群管功能与老项目一致，差异仅在协议端
- `部署配置.json`（真实 QQ 号等）与 `qq-group-bot\.env`、`qq-group-bot\config.json` 为个人配置，**不入库**，仓库只提供 `*.example.json` 模板
