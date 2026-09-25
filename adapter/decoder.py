#!/usr/bin/env python3
"""E1/WO-007：消息解码层 —— 全部二进制布局知识集中于此（K4）。

核心仓 95 个 MSG_* 枚举（ocgapi_constants.h 207-301 行）全部命名；
其中 core 实际会写出的 80 个里本层解码 79 个（TAG_SWAP 复杂 Rare 用例留待按需补）；
其余 15 个为 legacy 枚举（当前 core 无 writer，如 MSG_START/MSG_UPDATE_DATA，
见 vendor/repos/ygopro-core 全源 grep），若被未来版本写出则回退 UNKNOWN。

解码覆盖清单（79 种；"探针"= D1 两场对局实跑验证，"源"= 从 core writer 逐条提取）：
  通用/生命周期: WIN(5,探针) RETRY(1,源) HINT(2,源) FIELD_DISABLED(56,源)
                 MATCH_KILL(170,源) ROCK_PAPER_SCISSORS(132,源) HAND_RES(133,源)
  阶段/回合流:   NEW_TURN(40,探针) NEW_PHASE(41,探针) RELOAD_FIELD(162,探针)
  抽牌/LP:       DRAW(90,探针) DAMAGE(91,探针) RECOVER(92,探针) LPUPDATE(94,探针)
                 PAY_LPCOST(100,探针)
  移动/召唤:     MOVE(50,探针) SET(54,探针) POS_CHANGE(53,源) SWAP(55,源)
                 SUMMONING(60,探针) SUMMONED(61,源) SPSUMMONING(62,探针)
                 SPSUMMONED(63,源) FLIPSUMMONING(64,源) FLIPSUMMONED(65,源)
                 SHUFFLE_DECK(32,源) SHUFFLE_SET_CARD(36,源) SWAP_GRAVE_DECK(35,源)
                 REVERSE_DECK(37,源)
  连锁:          CHAINING(70,源) CHAINED(71,源) CHAIN_SOLVING(72,源)
                 CHAIN_SOLVED(73,源) CHAIN_END(74,源) CHAIN_NEGATED(75,源)
                 CHAIN_DISABLED(76,源)
  战斗/伤害步骤: ATTACK(110,探针) BATTLE(111,探针) ATTACK_DISABLED(112,源)
                 DAMAGE_STEP_START(113,源) DAMAGE_STEP_END(114,源)
  目标/装备:     BECOME_TARGET(83,源) EQUIP(93,源) CARD_TARGET(96,源)
                 CANCEL_TARGET(97,源) MISSED_EFFECT(120,源) REMOVE_CARDS(190,源)
  确认/展示:     CARD_SELECTED(80,源) RANDOM_SELECTED(81,源) CONFIRM_CARDS(31,源)
                 CONFIRM_DECKTOP(30,源) CONFIRM_EXTRATOP(42,源) DECK_TOP(38,源)
  投掷/提示:     TOSS_COIN(130,源) TOSS_DICE(131,源) CARD_HINT(160,源)
                 PLAYER_HINT(165,源)
  计数器:        ADD_COUNTER(101,源) REMOVE_COUNTER(102,源)
  SELECT_*（→ 服务层归一化 pending）:
                 SELECT_BATTLECMD(10,探针) SELECT_IDLECMD(11,探针)
                 SELECT_EFFECTYN(12,探针) SELECT_YESNO(13,探针) SELECT_OPTION(14,探针)
                 SELECT_CARD(15,探针) SELECT_CHAIN(16,探针) SELECT_PLACE(18,探针)
                 SELECT_POSITION(19,探针) SELECT_TRIBUTE(20,探针) SELECT_SUM(23,源)
                 SELECT_DISFIELD(24,源) SORT_CHAIN(21,源) SORT_CARD(25,源)
                 SELECT_UNSELECT_CARD(26,源) SELECT_COUNTER(22,源)
  ANNOUNCE_*:    ANNOUNCE_RACE(140,源) ANNOUNCE_ATTRIB(141,源) ANNOUNCE_CARD(142,源)
                 ANNOUNCE_NUMBER(143,源)

未解码（回退 UNKNOWN 事件 + SELECT_OTHER pending）：TAG_SWAP(161) 及 15 个 legacy
枚举（WAITING/START/UPDATE_DATA/UPDATE_CARD/REQUEST_DECK/SHUFFLE_HAND/REFRESH_DECK/
SHUFFLE_EXTRA/UNEQUIP/BE_CHAIN_TARGET/CREATE_RELATION/RELEASE_RELATION/AI_NAME/
SHOW_HINT/CUSTOM_MSG）。

布局依据：core 各 writer（duel.cpp generate_buffer：每消息 [u32 len][payload] 串联）；
解析失败（长度不符/越界）抛 _DecodeError → 上层降级为 DECODE_ERROR 事件，服务不崩。

响应编码器（encode_*）：把服务层的选择转成 core 应答二进制（响应布局同样只住本文件）。
"""
import struct

from core_binding import (LOCATION_DECK, LOCATION_GRAVE, LOCATION_HAND,
                          LOCATION_MZONE, LOCATION_REMOVED, LOCATION_SZONE,
                          POS_FACEUP_ATTACK, POS_FACEDOWN_ATTACK,
                          POS_FACEUP_DEFENSE, POS_FACEDOWN_DEFENSE)

# ---- 95 个 MSG 枚举命名（ocgapi_constants.h，全量） ----
MSG_NAMES = {
    1: "RETRY", 2: "HINT", 3: "WAITING", 4: "START", 5: "WIN", 6: "UPDATE_DATA",
    7: "UPDATE_CARD", 8: "REQUEST_DECK", 10: "SELECT_BATTLECMD",
    11: "SELECT_IDLECMD", 12: "SELECT_EFFECTYN", 13: "SELECT_YESNO",
    14: "SELECT_OPTION", 15: "SELECT_CARD", 16: "SELECT_CHAIN", 18: "SELECT_PLACE",
    19: "SELECT_POSITION", 20: "SELECT_TRIBUTE", 21: "SORT_CHAIN", 22: "SELECT_COUNTER",
    23: "SELECT_SUM", 24: "SELECT_DISFIELD", 25: "SORT_CARD",
    26: "SELECT_UNSELECT_CARD", 30: "CONFIRM_DECKTOP", 31: "CONFIRM_CARDS",
    32: "SHUFFLE_DECK", 33: "SHUFFLE_HAND", 34: "REFRESH_DECK",
    35: "SWAP_GRAVE_DECK", 36: "SHUFFLE_SET_CARD", 37: "REVERSE_DECK",
    38: "DECK_TOP", 39: "SHUFFLE_EXTRA", 40: "NEW_TURN", 41: "NEW_PHASE",
    42: "CONFIRM_EXTRATOP", 50: "MOVE", 53: "POS_CHANGE", 54: "SET", 55: "SWAP",
    56: "FIELD_DISABLED", 60: "SUMMONING", 61: "SUMMONED", 62: "SPSUMMONING",
    63: "SPSUMMONED", 64: "FLIPSUMMONING", 65: "FLIPSUMMONED", 70: "CHAINING",
    71: "CHAINED", 72: "CHAIN_SOLVING", 73: "CHAIN_SOLVED", 74: "CHAIN_END",
    75: "CHAIN_NEGATED", 76: "CHAIN_DISABLED", 80: "CARD_SELECTED",
    81: "RANDOM_SELECTED", 83: "BECOME_TARGET", 90: "DRAW", 91: "DAMAGE",
    92: "RECOVER", 93: "EQUIP", 94: "LPUPDATE", 95: "UNEQUIP", 96: "CARD_TARGET",
    97: "CANCEL_TARGET", 100: "PAY_LPCOST", 101: "ADD_COUNTER",
    102: "REMOVE_COUNTER", 110: "ATTACK", 111: "BATTLE", 112: "ATTACK_DISABLED",
    113: "DAMAGE_STEP_START", 114: "DAMAGE_STEP_END", 120: "MISSED_EFFECT",
    121: "BE_CHAIN_TARGET", 122: "CREATE_RELATION", 123: "RELEASE_RELATION",
    130: "TOSS_COIN", 131: "TOSS_DICE", 132: "ROCK_PAPER_SCISSORS",
    133: "HAND_RES", 140: "ANNOUNCE_RACE", 141: "ANNOUNCE_ATTRIB",
    142: "ANNOUNCE_CARD", 143: "ANNOUNCE_NUMBER", 160: "CARD_HINT",
    161: "TAG_SWAP", 162: "RELOAD_FIELD", 163: "AI_NAME", 164: "SHOW_HINT",
    165: "PLAYER_HINT", 170: "MATCH_KILL", 180: "CUSTOM_MSG", 190: "REMOVE_CARDS",
}
assert len(MSG_NAMES) == 95, "MSG 枚举命名必须 95 个齐全"

SELECT_MSGS = frozenset((10, 11, 12, 13, 14, 15, 16, 18, 19, 20, 21, 22, 23,
                         24, 25, 26))

PHASE_NAMES = {0x01: "DRAW", 0x02: "STANDBY", 0x04: "MAIN1",
               0x08: "BATTLE_START", 0x10: "BATTLE_STEP", 0x20: "DAMAGE",
               0x40: "DAMAGE_CAL", 0x80: "BATTLE", 0x100: "MAIN2", 0x200: "END"}
POS_NAMES = {POS_FACEUP_ATTACK: "faceup_attack",
             POS_FACEDOWN_ATTACK: "facedown_attack",
             POS_FACEUP_DEFENSE: "faceup_defense",
             POS_FACEDOWN_DEFENSE: "facedown_defense"}
LOCATION_NAMES = {LOCATION_DECK: "deck", LOCATION_HAND: "hand",
                  LOCATION_MZONE: "monster_zones", LOCATION_SZONE: "spell_trap_zones",
                  LOCATION_GRAVE: "graveyard", LOCATION_REMOVED: "banished",
                  0x40 + 0x4000: "overlay"}
# WIN reason（processor.cpp: win 判定处；winner=2(PLAYER_NONE) 时为平局）
WIN_REASON_NAMES = {0: "GIVE_UP", 1: "LP_ZERO", 2: "DECK_OUT"}


class _DecodeError(Exception):
    pass


class ByteReader:
    """小端二进制读取；越界抛 _DecodeError。"""

    def __init__(self, data):
        self.d = data
        self.o = 0

    def _need(self, n):
        if self.o + n > len(self.d):
            raise _DecodeError(f"越界: 需 {n} 字节 @ {self.o}, 总长 {len(self.d)}")

    def u8(self):
        self._need(1)
        v = self.d[self.o]
        self.o += 1
        return v

    def u16(self):
        self._need(2)
        v = struct.unpack_from("<H", self.d, self.o)[0]
        self.o += 2
        return v

    def u32(self):
        self._need(4)
        v = struct.unpack_from("<I", self.d, self.o)[0]
        self.o += 4
        return v

    def u64(self):
        self._need(8)
        v = struct.unpack_from("<Q", self.d, self.o)[0]
        self.o += 8
        return v

    def loc_info(self, with_pos=True):
        """卡引用 loc_info{controler u8, location u8, sequence u32[, position u32]}"""
        r = {"con": self.u8(), "loc": self.u8(), "seq": self.u32()}
        if with_pos:
            r["pos"] = self.u32()
        return r

    def entry_no_pos(self):
        """确认类条目 {code u32, con u8, loc u8, seq u32}（CONFIRM_*/SELECT_COUNTER）。"""
        return {"code": self.u32(), "con": self.u8(), "loc": self.u8(),
                "seq": self.u32()}

    def card_entry(self, with_param=False):
        e = {"code": self.u32(), "at": self.loc_info()}
        if with_param:
            e["param"] = self.u32()
        return e

    def loc_list(self):
        """u32 数量 + N×loc_info（无 code）。"""
        n = self.u32()
        return [self.loc_info() for _ in range(n)]

    def remaining(self):
        return len(self.d) - self.o


def split_chunks(buf):
    """[u32 len][payload]… -> [payload,…]（每块首字节为消息枚举）。"""
    out, off = [], 0
    while off < len(buf):
        if off + 4 > len(buf):
            raise _DecodeError(f"块头越界 @ {off}")
        (ln,) = struct.unpack_from("<I", buf, off)
        off += 4
        if off + ln > len(buf):
            raise _DecodeError(f"块体越界: len={ln} @ {off}")
        out.append(buf[off:off + ln])
        off += ln
    return out


def decode_message(chunk):
    """单块 [msg u8][payload] -> 事件 dict（含 type/enum/_consumed）。

    已知消息解码失败 -> {"type":"DECODE_ERROR",...}；未知枚举 -> UNKNOWN。
    """
    if not chunk:
        return {"type": "DECODE_ERROR", "reason": "空块", "raw_size": 0}
    msg, p = chunk[0], chunk[1:]
    name = MSG_NAMES.get(msg, f"MSG_{msg}")
    base = {"enum": msg}
    if msg not in MSG_NAMES:
        return {**base, "type": "UNKNOWN", "raw_size": len(p)}
    try:
        r = ByteReader(p)
        fn = globals().get("_decode_" + name.lower())
        if fn is None:
            # 命名但无解码器（15 个 legacy 枚举 + TAG_SWAP）：按未知处理
            return {**base, "type": "UNKNOWN", "name": name, "raw_size": len(p)}
        m = fn(r, p)
    except (_DecodeError, IndexError, struct.error) as e:
        return {**base, "type": "DECODE_ERROR", "name": name,
                "reason": str(e), "raw_size": len(p)}
    m.update(base)
    m["type"] = name
    m["_consumed"] = r.o
    m["_raw_size"] = len(p)
    return m


# ---- 各消息解码器（r=ByteReader, p=原始 payload） ----

def _decode_win(r, p):
    return {"winner": r.u8(), "reason": r.u8(),
            "reason_name": WIN_REASON_NAMES.get(p[1], "OTHER")}


def _decode_retry(r, p):
    return {}


def _decode_hint(r, p):
    return {"hint_type": r.u8(), "player": r.u8(), "data": r.u64()}


def _decode_field_disabled(r, p):
    return {"disabled": r.u32()}


def _decode_match_kill(r, p):
    return {"code": r.u32()}


def _decode_rock_paper_scissors(r, p):
    return {"stage": r.u8()}


def _decode_hand_res(r, p):
    v = r.u8()
    return {"p0": v & 3, "p1": (v >> 2) & 3}


def _decode_new_turn(r, p):
    return {"turn_player": r.u8()}


def _decode_new_phase(r, p):
    ph = r.u16()
    return {"phase": ph, "phase_name": PHASE_NAMES.get(ph, hex(ph))}


def _decode_reload_field(r, p):
    m = {"duel_options": r.u32()}
    for pl in (0, 1):
        info = {"lp": r.u32(), "monster_zones": [], "spell_trap_zones": []}
        for _ in range(7):  # mzone 7 槽
            if r.u8():
                info["monster_zones"].append({"pos": r.u8(), "overlay": r.u32()})
            else:
                info["monster_zones"].append(None)
        for _ in range(8):  # szone 8 槽
            if r.u8():
                info["spell_trap_zones"].append({"pos": r.u8(), "overlay": r.u32()})
            else:
                info["spell_trap_zones"].append(None)
        for k in ("deck_count", "hand_count", "grave_count", "banished_count",
                  "extra_count", "extra_top_count"):
            info[k] = r.u32()
        m[f"p{pl}"] = info
    n = r.u32()
    m["chains"] = [{"code": r.u32(), "at": r.loc_info()} for _ in range(n)]
    return m


def _decode_draw(r, p):
    player = r.u8()
    n = r.u32()
    return {"player": player,
            "cards": [{"code": r.u32(), "pos": r.u32()} for _ in range(n)]}


def _decode_lp_delta(r, p):
    return {"player": r.u8(), "amount": r.u32()}

_decode_damage = _decode_lp_delta
_decode_recover = _decode_lp_delta
_decode_pay_lpcost = _decode_lp_delta


def _decode_lpupdate(r, p):
    return {"player": r.u8(), "lp": r.u32()}


def _decode_move_like(r, p):
    return {"code": r.u32(), "at": r.loc_info()}

_decode_summoning = _decode_move_like
_decode_spsummoning = _decode_move_like
_decode_set = _decode_move_like
_decode_flipsummoning = _decode_move_like


def _decode_empty(r, p):
    return {}

_decode_summoned = _decode_empty
_decode_spsummoned = _decode_empty
_decode_flipsummoned = _decode_empty
_decode_chain_end = _decode_empty
_decode_attack_disabled = _decode_empty
_decode_damage_step_start = _decode_empty
_decode_damage_step_end = _decode_empty
_decode_reverse_deck = _decode_empty


def _decode_move(r, p):
    return {"code": r.u32(), "from": r.loc_info(), "to": r.loc_info(),
            "reason": r.u32()}


def _decode_pos_change(r, p):
    # code u32 + con u8 + loc u8 + seq u8 + prev_pos u8 + new_pos u8 = 9 字节
    #（operations.cpp:5308~5314；无 pos 字段、seq 为 u8）
    return {"code": r.u32(), "at": {"con": r.u8(), "loc": r.u8(), "seq": r.u8()},
            "prev_pos": r.u8(), "new_pos": r.u8()}


def _decode_swap(r, p):
    return {"code1": r.u32(), "at1": r.loc_info(),
            "code2": r.u32(), "at2": r.loc_info()}


def _decode_chaining(r, p):
    return {"code": r.u32(), "at": r.loc_info(),
            "trigger_con": r.u8(), "trigger_loc": r.u8(),
            "trigger_seq": r.u32(), "desc": r.u64(), "chain_count": r.u32()}


def _decode_chain_count(r, p):
    return {"chain_count": r.u8()}

_decode_chained = _decode_chain_count
_decode_chain_solving = _decode_chain_count
_decode_chain_solved = _decode_chain_count
_decode_chain_negated = _decode_chain_count
_decode_chain_disabled = _decode_chain_count


def _decode_attack(r, p):
    return {"attacker": r.loc_info(), "target": r.loc_info()}


def _decode_battle(r, p):
    m = {"attacker": r.loc_info(), "aa": r.u32(), "ad": r.u32(),
         "bd0": r.u8(), "target": r.loc_info(),
         "da": r.u32(), "dd": r.u32(), "bd1": r.u8()}
    return m


def _decode_become_target(r, p):
    return {"targets": r.loc_list()}


def _decode_missed_effect(r, p):
    at = r.loc_info()
    return {"at": at, "code": r.u32()}


def _decode_shuffle_deck(r, p):
    return {"player": r.u8()}


def _decode_swap_grave_deck(r, p):
    return {"player": r.u8()}


def _decode_shuffle_set_card(r, p):
    loc = r.u8()
    ct = r.u8()
    pairs = []
    for _ in range(ct):
        pairs.append({"from": r.loc_info(), "to": r.loc_info()})
    return {"loc": loc, "pairs": pairs}


def _decode_card_selected(r, p):
    return {"cards": r.loc_list()}


def _decode_random_selected(r, p):
    player = r.u8()
    return {"player": player, "cards": r.loc_list()}


def _decode_confirm_cards(r, p):
    player = r.u8()
    n = r.u32()
    return {"player": player,
            "cards": [r.entry_no_pos() for _ in range(n)]}

_decode_confirm_decktop = _decode_confirm_cards
_decode_confirm_extratop = _decode_confirm_cards


def _decode_deck_top(r, p):
    player = r.u8()
    n = r.u32()
    return {"player": player,
            "cards": [{"code": r.u32(), "pos": r.u32()} for _ in range(n)]}


def _decode_toss(r, p):
    player = r.u8()
    n = r.u8()
    return {"player": player, "results": [r.u8() for _ in range(n)]}

_decode_toss_coin = _decode_toss
_decode_toss_dice = _decode_toss


def _decode_card_hint(r, p):
    return {"at": r.loc_info(), "hint_type": r.u8(), "value": r.u64()}


def _decode_player_hint(r, p):
    return {"player": r.u8(), "hint_type": r.u8(), "value": r.u64()}


def _decode_counter(r, p):
    t = r.u16()
    m = {"counter_type": t, "at": {"con": r.u8(), "loc": r.u8(),
                                   "seq": r.u8()}, "count": r.u16()}
    return m

_decode_add_counter = _decode_counter
_decode_remove_counter = _decode_counter


def _decode_equip(r, p):
    return {"source": r.loc_info(), "target": r.loc_info()}


def _decode_card_target(r, p):
    return {"source": r.loc_info(), "target": r.loc_info()}

_decode_cancel_target = _decode_card_target


def _decode_remove_cards(r, p):
    return {"cards": r.loc_list()}


# ---- SELECT_* ----

def _activatable_entries(r):
    """code u32 + con u8 + loc u8 + seq u32 + desc u64 + mode u8（无 pos；
    playerop.cpp:21~44，探针实跑验证）。"""
    out = []
    n = r.u32()
    for _ in range(n):
        code = r.u32()
        at = {"con": r.u8(), "loc": r.u8(), "seq": r.u32()}
        out.append({"code": code, "at": at, "desc": r.u64(), "mode": r.u8()})
    return out


def _decode_select_battlecmd(r, p):
    m = {"player": r.u8()}
    m["activatable"] = _activatable_entries(r)
    n = r.u32()
    # attackable 条目 con/loc/seq/direct 均为 u8（playerop.cpp:45~60，探针实跑验证）
    m["attackable"] = []
    for _ in range(n):
        code = r.u32()
        at = {"con": r.u8(), "loc": r.u8(), "seq": r.u8()}
        m["attackable"].append({"code": code, "at": at, "direct": r.u8()})
    m["to_m2"] = r.u8()
    m["to_ep"] = r.u8()
    return m


def _decode_select_idlecmd(r, p):
    m = {"player": r.u8()}
    for key in ("summonable", "spsummonable", "repositionable", "msetable",
                "ssetable"):
        n = r.u32()
        entries = []
        for _ in range(n):
            code = r.u32()
            at = {"con": r.u8(), "loc": r.u8()}
            # repositionable 的 seq 是 u8，其余 u32（playerop.cpp:79~101）
            at["seq"] = r.u8() if key == "repositionable" else r.u32()
            entries.append({"code": code, "at": at})
        m[key] = entries
    m["activatable"] = _activatable_entries(r)
    m["to_bp"] = r.u8()
    m["to_ep"] = r.u8()
    m["can_shuffle"] = r.u8()
    return m


def _decode_select_effectyn(r, p):
    return {"player": r.u8(), "code": r.u32(), "at": r.loc_info(),
            "desc": r.u64()}


def _decode_select_yesno(r, p):
    return {"player": r.u8(), "desc": r.u64()}


def _decode_select_option(r, p):
    player = r.u8()
    n = r.u32()
    return {"player": player, "options": [r.u64() for _ in range(n)]}


def _decode_select_card(r, p):
    m = {"player": r.u8(), "cancelable": r.u8(), "min": r.u32(), "max": r.u32()}
    n = r.u32()
    m["cards"] = [r.card_entry() for _ in range(n)]
    return m


def _decode_select_tribute(r, p):
    # 与 SELECT_CARD 同构但条目不同：code u32 + con u8 + loc u8 + seq u32 +
    # release_param u8（无 pos，playerop.cpp:672~678）；应答格式与 SELECT_CARD
    # 相同（parse_response_cards）
    m = {"player": r.u8(), "cancelable": r.u8(), "min": r.u32(), "max": r.u32()}
    n = r.u32()
    m["cards"] = []
    for _ in range(n):
        code = r.u32()
        at = {"con": r.u8(), "loc": r.u8(), "seq": r.u32()}
        m["cards"].append({"code": code, "at": at,
                           "release_param": r.u8()})
    return m


def _decode_select_chain(r, p):
    m = {"player": r.u8(), "spe_count": r.u8(), "forced": r.u8(),
         "timing_p0": r.u32(), "timing_p1": r.u32()}
    n = r.u32()
    m["chains"] = [{"code": r.u32(), "at": r.loc_info(),
                    "desc": r.u64(), "mode": r.u8()} for _ in range(n)]
    return m


def _decode_select_place(r, p):
    return {"player": r.u8(), "count": r.u8(), "flag": r.u32()}

_decode_select_disfield = _decode_select_place


def _decode_select_position(r, p):
    return {"player": r.u8(), "code": r.u32(), "positions": r.u8()}


def _decode_select_sum(r, p):
    m = {"player": r.u8(), "op1": r.u8(), "op2": r.u8(), "sum": r.u32(),
         "min": r.u32(), "max": r.u32()}
    n = r.u32()
    m["must_cards"] = [r.card_entry(with_param=True) for _ in range(n)]
    n = r.u32()
    m["cards"] = [r.card_entry(with_param=True) for _ in range(n)]
    return m


def _decode_sort_card(r, p):
    player = r.u8()
    n = r.u32()
    cards = []
    for _ in range(n):
        cards.append({"code": r.u32(), "con": r.u8(), "loc": r.u32(),
                      "seq": r.u32()})  # 此列表 loc 为 u32（playerop.cpp:887~896）
    return {"player": player, "cards": cards}

_decode_sort_chain = _decode_sort_card


def _decode_select_unselect_card(r, p):
    m = {"player": r.u8(), "finishable": r.u8(), "cancelable": r.u8(),
         "min": r.u32(), "max": r.u32()}
    n = r.u32()
    m["select_cards"] = [r.card_entry() for _ in range(n)]
    n = r.u32()
    m["unselect_cards"] = [r.card_entry() for _ in range(n)]
    return m


def _decode_select_counter(r, p):
    m = {"player": r.u8(), "counter_type": r.u16(), "count": r.u16()}
    n = r.u32()
    m["cards"] = [r.entry_no_pos() for _ in range(n)]
    return m


def _decode_announce_number(r, p):
    player = r.u8()
    n = r.u8()
    return {"player": player, "options": [r.u64() for _ in range(n)]}


def _decode_announce_card(r, p):
    player = r.u8()
    n = r.u8()
    return {"player": player, "options": [r.u64() for _ in range(n)]}


def _decode_announce_race(r, p):
    return {"player": r.u8(), "count": r.u8(), "available": r.u64()}


def _decode_announce_attrib(r, p):
    return {"player": r.u8(), "count": r.u8(), "available": r.u32()}


# ---- 响应编码器（core 应答二进制；布局见 NOTES §5 / playerop.cpp 各 reader） ----

def encode_i32(v):
    return struct.pack("<i", v)


def encode_cancel():
    return encode_i32(-1)


def encode_yesno(accept):
    return encode_i32(1 if accept else 0)


def encode_position(pos):
    return encode_i32(pos)


def encode_idle(kind, cat_index):
    """IDLECMD: t | (s<<16)。t: 0召唤 1特召 2表示形式 3盖怪 4盖卡 5发动 6进BP 7EP 8洗牌"""
    t = {"summon": 0, "spsummon": 1, "reposition": 2, "mset": 3, "sset": 4,
         "activate": 5, "to_bp": 6, "to_ep": 7, "shuffle": 8}[kind]
    return encode_i32(t | (cat_index << 16))


def encode_battle(kind, cat_index):
    """BATTLECMD: t | (s<<16)。t: 0发动 1攻击 2M2 3EP"""
    t = {"activate": 0, "attack": 1, "to_m2": 2, "to_ep": 3}[kind]
    return encode_i32(t | (cat_index << 16))


def encode_card_indices(indices):
    """SELECT_CARD/TRIBUTE: i32 0 + u32 数量 + u32 索引表。"""
    return (struct.pack("<ii", 0, len(indices))
            + b"".join(struct.pack("<I", i) for i in indices))


def encode_place(picks):
    """SELECT_PLACE: 每项 3 字节 (player, LOCATION, seq)。"""
    out = b""
    for pick in picks:
        out += bytes([pick["player"], pick["loc"], pick["seq"]])
    return out


def decoded_count():
    return 79  # 与顶部覆盖清单一致（95 枚举 - 15 legacy - 1 TAG_SWAP）
