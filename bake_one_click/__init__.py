bl_info = {
    "name": "Bake One Click",
    "author": "yixiu",
    "version": (1, 23, 0),
    "blender": (5, 1, 0),
    "location": "View3D > Sidebar > Bake One Click",
    "description": "One-click baking with layered output to PSD",
    "category": "Object",
}

import bpy
from . import properties, _bake_core, ui_panel


classes = (
    properties.BakeProperties,
    ui_panel.BAKE_OT_bake_all,
    ui_panel.BAKE_OT_bake_layered,
    ui_panel.BAKE_OT_open_output_dir,
    ui_panel.BAKE_PT_mode_switch,
    ui_panel.BAKE_PT_layered_panel,
    ui_panel.BAKE_PT_normal_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.bake_props = bpy.props.PointerProperty(
        type=properties.BakeProperties
    )


def unregister():
    if hasattr(bpy.types.Scene, "bake_props"):
        del bpy.types.Scene.bake_props

    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass


if __name__ == "__main__":
    register()