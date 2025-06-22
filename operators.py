"""Blender operator implementations for the VjLooper add-on."""

import bpy
import importlib
import json
import random
import sys
from mathutils import Vector
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from bpy.types import Operator
from bpy_extras.io_utils import ExportHelper, ImportHelper

from . import signals


class VJLOOPER_OT_hot_reload(Operator):
    """Reload all VjLooper modules."""
    bl_idname = "vjlooper.hot_reload"
    bl_label = "Reload Addon"
    bl_description = "Reload VjLooper without restarting Blender"

    def execute(self, context):
        addon = sys.modules.get(__package__)
        if addon:
            if hasattr(addon, 'unregister'):
                addon.unregister()
            importlib.reload(addon.signals)
            importlib.reload(addon.operators)
            importlib.reload(addon.ui)
            importlib.reload(addon)
            if hasattr(addon, 'register'):
                addon.register()
        self.report({'INFO'}, "VjLooper reloaded")
        return {'FINISHED'}


class VJLOOPER_OT_add_signal(Operator):
    """Create a new SignalItem on the active object."""
    bl_idname = "vjlooper.add_signal"
    bl_label = "Add Animation"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, ctx):
        o = ctx.object
        sc = ctx.scene
        if not o:
            return {'CANCELLED'}
        it = o.signal_items.add()
        it.name = f"Animation{len(o.signal_items)+1:02d}"
        it.channel = sc.signal_new_channel
        it.signal_type = sc.signal_new_type
        it.amplitude = sc.signal_new_amplitude
        it.frequency = sc.signal_new_frequency
        it.amplitude_min = it.amplitude
        it.amplitude_max = it.amplitude
        it.frequency_min = it.frequency
        it.frequency_max = it.frequency
        it.phase_offset = sc.signal_new_phase
        it.duration = sc.signal_new_duration
        it.offset = sc.signal_new_offset
        it.loop_count = sc.signal_new_loops
        it.use_clamp = sc.signal_new_clamp
        it.clamp_min = sc.signal_new_clamp_min
        it.clamp_max = sc.signal_new_clamp_max
        it.noise_seed = sc.signal_new_noise
        it.smoothing = sc.signal_new_smoothing
        it.base_value = signals.get_channel_value(o, it.channel)
        it.start_frame = sc.frame_current
        marker = ctx.scene.timeline_markers.new(it.name, frame=it.start_frame)
        it.marker_name = marker.name
        return {'FINISHED'}


class VJLOOPER_OT_remove_signal(Operator):
    """Delete a SignalItem from the active object."""
    bl_idname = "vjlooper.remove_signal"
    bl_label = "Remove Animation"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty()

    def execute(self, ctx):
        o = ctx.object
        if not o or self.index >= len(o.signal_items):
            return {'CANCELLED'}
        it = o.signal_items[self.index]
        if it.marker_name:
            mk = ctx.scene.timeline_markers.get(it.marker_name)
            if mk:
                ctx.scene.timeline_markers.remove(mk)
        o.signal_items.remove(self.index)
        return {'FINISHED'}


class VJLOOPER_OT_randomize_signal(Operator):
    """Assign random amplitude and frequency within set ranges."""
    bl_idname = "vjlooper.randomize_signal"
    bl_label = "Randomize Signal"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty()

    def execute(self, ctx):
        obj = ctx.object
        if not obj or self.index >= len(obj.signal_items):
            return {'CANCELLED'}
        it = obj.signal_items[self.index]
        amp_min = min(it.amplitude_min, it.amplitude_max)
        amp_max = max(it.amplitude_min, it.amplitude_max)
        freq_min = min(it.frequency_min, it.frequency_max)
        freq_max = max(it.frequency_min, it.frequency_max)
        it.amplitude = random.uniform(amp_min, amp_max)
        it.frequency = random.uniform(freq_min, freq_max)
        return {'FINISHED'}


class VJLOOPER_OT_add_preset(Operator):
    """Store current object signals as a new preset."""
    bl_idname = "vjlooper.add_preset"
    bl_label = "Save Preset"

    name: StringProperty(default="Preset")
    category: StringProperty(default="General")

    def invoke(self, ctx, ev):
        return ctx.window_manager.invoke_props_dialog(self)

    def execute(self, ctx):
        sc = ctx.scene
        data = []
        for it in ctx.object.signal_items:
            data.append({
                p.identifier: getattr(it, p.identifier)
                for p in it.bl_rna.properties if not p.is_readonly
            })
        pr = sc.signal_presets.add()
        pr.name = self.name
        pr.data = json.dumps(data)
        pr.category = self.category
        if ctx.object.signal_items:
            pr.preview_icon = ctx.object.signal_items[0].signal_type
        return {'FINISHED'}


class VJLOOPER_OT_load_preset(Operator):
    """Apply the selected preset to the active object."""
    bl_idname = "vjlooper.load_preset"
    bl_label = "Load Preset"

    def execute(self, ctx):
        sc = ctx.scene
        idx = sc.signal_preset_index
        pr = sc.signal_presets[idx]
        if not signals.validate_preset(pr.data):
            self.report({'ERROR'}, "Invalid preset")
            return {'CANCELLED'}
        arr = json.loads(pr.data)
        signals.apply_preset_to_object(ctx.object, arr, sc.frame_current, sc.preset_mirror)
        mat_name = pr.name
        if mat_name in bpy.data.materials:
            mat = bpy.data.materials[mat_name]
            targets = ctx.selected_objects or [ctx.object]
            for ob in targets:
                if ob.type == 'MESH':
                    if ob.data.materials:
                        ob.data.materials[0] = mat
                    else:
                        ob.data.materials.append(mat)
        return {'FINISHED'}


class VJLOOPER_OT_apply_preset_multi(Operator):
    """Apply the active preset to all selected objects."""
    bl_idname = "vjlooper.apply_preset_multi"
    bl_label = "Apply Preset to Selection"

    def execute(self, ctx):
        sc = ctx.scene
        idx = sc.signal_preset_index
        if idx >= len(sc.signal_presets):
            return {'CANCELLED'}
        pr = sc.signal_presets[idx]
        if not signals.validate_preset(pr.data):
            self.report({'ERROR'}, "Invalid preset")
            return {'CANCELLED'}
        arr = json.loads(pr.data)
        offset = sc.multi_offset_frames
        selected = [o for o in ctx.selected_objects if o != ctx.object]
        for i, obj in enumerate(selected):
            signals.apply_preset_to_object(
                obj,
                arr,
                sc.frame_current,
                sc.preset_mirror,
                i * offset
            )
        return {'FINISHED'}


class VJLOOPER_OT_apply_preset_offset(Operator):
    """Apply active preset with advanced offset modes."""
    bl_idname = "vjlooper.apply_preset_offset"
    bl_label = "Apply Preset With Offset"

    mode: EnumProperty(
        items=[
            ('LINEAR', 'Linear', ''),
            ('RADIAL', 'Radial', ''),
            ('BPM', 'Beat', ''),
        ],
        default='LINEAR'
    )

    def execute(self, ctx):
        sc = ctx.scene
        idx = sc.signal_preset_index
        if idx >= len(sc.signal_presets):
            return {'CANCELLED'}
        pr = sc.signal_presets[idx]
        if not signals.validate_preset(pr.data):
            self.report({'ERROR'}, "Invalid preset")
            return {'CANCELLED'}
        arr = json.loads(pr.data)
        active = ctx.object
        selected = [o for o in ctx.selected_objects if o != active]
        if self.mode == 'LINEAR':
            step = sc.multi_offset_frames
            for i, obj in enumerate(selected):
                signals.apply_preset_to_object(
                    obj,
                    arr,
                    sc.frame_current,
                    sc.preset_mirror,
                    i * step,
                )
        elif self.mode == 'RADIAL':
            factor = sc.offset_radial_factor
            for obj in selected:
                dist = (obj.location - active.location).length
                off = int(dist * factor)
                signals.apply_preset_to_object(
                    obj,
                    arr,
                    sc.frame_current,
                    sc.preset_mirror,
                    off,
                )
        else:  # BPM
            bpm = sc.offset_bpm
            if bpm <= 0:
                bpm = 120
            frames_per_beat = ctx.scene.render.fps * 60 / bpm
            for i, obj in enumerate(selected):
                off = int(i * frames_per_beat)
                signals.apply_preset_to_object(
                    obj,
                    arr,
                    sc.frame_current,
                    sc.preset_mirror,
                    off,
                )
        return {'FINISHED'}


class VJLOOPER_OT_remove_preset(Operator):
    """Delete the selected preset from the list."""
    bl_idname = "vjlooper.remove_preset"
    bl_label = "Remove Preset"

    def execute(self, ctx):
        sc = ctx.scene
        sc.signal_presets.remove(sc.signal_preset_index)
        return {'FINISHED'}


class VJLOOPER_OT_export_presets(Operator, ExportHelper):
    """Export all presets to a JSON file."""
    bl_idname = "vjlooper.export_presets"
    bl_label = "Export Presets"
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'})

    def execute(self, ctx):
        data = [
            {
                "name": p.name,
                "data": json.loads(p.data),
                "preview_icon": p.preview_icon,
                "category": p.category,
            }
            for p in ctx.scene.signal_presets
        ]
        with open(self.filepath, 'w') as f:
            json.dump(data, f, indent=2)
        return {'FINISHED'}


class VJLOOPER_OT_import_presets(Operator, ImportHelper):
    """Load presets from a JSON file."""
    bl_idname = "vjlooper.import_presets"
    bl_label = "Import Presets"
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'})

    def execute(self, ctx):
        arr = json.load(open(self.filepath))
        sc = ctx.scene
        sc.signal_presets.clear()
        for e in arr:
            p = sc.signal_presets.add()
            p.name = e["name"]
            p.data = json.dumps(e["data"])
            p.preview_icon = e.get("preview_icon", "")
            p.category = e.get("category", "General")
        return {'FINISHED'}


class VJLOOPER_OT_rename_category(Operator):
    """Rename a preset category across all presets."""
    bl_idname = "vjlooper.rename_category"
    bl_label = "Rename Category"

    def execute(self, ctx):
        sc = ctx.scene
        old = sc.category_rename_from
        new = sc.category_rename_to
        for p in sc.signal_presets:
            if p.category == old:
                p.category = new
        return {'FINISHED'}


class VJLOOPER_OT_bake_settings(Operator):
    """Configure bake range and channel."""
    bl_idname = "vjlooper.bake_settings"
    bl_label = "Bake Settings"

    start: IntProperty(default=1)
    end: IntProperty(default=250)
    channel: EnumProperty(items=signals.CHANNEL_BAKE, default='LOC')

    def invoke(self, ctx, ev):
        return ctx.window_manager.invoke_props_dialog(self)

    def execute(self, ctx):
        sc = ctx.scene
        sc.bake_start = self.start
        sc.bake_end = self.end
        sc.bake_channel = self.channel
        return {'FINISHED'}


class VJLOOPER_OT_bake_animation(Operator):
    """Bake procedural signals to keyframes."""
    bl_idname = "vjlooper.bake_animation"
    bl_label = "Bake Animation"

    def execute(self, ctx):
        sc = ctx.scene
        for f in range(sc.bake_start, sc.bake_end + 1):
            sc.frame_set(f)
            for it in ctx.object.signal_items:
                if not it.enabled:
                    continue
                v = signals.calc_signal(it, ctx.object, f)
                if sc.bake_channel == 'LOC':
                    ctx.object.location = Vector((v,) * 3)
                if sc.bake_channel == 'ROT':
                    ctx.object.rotation_euler = Vector((v,) * 3)
                if sc.bake_channel == 'SCL':
                    ctx.object.scale = Vector((v,) * 3)
                ctx.object.keyframe_insert(data_path=sc.bake_channel.lower())
        return {'FINISHED'}


class VJLOOPER_OT_toggle_preset_brush(Operator):
    """Enable or disable preset brush mode."""
    bl_idname = "vjlooper.toggle_preset_brush"
    bl_label = "Toggle Preset Brush"

    def execute(self, ctx):
        sc = ctx.scene
        sc.preset_brush_active = not sc.preset_brush_active
        if sc.preset_brush_active:
            if signals.preset_brush_handler not in bpy.app.handlers.depsgraph_update_post:
                bpy.app.handlers.depsgraph_update_post.append(signals.preset_brush_handler)
        else:
            if signals.preset_brush_handler in bpy.app.handlers.depsgraph_update_post:
                bpy.app.handlers.depsgraph_update_post.remove(signals.preset_brush_handler)
        return {'FINISHED'}


class VJLOOPER_OT_set_pivot(Operator):
    """Move object origins to preset pivot positions."""
    bl_idname = "vjlooper.set_pivot"
    bl_label = "Set Pivot"

    location: EnumProperty(
        name="Pivot",
        items=[
            ('CENTER', "Center", ""),
            ('TL', "Top Left", ""),
            ('TR', "Top Right", ""),
            ('BL', "Bottom Left", ""),
            ('BR', "Bottom Right", ""),
        ],
        default='CENTER'
    )

    def execute(self, ctx):
        objs = [o for o in ctx.selected_objects if hasattr(o, "signal_items")]
        if not objs:
            self.report({'WARNING'}, "Select objects with animations")
            return {'CANCELLED'}
        cursor = ctx.scene.cursor.location.copy()
        for obj in objs:
            bbox = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
            xs = [v.x for v in bbox]
            ys = [v.y for v in bbox]
            zs = [v.z for v in bbox]
            if self.location == 'CENTER':
                loc = Vector((sum(xs) / 8, sum(ys) / 8, sum(zs) / 8))
            elif self.location == 'TL':
                loc = Vector((min(xs), max(ys), max(zs)))
            elif self.location == 'TR':
                loc = Vector((max(xs), max(ys), max(zs)))
            elif self.location == 'BL':
                loc = Vector((min(xs), min(ys), min(zs)))
            else:
                loc = Vector((max(xs), min(ys), min(zs)))
            ctx.scene.cursor.location = loc
            bpy.ops.object.origin_set(
                {'object': obj,
                 'selected_objects': [obj],
                 'active_object': obj},
                type='ORIGIN_CURSOR'
            )
        ctx.scene.cursor.location = cursor
        return {'FINISHED'}


class VJLOOPER_OT_apply_mat_sel(Operator):
    """Apply chosen material to selected objects."""
    bl_idname = "vjlooper.apply_mat_sel"
    bl_label = "Apply Material to Selection"

    def execute(self, ctx):
        sc = ctx.scene
        mats = signals.get_materials_list(sc)
        idx = sc.vj_material_index
        if idx >= len(mats):
            return {'CANCELLED'}
        mat = mats[idx]
        for ob in ctx.selected_objects:
            if ob.type == 'MESH':
                if ob.data.materials:
                    ob.data.materials[0] = mat
                else:
                    ob.data.materials.append(mat)
        return {'FINISHED'}


class VJLOOPER_OT_apply_mat_coll(Operator):
    """Apply chosen material to all objects in target collection."""
    bl_idname = "vjlooper.apply_mat_coll"
    bl_label = "Apply Material to Collection"

    def execute(self, ctx):
        sc = ctx.scene
        coll = sc.vj_target_collection
        mats = signals.get_materials_list(sc)
        idx = sc.vj_material_index
        if not coll or idx >= len(mats):
            return {'CANCELLED'}
        mat = mats[idx]
        for ob in coll.all_objects:
            if ob.type == 'MESH':
                if ob.data.materials:
                    ob.data.materials[0] = mat
                else:
                    ob.data.materials.append(mat)
        return {'FINISHED'}


class VJLOOPER_OT_select_with_mat(Operator):
    """Select all objects using the active material."""
    bl_idname = "vjlooper.select_with_mat"
    bl_label = "Select Objects With Material"

    def execute(self, ctx):
        sc = ctx.scene
        mats = signals.get_materials_list(sc)
        idx = sc.vj_material_index
        if idx >= len(mats):
            return {'CANCELLED'}
        mat = mats[idx]
        bpy.ops.object.select_all(action='DESELECT')
        for ob in bpy.data.objects:
            if any(s.material == mat for s in ob.material_slots):
                ob.select_set(True)
        return {'FINISHED'}


class VJLOOPER_OT_random_hue_shift(Operator):
    """Randomize hue around active material."""
    bl_idname = "vjlooper.random_hue_shift"
    bl_label = "Random Hue Shift"

    range: FloatProperty(default=0.1, min=0.0, max=1.0)

    def execute(self, ctx):
        import colorsys
        sc = ctx.scene
        mats = signals.get_materials_list(sc)
        idx = sc.vj_material_index
        if idx >= len(mats):
            return {'CANCELLED'}
        mat = mats[idx]
        col = mat.diffuse_color
        h, s, v = colorsys.rgb_to_hsv(col[0], col[1], col[2])
        h = (h + random.uniform(-self.range, self.range)) % 1.0
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        mat.diffuse_color = (r, g, b, col[3])
        return {'FINISHED'}


class VJLOOPER_OT_random_palette(Operator):
    """Generate color variations using harmonies."""
    bl_idname = "vjlooper.random_palette"
    bl_label = "Random Palette"

    hue_range: FloatProperty(default=0.1, min=0.0, max=1.0)
    sat_range: FloatProperty(default=0.1, min=0.0, max=1.0)
    val_range: FloatProperty(default=0.1, min=0.0, max=1.0)
    harmony: EnumProperty(
        items=[
            ('NONE', 'None', ''),
            ('TRIAD', 'Triad', ''),
            ('COMPLEMENT', 'Complement', ''),
        ],
        default='NONE'
    )

    def execute(self, ctx):
        import colorsys
        sc = ctx.scene
        mats = signals.get_materials_list(sc)
        idx = sc.vj_material_index
        if idx >= len(mats):
            return {'CANCELLED'}
        mat = mats[idx]
        h, s, v = colorsys.rgb_to_hsv(*mat.diffuse_color[:3])
        targets = [mat]
        for obj in ctx.selected_objects:
            for slot in obj.material_slots:
                if slot.material:
                    targets.append(slot.material)
        for m in set(targets):
            if self.harmony == 'TRIAD':
                options = [h, (h + 1/3) % 1.0, (h + 2/3) % 1.0]
                nh = random.choice(options)
            elif self.harmony == 'COMPLEMENT':
                options = [h, (h + 0.5) % 1.0]
                nh = random.choice(options)
            else:
                nh = h + random.uniform(-self.hue_range, self.hue_range)
            nh = nh % 1.0
            ns = max(0.0, min(1.0, s + random.uniform(-self.sat_range, self.sat_range)))
            nv = max(0.0, min(1.0, v + random.uniform(-self.val_range, self.val_range)))
            r, g, b = colorsys.hsv_to_rgb(nh, ns, nv)
            m.diffuse_color = (r, g, b, m.diffuse_color[3])
        return {'FINISHED'}


classes = (
    VJLOOPER_OT_hot_reload,
    VJLOOPER_OT_add_signal,
    VJLOOPER_OT_remove_signal,
    VJLOOPER_OT_randomize_signal,
    VJLOOPER_OT_add_preset,
    VJLOOPER_OT_load_preset,
    VJLOOPER_OT_apply_preset_multi,
    VJLOOPER_OT_apply_preset_offset,
    VJLOOPER_OT_remove_preset,
    VJLOOPER_OT_export_presets,
    VJLOOPER_OT_import_presets,
    VJLOOPER_OT_rename_category,
    VJLOOPER_OT_bake_settings,
    VJLOOPER_OT_bake_animation,
    VJLOOPER_OT_toggle_preset_brush,
    VJLOOPER_OT_set_pivot,
    VJLOOPER_OT_apply_mat_sel,
    VJLOOPER_OT_apply_mat_coll,
    VJLOOPER_OT_select_with_mat,
    VJLOOPER_OT_random_hue_shift,
    VJLOOPER_OT_random_palette,
)


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
