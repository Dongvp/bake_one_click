import bpy
import os
import subprocess
import sys
from . import _bake_core as core


# ==========================================================
# Operators
# ==========================================================

class BAKE_OT_bake_all(bpy.types.Operator):
    bl_idname = "bake.bake_all"
    bl_label = "Bake All"
    bl_description = "Bake all selected textures"

    def execute(self, context):
        return core.run_bake_all(self, context)


class BAKE_OT_bake_layered(bpy.types.Operator):
    bl_idname = "bake.bake_layered"
    bl_label = "Layered Bake"
    bl_description = ("Bake opaque and transparent high polys separately, "
                      "then output a layered PSD")

    def execute(self, context):
        return core.run_bake_layered(self, context)


class BAKE_OT_open_output_dir(bpy.types.Operator):
    bl_idname = "bake.open_output_dir"
    bl_label = "Open Output Dir"
    bl_description = "Open the bake output directory in the file manager"

    def execute(self, context):
        props = context.scene.bake_props
        output_dir = bpy.path.abspath(props.output_dir)
        try:
            os.makedirs(output_dir, exist_ok=True)
        except Exception as e:
            self.report({'ERROR'}, "Failed to create directory: " + str(e))
            return {'CANCELLED'}
        try:
            if sys.platform == 'win32':
                os.startfile(output_dir)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', output_dir])
            else:
                subprocess.Popen(['xdg-open', output_dir])
            self.report({'INFO'}, "Opened: " + output_dir)
        except Exception as e:
            self.report({'ERROR'}, "Failed to open: " + str(e))
            return {'CANCELLED'}
        return {'FINISHED'}


# ==========================================================
# Root panel (mode switch)
# ==========================================================

class BAKE_PT_mode_switch(bpy.types.Panel):
    bl_label = "Bake One Click"
    bl_idname = "BAKE_PT_mode_switch"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Bake One Click"
    bl_order = 0

    def draw(self, context):
        layout = self.layout
        props = context.scene.bake_props

        row = layout.row(align=True)
        row.scale_y = 1.4
        row.prop(props, "layered_enable",
                 text="Enable Layered Baking",
                 toggle=True, icon='RENDERLAYERS')


# ==========================================================
# Normal baking panel (only when layered_enable is False)
# ==========================================================

class BAKE_PT_normal_panel(bpy.types.Panel):
    bl_label = "Normal Baking"
    bl_idname = "BAKE_PT_normal_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Bake One Click"
    bl_parent_id = "BAKE_PT_mode_switch"
    bl_order = 1

    @classmethod
    def poll(cls, context):
        return not context.scene.bake_props.layered_enable

    def draw(self, context):
        layout = self.layout
        props = context.scene.bake_props

        if props.output_dir.startswith("//") and not bpy.data.filepath:
            box = layout.box()
            box.alert = True
            box.label(text="! Please save the .blend file first",
                      icon='ERROR')

        # ---- Texture Types ----
        box = layout.box()
        box.label(text="Texture Types:", icon='TEXTURE')
        row = box.row(align=True)
        row.prop(props, "bake_normal", toggle=True)
        row.prop(props, "bake_ao", toggle=True)
        row = box.row(align=True)
        row.prop(props, "bake_base_color", toggle=True)
        row.prop(props, "bake_roughness", toggle=True)
        row = box.row(align=True)
        row.prop(props, "bake_metallic", toggle=True)
        row.prop(props, "bake_displacement", toggle=True)

        # ---- Displacement options ----
        if props.bake_displacement:
            box = layout.box()
            box.prop(props, "bake_displacement_normalize", toggle=True)
            col = box.column()
            col.scale_y = 0.7
            col.label(text="Requires Displacement/Bump node")
            col.label(text="in high-poly material.")

        # ---- BaseColor Output ----
        if props.bake_base_color:
            box = layout.box()
            box.label(text="BaseColor Output:", icon='COLOR')
            box.prop(props, "merge_lighting", toggle=True)

        # ---- High to Low ----
        box = layout.box()
        box.label(text="High to Low:", icon='MOD_SHRINKWRAP')
        box.prop(props, "use_selected_to_active")


# ==========================================================
# Layered baking panel (only when layered_enable is True)
# ==========================================================

class BAKE_PT_layered_panel(bpy.types.Panel):
    bl_label = "Layered Baking"
    bl_idname = "BAKE_PT_layered_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Bake One Click"
    bl_parent_id = "BAKE_PT_mode_switch"
    bl_order = 1

    @classmethod
    def poll(cls, context):
        return context.scene.bake_props.layered_enable

    def draw(self, context):
        layout = self.layout
        props = context.scene.bake_props

        if props.output_dir.startswith("//") and not bpy.data.filepath:
            box = layout.box()
            box.alert = True
            box.label(text="! Please save the .blend file first",
                      icon='ERROR')

        # ---- Objects ----
        box = layout.box()
        box.label(text="Objects:", icon='OBJECT_DATA')
        col = box.column(align=True)
        col.prop(props, "layered_low")
        col.prop(props, "layered_opaque_high")
        col.prop(props, "layered_transparent_high")

        # ---- Lighting ----
        box = layout.box()
        box.label(text="Lighting:", icon='LIGHT')
        box.prop(props, "layered_merge_lighting", toggle=True)

        # ---- Layer names ----
        box = layout.box()
        box.label(text="Layer Names:", icon='RENDERLAYERS')
        col = box.column(align=True)
        col.prop(props, "layered_opaque_name")
        col.prop(props, "layered_transparent_name")
        col.prop(props, "layered_output_name")


# ==========================================================
# Common settings (always visible, below Normal/Layered)
# ==========================================================

class BAKE_PT_common_settings(bpy.types.Panel):
    bl_label = "Common Settings"
    bl_idname = "BAKE_PT_common_settings"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Bake One Click"
    bl_parent_id = "BAKE_PT_mode_switch"
    bl_order = 100

    def draw(self, context):
        layout = self.layout
        props = context.scene.bake_props

        # ---- Bake settings ----
        box = layout.box()
        box.label(text="Bake Settings:", icon='MOD_SHRINKWRAP')
        box.prop(props, "resolution")
        box.prop(props, "margin")
        box.prop(props, "cage_extrusion")
        box.prop(props, "max_ray_distance")

        col = box.column()
        col.scale_y = 0.7
        col.label(text="Cage / Ray: only used when Selected to Active.",
                  icon='INFO')


# ==========================================================
# Bake action button panel
# (header hidden, so it stays visible even if Common Settings
#  is collapsed; button text varies with mode)
# ==========================================================

class BAKE_PT_action(bpy.types.Panel):
    bl_label = "Bake Action"
    bl_idname = "BAKE_PT_action"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Bake One Click"
    bl_parent_id = "BAKE_PT_mode_switch"
    bl_order = 101
    bl_options = {'HIDE_HEADER'}   # 无标题栏，无折叠箭头

    def draw(self, context):
        layout = self.layout
        props = context.scene.bake_props

        row = layout.row(align=True)
        row.scale_y = 1.4
        if props.layered_enable:
            row.operator(
                "bake.bake_layered",
                text="Layered Bake + PSD",
                icon='RENDER_STILL',
            )
        else:
            row.operator(
                "bake.bake_all",
                text="Bake All",
                icon='RENDER_STILL',
            )


# ==========================================================
# Output directory panel (always visible)
# ==========================================================

class BAKE_PT_output_dir(bpy.types.Panel):
    bl_label = "Output"
    bl_idname = "BAKE_PT_output_dir"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Bake One Click"
    bl_parent_id = "BAKE_PT_mode_switch"
    bl_order = 102

    def draw(self, context):
        layout = self.layout
        props = context.scene.bake_props

        box = layout.box()
        box.label(text="Output:", icon='FILE_FOLDER')
        row = box.row(align=True)
        row.prop(props, "output_dir", text="")
        row.operator("bake.open_output_dir", text="", icon='FILE_FOLDER')


# ==========================================================
# Output files list (bottom, standard mode only)
# ==========================================================

class BAKE_PT_output_files(bpy.types.Panel):
    bl_label = "Output Files"
    bl_idname = "BAKE_PT_output_files"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Bake One Click"
    bl_parent_id = "BAKE_PT_mode_switch"
    bl_order = 103

    @classmethod
    def poll(cls, context):
        return not context.scene.bake_props.layered_enable

    def draw(self, context):
        layout = self.layout
        props = context.scene.bake_props

        col = layout.column()
        col.scale_y = 0.85

        if props.bake_normal:
            col.label(text="  - xxx_Normal.png")
        if props.bake_ao:
            col.label(text="  - xxx_AO.png")
        if props.bake_roughness:
            col.label(text="  - xxx_Roughness.png")
        if props.bake_metallic:
            col.label(text="  - xxx_Metallic.png")
        if props.bake_displacement:
            col.label(text="  - xxx_Displacement.exr")
        if props.bake_base_color:
            col.label(text="  - xxx_BaseColor.png")

        if not any([
            props.bake_normal, props.bake_ao, props.bake_roughness,
            props.bake_metallic, props.bake_base_color,
            props.bake_displacement,
        ]):
            col.label(text="  (no texture type selected)", icon='ERROR')