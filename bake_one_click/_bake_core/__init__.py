# bake_one_click/_bake_core/__init__.py
"""
转发层：
- Blender 5.x 扩展系统会先把 wheels/*.whl 解压到扩展自己的 site-packages，
  所以 _core 现在是顶层模块。
- 保留相对导入作为开发期回退（未安装 wheel 时）。
"""

try:
    import _core                      # 优先：由 wheel 提供的顶层模块
except ImportError:
    from . import _core               # 回退：本地 .pyd / .py（开发期）

for _name in ("run_bake_all", "run_bake_layered"):
    if hasattr(_core, _name):
        globals()[_name] = getattr(_core, _name)

__all__ = ["run_bake_all", "run_bake_layered"]