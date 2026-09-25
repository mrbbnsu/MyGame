#!/usr/bin/env python3
"""E1/WO-007 自测：无 TS 依赖，进程内直接调 service 函数（工单 §2 交付物）。

覆盖（工单 §5 验收 1 的 Python 半边 + 功能要求）：
  1. 绑定：DLL 加载、API 版本、DLL 缺失 -> 结构化错误
  2. 解码器：95 命名、覆盖 >=40、手工编码消息解码、UNKNOWN/DECODE_ERROR 回退
  3. 服务健壮性：非法请求结构化报错且进程存活；EOF 语义由集成测试覆盖
  4. 完整对局：自动应答打完整局，winner/reason 正确、零 MSG_RETRY
  5. 信息隐藏（K3）：对手手牌 code=null 数量保留；盖卡 code=null；己方可见
  6. 确定性：同 seed + 同应答脚本 -> 两局事件流逐字节一致
运行：python -X utf8 adapter/selftest.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core_binding as cb
import decoder
import service as svc
from core_binding import AdapterError, Config, OcgCore

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 卡组：普通怪为主 + 效果卡（强欲之壶 55144522 / 死者苏生 83764718 / 圣防 44095762）
VANILLA = [14575467, 47226949, 43096270]   # Zombino / Leotron / Alexandrite Dragon
POT, REBORN, MF = 55144522, 83764718, 44095762
SEED = [0x20260925, 1, 2, 3]


def make_deck():
    return (VANILLA * 9 + [POT] * 4 + [REBORN] * 4 + [MF] * 3)[:40]


CHECKS = []


def check(name, ok, detail=""):
    CHECKS.append((name, bool(ok), str(detail)[:160]))
    return bool(ok)


# ---------------- 自动应答策略（确定性脚本） ----------------

class Policy:
    """纯函数式于 pending + 少量跨请求记忆；同 seed 同策略 = 同应答脚本。"""

    def __init__(self, sset_p1=True):
        self.sset_p1 = sset_p1
        self.activated = set()

    def respond(self, state):
        p = state["pending"]
        if p is None:
            return None
        t, me = p["type"], p["player"]
        aggressive = me == 0
        if t == "IDLE":
            if aggressive:
                act = next((i for i, c in enumerate(p["choices"])
                            if c["kind"] == "activate"), None)
                if act is not None:
                    return {"choice": act}
                sm = next((i for i, c in enumerate(p["choices"])
                           if c["kind"] == "summon"), None)
                if sm is not None:
                    return {"choice": sm}
                bp = next((i for i, c in enumerate(p["choices"])
                           if c["kind"] == "to_bp"), None)
                if bp is not None:
                    return {"choice": bp}
            else:
                if self.sset_p1:
                    ss = next((i for i, c in enumerate(p["choices"])
                               if c["kind"] == "sset"), None)
                    if ss is not None:
                        self.sset_p1 = False
                        return {"choice": ss}
                    ms = next((i for i, c in enumerate(p["choices"])
                               if c["kind"] == "mset"), None)
                    if ms is not None:
                        return {"choice": ms}
            ep = next((i for i, c in enumerate(p["choices"])
                       if c["kind"] == "to_ep"), None)
            return {"choice": ep if ep is not None else len(p["choices"]) - 1}
        if t == "SELECT_BATTLE":
            if aggressive:
                atk = next((i for i, c in enumerate(p["choices"])
                            if c["kind"] == "attack"), None)
                if atk is not None:
                    return {"choice": atk}
                m2 = next((i for i, c in enumerate(p["choices"])
                           if c["kind"] == "to_m2"), None)
                if m2 is not None:
                    return {"choice": m2}
            ep = next((i for i, c in enumerate(p["choices"])
                       if c["kind"] == "to_ep"), None)
            return {"choice": ep if ep is not None else len(p["choices"]) - 1}
        if t == "SELECT_CHAIN":
            return {"cancel": True}          # 双方一律不连锁
        if t == "EFFECT_YESNO":
            return {"choice": 0 if aggressive else 1}   # p0 接受 / p1 拒绝
        if t == "SELECT_YESNO":
            return {"choice": 1}             # 统一 decline
        if t == "SELECT_CARD":
            if p["cancelable"] and p["min"] == 0:
                return {"cancel": True}
            return {"choice": list(range(min(p["min"], len(p["choices"]))))}
        if t == "SELECT_PLACE":
            return {"choice": 0}
        if t == "SELECT_POSITION":
            first = next((i for i, c in enumerate(p["choices"])
                          if c["pos"] == "faceup_attack"), 0)
            return {"choice": first}
        if t == "SELECT_OPTION":
            return {"choice": 0}
        if t == "SELECT_OTHER":
            if p["cancelable"]:
                return {"cancel": True}
            raise AssertionError(f"策略无法应答 SELECT_OTHER: {p['msg']}")
        raise AssertionError(f"未知 pending 类型: {t}")


def play_full_game(service, viewer=None, max_steps=4000):
    """自动应答打完整局。返回 (all_events, final_state, steps)。"""
    res = service.handle_request(
        {"id": 1, "cmd": "new_duel",
         "decks": [make_deck(), make_deck()],
         "opts": {"lp": 8000, "start_hand": 5, "seed": SEED}})
    assert res["ok"], res
    all_events = list(res["result"]["events"])
    policy = Policy()
    steps = 0
    while steps < max_steps:
        state = service.handle_request(
            {"id": 2, "cmd": "get_state", "viewer": viewer})["result"]["state"]
        if state["winner"] is not None:
            return all_events, state, steps
        p = state["pending"]
        if p is None:
            raise AssertionError("无 winner 但也无 pending —— 驱动停摆")
        body = policy.respond(state)
        body.update({"id": 3, "cmd": "respond"})
        if viewer is not None:
            body["viewer"] = viewer
        res = service.handle_request(body)
        assert res["ok"], f"respond 失败: {res}"
        all_events.extend(res["result"]["events"])
        steps += 1
    raise AssertionError(f"超过 {max_steps} 步未结束")


def canon(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


# ---------------- 各测试节 ----------------

def test_binding():
    core = OcgCore()
    v = core.version()
    check("绑定: DLL 加载且 API 版本 11.0", v == "11.0", v)
    core.destroy()
    bad = Config(dll=os.path.join(REPO, "no", "such.dll"))
    try:
        OcgCore(bad)
        check("绑定: DLL 缺失 -> DLL_NOT_FOUND", False, "未抛错")
    except AdapterError as e:
        check("绑定: DLL 缺失 -> DLL_NOT_FOUND", e.code == "DLL_NOT_FOUND", e.code)


def test_decoder():
    check("解码器: 95 枚举命名齐全", len(decoder.MSG_NAMES) == 95,
          len(decoder.MSG_NAMES))
    real_decoders = [n for n in dir(decoder) if n.startswith("_decode_")]
    # 去掉别名（= 赋值的共享实现），按顶层覆盖清单计数
    check("解码器: 覆盖 >= 40", decoder.decoded_count() >= 40,
          f"声明 {decoder.decoded_count()} / 实现函数 {len(real_decoders)}")
    # 手工编码: NEW_PHASE
    ev = decoder.decode_message(bytes([41, 0x04, 0]))
    check("解码器: NEW_PHASE", ev["type"] == "NEW_PHASE"
          and ev["phase_name"] == "MAIN1", ev)
    # 手工编码: MOVE（code + from + to + reason）
    payload = bytes([50]) + (123).to_bytes(4, "little") + bytes(
        [0, 0x02]) + (3).to_bytes(4, "little") + (1).to_bytes(4, "little") + \
        bytes([1, 0x04]) + (2).to_bytes(4, "little") + (1).to_bytes(4, "little") \
        + (0).to_bytes(4, "little")
    ev = decoder.decode_message(payload)
    check("解码器: MOVE", ev["type"] == "MOVE"
          and ev["to"]["seq"] == 2, ev)
    # 未知枚举 -> UNKNOWN
    ev = decoder.decode_message(bytes([99, 0xAA, 0xBB]))
    check("解码器: 未知枚举 -> UNKNOWN + raw_size",
          ev["type"] == "UNKNOWN" and ev["raw_size"] == 2, ev)
    # 已知消息坏长度 -> DECODE_ERROR（服务不崩的前提）
    ev = decoder.decode_message(bytes([13, 1]))  # SELECT_YESNO 需 u64 desc
    check("解码器: 布局不足 -> DECODE_ERROR", ev["type"] == "DECODE_ERROR", ev)
    # 坏块结构
    try:
        decoder.split_chunks(b"\x05\x00")
        check("解码器: 块体越界抛错", False, "未抛错")
    except Exception:
        check("解码器: 块体越界抛错", True)
    # 响应编码器
    check("编码器: idle summon", decoder.encode_idle("summon", 0) ==
          (0).to_bytes(4, "little", signed=True))
    check("编码器: cancel=-1", decoder.encode_cancel() ==
          (-1).to_bytes(4, "little", signed=True))
    check("编码器: card indices", decoder.encode_card_indices([0, 2]) ==
          (0).to_bytes(4, "little", signed=True) + (2).to_bytes(4, "little",
                                                                signed=False)
          + (0).to_bytes(4, "little") + (2).to_bytes(4, "little"))


def test_validation(service):
    def expect_err(req, code, label):
        res = service.handle_request(req)
        ok = (not res["ok"]) and res["error"]["code"] == code
        return check(f"校验: {label} -> {code}", ok, res.get("error"))

    expect_err({"id": 1, "cmd": "nope"}, "UNKNOWN_CMD", "未知 cmd")
    expect_err({"id": 1, "cmd": "get_state", "viewer": 0}, "NO_DUEL",
               "未 new_duel 先 get_state")
    expect_err({"id": 1, "cmd": "new_duel", "decks": [[], [1]]}, "BAD_REQUEST",
               "空卡组")
    expect_err({"id": 1, "cmd": "new_duel", "decks": [[1]]}, "BAD_REQUEST",
               "卡组数量 != 2")
    expect_err({"id": 1, "cmd": "new_duel", "decks": ["a", [1]]}, "BAD_REQUEST",
               "passcode 非整数")
    expect_err({"id": 1, "cmd": "new_duel", "decks": [[-5], [1]]}, "BAD_REQUEST",
               "passcode 负数")
    expect_err({"id": 1, "cmd": "new_duel", "decks": [[1], [1]],
                "opts": {"seed": [1, 2, 3, 4, 5]}}, "BAD_REQUEST", "seed 超长")
    expect_err({"id": 1, "cmd": "new_duel", "decks": [[1], [1]],
                "opts": {"mode": "MR9"}}, "BAD_REQUEST", "未知 mode")
    res = service.handle_request("not-a-dict")
    check("校验: 非 JSON 对象请求", res["error"]["code"] == "BAD_REQUEST", res)


def test_hiding(state0, state1):
    """state0/viewer=0, state1/viewer=1 的初始状态互查。"""
    p0v, p1v = state0["players"][0], state0["players"][1]
    check("隐藏: viewer=0 看自己手牌有 code",
          all(c["code"] is not None for c in p0v["hand"])
          and len(p0v["hand"]) == 5, len(p0v["hand"]))
    check("隐藏: viewer=0 看 p1 手牌全 null 且数量保留",
          all(c["code"] is None for c in p1v["hand"])
          and len(p1v["hand"]) == 5, f"hand={len(p1v['hand'])}")
    check("隐藏: viewer=1 看 p0 手牌全 null",
          all(c["code"] is None for c in state1["players"][0]["hand"]), "")
    # 墓地/除外是公开区：双方可见一致
    check("隐藏: 公开区双方一致",
          canon(state0["players"][0]["graveyard"])
          == canon(state1["players"][0]["graveyard"]), "")


def test_facedown_hidden(service, viewer, opp):
    """在当前对局中取 opp 全场盖卡，验证对手视角 code/atk/def 全隐藏。"""
    res = service.handle_request({"id": 9, "cmd": "get_state", "viewer": viewer})
    opp_side = res["result"]["state"]["players"][opp]
    facedowns = []
    for zone in ("monster_zones", "spell_trap_zones"):
        for slot in opp_side[zone]:
            if slot and not slot["face"]:
                facedowns.append(slot)
    check(f"隐藏: viewer={viewer} 看 p{opp} 盖卡 code 全 null",
          all(c["code"] is None for c in facedowns),
          f"{len(facedowns)} 张盖卡 {[c['pos'] for c in facedowns]}")
    # 对方视角的 ATK/DEF 也不得泄漏
    check(f"隐藏: viewer={viewer} 看 p{opp} 盖卡无 atk/def",
          all("atk" not in c and "def" not in c for c in facedowns), "")
    return len(facedowns)


def test_over(service):
    res = service.handle_request({"id": 11, "cmd": "respond", "choice": 0})
    check("健壮性: 终局后 respond -> DUEL_OVER",
          not res["ok"] and res["error"]["code"] == "DUEL_OVER", res.get("error"))
    res = service.handle_request({"id": 12, "cmd": "get_state", "viewer": 0})
    check("健壮性: 终局后 get_state 保留 winner",
          res["ok"] and res["result"]["state"]["winner"] is not None, "")


def main():
    print("== E1 Adapter v0 selftest ==")
    test_binding()
    test_decoder()

    core = OcgCore()
    service = svc.AdapterService(core=core)
    test_validation(service)

    # ---- 完整对局 + 过程可见性检查 ----
    t0 = __import__("time").time()
    events, final, steps = play_full_game(service)
    dt = __import__("time").time() - t0
    retry_events = [e for e in events if e["type"] == "RETRY"]
    bad_events = [e for e in events if e["type"] in ("DECODE_ERROR", "UNKNOWN")]
    check("对局: 打完整局且零 MSG_RETRY", final["winner"] is not None
          and not retry_events,
          f"winner={final['winner']} reason={final['reason']} steps={steps} "
          f"events={len(events)} {dt:.1f}s")
    check("对局: 零解码失败/未知消息", not bad_events,
          [(e['type'], e.get('name'), e.get('reason')) for e in bad_events][:5])
    check("对局: winner=0 / reason=1(LP_ZERO)（固定 seed+脚本下的预期）",
          final["winner"] == 0 and final["reason"] == 1,
          f"winner={final['winner']} reason={final['reason']}")
    loser_lp = final["players"][1]["lp"]
    check("对局: 败方 LP 归零", loser_lp == 0, loser_lp)
    check("对局: 胜方 LP > 0", final["players"][0]["lp"] > 0,
          final["players"][0]["lp"])
    check("对局: 回合数 >= 3", final["turn_count"] >= 3, final["turn_count"])
    has_move = any(e["type"] in ("SUMMONING", "SPSUMMONING") for e in events)
    has_battle = any(e["type"] in ("ATTACK", "BATTLE") for e in events)
    check("对局: 事件流含召唤与战斗", has_move and has_battle,
          f"move={has_move} battle={has_battle}")
    test_over(service)

    # ---- 信息隐藏：新对局，初始状态互查 + 盖卡检查 ----
    res = service.handle_request(
        {"id": 20, "cmd": "new_duel", "decks": [make_deck(), make_deck()],
         "opts": {"lp": 8000, "start_hand": 5, "seed": SEED}})
    check("隐藏: new_duel 成功", res["ok"], res.get("error"))
    st0 = service.handle_request({"id": 21, "cmd": "get_state",
                                  "viewer": 0})["result"]["state"]
    st1 = service.handle_request({"id": 22, "cmd": "get_state",
                                  "viewer": 1})["result"]["state"]
    test_hiding(st0, st1)
    # 驱动到 p1 完成首回合（含盖卡）后，即 turn_count 达 3（第 3 个 NEW_TURN = p0 第 2 回合）
    policy = Policy()
    ev_stream = []
    for i in range(60):
        cur = service.handle_request({"id": 23, "cmd": "get_state",
                                      "viewer": 0})["result"]["state"]
        if cur["turn_count"] >= 3:
            break
        if cur["pending"] is None or cur["winner"] is not None:
            break
        body = policy.respond(cur)
        body.update({"id": 24, "cmd": "respond", "viewer": 0})
        res = service.handle_request(body)
        assert res["ok"], res
        ev_stream.extend(res["result"]["events"])
    # 跨 p1 回合的抽牌事件对 viewer=0 必须无 code（数量保留）
    p1_draws = [e for e in ev_stream
                if e["type"] == "DRAW" and e.get("player") == 1]
    check("隐藏: viewer=0 的 p1 抽牌事件 code 全 null 且数量保留",
          bool(p1_draws) and all(c["code"] is None
                                 for d in p1_draws for c in d["cards"]),
          f"{len(p1_draws)} 次 DRAW {[len(d['cards']) for d in p1_draws]}")
    n_fd = test_facedown_hidden(service, viewer=0, opp=1)
    n_fd1 = test_facedown_hidden(service, viewer=1, opp=0)
    check("隐藏: p1 首回合盖卡在对手视角实际观测到", n_fd > 0, f"p1 盖卡 {n_fd} 张")
    # ---- 确定性：同 seed 同脚本两局事件流逐字节一致 ----
    core2 = OcgCore()
    svc2 = svc.AdapterService(core=core2)
    ev_a, fin_a, _ = play_full_game(service)
    ev_b, fin_b, _ = play_full_game(svc2)
    same_stream = canon(ev_a) == canon(ev_b)
    check("确定性: 同 seed 同脚本事件流逐字节一致", same_stream,
          "" if same_stream else _first_diff(canon(ev_a), canon(ev_b)))
    # duel_id 是会话序号不属于确定性范畴，剔除后比较
    strip = lambda s: {k: v for k, v in s.items() if k != "duel_id"}
    check("确定性: 终局状态一致", canon(strip(fin_a)) == canon(strip(fin_b)), "")
    core.destroy()
    core2.destroy()

    # ---- 汇总 ----
    fails = [c for c in CHECKS if not c[1]]
    for name, ok, detail in CHECKS:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    print(f"== {len(CHECKS) - len(fails)}/{len(CHECKS)} 通过 ==")
    return 1 if fails else 0


def _first_diff(a, b):
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return f"首个差异 @{i}: {a[max(0,i-40):i+40]!r} vs {b[max(0,i-40):i+40]!r}"
    return f"长度不同 {len(a)}/{len(b)}"


if __name__ == "__main__":
    sys.exit(main())
