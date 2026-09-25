#!/usr/bin/env python3
"""WO-005 P1 冒烟测试：ctypes 加载 ocgcore.dll，读 API 版本。"""
import ctypes, sys

dll = ctypes.CDLL(r"E:\Game\spike\ocg\out\ocgcore.dll")
major = ctypes.c_int()
minor = ctypes.c_int()
dll.OCG_GetVersion(ctypes.byref(major), ctypes.byref(minor))
print(f"OCG_GetVersion -> major={major.value} minor={minor.value}")
assert (major.value, minor.value) == (11, 0), "API 版本与 ocgapi_types.h 不符"
print("SMOKE TEST PASS: DLL 可加载、C 可调用")
