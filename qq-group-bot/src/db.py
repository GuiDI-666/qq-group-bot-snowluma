"""MySQL 访问层：游戏账号库（user）读写 + 角色库（player）只读。

设计要点：
- 短连接：每次操作即连即断（命令频率低，不为它维护常驻连接；
  也避开 MySQL wait_timeout 断连后连接池半死的问题）。
- 不阻塞事件循环：所有同步 DB 调用经 asyncio.to_thread 包装。
- 全部 SQL 走参数化（%s 占位），杜绝注入。
- 权限边界：user 库可写（注册/改密码），player 库只读（绑定QQ 除外——
  baseinfo.QQ 字段是绑定关系的落点，经用户确认放开写这一列）。
"""
from __future__ import annotations

import asyncio
import json
import secrets
import string
from pathlib import Path

import pymysql
import pymysql.cursors

CONFIG_PATH = Path(__file__).resolve().parents[1] / "mysql.json"

# 随机密码字符表：剔除 0/O/1/l/I 等易混淆字符
_PWD_ALPHABET = string.ascii_letters + string.digits
for _ch in "0O1lI":
    _PWD_ALPHABET = _PWD_ALPHABET.replace(_ch, "")


class DbError(Exception):
    """数据库操作失败（连接失败/约束冲突等），message 可直接回复给用户。"""


def load_config() -> dict:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except FileNotFoundError:
        raise DbError("数据库配置缺失（qq-group-bot/mysql.json），请联系管理员")
    except Exception as exc:
        raise DbError(f"数据库配置无效：{exc}")


def gen_password(length: int = 10) -> str:
    """生成随机初始密码：字母+数字，剔除易混淆字符。"""
    return "".join(secrets.choice(_PWD_ALPHABET) for _ in range(length))


def _connect(cfg: dict, db: str):
    try:
        return pymysql.connect(
            host=cfg.get("host", "127.0.0.1"),
            port=int(cfg.get("port", 3306)),
            user=cfg.get("user", "root"),
            password=cfg.get("password", ""),
            database=db,
            charset="utf8mb4",
            connect_timeout=5,
            read_timeout=10,
            write_timeout=10,
            autocommit=False,
            cursorclass=pymysql.cursors.DictCursor,
        )
    except Exception as exc:
        raise DbError(f"数据库连接失败，请联系管理员（{type(exc).__name__}）") from exc


def _run_sync(fn):
    """在线程池里跑同步 DB 函数，不阻塞 NoneBot 事件循环。"""
    return asyncio.to_thread(fn)


# ---------------- user 库（账号，读写） ----------------

# 角色 Uin 与账号 Uin 的固定偏移：baseinfo.Uin = user.Uin + 10000（已实测确认）
ROLE_UIN_OFFSET = 10000


def _sync_register(cfg: dict, qq: str, password: str) -> None:
    # 一人一号：user.Name=qq 已存在，或 player.baseinfo 已有角色绑了该 QQ，都拒绝
    conn = _connect(cfg, cfg.get("db_player", "player"))
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT Uin, NickName FROM `baseinfo` WHERE `QQ`=%s", (str(qq),))
            role = cur.fetchone()
    finally:
        conn.close()
    if role:
        raise DbError(
            f"你的 QQ 已绑定角色「{role['NickName']}」（一人一号），请直接用 /查看密码 查询密码"
        )

    conn = _connect(cfg, cfg.get("db_user", "user"))
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT Uin FROM `user` WHERE `Name`=%s", (qq,))
            if cur.fetchone():
                raise DbError("该 QQ 已注册过游戏账号，请直接用 /查看密码 查询")
            cur.execute(
                "INSERT INTO `user` (`Name`, `Password`, `Registration_time`) "
                "VALUES (%s, %s, %s)",
                (qq, password, __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            )
        conn.commit()
    except DbError:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise DbError(f"注册写入失败，请联系管理员（{type(exc).__name__}）") from exc
    finally:
        conn.close()


def _sync_find_account_by_qq(cfg: dict, qq: str) -> dict | None:
    """按 QQ 找账号，两条路径（**baseinfo 绑定关系优先**）：
    1) 绑定的号：baseinfo.QQ == QQ → 角色 Uin → user.user.Uin（昵称可得，权威路径）
    2) 机器人注册的新号：user.user.Name == QQ（角色可能尚未创建，兜底路径）
    返回 {"uin", "nickname", "name", "password"}；两条路径都未命中返回 None。
    """
    # 路径 1：baseinfo.QQ 反查
    conn = _connect(cfg, cfg.get("db_player", "player"))
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT Uin, NickName FROM `baseinfo` WHERE `QQ`=%s",
                (str(qq),),
            )
            roles = cur.fetchall()
    finally:
        conn.close()
    if len(roles) > 1:
        raise DbError("该 QQ 绑定了多个角色（数据异常），请联系管理员处理")
    if roles:
        role = roles[0]
        account_uin = role["Uin"] - ROLE_UIN_OFFSET
        conn = _connect(cfg, cfg.get("db_user", "user"))
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT `Uin`, `Name`, `Password` FROM `user` WHERE `Uin`=%s",
                    (account_uin,),
                )
                acc = cur.fetchone()
        finally:
            conn.close()
        if not acc:
            raise DbError("角色已绑定但找不到对应账号（数据异常），请联系管理员")
        return {
            "uin": acc["Uin"],  # 账号 Uin（baseinfo.Uin - 10000）
            "nickname": role["NickName"],
            "name": acc["Name"],
            "password": acc["Password"] or "",
        }

    # 路径 2：Name 直查（新注册、角色未建）
    conn = _connect(cfg, cfg.get("db_user", "user"))
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT `Uin`, `Name`, `Password` FROM `user` WHERE `Name`=%s",
                (str(qq),),
            )
            acc = cur.fetchone()
    finally:
        conn.close()
    if acc:
        return {
            "uin": acc["Uin"],
            "nickname": None,  # 角色可能还没建
            "name": acc["Name"],
            "password": acc["Password"] or "",
        }
    return None


def _sync_change_password(cfg: dict, uin: int, new_password: str) -> None:
    conn = _connect(cfg, cfg.get("db_user", "user"))
    try:
        with conn.cursor() as cur:
            n = cur.execute(
                "UPDATE `user` SET `Password`=%s WHERE `Uin`=%s",
                (new_password, uin),
            )
            if n == 0:
                raise DbError("账号不存在，无法修改")
        conn.commit()
    except DbError:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise DbError(f"密码写入失败，请联系管理员（{type(exc).__name__}）") from exc
    finally:
        conn.close()


# ---------------- player 库（角色，绑定关系写 baseinfo.QQ 一列） ----------------

def _sync_bind_qq(cfg: dict, qq: str, nickname: str) -> str:
    """把 QQ 绑定到指定角色名，返回角色昵称。一条 QQ 只能绑一个角色。"""
    conn = _connect(cfg, cfg.get("db_player", "player"))
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT `Uin`, `NickName`, `QQ` FROM `baseinfo` WHERE `NickName`=%s",
                (nickname,),
            )
            roles = cur.fetchall()
            if not roles:
                raise DbError(f"角色「{nickname}」不存在，请核对角色名（区分大小写）")
            if len(roles) > 1:
                raise DbError(f"存在 {len(roles)} 个同名角色，请联系管理员处理")
            role = roles[0]
            bound = (role.get("QQ") or "").strip()
            if bound and bound != str(qq):
                raise DbError("该角色已绑定其他 QQ，如需改绑请联系管理员解绑")
            # 一条 QQ 只能绑一个角色：检查是否已绑到别的角色
            cur.execute(
                "SELECT `NickName` FROM `baseinfo` WHERE `QQ`=%s AND `Uin`<>%s",
                (str(qq), role["Uin"]),
            )
            other = cur.fetchone()
            if other:
                raise DbError(f"你的 QQ 已绑定角色「{other['NickName']}」，不能重复绑定")
            cur.execute(
                "UPDATE `baseinfo` SET `QQ`=%s WHERE `Uin`=%s",
                (str(qq), role["Uin"]),
            )
        conn.commit()
        return role["NickName"]
    except DbError:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise DbError(f"绑定写入失败，请联系管理员（{type(exc).__name__}）") from exc
    finally:
        conn.close()


def _sync_unbind(cfg: dict, nickname: str) -> int:
    """管理员解绑：按角色名清空 QQ。返回解绑的角色数。"""
    conn = _connect(cfg, cfg.get("db_player", "player"))
    try:
        with conn.cursor() as cur:
            n = cur.execute(
                "UPDATE `baseinfo` SET `QQ`=NULL WHERE `NickName`=%s AND `QQ` IS NOT NULL AND `QQ`<>''",
                (nickname,),
            )
        conn.commit()
        return n
    except Exception as exc:
        conn.rollback()
        raise DbError(f"解绑失败，请联系管理员（{type(exc).__name__}）") from exc
    finally:
        conn.close()


# ---------------- 异步门面（供插件调用） ----------------

async def register(qq: str) -> str:
    """注册：账号=QQ号，随机初始密码。返回明文密码。"""
    cfg = load_config()
    password = gen_password()
    await _run_sync(lambda: _sync_register(cfg, str(qq), password))
    return password


async def get_account(qq: str) -> dict | None:
    """按 QQ 查账号（经 baseinfo.QQ 核对）。未绑定返回 None。"""
    cfg = load_config()
    return await _run_sync(lambda: _sync_find_account_by_qq(cfg, str(qq)))


async def change_password(qq: str, new_password: str) -> dict:
    """改密码：核对 baseinfo.QQ 后更新 user.user.Password。返回账号信息。"""
    cfg = load_config()
    acc = await _run_sync(lambda: _sync_find_account_by_qq(cfg, str(qq)))
    if not acc:
        raise DbError("你的 QQ 还没有绑定游戏角色，请先私聊我发送 /绑定QQ 角色名")
    await _run_sync(lambda: _sync_change_password(cfg, acc["uin"], new_password))
    return acc


async def bind_qq(qq: str, nickname: str) -> str:
    cfg = load_config()
    return await _run_sync(lambda: _sync_bind_qq(cfg, str(qq), nickname.strip()))


async def unbind(nickname: str) -> int:
    cfg = load_config()
    return await _run_sync(lambda: _sync_unbind(cfg, nickname.strip()))
