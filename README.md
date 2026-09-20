# QQ 群管机器人（SnowLuma + NoneBot 版）

> 独立项目，与「QQ群管机器人」（NapCat + NoneBot 老项目）**完全分离、互不干涉**。
> 两个项目有各自的协议端、业务进程、端口与配置；**同一个 QQ 号绝不能同时接两个协议端**（会互踢）。

## 为什么这样选

老项目用 NapCat（非官方协议实现），长期被风控踢下线（KickedOffLine 约 1.5 小时一次），"假在线僵死"频发。调研结论见 `docs\框架调研与迁移决策.md`：

- SnowLuma 通过 **hook 注入真实桌面版 QQ 客户端**，协议表现更接近真人客户端，社区有"换后不再被踢"的实证
- SnowLuma 输出标准 **OneBot v11**，与 NapCat 口径一致 → **群管业务不用重写**，老项目的 NoneBot 业务框架原样复用

```
SnowLuma（hook 桌面 QQ，协议端）
   └─ WS 客户端 ──> ws://127.0.0.1:8081/onebot/v11/ws ──> NoneBot 业务框架（群管功能）
```

## 目录结构

| 路径 | 说明 |
|---|---|
| `SnowLuma\` | 协议端本体（自带 Node.js，`launcher.bat` 启动，WebUI 5099） |
| `qq-group-bot\` | 业务框架（NoneBot）与全部群管插件，自老项目复制 |
| `venv\` | 本项目独立的 Python 虚拟环境（已装 nonebot 依赖） |
| `deploy\snowluma_deploy.py` | 部署脚本：准备 Python 环境、解压 SnowLuma、写 OneBot 配置、体检 |
| `deploy\snowluma_ctl.py` | 运维脚本：`check` 全网自检 / `stop` 精确停进程 |
| `deploy\snowluma_account.py` | 账号脚本：`list` / `switch` / `unload` / `sync-config`（走 SnowLuma WebUI API） |
| `部署配置.json` | 本项目参数（端口、账号、路径），可改；`.example.json` 为模板 |
| `docs\部署说明.md` | 从零部署到跑通的完整步骤 + 排障表 + 维护要点 |
| `docs\功能说明.md` | 群管功能清单、命令表、配置项说明 |
| `docs\框架调研与迁移决策.md` | 换框架的调研与决策记录 |
| `logs\bot.log` | 业务框架运行日志（启动脚本追加写入） |

## 快速开始（四个脚本）

| 脚本 | 用途 |
|---|---|
| `一键部署-SnowLuma版.bat` | 准备 Python 环境与依赖 → 解压 SnowLuma → 写 OneBot 配置 → 体检 |
| `启动-SnowLuma版.bat` | 启动协议端（新窗口）+ 业务框架（本窗口） |
| `自检-SnowLuma版.bat` | 全链路体检：目录、QQ 版本匹配、端口、hook 注入、WS 连接、账号接入 |
| `切换账号.bat` | 切换登录账号：走 SnowLuma API 卸载旧账号 hook、重载目标账号（QQ 换号仍需人工） |
| `关闭-SnowLuma版.bat` | 只停本套（SnowLuma + 业务框架），不动老项目 |

首次使用顺序：**桌面版 QQ 保持登录 → 一键部署 → 启动 → 在 SnowLuma 面板扫码登录目标账号 → 自检**

## 账号怎么安排（重要）

本项目与老项目的**账号必须错开**，同一个 QQ 号不能同时挂两个协议端（会互踢）。
账号是私有信息，**不写进仓库**，一律看各自的 `部署配置.json` 里的 `bot_qq` / `snowluma_bot_qq`：

| | 在哪儿看 | 怎么改 |
|---|---|---|
| 本项目 | 本项目 `部署配置.json` → `snowluma_bot_qq` | 双击 `切换账号.bat` |
| 老项目 | 老项目 `部署配置.json` → `bot_qq` | 改它的配置后重启老项目 |

⚠ **动手前先核对这两处是不是同一个号**。是同一个号的话，两个项目不能同时登录：老项目 NapCat 一旦登录成功，
就会把本项目踢下线（反之亦然）。处置方式二选一：把其中一个换成另一个号，或明确停用一边。

## 端口分配

| 端口 | 归属 |
|---|---|
| 5099 | SnowLuma 管理面板（WebUI） |
| 3100 | SnowLuma OneBot HTTP（避开老项目的 3000） |
| 3001 | SnowLuma OneBot WS 服务端 |
| 8081 | 本项目业务框架 NoneBot（老项目用 8080，互不冲突） |
| —— 老项目（互不干涉）—— | —— |
| 3000 / 6099 / 8080 | 老项目 NapCat HTTP / WS / NoneBot |

## 与老项目的红线

1. **同一 QQ 号不能同时接两个协议端**（会互踢）——见上一节「账号怎么安排」
2. 端口互不重叠，两个项目可同时运行、同时测试
3. 老项目保持可运行状态，随时能回滚（双击它的 `启动机器人.bat`）
4. 两个 QQ 号**共在**的群里，两边都会响应命令（各回一次）；想干净测试请用不共群的场景

## 注意事项

- SnowLuma 的 native hook **按 QQ 版本对齐**：QQ 自动升级可能导致 hook 失效，建议关闭 QQ 自动更新；当前是否匹配用 `自检-SnowLuma版.bat` 一键确认
- SnowLuma 必须与桌面版 QQ 用**同一个 Windows 用户、同样权限**运行，否则注入会失败
- SnowLuma 核心组件为 source-available 非商业许可，仅供学习研究，商用需授权
