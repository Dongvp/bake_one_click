import bpy
import os
import subprocess
import sys
from bpy.app.translations import pgettext_iface as iface_
from . import _bake_core as core          # ★ 只导入编译核心


# ==========================================================
# 主烘焙操作符（薄壳）
# ==========================================================

class BAKE_OT_bake_all(bpy.types.Operator):
    bl_idname = "bake.bake_all"
    bl_label = "一键烘焙"
    bl_description = "烘焙所有选中的贴图"

    def execute(self, context):
        # 全部逻辑在编译核心中
        return core.run_bake_all(self, context)


# ==========================================================
# 分层烘焙操作符（薄壳）
# ==========================================================

class BAKE_OT_bake_layered(bpy.types.Operator):
    bl_idname = "bake.bake_layered"
    bl_label = "一键分层烘焙"
    bl_description = "分别烘焙不透明高模和半透明高模，输出合并 PSD"

    def execute(self, context):
        return core.run_bake_layered(self, context)


# ==========================================================
# 辅助操作符
# ==========================================================

class BAKE_OT_open_output_dir(bpy.types.Operator):
    bl_idname = "bake.open_output_dir"
    bl_label = "打开输出目录"
    bl_description = "在文件管理器中打开烘焙输出目录"

    def execute(self, context):
        props = context.scene.bake_props
        output_dir = bpy.path.abspath(props.output_dir)
        try:
            os.makedirs(output_dir, exist_ok=True)
        except Exception as e:
            self.report(
                {'ERROR'},
                iface_("创建目录失败: {err}").format(err=str(e))
            )
            return {'CANCELLED'}
        try:
            if sys.platform == 'win32':
                os.startfile(output_dir)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', output_dir])
            else:
                subprocess.Popen(['xdg-open', output_dir])
            self.report(
                {'INFO'},
                iface_("已打开: {path}").format(path=output_dir)
            )
        except Exception as e:
            self.report(
                {'ERROR'},
                iface_("打开失败: {err}").format(err=str(e))
            )
            return {'CANCELLED'}
        return {'FINISHED'}


# ==========================================================
# 顶部：模式切换面板
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
        row.prop(props, "layered_enable", text=iface_("启用分层烘焙模式"),
                 toggle=True, icon='RENDERLAYERS')

        layout.separator()
        layout.prop(props, "resolution")


# ==========================================================
# 分层烘焙面板
# ==========================================================

class BAKE_PT_layered_panel(bpy.types.Panel):
    bl_label = "分层烘焙模式"
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

        box = layout.box()
        col = box.column(align=True)
        col.prop(props, "layered_low")
        col.prop(props, "layered_opaque_high")
        col.prop(props, "layered_transparent_high")

        box.prop(props, "layered_merge_lighting", toggle=True)

        box = layout.box()
        box.label(text=iface_("烘焙参数:"), icon='MOD_SHRINKWRAP')
        box.prop(props, "layered_cage_extrusion")
        box.prop(props, "layered_max_ray_distance")
        box.prop(props, "layered_margin")

        box = layout.box()
        col = box.column(align=True)
        col.prop(props, "layered_opaque_name")
        col.prop(props, "layered_transparent_name")
        col.prop(props, "layered_output_name")

        box = layout.box()
        row = box.row(align=True)
        row.prop(props, "output_dir", text="")
        row.operator("bake.open_output_dir", text="", icon='FILE_FOLDER')

        col = box.column()
        col.scale_y = 0.7
        col.label(text=iface_("将输出:"), icon='INFO')
        out_name = props.layered_output_name or "Layered"
        col.label(
            text=iface_("  • {name}.psd（含图层）").format(name=out_name)
        )

        layout.separator()
        layout.operator(
            "bake.bake_layered",
            text=iface_("一键分层烘焙") + " + PSD",
            icon='RENDER_STILL',
        )


# ==========================================================
# 普通烘焙面板
# ==========================================================

class BAKE_PT_normal_panel(bpy.types.Panel):
    bl_label = "普通烘焙模式"
    bl_idname = "BAKE_PT_normal_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Bake One Click"
    bl_parent_id = "BAKE_PT_mode_switch"
    bl_order = 2

    @classmethod
    def poll(cls, context):
        return not context.scene.bake_props.layered_enable

    def draw(self, context):
        layout = self.layout
        props = context.scene.bake_props

        # ★ 已删除三行写属性的代码（Blender 5.x 不允许在 draw() 里写 ID 属性）
        #   相关自动逻辑已由 properties.py 的 update 回调和 _core.run_bake_all 处理

        if props.output_dir.startswith("//") and not bpy.data.filepath:
            box = layout.box()
            box.alert = True
            box.label(text=iface_("⚠ 请先保存 .blend 文件"), icon='ERROR')

        box = layout.box()
        box.label(text=iface_("贴图类型:"), icon='TEXTURE')
        row = box.row(align=True)
        row.prop(props, "bake_normal", toggle=True)
        row.prop(props, "bake_ao", toggle=True)
        row = box.row(align=True)
        if props.bake_opacity:
            row.label(text=iface_("基础色（自动）"))
        else:
            row.prop(props, "bake_base_color", toggle=True)
        row.prop(props, "bake_roughness", toggle=True)
        row = box.row(align=True)
        row.prop(props, "bake_metallic", toggle=True)
        row.prop(props, "bake_opacity", toggle=True)

        if props.bake_base_color:
            box = layout.box()
            box.label(text=iface_("BaseColor 输出:"), icon='COLOR')
            box.prop(props, "merge_lighting", toggle=True)

        if props.bake_opacity:
            box = layout.box()
            box.label(text=iface_("透明贴图合并:"), icon='IMAGE_ALPHA')
            box.prop(props, "transparent_suffix")

            active = context.view_layer.objects.active
            if active and active.type == 'MESH':
                box.label(
                    text=iface_("将处理: {name}").format(name=active.name),
                    icon='OBJECT_DATA',
                )
            else:
                box.alert = True
                box.label(text=iface_("未选择激活物体"), icon='ERROR')

        box = layout.box()
        box.label(text=iface_("将输出以下文件:"), icon='FILE_IMAGE')
        col = box.column()
        col.scale_y = 0.7

        if props.bake_normal:
            col.label(text="  • xxx_Normal.png")
        if props.bake_ao:
            col.label(text="  • xxx_AO.png")
        if props.bake_roughness:
            col.label(text="  • xxx_Roughness.png")
        if props.bake_metallic:
            col.label(text="  • xxx_Metallic.png")

        if props.bake_opacity:
            suf = props.transparent_suffix or "Transparent"
            col.label(
                text=iface_("  • xxx_{suf}.png（合并，带 Alpha）").format(suf=suf),
                icon='CHECKMARK',
            )
        elif props.bake_base_color:
            col.label(text="  • xxx_BaseColor.png")

        if not any([
            props.bake_normal, props.bake_ao, props.bake_roughness,
            props.bake_metallic, props.bake_base_color, props.bake_opacity,
        ]):
            col.label(text=iface_("  （未选择任何贴图类型）"), icon='ERROR')

        box = layout.box()
        box.label(text=iface_("高模到低模:"), icon='MOD_SHRINKWRAP')
        box.prop(props, "use_selected_to_active")
        if props.use_selected_to_active:
            box.prop(props, "cage_extrusion")
            box.prop(props, "max_ray_distance")

        layout.prop(props, "margin")

        row = layout.row(align=True)
        row.prop(props, "output_dir", text="")
        row.operator("bake.open_output_dir", text="", icon='FILE_FOLDER')

        layout.separator()
        layout.operator("bake.bake_all",
                        text=iface_("一键烘焙"), icon='RENDER_STILL')