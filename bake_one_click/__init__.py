bl_info = {
    "name": "Bake One Click",
    "author": "yixiu",
    "version": (1, 23, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > Bake One Click",
    "description": "一键烘焙 + 分层烘焙合并输出 PSD",
    "category": "Object",
}

import bpy
from . import properties, _bake_core, ui_panel   # ★ 用编译核心替代 processing


# ==========================================================
# 翻译字典（内嵌，与原文件完全一致，此处省略重复粘贴）
# ==========================================================
translations_dict = {
    # ... 保持原样，一字不改 ...
}


classes = (
    properties.BakeProperties,
    ui_panel.BAKE_OT_bake_all,
    ui_panel.BAKE_OT_bake_layered,
    ui_panel.BAKE_OT_open_output_dir,
    ui_panel.BAKE_PT_mode_switch,
    ui_panel.BAKE_PT_layered_panel,
    ui_panel.BAKE_PT_normal_panel,
)

_translation_registered = False


def register():
    global _translation_registered

    if not _translation_registered:
        try:
            bpy.app.translations.register(__name__, translations_dict)
            _translation_registered = True
            print(f"[BakeOneClick] 翻译已注册: {__name__}")
        except Exception as e:
            print(f"[BakeOneClick] 翻译注册失败: {e}")

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.bake_props = bpy.props.PointerProperty(
        type=properties.BakeProperties
    )


def unregister():
    global _translation_registered

    if hasattr(bpy.types.Scene, "bake_props"):
        del bpy.types.Scene.bake_props

    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass

    if _translation_registered:
        try:
            bpy.app.translations.unregister(__name__)
            _translation_registered = False
        except Exception as e:
            print(f"[BakeOneClick] 翻译注销失败: {e}")


if __name__ == "__main__":
    register()