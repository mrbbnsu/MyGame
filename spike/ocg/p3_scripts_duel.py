#!/usr/bin/env python3
"""WO-005 P3 探针：CardScripts 真实卡效果验证（零自研效果逻辑）。

验证链路：Card ID → official/c{id}.lua → ocgcore 执行 → 结局可观测
用 Debug.AddCard 预置脚本（EDOPro 谜题模式同款机制）做确定性开局。

卡表（7 张，覆盖 P3 要求的全部类别）：
  55144522 强欲之壶 Pot of Greed    通常魔法：抽 2（抽牌）
  53129443 黑洞 Dark Hole           通常魔法：破坏全场怪兽（破坏）
  83764718 死者苏生 Monster Reborn  通常魔法：从对方墓地特召（墓地特召）
  83011277 杀人番茄 Mystic Tomato   触发：被战斗破坏→卡组特召 DARK（简单触发）
  44095762 圣防 Mirror Force        通常陷阱：破坏对方全场攻表（简单陷阱）
  70046172 突进 Rush Recklessly     通常陷阱：ATK+700（改变 ATK）
  32864 第 13 号墓 The 13th Grave   DARK 1200/900（番茄特召目标+战斗棋子）
  47226949 Leotron                  2000/0 通常怪兽（p1 主力 + 苏生目标）
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
from ocgcore_ctypes import (LOCATION_DECK, LOCATION_GRAVE, LOCATION_HAND,
                            LOCATION_MZONE, OcgCore, QUERY_ATTACK, QUERY_CODE,
                            QUERY_POSITION, QUERY_TYPE)
from miniduel import MinDuel, split_chunks

TOMATO, GRAVE, LEOTRON = 83011277, 32864, 47226949
POT, DARKHOLE, REBORN, MF, RUSH = 55144522, 53129443, 83764718, 44095762, 70046172

SETUP_LUA = """\
-- WO-005 P3 确定性开局（EDOPro 谜题 pre-script 同款）
Debug.AddCard({TOMATO},0,0,{HAND},0,0xA)
Debug.AddCard({RUSH},0,0,{HAND},0,0xA)
Debug.AddCard({MF},0,0,{HAND},0,0xA)
Debug.AddCard({POT},0,0,{HAND},0,0xA)
Debug.AddCard({REBORN},0,0,{HAND},0,0xA)
Debug.AddCard({DARKHOLE},0,0,{HAND},0,0xA)
Debug.AddCard({GRAVE},0,0,{DECK},0,0xA)
for _i=1,8 do Debug.AddCard({LEOTRON},0,0,{DECK},0,0xA) end
Debug.AddCard({LEOTRON},0,0,{DECK},0,0xA)
Debug.AddCard({LEOTRON},0,0,{DECK},0,0xA)
Debug.AddCard({LEOTRON},0,0,{DECK},0,0xA)
Debug.AddCard({LEOTRON},1,1,{HAND},0,0xA)
Debug.AddCard({LEOTRON},1,1,{DECK},0,0xA)
Debug.AddCard({LEOTRON},1,1,{DECK},0,0xA)
Debug.AddCard({LEOTRON},1,1,{DECK},0,0xA)
""".format(TOMATO=TOMATO, RUSH=RUSH, MF=MF, POT=POT, REBORN=REBORN,
           DARKHOLE=DARKHOLE, GRAVE=GRAVE, LEOTRON=LEOTRON,
           HAND=LOCATION_HAND, DECK=LOCATION_DECK)

# 计划：{(turn, player): [动作…]}；先攻方回合为奇数 1,3,5,7
PLAN = {
    (1, 0): [f"summon {TOMATO}", f"set {RUSH}", f"set {MF}", "ep"],
    (2, 1): ["ep"],
    (3, 0): [f"activate {POT}", f"attack {TOMATO} direct", "ep"],
    (4, 1): [f"summon {LEOTRON}", "ep"],
    (5, 0): [f"attack {TOMATO} {LEOTRON}", "ep"],
    (6, 1): [f"attack {LEOTRON} {GRAVE} chains={RUSH}:{GRAVE},{MF}", "ep"],
    (7, 0): [f"activate {REBORN} target={LEOTRON}", f"activate {DARKHOLE}", "ep"],
}


class ScenarioDuel(MinDuel):
    """按 PLAN 驱动的脚本化对局；证据收集进 self.evidence。"""

    def __init__(self, core, setup_lua):
        super().__init__(core, [], [], lp=8000, start_hand=0, setup_lua=setup_lua)
        self.evidence = {}
        self.plan = {k: list(v) for k, v in PLAN.items()}
        self.pending_attack = None
        self.expected_target = None
        self.chain_queue = []
        self.chain_targets = {}

    # ---- 工具 ----
    def hand(self, p):
        return self.core.query_location(p, LOCATION_HAND)

    def field_cards(self, p):
        return self.core.query_location(p, LOCATION_MZONE)

    def record(self, key, value):
        self.evidence[key] = value

    # ---- 应答 ----
    def _do_action(self, m, action):
        me = m["player"]
        parts = action.split()
        verb = parts[0]
        if verb in ("summon", "set", "activate"):
            code = int(parts[1])
            for part in parts[2:]:
                if part.startswith("target="):
                    self.expected_target = int(part[7:])
            key, t = {"summon": ("summonable", 0), "set": ("ssetable", 4),
                      "activate": ("activatable", 5)}[verb]
            idx = next((i for i, c in enumerate(m[key]) if c["code"] == code), None)
            if idx is None:
                raise RuntimeError(f"{verb} {code} 不在 {key} 列表: {[c['code'] for c in m[key]]}")
            self.record(f"action.{verb}.{code}", True)
            return struct.pack("<i", t | (idx << 16))
        if verb == "attack":
            code = int(parts[1])
            self.pending_attack = code
            self.expected_target = (int(parts[2])
                                    if len(parts) > 2 and parts[2] != "direct" else None)
            self.chain_queue = []
            self.chain_targets = {}
            for part in parts[3:]:
                if part.startswith("chains="):
                    for item in part[7:].split(","):
                        if ":" in item:
                            c, tg = item.split(":")
                            self.chain_queue.append(int(c))
                            self.chain_targets[int(c)] = int(tg)
                        else:
                            self.chain_queue.append(int(item))
            return struct.pack("<i", 6)  # 进战斗阶段
        if verb == "ep":
            return struct.pack("<i", 7 if m["to_ep"] else 6)
        raise RuntimeError(f"未知动作 {action}")

    def _answer(self, m):
        t = m["msg"]
        me = m.get("player", 0)
        if t == 11:  # IDLECMD 一律走计划
            return self._idle(m)
        # 攻击声明后的战斗指令
        if t == 10:
            code = self.pending_attack
            self.pending_attack = None
            if code is not None:
                idx = next((i for i, c in enumerate(m["attackable"])
                            if c["code"] == code), None)
                if idx is not None:
                    return struct.pack("<i", 1 | (idx << 16))
            if m["to_ep"]:
                return struct.pack("<i", 3)
            return struct.pack("<i", 2 if m["to_m2"] else 3)
        # 连锁：仅在攻击已宣告后按 chain_queue 消费；强制触发（番茄）必接；否则不连锁
        if t == 16:
            if me == 0 and self.attack_declared and self.chain_queue:
                want = self.chain_queue[0]
                idx = next((i for i, c in enumerate(m["chains"])
                            if c["code"] == want), None)
                if idx is not None:
                    self.chain_queue.pop(0)
                    self.record(f"action.chain.{want}", True)
                    self.expected_target = self.chain_targets.get(want)
                    return struct.pack("<i", idx)
            if me == 0 and TOMATO in [c["code"] for c in m["chains"]]:
                idx = next(i for i, c in enumerate(m["chains"])
                           if c["code"] == TOMATO)
                self.record("action.trigger.tomato", True)
                return struct.pack("<i", idx)
            return struct.pack("<i", -1)
        # 选卡：有期望目标就选它，否则按 min
        if t in (15, 20):
            if self.expected_target is not None:
                idx = next((i for i, c in enumerate(m["cards"])
                            if c["code"] == self.expected_target), None)
                if idx is not None:
                    self.record(f"action.select.{self.expected_target}", True)
                    self.expected_target = None
                    return struct.pack("<ii", 0, 1) + struct.pack("<I", idx)
                self.expected_target = None
            n = m["min"]
            if n == 0 and m["cancelable"]:
                return struct.pack("<i", -1)
            return struct.pack("<ii", 0, n) + b"".join(
                struct.pack("<I", i) for i in range(n))
        return super()._answer(m)

    def _idle(self, m):
        me = m["player"]
        key = (self.turn, me)
        acts = self.plan.get(key)
        if acts:
            action = acts.pop(0)
            ans = self._do_action(m, action)
            # 黑洞结算验收点：T7 p0 的 ep（结算完成后的 IDLECMD）时查场
            if (action == "ep" and self.turn == 7 and me == 0
                    and self.evidence.get("action.activate.53129443")
                    and not self.evidence.get("darkhole.verified")):
                ev = {"p0": [c.get(QUERY_CODE) for c in self.field_cards(0)],
                      "p1": [c.get(QUERY_CODE) for c in self.field_cards(1)]}
                self.record("darkhole.after", ev)
                self.evidence["darkhole.verified"] = True
            return ans
        if me == 1:  # p1 默认消极
            return struct.pack("<i", 7 if m["to_ep"] else 6)
        return struct.pack("<i", 7 if m["to_ep"] else 6)

    def _handle(self, m):
        t = m["msg"]
        super()._handle(m)
        # 抽牌证据：p0 一回合内 count=2 的 DRAW（强欲之壶）
        if t == 90 and m["player"] == 0 and len(m["cards"]) == 2:
            self.record("pot.draw2", {"turn": self.turn,
                                      "codes": [c["code"] for c in m["cards"]]})
        # 特召证据
        if t in (62, 60) and m["msg"] == 62:
            self.evidence.setdefault("spsummon", []).append(
                {"turn": self.turn, "code": m["code"], "con": m["at"]["con"]})

    def _post_assert_t3(self):
        """T6 p1 战斗空转时：验证突进加攻 + 镜反清场。"""
        ev = self.evidence
        ours = self.field_cards(0)
        ev["t3_raw_query"] = ours
        grave_on_field = next((c for c in ours if c.get(QUERY_CODE) == GRAVE), None)
        ev["rush.atk_on_field"] = grave_on_field and grave_on_field.get(QUERY_ATTACK)
        theirs = self.field_cards(1)
        ev["mirror.p1_mzone"] = [c.get(QUERY_CODE) for c in theirs]

    def run_scenario(self, max_turns=10):
        for _ in range(20000):
            status = self.pump()
            # T3 p1 战斗阶段空转的时机点做场面查询
            if (not self.evidence.get("t5_checked") and self.turn == 6
                    and status == 1 and self.pending_select
                    and self.pending_select["msg"] == 10
                    and self.pending_select["player"] == 1
                    and not self.pending_select["attackable"]):
                self._post_assert_t3()
                self.evidence["t5_checked"] = True
            if self.evidence.get("darkhole.verified"):
                return "SCENARIO_DONE"
            if self.retries:
                raise RuntimeError(f"MSG_RETRY：{self.last_select_name}")
            if self.over:
                return "END"
            if status == 0:
                return "END"
            if status == 1:
                if not self.pending_select:
                    raise RuntimeError("AWAITING 但无待答消息")
                if self.pending_select["msg"] == 11 and not self.plan.get(
                        (self.turn, self.pending_select["player"])):
                    pass
                ans = self._answer(self.pending_select)
                self.last_select_name = self.pending_select["name"]
                self.core.set_response(ans)
                self.pending_select = None
            if self.turn > max_turns:
                raise RuntimeError(f"超过 {max_turns} 回合")


def main():
    core = OcgCore()
    d = ScenarioDuel(core, SETUP_LUA)
    d.run_scenario()
    ev = d.evidence

    checks = {}

    def check(name, ok, detail=""):
        checks[name] = {"pass": bool(ok), "detail": str(detail)[:200]}

    # 1. 强欲之壶：抽 2
    pot = ev.get("pot.draw2", {})
    check("55144522 强欲之壶：抽 2 张", pot.get("codes") is not None, pot)
    # 2. 杀人番茄触发：从卡组特召第13号墓
    sp = [s for s in ev.get("spsummon", []) if s["code"] == GRAVE and s["con"] == 0]
    check("83011277 杀人番茄：战斗破坏→卡组特召 32864",
          bool(sp) and ev.get("action.select.32864"), sp)
    # 3. 突进：+700
    atk = ev.get("rush.atk_on_field")
    check("70046172 突进：32864 ATK 1200→1900", atk == 1900, atk)
    check("70046172 突进：连锁发动成功", ev.get("action.chain.70046172"), "")
    # 4. 圣防：p1 场面清空
    mzone = ev.get("mirror.p1_mzone")
    check("44095762 圣防：p1 怪兽区清空", mzone == [], mzone)
    check("44095762 圣防：连锁发动成功", ev.get("action.chain.44095762"), "")
    # 5. 死者苏生：从 p1 墓地特召 Leotron
    reb = [s for s in ev.get("spsummon", []) if s["code"] == LEOTRON and s["con"] == 0]
    check("83764718 死者苏生：特召对方墓地 47226949",
          bool(reb) and ev.get("action.select.47226949"), reb)
    # 6. 黑洞：全场清空
    check("53129443 黑洞：双方怪兽区清空",
          ev.get("darkhole.after", {}).get("p0") == []
          and ev.get("darkhole.after", {}).get("p1") == [],
          ev.get("darkhole.after"))
    # 战斗伤害背景验证
    check("直接攻击造成战斗伤害(8000-1400)",
          d.lp_state[1] == 8000 - 1400, d.lp_state)
    check("无 RETRY", d.retries == 0, d.retries)

    out = os.path.join(os.path.dirname(__file__), "out", "p3_transcript.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({
            "probe": "WO-005 P3 CardScripts 验证",
            "cards": {"55144522": "Pot of Greed", "53129443": "Dark Hole",
                      "83764718": "Monster Reborn", "83011277": "Mystic Tomato",
                      "44095762": "Mirror Force", "70046172": "Rush Recklessly",
                      "32864": "The 13th Grave", "47226949": "Leotron"},
            "final_lp": d.lp_state, "turns": d.turn, "evidence": ev,
            "verification": checks,
            "script_log": core.log_lines[:50],
            "transcript_msgs": len(d.transcript),
        }, f, ensure_ascii=False, indent=1, default=str)
    all_pass = all(c["pass"] for c in checks.values())
    print(f"P3 CardScripts：{'全部断言通过' if all_pass else '存在失败'}")
    for k, v in checks.items():
        print(f"  [{'PASS' if v['pass'] else 'FAIL'}] {k} — {v['detail']}")
    print(f"transcript -> {out}")
    core.destroy()
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
