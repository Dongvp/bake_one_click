# setup_wheel.py
"""
Cross-platform wheel builder for the compiled _core module.

Local Windows dev: prefers the standalone Python 3.13 install
                   (provides Python.h + python313.lib)
CI (GitHub Actions): falls back to sysconfig (setup-python comes
                     with full dev files)

Usage:
    python setup_wheel.py bdist_wheel

Output:
    dist/bake_one_click_core-1.23.0-cp313-cp313-<platform>.whl
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
    Return (include_dir, libs_dir_or_None).
    - Windows: libs_dir must exist (provides python3xx.lib)
    - Linux/macOS: libs_dir is None
    """
    roots = []
    env_root = os.environ.get("BOC_PY313_ROOT")
    if env_root:
        roots.append(env_root)
    if sys.platform == "win32":
        roots.append(r"C:\Users\yixiu\AppData\Local\Programs\Python\Python313")

    # 1) try standalone Python roots
    for root in roots:
        inc = os.path.join(root, "include")
        if not os.path.exists(os.path.join(inc, "Python.h")):
            continue
        if sys.platform == "win32":
            libs = os.path.join(root, "libs")
            if os.path.exists(os.path.join(libs, LIB_NAME + ".lib")):
                print("[setup_wheel] using standalone Python: " + root)
                return inc, libs
        else:
            print("[setup_wheel] using standalone Python: " + root)
            return inc, None

    # 2) fallback: sysconfig of current Python (used on CI)
    inc = sysconfig.get_path("include")
    if inc and os.path.exists(os.path.join(inc, "Python.h")):
        if sys.platform == "win32":
            libs = sysconfig.get_config_var("LIBDIR") or \
                   os.path.join(os.path.dirname(inc), "libs")
            if os.path.exists(os.path.join(libs, LIB_NAME + ".lib")):
                print("[setup_wheel] using sysconfig include: " + inc)
                return inc, libs
        else:
            print("[setup_wheel] using sysconfig include: " + inc)
            return inc, None

    return None, None


PY_INCLUDE, PY_LIBS = _find_py_dev()

if PY_INCLUDE is None:
    raise RuntimeError(
        "Python.h not found. Please make sure:\n"
        "  - Windows local: standalone Python 3.13 installed at\n"
        "    C:\\Users\\yixiu\\AppData\\Local\\Programs\\Python\\Python313\n"
        "  - CI: actions/setup-python@v5 has installed Python 3.13"
    )

if not os.path.exists(SOURCE_FILE):
    raise RuntimeError("Source file not found: " + SOURCE_FILE)

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