#!/usr/bin/env python3
"""E1/WO-007：ocgcore C API 的 ctypes 绑定（硬化自 spike/ocg/ocgcore_ctypes.py）。

- 结构体 1:1 对照 vendor/repos/ygopro-core/ocgapi_types.h（API 11.0）
- cardReader <- cards.cdb(datas 表)；scriptReader <- CardScripts 仓库布局
- 路径配置：构造参数 > CLI 参数(service.py) > 环境变量 > 仓库默认值
  环境变量：CLASSIC_DUEL_DLL / CLASSIC_DUEL_CDB / CLASSIC_DUEL_SCRIPTS
- 所有失败路径抛 AdapterError（结构化 code/message），服务层捕获后回 JSON 错误
"""
import ctypes
import os
import sqlite3
from ctypes import (CFUNCTYPE, POINTER, byref, c_char_p, c_int, c_int32,
                    c_uint8, c_uint16, c_uint32, c_uint64, c_void_p)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_DLL = os.path.join(REPO_ROOT, "spike", "ocg", "out", "ocgcore.dll")
DEFAULT_CDB = os.path.join(REPO_ROOT, "vendor", "edopro", "ProjectIgnis",
                           "expansions", "cards.cdb")
DEFAULT_SCRIPTS = os.path.join(REPO_ROOT, "vendor", "repos", "CardScripts")

ENV_DLL, ENV_CDB, ENV_SCRIPTS = ("CLASSIC_DUEL_DLL", "CLASSIC_DUEL_CDB",
                                 "CLASSIC_DUEL_SCRIPTS")

# ocgapi_constants.h（C API 层常量，注意 0x2=里攻 / 0x4=表守）
LOCATION_DECK, LOCATION_HAND, LOCATION_MZONE, LOCATION_SZONE = 0x01, 0x02, 0x04, 0x08
LOCATION_GRAVE, LOCATION_REMOVED, LOCATION_EXTRA = 0x10, 0x20, 0x40
POS_FACEUP_ATTACK = 0x1
POS_FACEDOWN_ATTACK = 0x2
POS_FACEUP_DEFENSE = 0x4
POS_FACEDOWN_DEFENSE = 0x8
POS_FACEUP = POS_FACEUP_ATTACK | POS_FACEUP_DEFENSE
POS_FACEDOWN = POS_FACEDOWN_ATTACK | POS_FACEDOWN_DEFENSE
TYPE_MONSTER, TYPE_SPELL, TYPE_TRAP = 0x1, 0x2, 0x4
TYPE_LINK = 0x4000000
DUEL_TEST_MODE = 0x01
# 规则时代预设（D1 报告 §建议 2：经典节奏直接用旧 Master Rule 预设）
DUEL_MODE_MR1, DUEL_MODE_MR2, DUEL_MODE_MR3, DUEL_MODE_MR4, DUEL_MODE_MR5 = (
    0x100, 0x200, 0x400, 0x800, 0x1000)
DUEL_MODE_MR1_FORB, DUEL_MODE_MR3_FORB, DUEL_MODE_MR4_FORB, DUEL_MODE_GOAT = (
    0x2000, 0x4000, 0x8000, 0x10000)

QUERY_CODE, QUERY_POSITION, QUERY_LEVEL, QUERY_TYPE = 0x1, 0x2, 0x10, 0x8
QUERY_ATTACK, QUERY_DEFENSE, QUERY_OVERRIDE = 0x100, 0x200, 0x80000000

# 规则时代预设（ocgapi_constants.h 416~423 行组合表达式的 Python 求值；
# FORB 变体是 TYPE 掩码不是 duel flag，v0 不提供）
_MODE = lambda *xs: sum(xs)
DUEL_MODE_MR1 = _MODE(0x100, 0x200, 0x400, 0x10000, 0x80000)
DUEL_MODE_GOAT = DUEL_MODE_MR1 | _MODE(0x4, 0x8, 0x20, 0x8000000, 0x10000000,
                                       0x20000000, 0x40000000, 0x80000000,
                                       0x100000000, 0x200000000, 0x400000000)
DUEL_MODE_MR2 = _MODE(0x200, 0x400, 0x10000, 0x80000)
DUEL_MODE_MR3 = _MODE(0x800, 0x1000, 0x10000, 0x80000)
DUEL_MODE_MR4 = _MODE(0x800, 0x2000, 0x10000, 0x80000)
DUEL_MODE_MR5 = _MODE(0x800, 0x2000, 0x4000, 0x8000, 0x20000)
MODE_FLAGS = {"default": 0, "MR1": DUEL_MODE_MR1, "GOAT": DUEL_MODE_GOAT,
              "MR2": DUEL_MODE_MR2, "MR3": DUEL_MODE_MR3, "MR4": DUEL_MODE_MR4,
              "MR5": DUEL_MODE_MR5}

PROCESS_END, PROCESS_AWAITING, PROCESS_CONTINUE = 0, 1, 2


class AdapterError(Exception):
    """结构化错误：code 供协议 error.code 使用，message 面向开发者。"""

    def __init__(self, code, message):
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message

    def to_dict(self):
        return {"code": self.code, "message": self.message}


class Config:
    """DLL/cdb/脚本根路径。优先级：显式参数 > 环境变量 > 仓库默认值。"""

    def __init__(self, dll=None, cdb=None, scripts=None):
        self.dll = os.path.abspath(dll or os.environ.get(ENV_DLL) or DEFAULT_DLL)
        self.cdb = os.path.abspath(cdb or os.environ.get(ENV_CDB) or DEFAULT_CDB)
        self.scripts = os.path.abspath(
            scripts or os.environ.get(ENV_SCRIPTS) or DEFAULT_SCRIPTS)

    def validate(self):
        if not os.path.isfile(self.dll):
            raise AdapterError(
                "DLL_NOT_FOUND",
                f"ocgcore.dll 不存在: {self.dll}（构建：bash spike/ocg/build_dll.sh，"
                f"或设 {ENV_DLL} 指向已有 DLL）")
        if not os.path.isfile(self.cdb):
            raise AdapterError(
                "CDB_NOT_FOUND",
                f"cards.cdb 不存在: {self.cdb}（设 {ENV_CDB}，见 vendor/VERSIONS.md）")
        if not os.path.isdir(self.scripts):
            raise AdapterError(
                "SCRIPTS_DIR_MISSING",
                f"CardScripts 目录不存在: {self.scripts}（设 {ENV_SCRIPTS}）")
        return self


# ---- 结构体（ocgapi_types.h） ----
class OCG_CardData(ctypes.Structure):
    _fields_ = [("code", c_uint32), ("alias", c_uint32),
                ("setcodes", POINTER(c_uint16)), ("type", c_uint32),
                ("level", c_uint32), ("attribute", c_uint32),
                ("race", c_uint64), ("attack", c_int32), ("defense", c_int32),
                ("lscale", c_uint32), ("rscale", c_uint32),
                ("link_marker", c_uint32)]


class OCG_Player(ctypes.Structure):
    _fields_ = [("startingLP", c_uint32), ("startingDrawCount", c_uint32),
                ("drawCountPerTurn", c_uint32)]


CARD_READER_CB = CFUNCTYPE(None, c_void_p, c_uint32, POINTER(OCG_CardData))
CARD_READER_DONE_CB = CFUNCTYPE(None, c_void_p, POINTER(OCG_CardData))
SCRIPT_READER_CB = CFUNCTYPE(c_int, c_void_p, c_void_p, c_char_p)
LOG_HANDLER_CB = CFUNCTYPE(None, c_void_p, c_char_p, c_int)


class OCG_DuelOptions(ctypes.Structure):
    _fields_ = [("seed", c_uint64 * 4), ("flags", c_uint64),
                ("team1", OCG_Player), ("team2", OCG_Player),
                ("cardReader", CARD_READER_CB), ("payload1", c_void_p),
                ("scriptReader", SCRIPT_READER_CB), ("payload2", c_void_p),
                ("logHandler", LOG_HANDLER_CB), ("payload3", c_void_p),
                ("cardReaderDone", CARD_READER_DONE_CB), ("payload4", c_void_p),
                ("enableUnsafeLibraries", c_uint8)]


class OCG_NewCardInfo(ctypes.Structure):
    _fields_ = [("team", c_uint8), ("duelist", c_uint8), ("code", c_uint32),
                ("con", c_uint8), ("loc", c_uint32), ("seq", c_uint32),
                ("pos", c_uint32)]


class OCG_QueryInfo(ctypes.Structure):
    _fields_ = [("flags", c_uint32), ("con", c_uint8), ("loc", c_uint32),
                ("seq", c_uint32), ("overlay_seq", c_uint32)]


class OcgCore:
    """加载 DLL + 数据/脚本源。回调引用全程保活防 GC。

    一个实例可先后承载多个 duel（create_duel 会销毁旧 handle）；
    DLL/数据源加载失败抛 AdapterError，core 调用异常包成 CORE_CALL_FAILED。
    """

    def __init__(self, config=None):
        self.config = (config or Config()).validate()
        try:
            self.dll = ctypes.CDLL(self.config.dll)
        except OSError as e:
            raise AdapterError("DLL_LOAD_FAILED",
                               f"加载 {self.config.dll} 失败: {e}") from e
        try:
            self.cdb = sqlite3.connect(self.config.cdb)
            self.cdb.execute("select 1 from datas limit 1").fetchone()
        except sqlite3.Error as e:
            raise AdapterError("CDB_INVALID",
                               f"cards.cdb 打开失败({self.config.cdb}): {e}") from e
        self.script_root = self.config.scripts
        self._setcodes_buf = {}
        self.script_cache = {}
        self.log_lines = []
        self.duel = None
        self._opts = None
        self._card_reader = CARD_READER_CB(self._card_reader)
        self._card_reader_done = CARD_READER_DONE_CB(self._card_reader_done)
        self._script_reader = SCRIPT_READER_CB(self._script_reader)
        self._log_handler = LOG_HANDLER_CB(self._log_handler)
        self._declare()

    def _declare(self):
        try:
            self.dll.OCG_GetVersion.argtypes = [POINTER(c_int), POINTER(c_int)]
            self.dll.OCG_CreateDuel.argtypes = [POINTER(c_void_p),
                                                POINTER(OCG_DuelOptions)]
            self._declare_fn("OCG_DestroyDuel", None, [c_void_p])
            self._declare_fn("OCG_DuelNewCard", None,
                             [c_void_p, POINTER(OCG_NewCardInfo)])
            self._declare_fn("OCG_StartDuel", None, [c_void_p])
            self.dll.OCG_DuelProcess.restype = c_int
            self.dll.OCG_DuelProcess.argtypes = [c_void_p]
            self.dll.OCG_DuelGetMessage.restype = c_void_p
            self.dll.OCG_DuelGetMessage.argtypes = [c_void_p, POINTER(c_uint32)]
            self._declare_fn("OCG_DuelSetResponse", None,
                             [c_void_p, c_void_p, c_uint32])
            self._declare_fn("OCG_LoadScript", c_int,
                             [c_void_p, c_char_p, c_uint32, c_char_p])
            self.dll.OCG_DuelQueryCount.restype = c_uint32
            self.dll.OCG_DuelQueryCount.argtypes = [c_void_p, c_uint8, c_uint32]
            self.dll.OCG_DuelQuery.restype = c_void_p
            self.dll.OCG_DuelQuery.argtypes = [c_void_p, POINTER(c_uint32),
                                               POINTER(OCG_QueryInfo)]
            self.dll.OCG_DuelQueryLocation.restype = c_void_p
            self.dll.OCG_DuelQueryLocation.argtypes = [c_void_p,
                                                       POINTER(c_uint32),
                                                       POINTER(OCG_QueryInfo)]
        except AttributeError as e:
            raise AdapterError("DLL_SYMBOL_MISSING", f"导出符号缺失: {e}") from e

    def _declare_fn(self, name, restype, argtypes):
        fn = getattr(self.dll, name)
        fn.restype = restype
        fn.argtypes = argtypes

    def version(self):
        ma, mi = c_int(), c_int()
        try:
            self.dll.OCG_GetVersion(byref(ma), byref(mi))
        except Exception as e:  # ctypes 调用层异常
            raise AdapterError("CORE_CALL_FAILED", f"OCG_GetVersion: {e}") from e
        return f"{ma.value}.{mi.value}"

    # ---- 数据源：cards.cdb -> OCG_CardData（映射规则经 core 源码 + P4 抽样验证） ----
    def _card_reader(self, payload, code, data_p):
        row = self.cdb.execute(
            "select alias,setcode,type,level,atk,def,race,attribute from datas "
            "where id=?", (code,)).fetchone()
        d = data_p[0]
        if row is None:
            d.code, d.alias, d.type, d.setcodes = code, 0, 0, None
            return
        alias, setcode, ctype, level, atk, dfn, race, attr = row
        d.code, d.alias, d.type = code, alias, ctype
        d.attack, d.defense = atk, dfn
        d.attribute, d.race = attr, race
        d.level = level & 0xFFFF
        d.lscale = (level >> 24) & 0xFF
        d.rscale = (level >> 16) & 0xFF
        if ctype & TYPE_LINK:
            d.link_marker = dfn & 0x1FF
            d.defense = 0
        d.link_marker = d.link_marker if ctype & TYPE_LINK else 0
        words = []
        v = setcode & 0xFFFFFFFF
        for i in range(4):
            w = (v >> (16 * i)) & 0xFFFF
            if w:
                words.append(w)
        buf = (c_uint16 * 5)(*words, 0)
        self._setcodes_buf[code] = buf          # 保活到 cardReaderDone
        d.setcodes = buf

    def _card_reader_done(self, payload, data_p):
        self._setcodes_buf.pop(data_p[0].code, None)

    # ---- 脚本源：CardScripts 布局（根库 + official + unofficial + rush + skill…） ----
    SCRIPT_DIRS = ["", "official", "unofficial", "rush", "skill", "pre-errata",
                   "goat"]

    def resolve_script(self, name):
        name = name.decode() if isinstance(name, bytes) else name
        if name in self.script_cache:
            return self.script_cache[name]
        blob = None
        for d in self.SCRIPT_DIRS:
            p = os.path.join(self.script_root, d, name)
            if os.path.isfile(p):
                with open(p, "rb") as f:
                    blob = f.read()
                break
        self.script_cache[name] = blob  # 通常怪兽无脚本是正常路径，缓存否定结果
        return blob

    def _script_reader(self, payload, duel, name):
        blob = self.resolve_script(name)
        if blob is None:
            self.log_lines.append(f"[script-missing] {name}")
            return 0
        try:
            ok = self.dll.OCG_LoadScript(duel, blob, len(blob), name)
        except Exception as e:
            self.log_lines.append(f"[script-load-error] {name}: {e}")
            return 0
        return 1 if ok else 0

    def _log_handler(self, payload, string, ltype):
        msg = string.decode(errors="replace") if string else ""
        self.log_lines.append(f"[log:{ltype}] {msg}")
        # 不打印到 stdout（stdout 是协议通道）；服务层按需写 stderr

    # ---- duel 生命周期 ----
    def create_duel(self, seed=(0x20260925, 1, 2, 3), flags=DUEL_TEST_MODE,
                    lp=8000, start_hand=5, draw_per_turn=1):
        """创建 duel 并预载 constant.lua/utility.lua（core 不自载全局脚本）。

        seed: 至多 4 个 u64；不足补 0（xoshiro256 状态）。
        """
        if self.duel is not None:
            self.destroy()
        seed = list(seed or [])
        seed = [c_uint64(int(s) & 0xFFFFFFFFFFFFFFFF) for s in seed[:4]]
        seed += [c_uint64(0)] * (4 - len(seed))
        opts = OCG_DuelOptions()
        opts.seed = (c_uint64 * 4)(*seed)
        opts.flags = c_uint64(int(flags))
        opts.team1 = OCG_Player(int(lp), int(start_hand), int(draw_per_turn))
        opts.team2 = OCG_Player(int(lp), int(start_hand), int(draw_per_turn))
        opts.cardReader = self._card_reader
        opts.cardReaderDone = self._card_reader_done
        opts.scriptReader = self._script_reader
        opts.logHandler = self._log_handler
        opts.payload1 = opts.payload2 = opts.payload3 = opts.payload4 = None
        opts.enableUnsafeLibraries = 0
        self._opts = opts  # 保活（core 持有回调指针）
        duel = c_void_p()
        try:
            status = self.dll.OCG_CreateDuel(byref(duel), byref(opts))
        except Exception as e:
            raise AdapterError("CORE_CALL_FAILED", f"OCG_CreateDuel: {e}") from e
        if status != 0:
            raise AdapterError("CREATE_DUEL_FAILED",
                               f"OCG_CreateDuel status={status}")
        self.duel = duel
        for lib in ("constant.lua", "utility.lua"):
            blob = self.resolve_script(lib)
            if not blob:
                self.destroy()
                raise AdapterError("SCRIPTS_DIR_MISSING",
                                   f"全局脚本缺失: {lib}（检查 {ENV_SCRIPTS}）")
            if not self.dll.OCG_LoadScript(self.duel, blob, len(blob),
                                           lib.encode()):
                self.destroy()
                raise AdapterError("CORE_CALL_FAILED",
                                   f"OCG_LoadScript 失败: {lib}")
        return duel

    def new_card(self, team, code, loc, seq=0, pos=0x2, duelist=0):
        """duelist 必须=0：非 0 是 TAG 轮换的副卡组（坑 #6）。"""
        info = OCG_NewCardInfo(team=team, duelist=duelist, code=code,
                               con=team, loc=loc, seq=seq, pos=pos)
        self.dll.OCG_DuelNewCard(self.duel, byref(info))

    def start(self):
        self.dll.OCG_StartDuel(self.duel)

    def process(self):
        return self.dll.OCG_DuelProcess(self.duel)

    def get_message(self):
        ln = c_uint32()
        ptr = self.dll.OCG_DuelGetMessage(self.duel, byref(ln))
        if not ln.value:
            return b""
        return ctypes.string_at(ptr, ln.value)  # 立即拷贝（内部缓冲下次调用失效）

    def set_response(self, blob):
        self.dll.OCG_DuelSetResponse(self.duel, blob, len(blob))

    def query_count(self, team, loc):
        return int(self.dll.OCG_DuelQueryCount(self.duel, team, loc))

    def query_location(self, team, loc,
                       flags=QUERY_CODE | QUERY_POSITION | QUERY_TYPE
                       | QUERY_LEVEL | QUERY_ATTACK | QUERY_DEFENSE):
        """整区查询。返回 [slot][card-dict]；MZONE/SZONE 按槽序（空槽=None），
        动态列表（hand/grave/removed）紧凑排列。"""
        ln = c_uint32()
        info = OCG_QueryInfo(flags=flags, con=team, loc=loc, seq=0,
                             overlay_seq=0)
        ptr = self.dll.OCG_DuelQueryLocation(self.duel, byref(ln), byref(info))
        if not ln.value:
            return []
        raw = ctypes.string_at(ptr, ln.value)  # 立即拷贝
        return parse_query_buffer(raw[4:], flags)  # 首部 u32 总长前缀（坑 #5）

    def destroy(self):
        if self.duel is not None:
            self.dll.OCG_DestroyDuel(self.duel)
            self.duel = None


# ---- 查询缓冲解析（card.cpp CHECK_AND_INSERT_T：每字段 [u16 len][u32 tag][value len-4]；
#      ocgapi.cpp populate：空槽写 int16 0 → MZONE(7)/SZONE(8) 槽序即 seq） ----
_SIGNED_TAGS = (QUERY_ATTACK, QUERY_DEFENSE)  # i32 原位（"?" 为负值）


def parse_query_buffer(buf, flags):
    cards, off, slot = [], 0, 0
    while off + 2 <= len(buf):
        ln = int.from_bytes(buf[off:off + 2], "little")
        off += 2
        if ln == 0:          # 空槽位（仅固定槽位区域出现）
            cards.append(None)
            slot += 1
            continue
        tag = int.from_bytes(buf[off:off + 4], "little")
        off += 4
        payload = buf[off:off + ln - 4]
        off += ln - 4
        if tag == QUERY_CODE:
            cards.append({"seq": slot, "code": int.from_bytes(payload, "little")})
        elif tag == QUERY_OVERRIDE or not payload:
            continue  # 0x80000000 终结标记
        elif cards:
            value = int.from_bytes(payload, "little")
            if tag in _SIGNED_TAGS and value >= 0x80000000:
                value -= 1 << 32
            cards[-1][tag] = value
        slot += 1 if tag == QUERY_CODE else 0
    return cards


def close_quietly(core):
    try:
        core.destroy()
    except Exception:
        pass
