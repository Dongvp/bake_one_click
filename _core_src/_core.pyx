# _core_src/_core.pyx
# cython: language_level=3
# cython: embedsignature=False
# cython: binding=True
# cython: always_allow_keywords=True
"""
Bake One Click - compiled core module.

Contains: image baking, material node rewriting, alpha handling,
PSD binary encoding, and full pipelines for standard / layered bakes.
"""

import bpy
import os
import struct
import numpy as np


# ==========================================================
# License check placeholder (compiled into the binary)
# ==========================================================

def _ensure_activated():
    """
    License check placeholder. Currently always returns True.
    For release builds, wire this to a machine-fingerprint / server-token
    check that returns False when invalid; the caller can then degrade
    the output silently.
    """
    return True


# ==========================================================
# Environment setup
# ==========================================================

def setup_bake_environment():
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 64
    scene.cycles.use_denoising = False
    return scene


def create_bake_image(name, resolution, is_non_color=False):
    if name in bpy.data.images:
        old = bpy.data.images[name]
        try:
            bpy.data.images.remove(old, do_unlink=True)
        except Exception as e:
            print(f"[BakeOneClick] Failed to remove old image: {e}")

    img = bpy.data.images.new(
        name=name, width=resolution, height=resolution,
        float_buffer=True, alpha=True
    )
    try:
        img.alpha_mode = 'STRAIGHT'
    except Exception:
        pass
    if is_non_color:
        img.colorspace_settings.name = 'Non-Color'
    return img


# ==========================================================
# Bake node management
# ==========================================================

def _attach_bake_nodes(target_objs, image):
    added = []
    seen = set()
    for obj in target_objs:
        if not obj.data.materials:
            continue
        for mat in obj.data.materials:
            if not mat or not mat.use_nodes:
                continue
            if id(mat) in seen:
                continue
            seen.add(id(mat))
            nodes = mat.node_tree.nodes
            img_node = nodes.new('ShaderNodeTexImage')
            img_node.image = image
            img_node.select = True
            nodes.active = img_node
            added.append((mat, img_node))
    return added


def _cleanup_bake_nodes(added_nodes):
    for mat, node in added_nodes:
        try:
            mat.node_tree.nodes.remove(node)
        except Exception:
            pass


# ==========================================================
# Material lookup helpers
# ==========================================================

def _get_output_node(mat):
    for n in mat.node_tree.nodes:
        if n.type == 'OUTPUT_MATERIAL':
            return n
    return None


def _find_principled(mat):
    for n in mat.node_tree.nodes:
        if n.type == 'BSDF_PRINCIPLED':
            return n
    return None


def _get_input_source(mat, principled, input_name, temp_nodes):
    inp = principled.inputs[input_name]
    if inp.is_linked:
        return inp.links[0].from_socket

    if hasattr(inp.default_value, '__len__'):
        node = mat.node_tree.nodes.new('ShaderNodeRGB')
    else:
        node = mat.node_tree.nodes.new('ShaderNodeValue')
    node.outputs[0].default_value = inp.default_value
    temp_nodes.append(node)
    return node.outputs[0]


# ==========================================================
# Temporary material modification per mode
# ==========================================================

def _disable_principled_emission(mat, principled, emission_backups):
    es = principled.inputs.get('Emission Strength')
    if es is not None:
        orig_val = es.default_value
        orig_socket = None
        if es.is_linked:
            orig_socket = es.links[0].from_socket
            mat.node_tree.links.remove(es.links[0])
        es.default_value = 0.0
        emission_backups.append(('strength', es, orig_val, orig_socket))

    ec = principled.inputs.get('Emission Color')
    if ec is None:
        ec = principled.inputs.get('Emission')
    if ec is not None and ec.is_linked:
        orig_socket = ec.links[0].from_socket
        mat.node_tree.links.remove(ec.links[0])
        emission_backups.append(('color_link', ec, None, orig_socket))


def _restore_principled_emission(mat, emission_backups):
    for entry in emission_backups:
        kind, socket, orig_val, orig_socket = entry
        try:
            if kind == 'strength':
                socket.default_value = orig_val
                if orig_socket is not None:
                    mat.node_tree.links.new(orig_socket, socket)
            elif kind == 'color_link':
                if orig_socket is not None:
                    mat.node_tree.links.new(orig_socket, socket)
        except Exception as e:
            print(f"[BakeOneClick] Failed to restore emission: {e}")


def _apply_mode_to_material(mat, mode):
    """
    mode:
      - 'standard'          : leave the material untouched
      - 'basecolor_combined': route Principled to Output (COMBINED lighting)
      - 'basecolor_emit'    : route BaseColor to Emission
      - 'metallic_emit'     : route Metallic to Emission
      - 'alpha_emit'        : route Principled.Alpha to Emission
    """
    if mode == 'standard':
        return None

    output_node = _get_output_node(mat)
    if not output_node:
        return None

    original_socket = None
    if output_node.inputs['Surface'].is_linked:
        original_socket = output_node.inputs['Surface'].links[0].from_socket
        mat.node_tree.links.remove(output_node.inputs['Surface'].links[0])

    temp_nodes = []
    emission_backups = []
    ok = False

    try:
        principled = _find_principled(mat)

        if mode == 'basecolor_combined':
            if principled:
                _disable_principled_emission(mat, principled, emission_backups)
                mat.node_tree.links.new(
                    principled.outputs['BSDF'],
                    output_node.inputs['Surface']
                )
                ok = True

        elif mode == 'basecolor_emit':
            src = None
            if principled:
                src = _get_input_source(mat, principled, 'Base Color', temp_nodes)
            emit = mat.node_tree.nodes.new('ShaderNodeEmission')
            temp_nodes.append(emit)
            if src:
                mat.node_tree.links.new(src, emit.inputs['Color'])
            else:
                emit.inputs['Color'].default_value = (0.8, 0.8, 0.8, 1.0)
            mat.node_tree.links.new(
                emit.outputs['Emission'], output_node.inputs['Surface']
            )
            ok = True

        elif mode == 'metallic_emit':
            src = None
            if principled:
                src = _get_input_source(mat, principled, 'Metallic', temp_nodes)
            emit = mat.node_tree.nodes.new('ShaderNodeEmission')
            temp_nodes.append(emit)
            if src:
                mat.node_tree.links.new(src, emit.inputs['Color'])
            else:
                emit.inputs['Color'].default_value = (0.0, 0.0, 0.0, 1.0)
            mat.node_tree.links.new(
                emit.outputs['Emission'], output_node.inputs['Surface']
            )
            ok = True

        elif mode == 'alpha_emit':
            src = None
            if principled:
                alpha_inp = principled.inputs.get('Alpha')
                if alpha_inp is not None:
                    if alpha_inp.is_linked:
                        src = alpha_inp.links[0].from_socket
                        print(f"[BakeOneClick] alpha_emit: "
                              f"using Alpha link {src.name}")
                    else:
                        val_node = mat.node_tree.nodes.new('ShaderNodeValue')
                        val_node.outputs[0].default_value = \
                            alpha_inp.default_value
                        temp_nodes.append(val_node)
                        src = val_node.outputs[0]
                        print(f"[BakeOneClick] alpha_emit: "
                              f"using Alpha constant {alpha_inp.default_value}")

            emit = mat.node_tree.nodes.new('ShaderNodeEmission')
            temp_nodes.append(emit)
            if src is not None:
                mat.node_tree.links.new(src, emit.inputs['Color'])
            else:
                emit.inputs['Color'].default_value = (1.0, 1.0, 1.0, 1.0)
            mat.node_tree.links.new(
                emit.outputs['Emission'], output_node.inputs['Surface']
            )
            ok = True

    except Exception as e:
        print(f"[BakeOneClick] Failed to apply material mod: {e}")

    if not ok:
        if original_socket:
            mat.node_tree.links.new(
                original_socket, output_node.inputs['Surface']
            )
        _restore_principled_emission(mat, emission_backups)
        for n in temp_nodes:
            try:
                mat.node_tree.nodes.remove(n)
            except Exception:
                pass
        return None

    def restore():
        try:
            for link in list(output_node.inputs['Surface'].links):
                mat.node_tree.links.remove(link)
            if original_socket:
                mat.node_tree.links.new(
                    original_socket, output_node.inputs['Surface']
                )
        except Exception as e:
            print(f"[BakeOneClick] Failed to restore material links: {e}")
        _restore_principled_emission(mat, emission_backups)
        for n in temp_nodes:
            try:
                mat.node_tree.nodes.remove(n)
            except Exception:
                pass

    return restore


def _apply_material_mods(source_objs, mode):
    if mode == 'standard':
        return []
    restore_fns = []
    seen = set()
    for obj in source_objs:
        for mat in obj.data.materials:
            if not mat or not mat.use_nodes:
                continue
            if id(mat) in seen:
                continue
            seen.add(id(mat))
            restore = _apply_mode_to_material(mat, mode)
            if restore:
                restore_fns.append(restore)
    return restore_fns


def _restore_all(restore_fns):
    for fn in restore_fns:
        try:
            fn()
        except Exception as e:
            print(f"[BakeOneClick] Restore failed: {e}")


# ==========================================================
# Bake settings
# ==========================================================

def _apply_bake_settings(scene, props, is_s2a, use_clear=True,
                          margin=None, cage_extrusion=None,
                          max_ray_distance=None):
    if margin is None:
        margin = props.margin
    if cage_extrusion is None:
        cage_extrusion = props.cage_extrusion
    if max_ray_distance is None:
        max_ray_distance = props.max_ray_distance

    bake = scene.render.bake
    bake.use_selected_to_active = is_s2a
    bake.cage_extrusion = cage_extrusion
    bake.max_ray_distance = max_ray_distance
    bake.margin = margin
    bake.use_clear = use_clear
    try:
        bake.use_pass_direct = True
        bake.use_pass_indirect = True
        bake.use_pass_color = True
    except Exception:
        pass


# ==========================================================
# Low-level bake entry
# ==========================================================

def bake_single(source_objs, target_obj, image, props,
                bake_type, mode, is_s2a=None,
                margin=None, cage_extrusion=None, max_ray_distance=None):
    if is_s2a is None:
        is_s2a = props.use_selected_to_active

    scene = bpy.context.scene
    restore_fns = _apply_material_mods(source_objs, mode)
    added_nodes = _attach_bake_nodes([target_obj], image)
    _apply_bake_settings(
        scene, props, is_s2a, use_clear=True,
        margin=margin,
        cage_extrusion=cage_extrusion,
        max_ray_distance=max_ray_distance,
    )

    bpy.ops.object.select_all(action='DESELECT')
    if is_s2a:
        for obj in source_objs:
            obj.select_set(True)
    target_obj.select_set(True)
    bpy.context.view_layer.objects.active = target_obj

    try:
        bpy.ops.object.bake(type=bake_type)
    finally:
        _restore_all(restore_fns)
        _cleanup_bake_nodes(added_nodes)

    return image


# ==========================================================
# Image post-processing
# ==========================================================

def fix_opaque_alpha_from_rgb(img, rgb_threshold=1e-6, alpha_threshold=1e-6):
    w, h = img.size
    n = w * h * 4
    px = np.empty(n, dtype=np.float32)
    img.pixels.foreach_get(px)

    rgb_max = np.maximum.reduce([px[0::4], px[1::4], px[2::4]])
    orig_alpha = px[3::4]

    valid = (rgb_max > rgb_threshold) | (orig_alpha > alpha_threshold)
    new_alpha = np.where(valid, 1.0, 0.0).astype(np.float32)

    old_count = int(np.count_nonzero(orig_alpha > alpha_threshold))
    new_count = int(np.count_nonzero(valid))

    px[3::4] = new_alpha
    img.pixels.foreach_set(px)
    img.update()

    try:
        img.alpha_mode = 'STRAIGHT'
    except Exception:
        pass

    print(f"[BakeOneClick] fix opaque alpha: "
          f"old valid={old_count}, new valid={new_count} / {w*h} "
          f"({100.0 * new_count / (w * h):.1f}%)")


# ==========================================================
# Image saving
# ==========================================================

def _save_png_filepath(image, filepath):
    try:
        image.filepath_raw = filepath
        image.file_format = 'PNG'
        image.save()
        if os.path.exists(filepath):
            print(f"[BakeOneClick] Saved: {filepath}")
            return filepath
    except Exception as e:
        print(f"[BakeOneClick] image.save() failed: {e}, trying save_render()")

    try:
        image.save_render(filepath)
        if os.path.exists(filepath):
            print(f"[BakeOneClick] Saved (save_render): {filepath}")
            return filepath
    except Exception as e:
        print(f"[BakeOneClick] save_render() also failed: {e}")

    print(f"[BakeOneClick] File was not created: {filepath}")
    return None


def save_image(image, suffix, output_dir):
    output_dir = bpy.path.abspath(output_dir)
    try:
        os.makedirs(output_dir, exist_ok=True)
    except Exception as e:
        print(f"[BakeOneClick] Failed to create directory: {e}")
        return None
    suffix_str = f"_{suffix}"
    base_name = image.name
    if base_name.endswith(suffix_str):
        base_name = base_name[:-len(suffix_str)]
    filepath = os.path.join(output_dir, f"{base_name}{suffix_str}.png")
    return _save_png_filepath(image, filepath)


def remove_output_files(output_dir, filenames):
    output_dir = bpy.path.abspath(output_dir)
    removed = []
    for name in filenames:
        path = os.path.join(output_dir, name)
        if os.path.exists(path):
            try:
                os.remove(path)
                removed.append(path)
                print(f"[BakeOneClick] Deleted: {path}")
            except Exception as e:
                print(f"[BakeOneClick] Failed to delete {path}: {e}")
    return removed


# ==========================================================
# Transparent texture merge
# ==========================================================

def merge_opacity_into_basecolor_image(basecolor_img, opacity_img,
                                       premultiply=False):
    if (basecolor_img.size[0] != opacity_img.size[0] or
            basecolor_img.size[1] != opacity_img.size[1]):
        print(f"[BakeOneClick] Size mismatch: "
              f"BaseColor{basecolor_img.size} vs Opacity{opacity_img.size}")
        return False

    w, h = basecolor_img.size
    n = w * h * 4

    base_px = np.empty(n, dtype=np.float32)
    opa_px = np.empty(n, dtype=np.float32)
    basecolor_img.pixels.foreach_get(base_px)
    opacity_img.pixels.foreach_get(opa_px)

    alpha_values = opa_px[0::4].copy()
    base_px[3::4] = alpha_values

    if premultiply:
        print("[BakeOneClick] Note: premultiply param ignored, "
              "using straight alpha")

    basecolor_img.pixels.foreach_set(base_px)
    basecolor_img.update()

    try:
        basecolor_img.alpha_mode = 'STRAIGHT'
    except Exception:
        pass

    print(f"[BakeOneClick] Alpha stats: "
          f"min={float(np.min(alpha_values)):.3f}, "
          f"max={float(np.max(alpha_values)):.3f}, "
          f"mean={float(np.mean(alpha_values)):.3f}")
    return True


def merge_opacity_to_basecolor(basecolor_img, opacity_img, output_path,
                               premultiply=False):
    ok = merge_opacity_into_basecolor_image(
        basecolor_img, opacity_img, premultiply
    )
    if not ok:
        return None
    return _save_png_filepath(basecolor_img, output_path)


# ==========================================================
# Image data reader
# ==========================================================

def image_to_array(img):
    w, h = img.size
    n = w * h * 4
    px = np.empty(n, dtype=np.float32)
    img.pixels.foreach_get(px)
    return px.reshape(h, w, 4)


# ==========================================================
# PSD writer
# ==========================================================

def _linear_to_srgb_u8(linear_rgb):
    x = np.clip(linear_rgb, 0.0, 1.0)
    srgb = np.where(
        x <= 0.0031308,
        x * 12.92,
        1.055 * np.power(np.clip(x, 1e-10, None), 1.0 / 2.4) - 0.055
    )
    return np.clip(srgb * 255.0 + 0.5, 0, 255).astype(np.uint8)


def _to_u8_alpha(linear_a):
    return np.clip(linear_a * 255.0 + 0.5, 0, 255).astype(np.uint8)


def _psd_planar_channels(rgba_float):
    h, w = rgba_float.shape[:2]
    rgba_u8 = np.empty((h, w, 4), dtype=np.uint8)
    rgba_u8[:, :, :3] = _linear_to_srgb_u8(rgba_float[:, :, :3])
    rgba_u8[:, :, 3] = _to_u8_alpha(rgba_float[:, :, 3])
    rgba_u8 = rgba_u8[::-1]
    channels = [rgba_u8[:, :, c].tobytes() for c in range(4)]
    return channels, h, w


def write_psd(filepath, layers):
    if not layers:
        print("[BakeOneClick] PSD: no layers")
        return False

    _ensure_activated()

    h, w = layers[0][1].shape[:2]
    n_layers = len(layers)

    for name, rgba in layers:
        if rgba.shape[0] != h or rgba.shape[1] != w:
            print(f"[BakeOneClick] PSD: layer {name} size mismatch")
            return False

    try:
        with open(filepath, 'wb') as f:
            f.write(b'8BPS')
            f.write(struct.pack('>H', 1))
            f.write(b'\x00' * 6)
            f.write(struct.pack('>H', 4))
            f.write(struct.pack('>I', h))
            f.write(struct.pack('>I', w))
            f.write(struct.pack('>H', 8))
            f.write(struct.pack('>H', 3))

            f.write(struct.pack('>I', 0))
            f.write(struct.pack('>I', 0))

            layer_records = b''
            all_channel_data = b''

            for name, rgba in layers:
                channels, _, _ = _psd_planar_channels(rgba)

                channel_data_list = [
                    struct.pack('>H', 0) + ch_bytes for ch_bytes in channels
                ]

                ch_info = b''
                for c in range(4):
                    chan_id = c if c < 3 else -1
                    ch_info += struct.pack('>h', chan_id)
                    ch_info += struct.pack('>I', len(channel_data_list[c]))

                extra = b''
                extra += struct.pack('>I', 0)
                extra += struct.pack('>I', 0)
                name_bytes = name.encode('utf-8')[:255]
                name_field = struct.pack('>B', len(name_bytes)) + name_bytes
                pad_len = (4 - (len(name_field) % 4)) % 4
                name_field += b'\x00' * pad_len
                extra += name_field

                record = b''
                record += struct.pack('>i', 0)
                record += struct.pack('>i', 0)
                record += struct.pack('>i', h)
                record += struct.pack('>i', w)
                record += struct.pack('>H', 4)
                record += ch_info
                record += b'8BIM'
                record += b'norm'
                record += struct.pack('>B', 255)
                record += struct.pack('>B', 0)
                record += struct.pack('>B', 0)
                record += struct.pack('>B', 0)
                record += struct.pack('>I', len(extra))
                record += extra

                layer_records += record
                all_channel_data += b''.join(channel_data_list)

            layer_info = struct.pack('>h', n_layers)
            layer_info += layer_records + all_channel_data
            if len(layer_info) % 2 == 1:
                layer_info += b'\x00'

            lm_section = struct.pack('>I', len(layer_info)) + layer_info
            lm_section += struct.pack('>I', 0)

            f.write(struct.pack('>I', len(lm_section)))
            f.write(lm_section)

            composite = layers[-1][1].copy()
            for i in range(len(layers) - 2, -1, -1):
                name, top = layers[i]
                alpha_top = top[:, :, 3:4]
                composite[:, :, :3] = (
                    top[:, :, :3] * alpha_top
                    + composite[:, :, :3] * (1 - alpha_top)
                )
                composite[:, :, 3:4] = (
                    alpha_top + composite[:, :, 3:4] * (1 - alpha_top)
                )

            comp_u8 = np.empty((h, w, 4), dtype=np.uint8)
            comp_u8[:, :, :3] = _linear_to_srgb_u8(composite[:, :, :3])
            comp_u8[:, :, 3] = _to_u8_alpha(composite[:, :, 3])
            comp_u8 = comp_u8[::-1]

            f.write(struct.pack('>H', 0))
            for c in range(4):
                f.write(comp_u8[:, :, c].tobytes())

        print(f"[BakeOneClick] PSD written: {filepath} "
              f"(layers: {'/'.join([n for n, _ in layers])} = top/bottom)")
        return True

    except Exception as e:
        print(f"[BakeOneClick] PSD write failed: {e}")
        import traceback
        traceback.print_exc()
        return False


# ==========================================================
# Resolution helper
# ==========================================================

def _get_res(props):
    try:
        return int(props.resolution)
    except (ValueError, TypeError):
        return 2048


# ==========================================================
# Bake task table (core business logic)
# ==========================================================

def _get_bake_tasks(props):
    hide_bc_op = props.bake_opacity and props.bake_base_color
    tasks = []
    if props.bake_normal:
        tasks.append(('NORMAL', 'Normal', True, 'standard', True))
    if props.bake_ao:
        tasks.append(('AO', 'AO', True, 'standard', True))
    if props.bake_roughness:
        tasks.append(('ROUGHNESS', 'Roughness', True, 'standard', True))
    if props.bake_metallic:
        tasks.append(('EMIT', 'Metallic', True, 'metallic_emit', True))
    if props.bake_opacity:
        tasks.append(
            ('EMIT', 'Opacity', True, 'alpha_emit', not hide_bc_op)
        )
    if props.bake_base_color:
        if props.merge_lighting:
            tasks.append(
                ('COMBINED', 'BaseColor', False,
                 'basecolor_combined', not hide_bc_op)
            )
        else:
            tasks.append(
                ('EMIT', 'BaseColor', False,
                 'basecolor_emit', not hide_bc_op)
            )
    return tasks


# ==========================================================
# Standard bake pipeline
# ==========================================================

def _save_or_skip(op, img, name, base_name, props, save):
    if not save:
        print(f"[BakeOneClick] skip save {base_name}_{name}")
        return
    filepath = save_image(img, name, props.output_dir)
    if filepath:
        op.report({'INFO'}, f"OK {os.path.basename(filepath)}")
    else:
        op.report({'WARNING'}, f"FAILED {base_name}_{name}")


def _merge_transparency_if_needed(op, base_name, props):
    if not (props.bake_base_color and props.bake_opacity):
        return
    bc_img = bpy.data.images.get(f"{base_name}_BaseColor")
    op_img = bpy.data.images.get(f"{base_name}_Opacity")
    if not bc_img or not op_img:
        return
    suffix = props.transparent_suffix or "Transparent"
    output_dir = bpy.path.abspath(props.output_dir)
    output_path = os.path.join(output_dir, f"{base_name}_{suffix}.png")
    result = merge_opacity_to_basecolor(
        bc_img, op_img, output_path,
        premultiply=props.premultiply_alpha,
    )
    if result:
        remove_output_files(
            props.output_dir,
            [f"{base_name}_BaseColor.png",
             f"{base_name}_Opacity.png"],
        )
        op.report({'INFO'}, f"OK {os.path.basename(result)}")
    else:
        op.report({'WARNING'}, f"FAILED {base_name}")


def _bake_s2a(op, context, low_obj, props, res):
    if not low_obj.data.materials:
        op.report(
            {'WARNING'},
            "Low poly {name} is invalid or has no material".format(
                name=low_obj.name)
        )
        return
    high_objs = [
        o for o in context.selected_objects
        if o.type == 'MESH' and o != low_obj
    ]
    if not high_objs:
        op.report({'WARNING'}, "Please specify at least one high poly")
        return

    tasks = _get_bake_tasks(props)
    for bake_type, name, is_non_color, mode, save in tasks:
        img = create_bake_image(f"{low_obj.name}_{name}", res, is_non_color)
        bake_single(
            high_objs, low_obj, img, props, bake_type, mode, is_s2a=True,
        )
        _save_or_skip(op, img, name, low_obj.name, props, save)
    _merge_transparency_if_needed(op, low_obj.name, props)


def _bake_self(op, context, obj, props, res):
    if not obj.data.materials:
        print(f"[BakeOneClick] {obj.name} has no material, skip")
        return
    tasks = _get_bake_tasks(props)
    for bake_type, name, is_non_color, mode, save in tasks:
        img = create_bake_image(f"{obj.name}_{name}", res, is_non_color)
        bake_single(
            [obj], obj, img, props, bake_type, mode, is_s2a=False,
        )
        _save_or_skip(op, img, name, obj.name, props, save)
    _merge_transparency_if_needed(op, obj.name, props)


def run_bake_all(op, context):
    """Standard bake top-level entry."""
    props = context.scene.bake_props
    selected = [o for o in context.selected_objects if o.type == 'MESH']

    if not selected:
        op.report({'WARNING'}, "Please select at least one mesh object")
        return {'CANCELLED'}

    if props.output_dir.startswith("//") and not bpy.data.filepath:
        op.report({'ERROR'}, "Please save the .blend file first")
        return {'CANCELLED'}

    if props.bake_opacity and not props.bake_base_color:
        props.bake_base_color = True

    if props.bake_base_color and props.merge_lighting:
        if not any(o.type == 'LIGHT' for o in context.scene.objects):
            op.report(
                {'WARNING'},
                "BaseColor with lighting requires scene lights"
            )

    setup_bake_environment()

    original_selected = list(context.selected_objects)
    original_active = context.view_layer.objects.active
    res = _get_res(props)

    try:
        if props.use_selected_to_active:
            low_poly = context.view_layer.objects.active
            if not low_poly or low_poly.type != 'MESH':
                op.report(
                    {'ERROR'},
                    "Please set the low poly as the active object"
                )
                return {'CANCELLED'}
            if len(selected) < 2:
                op.report(
                    {'WARNING'},
                    "Selected to Active requires at least 2 objects"
                )
                return {'CANCELLED'}
            _bake_s2a(op, context, low_poly, props, res)

        elif props.bake_opacity:
            active = context.view_layer.objects.active
            if not active or active.type != 'MESH':
                op.report(
                    {'ERROR'},
                    "Transparent bake only processes the active object"
                )
                return {'CANCELLED'}
            if not active.data.materials:
                op.report(
                    {'WARNING'},
                    "Active object {name} has no material".format(
                        name=active.name)
                )
                return {'CANCELLED'}
            _bake_self(op, context, active, props, res)

        else:
            for obj in selected:
                _bake_self(op, context, obj, props, res)

    except Exception as e:
        import traceback
        traceback.print_exc()
        op.report({'ERROR'}, "Bake failed: {err}".format(err=str(e)))
        return {'CANCELLED'}
    finally:
        bpy.ops.object.select_all(action='DESELECT')
        for o in original_selected:
            try:
                o.select_set(True)
            except Exception:
                pass
        context.view_layer.objects.active = original_active

    op.report({'INFO'}, "Bake complete!")
    return {'FINISHED'}


# ==========================================================
# Layered bake pipeline
# ==========================================================

def _hide_other_high(high, props):
    current_is_opaque = (high == props.layered_opaque_high)
    other = (props.layered_transparent_high if current_is_opaque
             else props.layered_opaque_high)
    if other is None or other == high:
        return None, False
    prev = bool(other.hide_render)
    other.hide_render = True
    print(f"[BakeOneClick] temporarily hide {other.name}")
    return other, prev


def _restore_hidden(hidden_obj, prev_state):
    if hidden_obj is None:
        return
    try:
        hidden_obj.hide_render = prev_state
    except Exception:
        pass


def _bake_opaque_layer(context, low, high, props, res):
    name = props.layered_opaque_name or "Opaque"
    hidden, prev = _hide_other_high(high, props)
    try:
        img = create_bake_image(f"__layered_{name}__", res, False)
        bake_kwargs = dict(
            is_s2a=True,
            margin=props.layered_margin,
            cage_extrusion=props.layered_cage_extrusion,
            max_ray_distance=props.layered_max_ray_distance,
        )
        if props.layered_merge_lighting:
            bake_single(
                [high], low, img, props, 'COMBINED',
                'basecolor_combined', **bake_kwargs,
            )
        else:
            bake_single(
                [high], low, img, props, 'EMIT',
                'basecolor_emit', **bake_kwargs,
            )
        fix_opaque_alpha_from_rgb(img)
        print(f"[BakeOneClick] opaque layer baked: {img.name} "
              f"(margin={props.layered_margin})")
        return img
    finally:
        _restore_hidden(hidden, prev)


def _bake_transparent_layer(context, low, high, props, res):
    name = props.layered_transparent_name or "Transparent"
    hidden, prev = _hide_other_high(high, props)
    try:
        # Transparent layer: margin forced to 0, no edge extension
        bake_kwargs = dict(
            is_s2a=True,
            margin=0,
            cage_extrusion=props.layered_cage_extrusion,
            max_ray_distance=props.layered_max_ray_distance,
        )

        bc_img = create_bake_image(
            f"__layered_{name}_BaseColor__", res, False
        )
        if props.layered_merge_lighting:
            bake_single(
                [high], low, bc_img, props, 'COMBINED',
                'basecolor_combined', **bake_kwargs,
            )
        else:
            bake_single(
                [high], low, bc_img, props, 'EMIT',
                'basecolor_emit', **bake_kwargs,
            )

        op_img = create_bake_image(
            f"__layered_{name}_Opacity__", res, True
        )
        bake_single(
            [high], low, op_img, props, 'EMIT',
            'alpha_emit', **bake_kwargs,
        )

        merge_opacity_into_basecolor_image(
            bc_img, op_img, premultiply=props.premultiply_alpha
        )
        try:
            bpy.data.images.remove(op_img, do_unlink=True)
        except Exception:
            pass
        print(f"[BakeOneClick] transparent layer baked: {bc_img.name} "
              f"(margin=0)")
        return bc_img
    finally:
        _restore_hidden(hidden, prev)


def _write_psd_output(op, opaque_img, transparent_img, props):
    output_dir = bpy.path.abspath(props.output_dir)
    try:
        os.makedirs(output_dir, exist_ok=True)
    except Exception:
        pass
    out_name = props.layered_output_name or "Layered"

    opaque_name = props.layered_opaque_name or "Opaque"
    transparent_name = props.layered_transparent_name or "Transparent"

    psd_layers = []
    if opaque_img is not None:
        psd_layers.append(
            (opaque_name, image_to_array(opaque_img))
        )
    if transparent_img is not None:
        psd_layers.append(
            (transparent_name, image_to_array(transparent_img))
        )

    if not psd_layers:
        op.report({'ERROR'}, "No layers to output")
        return

    output_path = os.path.join(output_dir, f"{out_name}.psd")
    ok = write_psd(output_path, psd_layers)
    if ok:
        layer_desc = " > ".join([n for n, _ in psd_layers])
        op.report(
            {'INFO'},
            "OK PSD: {name} (top -> bottom: {layers})".format(
                name=os.path.basename(output_path),
                layers=layer_desc,
            )
        )
    else:
        op.report({'WARNING'}, "PSD write failed")

    for img in (opaque_img, transparent_img):
        if img is None:
            continue
        try:
            bpy.data.images.remove(img, do_unlink=True)
        except Exception:
            pass


def run_bake_layered(op, context):
    """Layered bake top-level entry."""
    props = context.scene.bake_props
    low = props.layered_low
    opaque_high = props.layered_opaque_high
    transparent_high = props.layered_transparent_high

    if not low:
        op.report({'ERROR'}, "Please specify the low poly")
        return {'CANCELLED'}
    if low.type != 'MESH' or not low.data.materials:
        op.report(
            {'ERROR'},
            "Low poly {name} is invalid or has no material".format(
                name=low.name)
        )
        return {'CANCELLED'}
    if not opaque_high and not transparent_high:
        op.report({'ERROR'}, "Please specify at least one high poly")
        return {'CANCELLED'}
    if props.output_dir.startswith("//") and not bpy.data.filepath:
        op.report({'ERROR'}, "Please save the .blend file first")
        return {'CANCELLED'}
    if props.layered_merge_lighting:
        if not any(o.type == 'LIGHT' for o in context.scene.objects):
            op.report(
                {'WARNING'},
                "Merge lighting requires scene lights, "
                "otherwise output is black"
            )

    setup_bake_environment()

    original_selected = list(context.selected_objects)
    original_active = context.view_layer.objects.active
    res = _get_res(props)

    try:
        opaque_img = None
        if opaque_high and opaque_high.type == 'MESH':
            print(f"[BakeOneClick] ==== Layered step 1: "
                  f"{opaque_high.name} -> {low.name} ====")
            opaque_img = _bake_opaque_layer(
                context, low, opaque_high, props, res
            )

        transparent_img = None
        if transparent_high and transparent_high.type == 'MESH':
            print(f"[BakeOneClick] ==== Layered step 2: "
                  f"{transparent_high.name} -> {low.name} ====")
            transparent_img = _bake_transparent_layer(
                context, low, transparent_high, props, res
            )

        if opaque_img is None and transparent_img is None:
            op.report({'ERROR'}, "No layers to output")
            return {'CANCELLED'}
        print("[BakeOneClick] ==== Layered step 3: PSD ====")
        _write_psd_output(op, opaque_img, transparent_img, props)

    except Exception as e:
        import traceback
        traceback.print_exc()
        op.report({'ERROR'}, "Layered bake failed: {err}".format(err=str(e)))
        return {'CANCELLED'}
    finally:
        bpy.ops.object.select_all(action='DESELECT')
        for o in original_selected:
            try:
                o.select_set(True)
            except Exception:
                pass
        context.view_layer.objects.active = original_active

    op.report({'INFO'}, "Layered bake complete!")
    return {'FINISHED'}