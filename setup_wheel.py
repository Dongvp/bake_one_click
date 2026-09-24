# setup_wheel.py
"""
跨平台构建 wheel 的脚本。

本地 Windows 开发时：优先使用独立安装的 Python 3.13（提供 Python.h + python313.lib）
CI 环境（GitHub Actions）：自动回退到 sysconfig（setup-python 装的 Python 带完整开发文件）

用法:
    python setup_wheel.py bdist_wheel
"""
import os
import sys
import sysconfig
from setuptools import setup, Extension
from Cython.Build import cythonize
import numpy as np


MODULE_NAME = "_core"
SOURCE_FILE = "_core_src/_core.pyx"
LIB_NAME = f"python{sys.version_info.major}{sys.version_info.minor}"


def _find_py_dev():
    """
    返回 (include_dir, libs_dir_or_None)
    - Windows: libs_dir 必须存在（提供 python313.lib）
    - Linux/macOS: libs_dir 为 None
    """
    # 候选根目录：环境变量优先，其次硬编码的独立 Python 3.13
    roots = []
    env_root = os.environ.get("BOC_PY313_ROOT")
    if env_root:
        roots.append(env_root)
    if sys.platform == "win32":
        roots.append(r"C:\Users\yixiu\AppData\Local\Programs\Python\Python313")

    # 1) 尝试独立 Python 根目录
    for root in roots:
        inc = os.path.join(root, "include")
        if not os.path.exists(os.path.join(inc, "Python.h")):
            continue
        if sys.platform == "win32":
            libs = os.path.join(root, "libs")
            if os.path.exists(os.path.join(libs, LIB_NAME + ".lib")):
                print(f"[setup_wheel] 使用独立 Python: {root}")
                return inc, libs
        else:
            print(f"[setup_wheel] 使用独立 Python: {root}")
            return inc, None

    # 2) Fallback: 当前 Python 的 sysconfig（CI 里用）
    inc = sysconfig.get_path("include")
    if inc and os.path.exists(os.path.join(inc, "Python.h")):
        if sys.platform == "win32":
            libs = sysconfig.get_config_var("LIBDIR") or \
                   os.path.join(os.path.dirname(inc), "libs")
            if os.path.exists(os.path.join(libs, LIB_NAME + ".lib")):
                print(f"[setup_wheel] 使用 sysconfig: {inc}")
                return inc, libs
        else:
            print(f"[setup_wheel] 使用 sysconfig: {inc}")
            return inc, None

    return None, None


PY_INCLUDE, PY_LIBS = _find_py_dev()

if PY_INCLUDE is None:
    raise RuntimeError(
        "找不到 Python.h。请确认：\n"
        "  - Windows 本地：独立 Python 3.13 已安装到\n"
        "    C:\\Users\\yixiu\\AppData\\Local\\Programs\\Python\\Python313\n"
        "  - CI 环境：actions/setup-python@v5 已装 Python 3.13"
    )

if not os.path.exists(SOURCE_FILE):
    raise RuntimeError(f"找不到源文件: {SOURCE_FILE}")

extra_args = ["/O2"] if sys.platform == "win32" else ["-O3"]

ext_kwargs = dict(
    name=MODULE_NAME,
    sources=[SOURCE_FILE],
    include_dirs=[np.get_include(), PY_INCLUDE],
    extra_compile_args=extra_args,
)
if sys.platform == "win32":
    ext_kwargs["library_dirs"] = [PY_LIBS]
    ext_kwargs["libraries"] = [LIB_NAME]

setup(
    name="bake_one_click_core",
    version="1.23.0",
    packages=[],
    py_modules=[],
    ext_modules=cythonize(
        [Extension(**ext_kwargs)],
        compiler_directives={
            "language_level": "3",
            "embedsignature": False,
            "binding": True,
            "always_allow_keywords": True,
        },
        annotate=False,
        quiet=True,
    ),
    zip_safe=False,
)