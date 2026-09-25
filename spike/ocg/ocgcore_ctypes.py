#!/usr/bin/env python3
"""WO-005 P2 探针：ocgcore C API 的 ctypes 绑定与数据源实现。

- 结构体定义 1:1 对照 vendor/repos/ygopro-core/ocgapi_types.h（API 11.0）
- cardReader <- expansions/cards.cdb (datas 表)
- scriptReader <- CardScripts 仓库布局（根库 + official/ + unofficial/ + rush/ + skill/）
- 宿主预载 constant.lua + utility.lua（utility.lua 尾部经 Duel.LoadScript 链载 proc_*）
"""
import ctypes
import os
import sqlite3
from ctypes import (CFUNCTYPE, POINTER, c_char_p, c_int, c_int32, c_uint8,
                    c_uint16, c_uint32, c_uint64, c_void_p, byref)

DLL_PATH = os.path.join(os.path.dirname(__file__), "out", "ocgcore.dll")
CDB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "vendor",
                        "edopro", "ProjectIgnis", "expansions", "cards.cdb")
SCRIPT_ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "vendor",
                           "repos", "CardScripts")

# ocgapi_constants.h 关键常量（探针用到的子集）
LOCATION_DECK, LOCATION_HAND, LOCATION_MZONE, LOCATION_SZONE = 0x01, 0x02, 0x04, 0x08
LOCATION_GRAVE, LOCATION_REMOVED, LOCATION_EXTRA = 0x10, 0x20, 0x40
POS_FACEUP_ATTACK = 0x1
TYPE_MONSTER, TYPE_SPELL, TYPE_TRAP = 0x1, 0x2, 0x4
TYPE_LINK = 0x4000000
DUEL_TEST_MODE = 0x01

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

QUERY_CODE, QUERY_POSITION, QUERY_LEVEL, QUERY_TYPE = 0x1, 0x2, 0x10, 0x8
QUERY_ATTACK, QUERY_DEFENSE, QUERY_OVERRIDE = 0x100, 0x200, 0x80000000


class OcgCore:
    """加载 DLL + 数据/脚本源，持有回调引用防止 GC。"""

    def __init__(self, dll_path=DLL_PATH, cdb_path=CDB_PATH, script_root=SCRIPT_ROOT):
        self.dll = ctypes.CDLL(dll_path)
        self.cdb = sqlite3.connect(os.path.abspath(cdb_path))
        self.script_root = os.path.abspath(script_root)
        self._setcodes_buf = {}
        self.script_cache = {}
        self.log_lines = []
        self._card_reader = CARD_READER_CB(self._card_reader)
        self._card_reader_done = CARD_READER_DONE_CB(self._card_reader_done)
        self._script_reader = SCRIPT_READER_CB(self._script_reader)
        self._log_handler = LOG_HANDLER_CB(self._log_handler)
        self.dll.OCG_GetVersion.argtypes = [POINTER(c_int), POINTER(c_int)]
        self.dll.OCG_CreateDuel.argtypes = [POINTER(c_void_p), POINTER(OCG_DuelOptions)]
        self._declare("OCG_DestroyDuel", None, [c_void_p])
        self._declare("OCG_DuelNewCard", None, [c_void_p, POINTER(OCG_NewCardInfo)])
        self._declare("OCG_StartDuel", None, [c_void_p])
        self.dll.OCG_DuelProcess.restype = c_int
        self.dll.OCG_DuelProcess.argtypes = [c_void_p]
        self.dll.OCG_DuelGetMessage.restype = c_void_p
        self.dll.OCG_DuelGetMessage.argtypes = [c_void_p, POINTER(c_uint32)]
        self._declare("OCG_DuelSetResponse", None, [c_void_p, c_void_p, c_uint32])
        self._declare("OCG_LoadScript", c_int, [c_void_p, c_char_p, c_uint32, c_char_p])
        self.dll.OCG_DuelQueryCount.restype = c_uint32
        self.dll.OCG_DuelQueryCount.argtypes = [c_void_p, c_uint8, c_uint32]
        self.dll.OCG_DuelQuery.restype = c_void_p
        self.dll.OCG_DuelQuery.argtypes = [c_void_p, POINTER(c_uint32), POINTER(OCG_QueryInfo)]
        self.dll.OCG_DuelQueryLocation.restype = c_void_p
        self.dll.OCG_DuelQueryLocation.argtypes = [c_void_p, POINTER(c_uint32), POINTER(OCG_QueryInfo)]

    def _declare(self, name, restype, argtypes):
        fn = getattr(self.dll, name)
        fn.restype = restype
        fn.argtypes = argtypes

    # ---- 数据源：cards.cdb -> OCG_CardData（字段映射经 core 源码/抽样双重验证） ----
    def _read_cdb(self, code):
        row = self.cdb.execute(
            "select alias,setcode,type,level,atk,def,race,attribute from datas where id=?",
            (code,)).fetchone()
        return row

    def _card_reader(self, payload, code, data_p):
        row = self._read_cdb(code)
        d = data_p[0]
        if row is None:
            d.code, d.alias, d.type = code, 0, 0
            d.setcodes = None
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
        words = []
        v = setcode & 0xFFFFFFFF
        for i in range(4):
            w = (v >> (16 * i)) & 0xFFFF
            if w:
                words.append(w)
        buf = (c_uint16 * 5)(*words, 0)
        self._setcodes_buf[code] = buf          # 保活到 cardReaderDone
        d.setcodes = buf
        d.link_marker = d.link_marker if ctype & TYPE_LINK else 0

    def _card_reader_done(self, payload, data_p):
        code = data_p[0].code
        self._setcodes_buf.pop(code, None)

    # ---- 脚本源：CardScripts 布局 ----
    SCRIPT_DIRS = ["", "official", "unofficial", "rush", "skill", "pre-errata", "goat"]

    def resolve_script(self, name):
        name = name.decode() if isinstance(name, bytes) else name
        if name in self.script_cache:
            return self.script_cache[name]
        for d in self.SCRIPT_DIRS:
            p = os.path.join(self.script_root, d, name)
            if os.path.isfile(p):
                with open(p, "rb") as f:
                    self.script_cache[name] = f.read()
                return self.script_cache[name]
        self.script_cache[name] = None
        return None

    def _script_reader(self, payload, duel, name):
        blob = self.resolve_script(name)
        if blob is None:
            self.log_lines.append(f"[script-missing] {name}")
            return 0
        ok = self.dll.OCG_LoadScript(duel, blob, len(blob), name)
        return 1 if ok else 0

    def _log_handler(self, payload, string, ltype):
        msg = string.decode(errors="replace") if string else ""
        self.log_lines.append(f"[log:{ltype}] {msg}")
        if ltype == 0:  # OCG_LOG_TYPE_ERROR
            print("CORE ERROR:", msg)

    # ---- duel 生命周期 ----
    def create_duel(self, seed=(0x20260925, 1, 2, 3), flags=DUEL_TEST_MODE,
                    lp=8000, start_hand=5, draw_per_turn=1):
        opts = OCG_DuelOptions()
        opts.seed = (c_uint64 * 4)(*seed)
        opts.flags = flags
        opts.team1 = OCG_Player(lp, start_hand, draw_per_turn)
        opts.team2 = OCG_Player(lp, start_hand, draw_per_turn)
        opts.cardReader = self._card_reader
        opts.cardReaderDone = self._card_reader_done
        opts.scriptReader = self._script_reader
        opts.logHandler = self._log_handler
        opts.payload1 = opts.payload2 = opts.payload3 = opts.payload4 = None
        opts.enableUnsafeLibraries = 0
        self._opts = opts  # 保活
        duel = c_void_p()
        status = self.dll.OCG_CreateDuel(byref(duel), byref(opts))
        if status != 0:
            raise RuntimeError(f"OCG_CreateDuel status={status}")
        self.duel = duel
        # 预载全局脚本（core 不自载；utility.lua 尾部链载 proc_*）
        for lib in ("constant.lua", "utility.lua"):
            blob = self.resolve_script(lib)
            if not blob:
                raise RuntimeError(f"全局脚本缺失: {lib}")
            if not self.dll.OCG_LoadScript(self.duel, blob, len(blob), lib.encode()):
                raise RuntimeError(f"OCG_LoadScript 失败: {lib}")
        return duel

    def new_card(self, team, code, loc, seq=0, pos=0x2, duelist=0):
        # duelist 必须=0：非 0 是 TAG 轮换的副卡组（ocgapi.cpp OCG_DuelNewCard）
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
        return ctypes.string_at(ptr, ln.value)  # 立即拷贝（内部缓冲会失效）

    def set_response(self, blob):
        self.dll.OCG_DuelSetResponse(self.duel, blob, len(blob))

    def query_location(self, team, loc, flags=QUERY_CODE | QUERY_POSITION | QUERY_TYPE
                       | QUERY_LEVEL | QUERY_ATTACK | QUERY_DEFENSE):
        ln = c_uint32()
        info = OCG_QueryInfo(flags=flags, con=team, loc=loc, seq=0, overlay_seq=0)
        ptr = self.dll.OCG_DuelQueryLocation(self.duel, byref(ln), byref(info))
        if not ln.value:
            return []
        raw = ctypes.string_at(ptr, ln.value)  # 立即拷贝（内部缓冲会失效）
        return parse_query_buffer(raw[4:], flags)  # 首部有 u32 总长前缀（ocgapi.cpp）

    def destroy(self):
        self.dll.OCG_DestroyDuel(self.duel)


# ---- 查询缓冲解析（card.cpp CHECK_AND_INSERT_T：每字段 = [u16 len][u32 tag][value len-4]；
#      len 值本身 = sizeof(tag)+sizeof(value)。空槽 = u16 0；QUERY_CODE 为卡片首字段） ----
def parse_query_buffer(buf, flags):
    cards, off, cur = [], 0, None
    while off + 2 <= len(buf):
        ln = int.from_bytes(buf[off:off + 2], "little"); off += 2
        if ln == 0:          # 空槽位
            continue
        tag = int.from_bytes(buf[off:off + 4], "little"); off += 4
        payload = buf[off:off + ln - 4]; off += ln - 4
        if tag == QUERY_CODE:
            cur = {tag: int.from_bytes(payload, "little")}
            cards.append(cur)
        elif cur is not None and payload:
            cur[tag] = int.from_bytes(payload, "little")
    return cards
