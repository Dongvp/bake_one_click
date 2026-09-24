# setup_wheel.py
import os
import sys
import sysconfig
from setuptools import setup, Extension
from Cython.Build import cythonize
import numpy as np

MODULE_NAME = "_core"
SOURCE_FILE = "_core_src/_core.pyx"

# 自动检测当前 Python 的 include / libs
PY_INCLUDE = sysconfig.get_path("include")
PY_LIBS = sysconfig.get_config_var("LIBDIR") or \
          os.path.join(os.path.dirname(PY_INCLUDE), "libs")
PY_LIB_NAME = f"python{sys.version_info.major}{sys.version_info.minor}"

if not os.path.exists(os.path.join(PY_INCLUDE, "Python.h")):
    raise RuntimeError(f"找不到 Python.h: {PY_INCLUDE}")
if not os.path.exists(SOURCE_FILE):
    raise RuntimeError(f"找不到源文件: {SOURCE_FILE}")

extra_args = ["/O2"] if sys.platform == "win32" else ["-O3"]

# Linux/mac 上加 libraries 会导致某些构建环境报错，所以按平台区分
ext_kwargs = dict(
    name=MODULE_NAME,
    sources=[SOURCE_FILE],
    include_dirs=[np.get_include(), PY_INCLUDE],
    extra_compile_args=extra_args,
)
if sys.platform == "win32":
    ext_kwargs["library_dirs"] = [PY_LIBS]
    ext_kwargs["libraries"] = [PY_LIB_NAME]

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