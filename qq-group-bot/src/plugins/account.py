"""游戏账号服务：注册 / 绑定QQ / 查看密码 / 修改密码（MySQL 直连游戏库）。

安全模型（重要）：
- 涉及密码的命令（注册/查看密码/修改密码/绑定QQ）**只在实际私聊会话里执行**，
  回复就在同一会话——机器人绝不主动外发私聊（实测非好友主动私聊不可达）。
  群聊里发这些命令只回复一句指引，提示玩家私聊机器人办理。
- 身份核对原理：QQ 号由协议层保证不可伪造。查/改密码时直接拿发送者 QQ
  匹配 user 库账号名或 baseinfo.QQ，匹配不上即拒绝——知道角色名也冒充不了。
- 一人一号：user.Name=QQ 或 baseinfo.QQ=QQ 任一存在即拒绝再次注册/绑定。

管理命令（仅超级管理员）：
  /添加账号群 群号 / /移除账号群 群号 / /账号群列表 —— 控制群聊指引的生效范围
  /解绑 角色名 —— 清空角色的 QQ 绑定（纠错用）
"""
import json
from pathlib import Path

from nonebot import on_command
from nonebot.adapters.onebot.v11 import Message, MessageEvent, GroupMessageEvent
from nonebot.params import CommandArg

from .. import db
from ..db import DbError

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.json"

GUIDE = (
    "⚠ 账号命令涉及密码，请私聊机器人办理：\n"
    "先加机器人为好友，然后私聊发送：\n"
    "/注册 —— 注册游戏账号（账号=你的QQ号，随机初始密码）\n"
    "/绑定QQ 角色名 —— 把你的QQ绑定到游戏角色\n"
    "/查看密码 —— 查看账号密码\n"
    "/修改密码 新密码 —— 修改密码"
)


def _load() -> dict:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(cfg: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def _plain(args: Message) -> str:
    return args.extract_plain_text().strip()


def _account_group_ok(group_id: int) -> bool:
    """账号功能的群聊指引生效范围（语义与 managed_groups 一致：空 = 所有群）。"""
    groups = _load().get("account_groups", [])
    return True if not groups else group_id in groups


async def _finish_or_guide(matcher, event: MessageEvent, private_coro_fn):
    """群聊 → 回指引；私聊 → 执行。"""
    if isinstance(event, GroupMessageEvent):
        if _account_group_ok(event.group_id):
            await matcher.finish(GUIDE)
        return  # 非生效群：静默
    await private_coro_fn()


# ---------------- 注册 ----------------
register_cmd = on_command("注册", aliases={"注册账号", "注册游戏账号"}, priority=5, block=True)


@register_cmd.handle()
async def handle_register(event: MessageEvent):
    async def _do():
        qq = str(event.user_id)
        try:
            password = await db.register(qq)
            await register_cmd.finish(
                f"✅ 注册成功！\n游戏账号：{qq}\n初始密码：{password}\n"
                f"\n请妥善保管，可随时发 /查看密码 查看。"
                f"\n提示：进游戏后可发 /绑定QQ 角色名 把 QQ 绑到角色。"
            )
        except DbError as e:
            await register_cmd.finish(f"❌ {e}")

    await _finish_or_guide(register_cmd, event, _do)


# ---------------- 绑定QQ ----------------
bind_cmd = on_command("绑定QQ", aliases={"绑定qq", "绑定角色"}, priority=5, block=True)


@bind_cmd.handle()
async def handle_bind(event: MessageEvent, args: Message = CommandArg()):
    async def _do():
        nickname = _plain(args)
        if not nickname:
            await bind_cmd.finish(
                "私聊用法：/绑定QQ 角色名\n例：/绑定QQ 飞车小白\n"
                "（角色名以游戏内显示的昵称为准）"
            )
        try:
            name = await db.bind_qq(str(event.user_id), nickname)
            await bind_cmd.finish(f"✅ 绑定成功！你的 QQ 已绑定角色「{name}」\n现在可以 /查看密码 / /修改密码 了")
        except DbError as e:
            await bind_cmd.finish(f"❌ {e}")

    await _finish_or_guide(bind_cmd, event, _do)


# ---------------- 查看密码 ----------------
show_pwd = on_command("查看密码", aliases={"我的密码", "查询密码"}, priority=5, block=True)


@show_pwd.handle()
async def handle_show_pwd(event: MessageEvent):
    async def _do():
        try:
            acc = await db.get_account(str(event.user_id))
        except DbError as e:
            await show_pwd.finish(f"❌ {e}")
            return
        if not acc:
            await show_pwd.finish(
                "未找到你的账号：\n"
                "- 机器人注册的号：直接发 /注册 即可\n"
                "- 老玩家：请先发 /绑定QQ 角色名 绑定后再查"
            )
            return
        nick = f"\n游戏角色：{acc['nickname']}" if acc["nickname"] else ""
        await show_pwd.finish(
            f"【你的游戏账号】{acc['name']}{nick}\n密码：{acc['password']}\n\n⚠ 请勿泄露给他人"
        )

    await _finish_or_guide(show_pwd, event, _do)


# ---------------- 修改密码 ----------------
VALID_PWD_MSG = "新密码要求：6~16 位，只能包含字母和数字"


def _valid_password(pwd: str) -> bool:
    return 6 <= len(pwd) <= 16 and pwd.isalnum() and pwd.isascii()


change_pwd = on_command("修改密码", aliases={"改密码", "重置密码"}, priority=5, block=True)


@change_pwd.handle()
async def handle_change_pwd(event: MessageEvent, args: Message = CommandArg()):
    async def _do():
        new_pwd = _plain(args).split()[0] if _plain(args) else ""
        if not _valid_password(new_pwd):
            await change_pwd.finish(f"私聊用法：/修改密码 新密码\n{VALID_PWD_MSG}")
        try:
            acc = await db.change_password(str(event.user_id), new_pwd)
            await change_pwd.finish(
                f"✅ 密码修改成功！\n游戏账号：{acc['name']}\n新密码：{new_pwd}"
            )
        except DbError as e:
            await change_pwd.finish(f"❌ {e}")

    await _finish_or_guide(change_pwd, event, _do)


# ---------------- 超级管理员：账号群设置 ----------------

add_acct_group = on_command("添加账号群", priority=5, block=True)


@add_acct_group.handle()
async def handle_add_acct_group(event: MessageEvent, args: Message = CommandArg()):
    if not await _check_superuser(event):
        return
    text = _plain(args)
    gid = None
    if isinstance(event, GroupMessageEvent) and not text:
        gid = event.group_id  # 群里直接 /添加账号群 = 添加当前群
    elif text.isdigit():
        gid = int(text)
    if gid is None:
        await add_acct_group.finish("用法：/添加账号群 群号（群聊内可直接 /添加账号群 添加当前群）")
    cfg = _load()
    groups = cfg.get("account_groups", [])
    if gid in groups:
        await add_acct_group.finish(f"群 {gid} 已在账号群名单中")
    groups.append(gid)
    cfg["account_groups"] = groups
    _save(cfg)
    await add_acct_group.finish(
        f"✅ 群 {gid} 已加入账号群名单（共 {len(groups)} 个）\n"
        "名单内的群才会响应账号命令并提示玩家私聊办理；名单为空 = 所有群生效"
    )


remove_acct_group = on_command("移除账号群", aliases={"删除账号群"}, priority=5, block=True)


@remove_acct_group.handle()
async def handle_remove_acct_group(event: MessageEvent, args: Message = CommandArg()):
    if not await _check_superuser(event):
        return
    text = _plain(args)
    if not text.isdigit():
        await remove_acct_group.finish("用法：/移除账号群 群号")
    gid = int(text)
    cfg = _load()
    groups = cfg.get("account_groups", [])
    if gid not in groups:
        await remove_acct_group.finish(f"群 {gid} 不在账号群名单中")
    groups.remove(gid)
    cfg["account_groups"] = groups
    _save(cfg)
    if groups:
        await remove_acct_group.finish(f"✅ 群 {gid} 已移出账号群名单，剩余 {len(groups)} 个")
    await remove_acct_group.finish("✅ 已移出（名单已空，当前所有群都会响应账号命令指引）")


list_acct_group = on_command("账号群列表", priority=5, block=True)


@list_acct_group.handle()
async def handle_list_acct_group(event: MessageEvent):
    if not await _check_superuser(event):
        return
    groups = _load().get("account_groups", [])
    if not groups:
        await list_acct_group.finish(
            "账号群名单为空 = 所有群都会响应账号命令指引\n"
            "私聊发『/添加账号群 群号』可切换为白名单模式"
        )
    lines = [f"账号群名单（仅以下群响应账号命令指引），共 {len(groups)} 个："]
    lines += [f"- {g}" for g in groups]
    await list_acct_group.finish("\n".join(lines))


# ---------------- 超级管理员：解绑 ----------------
unbind_cmd = on_command("解绑", priority=5, block=True)


@unbind_cmd.handle()
async def handle_unbind(event: MessageEvent, args: Message = CommandArg()):
    if not await _check_superuser(event):
        return
    nickname = _plain(args)
    if not nickname:
        await unbind_cmd.finish("用法：/解绑 角色名 —— 清空该角色的 QQ 绑定（玩家可重新绑定）")
    try:
        n = await db.unbind(nickname)
    except DbError as e:
        await unbind_cmd.finish(f"❌ {e}")
        return
    if n:
        await unbind_cmd.finish(f"✅ 角色「{nickname}」已解绑（{n} 个），玩家可重新 /绑定QQ")
    await unbind_cmd.finish(f"角色「{nickname}」本来就没有绑定 QQ")


async def _check_superuser(event: MessageEvent) -> bool:
    """超管判断：env SUPERUSERS 内的 QQ。非超管静默。"""
    from nonebot import get_driver

    superusers = {int(u) for u in (get_driver().config.superusers or set())}
    if int(event.user_id) not in superusers:
        return False
    return True
