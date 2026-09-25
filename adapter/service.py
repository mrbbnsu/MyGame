#!/usr/bin/env python3
"""E1/WO-007：Classic Duel Adapter v0 —— JSON Lines over stdio 服务（K1）。

协议（详见 protocol.md）：请求 {id, cmd, ...}，响应 {id, ok, result|error}。
  new_duel {decks:[int[],int[]], opts{lp,start_hand,seed,mode}} -> {duel_id, state, events}
  get_state {viewer}                -> {state}          （K3：只暴露该视角可见信息）
  respond  {choice|cancel, viewer?} -> {state, events}  （应用选择，驱动到下一个输入点）

职责边界：
  - 二进制布局知识全部在 decoder.py / core_binding.py（K4）；本文件只有协议语义
  - 状态 = passcode + 规则语义，无文本/图片（K2）
  - 服务进程对任何请求错误/core 异常保持存活；stdin EOF 干净退出
  - v0 单对局：新 new_duel 会销毁旧对局（duel_id 递增预留）
  - WIN 后宿主停止驱动（NOTES 坑 #9）：over 后 respond 返回 DUEL_OVER
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core_binding as cb
import decoder
from core_binding import AdapterError, Config, OcgCore, POS_FACEDOWN, POS_FACEUP

MAX_PUMP_ITER = 100000        # 单次驱动 process() 上限（防死循环）
MAX_RETRIES_PER_RESPOND = 64  # 应答被拒（MSG_RETRY）上限，超过判 DUEL_RETRY_LOOP
ZONE_QUERY_FLAGS = (cb.QUERY_CODE | cb.QUERY_POSITION | cb.QUERY_TYPE
                    | cb.QUERY_LEVEL | cb.QUERY_ATTACK | cb.QUERY_DEFENSE)

SERVICE_VERSION = "0.1.0"
PROTOCOL_VERSION = 1

_DECK = cb.LOCATION_DECK
_HAND = cb.LOCATION_HAND
_MZONE = cb.LOCATION_MZONE
_SZONE = cb.LOCATION_SZONE
_GRAVE = cb.LOCATION_GRAVE
_REMOVED = cb.LOCATION_REMOVED
_EXTRA = cb.LOCATION_EXTRA

_QPOS, _QLEVEL = cb.QUERY_POSITION, cb.QUERY_LEVEL
_QATK, _QDEF = cb.QUERY_ATTACK, cb.QUERY_DEFENSE


class DuelSession:
    """一场对局的宿主侧跟踪：LP/回合/阶段/胜负从事件流推导，盘面用查询实时读。"""

    def __init__(self, duel_id, core, opts):
        self.duel_id = duel_id
        self.core = core
        self.lp = [opts["lp"], opts["lp"]]
        self.turn_player = 0
        self.turn_count = 0
        self.phase = 0
        self.phase_name = None
        self.winner = None
        self.reason = None
        self.over = False
        self.attacked = set()          # {(con, loc, seq)} 本回合已宣言攻击
        self.retries = 0
        self.pending = None            # 原始 SELECT 事件
        self.pending_norm = None       # 归一化 pending（协议结构）
        self.pending_answers = None    # {choice 下标: 应答二进制}

    # ---- 事件观察（宿主侧状态推导；与探针 MinDuel._handle 同源） ----
    def observe(self, ev):
        t = ev["type"]
        if t == "RELOAD_FIELD":
            self.lp = [ev["p0"]["lp"], ev["p1"]["lp"]]
        elif t == "NEW_TURN":
            self.turn_player = ev["turn_player"]
            self.turn_count += 1
            self.attacked.clear()
        elif t == "NEW_PHASE":
            self.phase = ev["phase"]
            self.phase_name = ev["phase_name"]
        elif t == "DAMAGE":
            self.lp[ev["player"]] -= ev["amount"]
        elif t == "RECOVER":
            self.lp[ev["player"]] += ev["amount"]
        elif t == "LPUPDATE":
            self.lp[ev["player"]] = ev["lp"]
        elif t == "PAY_LPCOST":
            self.lp[ev["player"]] -= ev["amount"]
        elif t == "WIN":
            self.winner = ev["winner"]
            self.reason = ev["reason"]
            self.over = True
        elif t == "ATTACK":
            a = ev["attacker"]
            self.attacked.add((a["con"], a["loc"], a["seq"]))
        elif t == "RETRY":
            self.retries += 1


class AdapterService:
    """进程内服务核心；stdio 循环是薄壳（main）。"""

    def __init__(self, config=None, core=None):
        self.core = core or OcgCore(config)
        self.session = None
        self.next_duel_id = 1

    # ================= 请求分发 =================
    def handle_request(self, obj):
        """单请求 -> 响应 dict（不抛异常；一切错误结构化）。"""
        try:
            if not isinstance(obj, dict):
                raise AdapterError("BAD_REQUEST", "请求必须是 JSON 对象")
            rid = obj.get("id")
            cmd = obj.get("cmd")
            handler = {"new_duel": self.cmd_new_duel,
                       "get_state": self.cmd_get_state,
                       "respond": self.cmd_respond}.get(cmd)
            if handler is None:
                raise AdapterError("UNKNOWN_CMD", f"未知 cmd: {cmd!r}")
            result = handler(obj)
            return {"id": rid, "ok": True, "result": result}
        except AdapterError as e:
            return {"id": obj.get("id") if isinstance(obj, dict) else None,
                    "ok": False, "error": e.to_dict()}
        except Exception as e:  # 任何意外都不允许杀死服务进程
            print(f"[adapter] 未预期异常: {e!r}", file=sys.stderr)
            return {"id": obj.get("id") if isinstance(obj, dict) else None,
                    "ok": False,
                    "error": {"code": "INTERNAL", "message": repr(e)}}

    # ================= new_duel =================
    def cmd_new_duel(self, req):
        decks = req.get("decks")
        opts = dict(req.get("opts") or {})
        if (not isinstance(decks, list) or len(decks) != 2
                or not all(isinstance(d, list) for d in decks)):
            raise AdapterError("BAD_REQUEST",
                               "decks 必须是 [卡组0, 卡组1] 两个 passcode 数组")
        for name, d in (("decks[0]", decks[0]), ("decks[1]", decks[1])):
            if not d:
                raise AdapterError("BAD_REQUEST", f"{name} 为空（卡组非空是前置校验）")
            for i, code in enumerate(d):
                if not isinstance(code, int) or isinstance(code, bool) \
                        or not (0 <= code < (1 << 32)):
                    raise AdapterError(
                        "BAD_REQUEST", f"{name}[{i}] 不是合法 passcode: {code!r}")
        lp = _int_field(opts, "lp", 8000, 1, 0xFFFFFFFF)
        start_hand = _int_field(opts, "start_hand", 5, 0, 60)
        seed = opts.get("seed", [0x20260925, 1, 2, 3])
        if not isinstance(seed, list) or not seed \
                or len(seed) > 4 or not all(
                    isinstance(x, int) and not isinstance(x, bool) and 0 <= x
                    < (1 << 64) for x in seed):
            raise AdapterError("BAD_REQUEST",
                               "seed 必须是 1~4 个 u64 的数组（确定性锚点）")
        mode = opts.get("mode", "default")
        if mode not in cb.MODE_FLAGS:
            raise AdapterError("BAD_REQUEST",
                               f"mode 必须是 {sorted(cb.MODE_FLAGS)} 之一")
        flags = cb.DUEL_TEST_MODE | cb.MODE_FLAGS[mode]

        self.core.create_duel(seed=seed, flags=flags, lp=lp,
                              start_hand=start_hand)
        for p, deck in enumerate(decks):
            for code in deck:
                self.core.new_card(p, code, _DECK)
        self.core.start()

        session = DuelSession(self.next_duel_id, self.core, {"lp": lp})
        self.next_duel_id += 1
        self.session = session
        events = self._pump(session)
        return {"duel_id": session.duel_id,
                "state": self.build_state(session, req.get("viewer")),
                "events": [_redact_event(ev, req.get("viewer"))
                           for ev in events]}

    # ================= get_state =================
    def cmd_get_state(self, req):
        self._require_session()
        return {"state": self.build_state(self.session, req.get("viewer"))}

    # ================= respond =================
    def cmd_respond(self, req):
        session = self._require_session()
        if session.over:
            raise AdapterError("DUEL_OVER", "对局已结束（WIN 已发出，宿主停止驱动）")
        if session.pending_norm is None:
            raise AdapterError("NO_PENDING",
                               "当前没有待应答的选择（等待服务驱动或对局未开始）")
        blob = self._encode_respond(session.pending_norm, session.pending_answers,
                                    req)
        retries_before = session.retries
        self.core.set_response(blob)
        events = self._pump(session)
        if session.retries - retries_before > MAX_RETRIES_PER_RESPOND:
            raise AdapterError("DUEL_RETRY_LOOP",
                               f"应答被 core 连续拒绝 {session.retries - retries_before} 次")
        viewer = req.get("viewer")
        return {"state": self.build_state(session, viewer),
                "events": [_redact_event(ev, viewer) for ev in events]}

    def _require_session(self):
        if self.session is None:
            raise AdapterError("NO_DUEL", "尚未 new_duel")
        return self.session

    # ================= 驱动循环 =================
    def _pump(self, session):
        """process 到 AWAITING/END，解码全部消息。返回本次事件列表（未过滤）。"""
        events, select = [], None
        session.pending = session.pending_norm = None
        session.pending_answers = None
        for _ in range(MAX_PUMP_ITER):
            status = session.core.process()
            buf = session.core.get_message()
            for chunk in decoder.split_chunks(buf):
                ev = decoder.decode_message(chunk)
                # 全量消费校验：解码器与 core writer 布局必须逐字节对齐
                if ev["type"] in ("DECODE_ERROR", "UNKNOWN"):
                    print(f"[adapter] {ev['type']}: {ev}", file=sys.stderr)
                    events.append(ev)
                    continue
                if ev["_consumed"] != ev["_raw_size"]:
                    bad = {"type": "DECODE_ERROR", "enum": ev["enum"],
                           "name": ev["type"], "raw_size": ev["_raw_size"],
                           "reason": f"消费 {ev['_consumed']}/{ev['_raw_size']} 字节"}
                    print(f"[adapter] {bad}", file=sys.stderr)
                    events.append(bad)
                    continue
                events.append(ev)
                if ev["enum"] in decoder.SELECT_MSGS:
                    select = ev   # AWAITING 对应唯一的待答选择；保留最后一个
                else:
                    session.observe(ev)
            if session.over:
                break               # 契约：WIN 后停止驱动（坑 #9）
            if status == cb.PROCESS_END:
                break
            if status == cb.PROCESS_AWAITING:
                if select is None:
                    raise AdapterError(
                        "AWAITING_NO_PENDING",
                        "core 等待应答但缓冲中无已知 SELECT 消息")
                break
            # CONTINUE：处理单元未耗尽，继续 pump
        else:
            raise AdapterError("DUEL_STUCK",
                               f"process 超过 {MAX_PUMP_ITER} 次仍未稳定")
        if select is not None and not session.over:
            session.pending = select
            session.pending_norm, session.pending_answers = \
                normalize_pending(select)
        return events

    # ================= 应答编码（选择 -> core 二进制） =================
    @staticmethod
    def _encode_respond(pending, answers, req):
        ptype = pending["type"]
        cancel = req.get("cancel", False)
        choice = req.get("choice")
        if cancel:
            if not pending.get("cancelable"):
                raise AdapterError("CHOICE_INVALID",
                                   f"{ptype} 不可取消")
            if ptype in ("SELECT_CARD", "SELECT_CHAIN", "SELECT_OTHER"):
                return decoder.encode_cancel()
            raise AdapterError("CHOICE_INVALID", f"{ptype} 无取消应答路径")
        if ptype == "SELECT_CARD":
            idx = _index_list(choice, "choice")
            if not pending["cancelable"] and len(idx) < pending["min"]:
                raise AdapterError("CHOICE_INVALID",
                                   f"至少选 {pending['min']} 张")
            if len(idx) > pending["max"]:
                raise AdapterError("CHOICE_INVALID",
                                   f"最多选 {pending['max']} 张")
            for i in idx:
                _check_index(i, len(pending["choices"]))
            return decoder.encode_card_indices(idx)
        if ptype == "SELECT_PLACE":
            idx = _index_list(choice, "choice")
            if len(idx) != pending["count"]:
                raise AdapterError("CHOICE_INVALID",
                                   f"需要选 {pending['count']} 个位置")
            picks = []
            for i in idx:
                _check_index(i, len(pending["choices"]))
                picks.append(pending["choices"][i]["pick"])
            return decoder.encode_place(picks)
        # 单下标类型
        i = _single_index(choice)
        _check_index(i, len(pending["choices"]))
        if ptype in ("IDLE", "SELECT_BATTLE", "SELECT_CHAIN", "EFFECT_YESNO",
                     "SELECT_YESNO", "SELECT_OPTION", "SELECT_POSITION"):
            return answers[i]
        raise AdapterError("CHOICE_INVALID",
                           f"{ptype} 仅支持 cancel（SELECT_OTHER 未覆盖类型）")

    # ================= 状态构建（K2/K3） =================
    def build_state(self, session, viewer):
        if viewer is None:
            pass
        elif isinstance(viewer, bool) or viewer not in (0, 1):
            raise AdapterError("BAD_REQUEST", "viewer 必须是 0|1|null")
        core = session.core
        s = {"duel_id": session.duel_id,
             "turn_player": session.turn_player,
             "turn_count": session.turn_count,
             "phase": session.phase_name,
             "winner": session.winner,
             "reason": session.reason,
             "protocol_version": PROTOCOL_VERSION,
             "players": []}
        players = s["players"]
        for p in (0, 1):
            hand_q = core.query_location(p, _HAND)
            mzone_q = core.query_location(p, _MZONE)
            szone_q = core.query_location(p, _SZONE)
            grave_q = core.query_location(p, _GRAVE)
            rem_q = core.query_location(p, _REMOVED)
            hand = []
            for c in hand_q:
                vis = viewer is None or p == viewer
                hand.append({"code": c["code"] if vis else None})
            players.append({
                "lp": session.lp[p],
                "deck_count": core.query_count(p, _DECK),
                "hand": hand,
                "monster_zones": [_zone_card(c, p, _MZONE, viewer, session)
                                  for c in mzone_q],
                "spell_trap_zones": [_zone_card(c, p, _SZONE, viewer, session)
                                     for c in szone_q],
                "graveyard": [_zone_card(c, p, _GRAVE, viewer, session)
                              for c in grave_q],
                "banished": [_zone_card(c, p, _REMOVED, viewer, session)
                             for c in rem_q],
                "extra_count": core.query_count(p, _EXTRA),
            })
        s["players"] = players
        s["pending"] = (_redact_pending(session.pending_norm, viewer)
                        if session.pending_norm else None)
        return s


# ---------- pending 归一化（decoded SELECT -> 协议 pending + 应答表） ----------

def normalize_pending(sel):
    msg = sel["enum"]
    player = sel.get("player", 0)
    if msg == 11:
        return _norm_idle(sel, player)
    if msg == 10:
        return _norm_battle(sel, player)
    if msg == 16:
        return _norm_chain(sel, player)
    if msg == 12:
        card = _card_ref({"code": sel["code"], "at": sel["at"]})
        choices = [{"kind": "accept"}, {"kind": "decline"}]
        pend = {"type": "EFFECT_YESNO", "player": player, "prompt": sel["desc"],
                "cancelable": False, "card": card, "desc": sel["desc"],
                "choices": choices}
        answers = {0: decoder.encode_yesno(True), 1: decoder.encode_yesno(False)}
        return pend, answers
    if msg == 13:
        choices = [{"kind": "accept"}, {"kind": "decline"}]
        pend = {"type": "SELECT_YESNO", "player": player, "prompt": sel["desc"],
                "cancelable": False, "desc": sel["desc"], "choices": choices}
        answers = {0: decoder.encode_yesno(True), 1: decoder.encode_yesno(False)}
        return pend, answers
    if msg == 14:
        choices = [{"kind": "option", "desc": d} for d in sel["options"]]
        pend = {"type": "SELECT_OPTION", "player": player, "prompt": None,
                "cancelable": False, "choices": choices}
        answers = {i: decoder.encode_i32(i) for i in range(len(choices))}
        return pend, answers
    if msg in (15, 20):
        cards = [_choice_card(e) for e in sel["cards"]]
        pend = {"type": "SELECT_CARD", "player": player, "prompt": None,
                "cancelable": bool(sel["cancelable"]),
                "min": sel["min"], "max": sel["max"],
                "tribute": msg == 20, "choices": cards}
        return pend, {}
    if msg in (18, 24):
        return _norm_place(sel, player, disfield=(msg == 24))
    if msg == 19:
        choices = []
        answers = {}
        bits = sel["positions"]
        for pos in (cb.POS_FACEUP_ATTACK, cb.POS_FACEDOWN_ATTACK,
                    cb.POS_FACEUP_DEFENSE, cb.POS_FACEDOWN_DEFENSE):
            if bits & pos:
                answers[len(choices)] = decoder.encode_position(pos)
                choices.append({"kind": "position", "pos": _pos_name(pos)})
        pend = {"type": "SELECT_POSITION", "player": player,
                "prompt": None, "cancelable": False,
                "card": _card_ref({"code": sel["code"], "at": None}),
                "choices": choices}
        return pend, answers
    # 未覆盖的 SELECT_*：保留原始参数，v0 只支持取消（cancel -> -1）
    raw = {k: v for k, v in sel.items()
           if k not in ("type", "enum", "_consumed", "_raw_size")}
    pend = {"type": "SELECT_OTHER", "player": player, "prompt": None,
            "cancelable": _other_cancelable(sel),
            "msg": sel["type"], "params": raw, "choices": []}
    return pend, {}


def _norm_idle(sel, player):
    choices, answers = [], {}
    groups = (("summon", "summonable"), ("spsummon", "spsummonable"),
              ("reposition", "repositionable"), ("mset", "msetable"),
              ("sset", "ssetable"), ("activate", "activatable"))
    for kind, key in groups:
        for i, e in enumerate(sel[key]):
            c = {"kind": kind, "card": _card_ref(e)}
            if kind == "activate":
                c["desc"] = e["desc"]
            answers[len(choices)] = decoder.encode_idle(kind, i)
            choices.append(c)
    if sel.get("can_shuffle"):
        answers[len(choices)] = decoder.encode_idle("shuffle", 0)
        choices.append({"kind": "shuffle"})
    if sel.get("to_bp"):
        answers[len(choices)] = decoder.encode_idle("to_bp", 0)
        choices.append({"kind": "to_bp"})
    answers[len(choices)] = decoder.encode_idle("to_ep", 0)
    choices.append({"kind": "to_ep"})
    return {"type": "IDLE", "player": player, "prompt": None,
            "cancelable": False, "choices": choices}, answers


def _norm_battle(sel, player):
    choices, answers = [], {}
    for i, e in enumerate(sel["activatable"]):
        answers[len(choices)] = decoder.encode_battle("activate", i)
        choices.append({"kind": "activate", "card": _card_ref(e),
                        "desc": e["desc"]})
    for i, e in enumerate(sel["attackable"]):
        c = {"kind": "attack", "attacker": _card_ref(e),
             "direct": bool(e["direct"])}
        answers[len(choices)] = decoder.encode_battle("attack", i)
        choices.append(c)
    if sel.get("to_m2"):
        answers[len(choices)] = decoder.encode_battle("to_m2", 0)
        choices.append({"kind": "to_m2"})
    if sel.get("to_ep"):
        answers[len(choices)] = decoder.encode_battle("to_ep", 0)
        choices.append({"kind": "to_ep"})
    return {"type": "SELECT_BATTLE", "player": player, "prompt": None,
            "cancelable": False, "choices": choices}, answers


def _norm_chain(sel, player):
    choices = [{"kind": "chain", "card": _card_ref(e), "desc": e["desc"],
                "index": i} for i, e in enumerate(sel["chains"])]
    pend = {"type": "SELECT_CHAIN", "player": player, "prompt": None,
            "cancelable": not sel["forced"], "forced": bool(sel["forced"]),
            "choices": choices}
    answers = {i: decoder.encode_i32(i) for i in range(len(choices))}
    return pend, answers


def _norm_place(sel, player, disfield):
    """flag 位图 -> 可选位置列表。位=1 禁用（坑 #7）；
    位 0~7 己方 mzone、8~15 己方 szone、16~23 对方 mzone、24~31 对方 szone。"""
    choices, answers = [], {}
    flag = sel["flag"]
    for bit in range(32):
        if flag & (1 << bit):
            continue
        if bit < 8:
            owner, loc, seq = player, _MZONE, bit
        elif bit < 16:
            owner, loc, seq = player, _SZONE, bit - 8
        elif bit < 24:
            owner, loc, seq = 1 - player, _MZONE, bit - 16
        else:
            owner, loc, seq = 1 - player, _SZONE, bit - 24
        zone = "monster" if loc == _MZONE else "spell_trap"
        pick = {"player": owner, "loc": loc, "seq": seq}
        answers[len(choices)] = decoder.encode_place([pick])
        choices.append({"kind": "place", "zone": zone, "seq": seq,
                        "owner": owner, "pick": pick})
    pend = {"type": "SELECT_PLACE", "player": player, "prompt": None,
            "cancelable": False, "count": sel["count"],
            "disfield": disfield, "choices": choices}
    return pend, answers


def _other_cancelable(sel):
    """未覆盖 SELECT_* 是否有 -1 取消路径（无 cancelable 字段的保守给 False，
    但 UNSELECT/SORT 类消息核心 reader 接受 -1）。"""
    if sel["enum"] in (26, 21, 25, 23, 22):
        return True
    return bool(sel.get("cancelable", 0)) if "cancelable" in sel else False


# ---------- 视角可见性（K3 红线） ----------

def visible(at, viewer):
    """卡引用在该视角下是否可见 code。viewer=None 为全可见（驱动/测试模式）。"""
    if viewer is None:
        return True
    loc, con, pos = at.get("loc"), at.get("con"), at.get("pos")
    if loc == _HAND:
        return con == viewer
    if loc in (_DECK, _EXTRA):
        return False                     # v0 不暴露卡组/额外内容
    if loc in (_MZONE, _SZONE):
        if con == viewer:
            return True                  # 己方场上的盖卡自己可见
        return pos is not None and bool(pos & POS_FACEUP)
    if loc in (_GRAVE, _REMOVED):
        return pos is None or not (pos & POS_FACEDOWN)
    return False


def _redact_pending(pend, viewer):
    """pending 深拷贝并按视角隐藏卡 code（通用遍历：任何含 code 的卡引用）。"""
    if viewer is None:
        return pend
    out = json.loads(json.dumps(pend))    # 深拷贝（pending 小，安全）

    def walk(node):
        if isinstance(node, list):
            for x in node:
                walk(x)
        elif isinstance(node, dict):
            if isinstance(node.get("code"), int):
                at = node.get("at") if isinstance(node.get("at"), dict) else node
                if not visible(at, viewer):
                    node["code"] = None
            for x in node.values():
                if isinstance(x, (list, dict)):
                    walk(x)

    walk(out)
    return out


def _redact_event(ev, viewer):
    """事件按视角隐藏（事件流同样不得泄漏，K3 延伸）。viewer=None 全可见。"""
    if viewer is None:
        return {k: v for k, v in ev.items() if not k.startswith("_")}
    out = {k: v for k, v in ev.items() if not k.startswith("_")}
    t = out["type"]
    if t == "DRAW" and out.get("player") != viewer:
        out["cards"] = [{"code": None, "pos": c["pos"]} for c in out["cards"]]
        return out
    pairs = []
    if "code" in out and "at" in out:
        pairs.append((out, "code", out["at"]))
    if t == "MOVE" and "to" in out:
        pairs.append((out, "code", out["to"]))
    if t == "POS_CHANGE":
        out["code"] = out["code"] if visible(out["at"], viewer) else None
        return out
    if t == "SWAP":
        out["code1"] = out["code1"] if visible(out["at1"], viewer) else None
        out["code2"] = out["code2"] if visible(out["at2"], viewer) else None
        return out
    for obj, key, at in pairs:
        if not visible(at, viewer):
            obj[key] = None
    return out


# ---------- 小工具 ----------

def _card_ref(e):
    """解码条目 {code, at} -> 协议卡引用 {code, con, loc, seq[, pos]}。"""
    ref = {"code": e["code"]}
    at = e.get("at") or {}
    ref.update({k: at[k] for k in ("con", "loc", "seq") if k in at})
    if "pos" in at:
        ref["pos"] = at["pos"]
    return ref


def _choice_card(e):
    """SELECT_CARD 条目 -> choice {card: {code, con, loc, seq, pos}}。"""
    return {"card": _card_ref(e)}


def _pos_name(pos):
    if pos in decoder.POS_NAMES:
        return decoder.POS_NAMES[pos]
    if pos & POS_FACEDOWN == POS_FACEDOWN:
        return "facedown"          # 盖放未定向（里攻|里守位同时置位）
    if pos & POS_FACEUP == POS_FACEUP:
        return "faceup"
    return hex(pos)


def _zone_card(c, owner, loc, viewer, session):
    """查询槽 -> 协议卡位。空槽 None；隐藏 code 保留 pos/face/数量。"""
    if c is None:
        return None
    pos = c.get(_QPOS)
    vis = visible({"con": owner, "loc": loc, "seq": c["seq"], "pos": pos},
                  viewer)
    card = {"code": c["code"] if vis else None,
            "pos": _pos_name(pos) if pos is not None else None,
            "face": bool(pos & POS_FACEUP) if pos is not None else None}
    if loc == _MZONE:
        if vis and _QATK in c:
            card["atk"] = c[_QATK]
        if vis and _QDEF in c:
            card["def"] = c[_QDEF]
        if (owner, loc, c["seq"]) in session.attacked:
            card["has_attacked"] = True
    return card


def _int_field(opts, name, default, lo, hi):
    v = opts.get(name, default)
    if not isinstance(v, int) or isinstance(v, bool) or not (lo <= v <= hi):
        raise AdapterError("BAD_REQUEST",
                           f"opts.{name} 必须是 {lo}~{hi} 的整数，得到 {v!r}")
    return v


def _index_list(choice, name):
    if isinstance(choice, int) and not isinstance(choice, bool):
        return [choice]
    if (isinstance(choice, list) and choice
            and all(isinstance(i, int) and not isinstance(i, bool) for i in choice)):
        return list(choice)
    raise AdapterError("BAD_REQUEST", f"{name} 必须是下标或下标数组")


def _single_index(choice):
    if isinstance(choice, int) and not isinstance(choice, bool):
        return choice
    raise AdapterError("BAD_REQUEST", "choice 必须是 choices 的下标")


def _check_index(i, n):
    if not (0 <= i < n):
        raise AdapterError("CHOICE_INVALID", f"下标 {i} 超出 choices 范围 [0,{n})")


# ---------- stdio 薄壳 ----------

def main(argv=None):
    ap = argparse.ArgumentParser(description="Classic Duel Adapter v0")
    ap.add_argument("--dll", default=None, help="ocgcore.dll 路径")
    ap.add_argument("--cdb", default=None, help="cards.cdb 路径")
    ap.add_argument("--scripts", default=None, help="CardScripts 根目录")
    args = ap.parse_args(argv)
    # 协议通道只用二进制 IO，绕开 Windows 控制台编码；诊断全走 stderr
    out, err = sys.stdout.buffer, sys.stderr
    config = Config(dll=args.dll, cdb=args.cdb, scripts=args.scripts)
    try:
        service = AdapterService(config)
    except AdapterError as e:
        # 启动失败：协议行报告后退出（客户端拿到结构化原因）
        out.write(json.dumps({"id": None, "ok": False,
                              "error": e.to_dict(),
                              "fatal": True},
                             ensure_ascii=False).encode("utf-8") + b"\n")
        out.flush()
        return 1
    hello = {"id": None, "ok": True,
             "result": {"ready": True, "service_version": SERVICE_VERSION,
                        "protocol_version": PROTOCOL_VERSION,
                        "core_api_version": service.core.version()}}
    out.write(json.dumps(hello, ensure_ascii=False).encode("utf-8") + b"\n")
    out.flush()
    for line in sys.stdin.buffer:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            resp = {"id": None, "ok": False, "error": {
                "code": "BAD_REQUEST", "message": f"JSON 行解析失败: {e}"}}
        else:
            resp = service.handle_request(req)
        out.write(json.dumps(resp, ensure_ascii=False,
                             allow_nan=False).encode("utf-8") + b"\n")
        out.flush()
    # stdin EOF：清理并干净退出
    service.core.destroy()
    print("[adapter] EOF，服务退出", file=err)
    return 0


if __name__ == "__main__":
    sys.exit(main())
