import bpy


def _on_opacity_changed(self, context):
    if self.bake_opacity:
        self.bake_base_color = True


RESOLUTION_ITEMS = [
    ('256',  '256 x 256',   '256 x 256'),
    ('512',  '512 x 512',   '512 x 512'),
    ('1024', '1024 x 1024', '1024 x 1024'),
    ('2048', '2048 x 2048', '2048 x 2048'),
    ('4096', '4096 x 4096', '4096 x 4096'),
]


class BakeProperties(bpy.types.PropertyGroup):
    resolution: bpy.props.EnumProperty(
        name="Resolution",
        items=RESOLUTION_ITEMS,
        default='2048',
        description="Bake texture resolution",
    )

    margin: bpy.props.IntProperty(
        name="Margin", default=16, min=0, max=64,
        description="UV island edge margin",
    )

    bake_normal: bpy.props.BoolProperty(name="Normal", default=True)
    bake_ao: bpy.props.BoolProperty(name="AO", default=True)
    bake_base_color: bpy.props.BoolProperty(name="Base Color", default=False)
    bake_roughness: bpy.props.BoolProperty(name="Roughness", default=False)
    bake_metallic: bpy.props.BoolProperty(name="Metallic", default=False)
    bake_opacity: bpy.props.BoolProperty(
        name="Opacity", default=True, update=_on_opacity_changed,
    )

    merge_lighting: bpy.props.BoolProperty(
        name="BaseColor with Lighting", default=False,
    )

    merge_transparency: bpy.props.BoolProperty(
        name="Merge to Transparent", default=True,
    )
    transparent_suffix: bpy.props.StringProperty(
        name="Transparent Suffix", default="Transparent",
    )
    premultiply_alpha: bpy.props.BoolProperty(
        name="Premultiply Alpha", default=True,
    )

    use_selected_to_active: bpy.props.BoolProperty(
        name="Selected to Active", default=False,
    )
    cage_extrusion: bpy.props.FloatProperty(
        name="Cage Extrusion", default=0.0, min=0.0, max=10.0
    )
    max_ray_distance: bpy.props.FloatProperty(
        name="Max Ray Distance", default=0.0, min=0.0, max=10.0
    )

    output_dir: bpy.props.StringProperty(
        name="Output Dir", default="//bake_output", subtype='DIR_PATH'
    )

    layered_enable: bpy.props.BoolProperty(
        name="Enable Layered Baking", default=False,
    )
    layered_merge_lighting: bpy.props.BoolProperty(
        name="Merge Lighting",
        default=False,
        description="On: both high polys use COMBINED (lit). "
                    "Off: both use EMIT (unlit)."
    )

    layered_margin: bpy.props.IntProperty(
        name="Margin", default=16, min=0, max=64,
        description="Only applies to the opaque layer. "
                    "Transparent layer has no margin."
    )
    layered_cage_extrusion: bpy.props.FloatProperty(
        name="Cage Extrusion", default=0.0, min=0.0, max=10.0,
    )
    layered_max_ray_distance: bpy.props.FloatProperty(
        name="Max Ray Distance", default=0.0, min=0.0, max=10.0,
    )

    layered_low: bpy.props.PointerProperty(
        name="Low Poly", type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH',
    )
    layered_opaque_high: bpy.props.PointerProperty(
        name="Opaque High Poly", type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH',
    )
    layered_transparent_high: bpy.props.PointerProperty(
        name="Transparent High Poly", type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH',
    )

    layered_opaque_name: bpy.props.StringProperty(
        name="Opaque Layer", default="Opaque",
    )
    layered_transparent_name: bpy.props.StringProperty(
        name="Transparent Layer", default="Transparent",
    )
    layered_output_name: bpy.props.StringProperty(
        name="Output Name", default="Layered",
    )