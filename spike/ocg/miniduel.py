#!/usr/bin/env python3
"""WO-005 P2 探针：脱离 EDOPro 客户端、纯 ocgcore 的最小对局驱动。

- 消息布局全部从 vendor/repos/ygopro-core 当前源码提取（spike/ocg/message_writers.txt）
- 缓冲格式：每条消息一块 [u32 len][payload]，顺序拼接（duel.cpp generate_buffer）
- 自动应答策略：玩家 0 = 进取（召唤→攻击→M2→EP），玩家 1 = 消极（直接 EP）
- 产出 transcript JSON 供 P2 验收复核
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
from ocgcore_ctypes import (OcgCore, LOCATION_MZONE, POS_FACEUP_ATTACK, DUEL_TEST_MODE)

MSG_NAMES = {
    1: "RETRY", 2: "HINT", 3: "WAITING", 4: "START", 5: "WIN", 6: "UPDATE_DATA",
    7: "UPDATE_CARD", 10: "SELECT_BATTLECMD", 11: "SELECT_IDLECMD",
    12: "SELECT_EFFECTYN", 13: "SELECT_YESNO", 14: "SELECT_OPTION",
    15: "SELECT_CARD", 16: "SELECT_CHAIN", 18: "SELECT_PLACE", 19: "SELECT_POSITION",
    20: "SELECT_TRIBUTE", 23: "SELECT_SUM", 26: "SELECT_UNSELECT_CARD",
    40: "NEW_TURN", 41: "NEW_PHASE", 50: "MOVE", 53: "POS_CHANGE", 54: "SET",
    60: "SUMMONING", 61: "SUMMONED", 62: "SPSUMMONING", 63: "SPSUMMONED",
    64: "FLIPSUMMONING", 70: "CHAINING", 71: "CHAINED", 72: "CHAIN_SOLVING",
    73: "CHAIN_SOLVED", 74: "CHAIN_END", 90: "DRAW", 91: "DAMAGE", 92: "RECOVER",
    94: "LPUPDATE", 110: "ATTACK", 111: "BATTLE", 112: "ATTACK_DISABLED",
    113: "DAMAGE_STEP_START", 114: "DAMAGE_STEP_END", 100: "PAY_LPCOST",
    162: "RELOAD_FIELD", 83: "BECOME_TARGET", 120: "MISSED_EFFECT",
    32: "SHUFFLE_DECK", 33: "SHUFFLE_HAND", 80: "CARD_SELECTED", 81: "RANDOM_SELECTED",
}
SELECT_MSGS = {10, 11, 12, 13, 14, 15, 16, 18, 19, 20, 23, 26}

PHASE_NAMES = {0x01: "DRAW", 0x02: "STANDBY", 0x04: "MAIN1", 0x08: "BATTLE_START",
               0x10: "BATTLE_STEP", 0x20: "DAMAGE", 0x40: "DAMAGE_CAL", 0x80: "BATTLE",
               0x100: "MAIN2", 0x200: "END"}


class ByteReader:
    def __init__(self, data):
        self.d = data
        self.o = 0

    def u8(self):
        v = self.d[self.o]; self.o += 1; return v

    def i8(self):
        v = struct.unpack_from("<b", self.d, self.o)[0]; self.o += 1; return v

    def u16(self):
        v = struct.unpack_from("<H", self.d, self.o)[0]; self.o += 2; return v

    def u32(self):
        v = struct.unpack_from("<I", self.d, self.o)[0]; self.o += 4; return v

    def u64(self):
        v = struct.unpack_from("<Q", self.d, self.o)[0]; self.o += 8; return v

    def loc_info(self):
        return {"con": self.u8(), "loc": self.u8(), "seq": self.u32(), "pos": self.u32()}

    def remaining(self):
        return len(self.d) - self.o

    def rest(self):
        v = self.d[self.o:]; self.o = len(self.d); return v


def split_chunks(buf):
    """[u32 len][payload]… -> [(len, payload)]"""
    out, off = [], 0
    while off < len(buf):
        (ln,) = struct.unpack_from("<I", buf, off); off += 4
        out.append(buf[off:off + ln]); off += ln
    return out


def decode(msg, p):
    """按 core 源码布局解码为 dict；返回 (dict, 消费字节数)。"""
    r = ByteReader(p)
    m = {"msg": msg, "name": MSG_NAMES.get(msg, f"UNK_{msg}")}
    if msg == 162:  # RELOAD_FIELD
        m["duel_options"] = r.u32()
        for pl in (0, 1):
            info = {"lp": r.u32(), "mzone": [], "szone": []}
            for _ in range(7):
                if r.u8():
                    pos = r.u8(); ov = r.u32()
                    info["mzone"].append({"pos": pos, "overlay": ov})
                else:
                    info["mzone"].append(None)
            for _ in range(8):
                if r.u8():
                    pos = r.u8(); ov = r.u32()
                    info["szone"].append({"pos": pos, "overlay": ov})
                else:
                    info["szone"].append(None)
            for k in ("deck", "hand", "grave", "removed", "extra", "extra_p"):
                info[k] = r.u32()
            m[f"p{pl}"] = info
        n = r.u32()
        m["chains"] = [{"code": r.u32(), "at": r.loc_info()} for _ in range(n)]
    elif msg == 40:  # NEW_TURN
        m["turn_player"] = r.u8()
    elif msg == 41:  # NEW_PHASE
        ph = r.u16()
        m["phase"] = ph
        m["phase_name"] = PHASE_NAMES.get(ph, hex(ph))
    elif msg in (90,):  # DRAW
        m["player"] = r.u8()
        n = r.u32()
        m["cards"] = [{"code": r.u32(), "pos": r.u32()} for _ in range(n)]
    elif msg in (91, 92, 94, 100):  # DAMAGE/RECOVER/LPUPDATE/PAY_LPCOST
        m["player"] = r.u8()
        m["amount"] = r.u32()
    elif msg in (60, 62, 54):  # SUMMONING/SPSUMMONING/SET
        m["code"] = r.u32()
        m["at"] = r.loc_info()
    elif msg == 50:  # MOVE
        m["code"] = r.u32()
        m["from"] = r.loc_info()
        m["to"] = r.loc_info()
        m["reason"] = r.u32()
    elif msg == 110:  # ATTACK
        m["attacker"] = r.loc_info()
        m["target"] = r.loc_info()
    elif msg == 111:  # BATTLE
        m["attacker"] = r.loc_info()
        m["aa"] = r.u32(); m["ad"] = r.u32(); m["bd0"] = r.u8()
        m["target"] = r.loc_info()
        m["da"] = r.u32(); m["dd"] = r.u32(); m["bd1"] = r.u8()
    elif msg == 5:  # WIN
        m["winner"] = r.u8()
        m["reason"] = r.u8()
    elif msg in (10,):  # SELECT_BATTLECMD
        m["player"] = r.u8()
        n = r.u32()
        # activatable 条目：code u32 + controler u8 + location u8 + seq u32 + desc u64 + mode u8
        m["activatable"] = [{"code": r.u32(), "con": r.u8(), "loc": r.u8(),
                             "seq": r.u32(), "desc": r.u64(), "mode": r.u8()}
                            for _ in range(n)]
        n = r.u32()
        m["attackable"] = [{"code": r.u32(), "con": r.u8(), "loc": r.u8(),
                            "seq": r.u8(), "direct": r.u8()} for _ in range(n)]
        m["to_m2"] = r.u8()
        m["to_ep"] = r.u8()
    elif msg in (11,):  # SELECT_IDLECMD
        m["player"] = r.u8()
        for key in ("summonable", "spsummonable", "repositionable", "msetable",
                    "ssetable"):
            n = r.u32()
            m[key] = []
            for _ in range(n):
                code = r.u32()
                con, loc = r.u8(), r.u8()
                # repositionable 的 seq 是 u8，其余 u32（playerop.cpp:79~101）
                seq = r.u8() if key == "repositionable" else r.u32()
                m[key].append({"code": code, "con": con, "loc": loc, "seq": seq})
        n = r.u32()
        # activatable 条目与 BATTLECMD 同构：code u32 + u8 + u8 + seq u32 + desc u64 + mode u8
        m["activatable"] = [{"code": r.u32(), "con": r.u8(), "loc": r.u8(),
                             "seq": r.u32(), "desc": r.u64(), "mode": r.u8()}
                            for _ in range(n)]
        m["to_bp"] = r.u8(); m["to_ep"] = r.u8(); m["can_shuffle"] = r.u8()
    elif msg == 15 or msg == 20:  # SELECT_CARD / SELECT_TRIBUTE
        m["player"] = r.u8()
        m["cancelable"] = r.u8()
        m["min"] = r.u32(); m["max"] = r.u32()
        n = r.u32()
        m["cards"] = [{"code": r.u32(), "at": r.loc_info()} for _ in range(n)]
    elif msg == 18:  # SELECT_PLACE
        m["player"] = r.u8()
        m["count"] = r.u8()
        m["flag"] = r.u32()
    elif msg == 19:  # SELECT_POSITION
        m["player"] = r.u8()
        m["code"] = r.u32()
        m["positions"] = r.u8()
    elif msg == 12:  # SELECT_EFFECTYN
        m["player"] = r.u8(); m["code"] = r.u32(); m["at"] = r.loc_info(); m["desc"] = r.u64()
    elif msg == 13:  # SELECT_YESNO
        m["player"] = r.u8(); m["desc"] = r.u64()
    elif msg == 14:  # SELECT_OPTION
        m["player"] = r.u8(); n = r.u32()
        m["options"] = [r.u64() for _ in range(n)]
    elif msg == 16:  # SELECT_CHAIN
        m["player"] = r.u8(); m["spe_count"] = r.u8(); m["forced"] = r.u8()
        m["timing_p0"] = r.u32(); m["timing_p1"] = r.u32()
        n = r.u32()
        m["chains"] = [{"code": r.u32(), "at": r.loc_info(), "desc": r.u64(),
                        "mode": r.u8()} for _ in range(n)]
    else:
        m["hex"] = p.hex()
        m["_raw_len"] = len(p)
        return m, len(p)
    m["_consumed"] = r.o
    return m, r.o


class MinDuel:
    """最小对局驱动：跑完一局 + 全程 transcript + 状态断言。"""

    def __init__(self, core, deck0, deck1, lp=8000, start_hand=5, setup_lua=None):
        self.core = core
        self.lp = lp
        self.transcript = []
        self.lp_state = {0: lp, 1: lp}
        self.turn = 0
        self.turn_player = 0
        self.phase = 0
        self.draws = {0: [], 1: []}
        self.summons = []
        self.battles = []
        self.retries = 0
        self.winner = None
        self.win_reason = None
        self.over = False
        self.pending_select = None
        self.summoned_this_turn = {0: False, 1: False}
        self.last_select_name = None
        self.attack_declared = False
        core.create_duel(flags=DUEL_TEST_MODE, lp=lp, start_hand=start_hand)
        for code in deck0:
            core.new_card(0, code, 0x01)  # LOCATION_DECK
        for code in deck1:
            core.new_card(1, code, 0x01)
        if setup_lua:
            # 预置脚本须在 StartDuel 之前载入（EDOPro 谜题同序）
            blob = setup_lua.encode()
            if not core.dll.OCG_LoadScript(core.duel, blob, len(blob), b"prescript"):
                raise RuntimeError("prescript 加载失败")
        core.start()

    # ---- 消息处理 ----
    def _handle(self, m):
        t = m["msg"]
        if t == 162:
            self.lp_state = {0: m["p0"]["lp"], 1: m["p1"]["lp"]}
        elif t == 40:
            self.turn_player = m["turn_player"]
            self.turn += 1
            self.summoned_this_turn = {0: False, 1: False}
            self.attack_declared = False
        elif t == 41:
            self.phase = m["phase"]
        elif t in (91, 92):  # DAMAGE/RECOVER
            sign = -1 if t == 91 else 1
            self.lp_state[m["player"]] += sign * m["amount"]
        elif t in (94,):  # LPUPDATE
            self.lp_state[m["player"]] = m["amount"]
        elif t == 90:
            self.draws[m["player"]].append({"turn": self.turn,
                                            "count": len(m["cards"])})
        elif t in (60, 62):
            self.summons.append({"turn": self.turn, "player": m["at"]["con"],
                                 "code": m["code"], "seq": m["at"]["seq"],
                                 "pos": m["at"]["pos"]})
        elif t in (110, 111):
            self.battles.append({"turn": self.turn, "msg": m["name"], **{
                k: m.get(k) for k in ("attacker", "target", "aa", "da")}})
            if t == 110:
                self.attack_declared = True
        elif t == 1:
            self.retries += 1
        elif t == 5:
            self.winner, self.win_reason = m["winner"], m["reason"]
            self.over = True
        if t in SELECT_MSGS:
            self.pending_select = m

    def pump(self):
        """process 一次并解码全部消息。返回 status。"""
        status = self.core.process()
        for chunk in split_chunks(self.core.get_message()):
            mid = chunk[0]
            m, consumed = decode(mid, chunk[1:])
            if consumed + 1 != len(chunk):
                m["parse_error"] = f"consumed {consumed}/{len(chunk)-1}"
                m["hex_tail"] = chunk[1:][consumed:].hex()
                raise RuntimeError(f"消息解析长度不符: {m['name']}: {m}")
            self.transcript.append(m)
            self._handle(m)
        return status

    # ---- 自动应答 ----
    def _answer(self, m):
        me = m.get("player", 0)
        aggressive = (me == 0)
        t = m["msg"]
        if t == 11:  # IDLECMD
            if aggressive and m["summonable"] and not self.summoned_this_turn[me]:
                self.summoned_this_turn[me] = True
                return struct.pack("<i", 0 | (0 << 16))
            if aggressive and m["to_bp"]:
                return struct.pack("<i", 6)
            if m["to_ep"]:
                return struct.pack("<i", 7)
            return struct.pack("<i", 6)
        if t == 10:  # BATTLECMD
            if aggressive and m["attackable"]:
                idx = next((i for i, c in enumerate(m["attackable"]) if c["direct"]),
                           0)
                return struct.pack("<i", 1 | (idx << 16))
            if m["to_m2"]:
                return struct.pack("<i", 2)
            return struct.pack("<i", 3)
        if t == 18:  # SELECT_PLACE：flag 位=1 为禁用（operations.cpp: `flag | ~0x1f`）；
            #            己方 MZONE 位 0~6、SZONE 位 8~15，选最低可用
            flag = m["flag"]
            for seq in range(7):
                if (flag & (1 << seq)) == 0:
                    return bytes([me, 0x04, seq])
            for seq in range(8):
                if (flag & (0x100 << seq)) == 0:
                    return bytes([me, 0x08, seq])
            raise RuntimeError(f"SELECT_PLACE 无可用怪兽区 flag={flag:08x}")
        if t == 19:
            return struct.pack("<i", POS_FACEUP_ATTACK)
        if t in (15, 20):  # SELECT_CARD/TRIBUTE
            n = min(m["min"], len(m["cards"])) if m["min"] else 0
            if n == 0 and m["cancelable"]:
                return struct.pack("<i", -1)
            out = struct.pack("<ii", 0, n) + b"".join(
                struct.pack("<I", i) for i in range(n))
            return out
        if t == 12:  # SELECT_EFFECTYN：唯一可选触发以此询问（非 SELECT_CHAIN）→ 接受
            return struct.pack("<i", 1)
        if t == 13:  # SELECT_YESNO：否
            return struct.pack("<i", 0)
        if t == 14:
            return struct.pack("<i", 0)
        if t == 16:  # SELECT_CHAIN：不连锁 = -1（0 是选中第 0 条链，playerop.cpp:492）
            return struct.pack("<i", -1)
        if t == 26:  # SELECT_UNSELECT_CARD
            return struct.pack("<i", -1)
        raise RuntimeError(f"未实现的应答消息: {m['name']}")

    def _answer_passive(self, m):
        """WIN 后的残留询问：能拒绝就拒绝，不能就选最小动作，不开新行为。"""
        t = m["msg"]
        if t == 11:  # IDLECMD：直接终了
            return struct.pack("<i", 7 if m["to_ep"] else 6)
        if t == 10:  # BATTLECMD：终了
            return struct.pack("<i", 3 if m["to_ep"] else 2)
        if t == 18:  # SELECT_PLACE：同进取分支
            flag = m["flag"]
            for seq in range(7):
                if (flag & (1 << seq)) == 0:
                    return bytes([m["player"], 0x04, seq])
        if t == 19:
            return struct.pack("<i", POS_FACEUP_ATTACK)
        if t in (15, 20):
            if m["cancelable"]:
                return struct.pack("<i", -1)
            n = m["min"]
            return struct.pack("<ii", 0, n) + b"".join(
                struct.pack("<I", i) for i in range(n))
        if t in (12, 13, 14):
            return struct.pack("<i", 0)
        if t in (16, 26):
            return struct.pack("<i", -1)
        raise RuntimeError(f"WIN 后未实现的消极应答: {m['name']}")

    def run(self, max_turns=12):
        last_answer = None
        for _ in range(20000):
            status = self.pump()
            if self.retries:
                raise RuntimeError(
                    f"出现 MSG_RETRY：响应被 core 拒绝。last_select="
                    f"{self.last_select_name} answer={last_answer.hex() if last_answer else '-'}")
            if self.over:
                # 契约：core 的 END 仅表示"处理单元耗尽"；胜负终局由宿主在收到
                # MSG_WIN 后停止驱动（EDOPro 客户端同样如此）。WIN 后 core 可能还有
                # 残留处理单元/询问，宿主不应再喂新动作。
                return "END"
            if status == 0:  # END
                return "END"
            if status == 1:  # AWAITING
                if not self.pending_select:
                    raise RuntimeError("AWAITING 但未发现待答选择消息")
                last_answer = self._answer(self.pending_select)
                self.last_select_name = self.pending_select["name"]
                self.core.set_response(last_answer)
                self.pending_select = None
            if self.turn > max_turns:
                raise RuntimeError(f"超过 {max_turns} 回合未结束")
        raise RuntimeError("process 次数超限")

    # ---- 验收断言 ----
    def verify(self, expect_winner=0):
        checks = {}

        def check(name, ok, detail=""):
            checks[name] = {"pass": bool(ok), "detail": detail}

        check("无 RETRY", self.retries == 0, f"retries={self.retries}")
        check("决斗已结束", self.winner is not None,
              f"winner={self.winner} reason={self.win_reason}")
        check("赢家符合预期", self.winner == expect_winner,
              f"winner={self.winner}")
        check("对手 LP 归零", self.lp_state[1 - expect_winner] == 0,
              f"LP={self.lp_state}")
        our_summons = [s for s in self.summons if s["player"] == 0]
        check("发生通常召唤", len(our_summons) > 0, f"{our_summons[:2]}")
        check("发生攻击", any(b["msg"] == "ATTACK" for b in self.battles),
              f"{len(self.battles)} 条战斗消息")
        dmg = [t for t in self.transcript
               if t["msg"] == 91 and t["player"] == 1]
        check("对手受到战斗伤害", sum(d["amount"] for d in dmg) >= 8000,
              f"伤害明细={[(d['amount']) for d in dmg]}")
        check("回合数≥3", self.turn >= 3, f"turns={self.turn}")
        t1_draw = [d for d in self.draws[0] if d["turn"] == 1]
        check("先攻第 1 回合无抽牌（现行规则）", not t1_draw, f"{t1_draw}")
        return checks


DECK_A = [14575467, 47226949, 43096270]  # Zombino / Leotron / Alexandrite Dragon
def make_deck():
    # 40 张（避免小卡组 deck out 干扰 P2 战斗验证）
    return (DECK_A * 13 + DECK_A[:1])[:40]

def run_min_duel(verbose=True):
    core = OcgCore()
    d = MinDuel(core, make_deck(), make_deck())
    ver_major = ctypes_major = None
    ma = __import__("ctypes").c_int(); mi = __import__("ctypes").c_int()
    core.dll.OCG_GetVersion(__import__("ctypes").byref(ma), __import__("ctypes").byref(mi))
    d.run()
    checks = d.verify()
    transcript = {
        "probe": "WO-005 P2 最小对局",
        "core_api_version": f"{ma.value}.{mi.value}",
        "core_commit": "efc21aa433b88cd35b7c37db4072a35c58d9d435",
        "duel_flags": "DUEL_TEST_MODE(0x1)，MR5 默认规则",
        "seed": [0x20260925, 1, 2, 3],
        "deck": {"p0": make_deck(), "p1": make_deck()},
        "final": {"lp": d.lp_state, "turns": d.turn, "winner": d.winner,
                  "win_reason": d.win_reason, "retries": d.retries},
        "verification": checks,
        "first_turn_draw_p0": [x for x in d.draws[0] if x["turn"] == 1],
        "transcript": d.transcript,
        "script_log": core.log_lines[:50],
    }
    out = os.path.join(os.path.dirname(__file__), "out", "p2_transcript.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(transcript, f, ensure_ascii=False, indent=1)
    if verbose:
        all_pass = all(c["pass"] for c in checks.values())
        print(f"P2 最小对局：{'全部断言通过' if all_pass else '存在失败断言'}")
        for k, v in checks.items():
            print(f"  [{'PASS' if v['pass'] else 'FAIL'}] {k} — {v['detail']}")
        print(f"transcript -> {out}")
    core.destroy()
    return transcript


if __name__ == "__main__":
    run_min_duel()
