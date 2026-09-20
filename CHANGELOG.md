# 版本更新说明（CHANGELOG）

> 本项目（QQ 群管机器人 · **SnowLuma + NoneBot** 版）的所有版本变更记录。新版本发布时在最上方追加。
> 格式参考：[Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)
> 当前版本：**v1.0.0**（见 `VERSION` 文件）

## 版本策略

- 本项目与原项目（`QQ群管机器人`，NapCat + NoneBot）**版本线相互独立**，各自演进、互不覆盖
- 每次发版 = 一个独立 commit，禁止 force push / 改写已推送历史，旧 tag 永不移动
- 发版三件套：本文件新增条目 + 更新 `VERSION` + 打 annotated tag 一并推送

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
