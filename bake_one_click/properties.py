import bpy


def _on_opacity_changed(self, context):
    if self.bake_opacity:
        self.bake_base_color = True


# ==========================================================
# 分辨率枚举
# ==========================================================

RESOLUTION_ITEMS = [
    ('256',  '256 x 256',   '256 x 256'),
    ('512',  '512 x 512',   '512 x 512'),
    ('1024', '1024 x 1024', '1024 x 1024'),
    ('2048', '2048 x 2048', '2048 x 2048'),
    ('4096', '4096 x 4096', '4096 x 4096'),
]


class BakeProperties(bpy.types.PropertyGroup):
    resolution: bpy.props.EnumProperty(
        name="分辨率",
        items=RESOLUTION_ITEMS,
        default='2048',
        description="烘焙图像分辨率",
    )

    margin: bpy.props.IntProperty(
        name="边缘扩展", default=16, min=0, max=64,
    )

    bake_normal: bpy.props.BoolProperty(name="法线", default=True)
    bake_ao: bpy.props.BoolProperty(name="AO", default=True)
    bake_base_color: bpy.props.BoolProperty(name="基础色", default=False)
    bake_roughness: bpy.props.BoolProperty(name="粗糙度", default=False)
    bake_metallic: bpy.props.BoolProperty(name="金属度", default=False)
    bake_opacity: bpy.props.BoolProperty(
        name="不透明度", default=True, update=_on_opacity_changed,
    )

    merge_lighting: bpy.props.BoolProperty(
        name="BaseColor 合并光照", default=False,
    )

    merge_transparency: bpy.props.BoolProperty(
        name="合并为透明贴图", default=True,
    )
    transparent_suffix: bpy.props.StringProperty(
        name="透明贴图后缀", default="Transparent",
    )
    premultiply_alpha: bpy.props.BoolProperty(
        name="预乘 Alpha", default=True,
    )

    use_selected_to_active: bpy.props.BoolProperty(
        name="选定到激活", default=False,
    )
    cage_extrusion: bpy.props.FloatProperty(
        name="笼子挤出", default=0.0, min=0.0, max=10.0
    )
    max_ray_distance: bpy.props.FloatProperty(
        name="最大射线距离", default=0.0, min=0.0, max=10.0
    )

    output_dir: bpy.props.StringProperty(
        name="输出目录", default="//bake_output", subtype='DIR_PATH'
    )

    # ==========================================================
    # 分层烘焙模式
    # ==========================================================
    layered_enable: bpy.props.BoolProperty(
        name="启用分层烘焙模式", default=False,
    )
    layered_merge_lighting: bpy.props.BoolProperty(
        name="合并光照",
        default=False,
        description="开启：两个高模都使用 COMBINED 烘焙（受场景光照影响）；"
                    "关闭：都使用 EMIT（无光照）"
    )

    # 分层模式专用烘焙参数（不与普通模式共用）
    layered_margin: bpy.props.IntProperty(
        name="边缘扩展", default=16, min=0, max=64,
        description="只作用于不透明层，半透明层不做边缘扩展"
    )
    layered_cage_extrusion: bpy.props.FloatProperty(
        name="笼子挤出", default=0.0, min=0.0, max=10.0,
    )
    layered_max_ray_distance: bpy.props.FloatProperty(
        name="最大射线距离", default=0.0, min=0.0, max=10.0,
    )

    layered_low: bpy.props.PointerProperty(
        name="低模", type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH',
    )
    layered_opaque_high: bpy.props.PointerProperty(
        name="不透明高模", type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH',
    )
    layered_transparent_high: bpy.props.PointerProperty(
        name="半透明高模", type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH',
    )

    layered_opaque_name: bpy.props.StringProperty(
        name="不透明层名", default="Opaque",
    )
    layered_transparent_name: bpy.props.StringProperty(
        name="半透明层名", default="Transparent",
    )
    layered_output_name: bpy.props.StringProperty(
        name="合并输出名", default="Layered",
    )