# 版本更新说明（CHANGELOG）

> 本项目（QQ 群管机器人 · **SnowLuma + NoneBot** 版）的所有版本变更记录。新版本发布时在最上方追加。
> 格式参考：[Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)
> 当前版本：**v1.1.0**（见 `VERSION` 文件）

## 版本策略

- 本项目与原项目（`QQ群管机器人`，NapCat + NoneBot）**版本线相互独立**，各自演进、互不覆盖
- 每次发版 = 一个独立 commit，禁止 force push / 改写已推送历史，旧 tag 永不移动
- 发版三件套：本文件新增条目 + 更新 `VERSION` + 打 annotated tag 一并推送

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
