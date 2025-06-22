"""Core signal evaluation helpers for VjLooper."""

import bpy
import json
from pathlib import Path
from mathutils import Vector
from bpy_extras.view3d_utils import location_3d_to_region_2d
import blf

from .core import signals as core_signals
from .core import persistence as core_persistence

class SignalCache:
    """Simple per-frame cache for computed signal values."""
    def __init__(self):
        self.cache = {}
        self.last_frame = -1

    def get(self, key, frame, calc):
        if frame != self.last_frame:
            self.cache.clear()
            self.last_frame = frame
        if key not in self.cache:
            self.cache[key] = calc()
        return self.cache[key]

signal_cache = SignalCache()
smoothing_cache = {}

CHANNEL_BAKE = [
    ('LOC', 'Location', ''),
    ('ROT', 'Rotation', ''),
    ('SCL', 'Scale',   ''),
]

CHANNEL_ITEMS = [
    ('LOC_X', "Position X", ""),
    ('LOC_Y', "Position Y", ""),
    ('LOC_Z', "Position Z", ""),
    ('ROT_X', "Rotation X", ""),
    ('ROT_Y', "Rotation Y", ""),
    ('ROT_Z', "Rotation Z", ""),
    ('SCL_X', "Scale X",   ""),
    ('SCL_Y', "Scale Y",   ""),
    ('SCL_Z', "Scale Z",   ""),
    ('SCL_ALL', "Uniform Scale", ""),
]

brush_last_obj = None
brush_counter  = 0
preview_handle  = None


def update_frequency(self, ctx):
    """Quantize frequency when loop lock is active."""
    sc = ctx.scene
    if getattr(sc, "loop_lock", False) and self.duration:
        q = round(self.frequency * self.duration) / self.duration
        if abs(q - self.frequency) > 1e-6:
            self["frequency"] = q


def update_duration(self, ctx):
    """Quantize frequency when duration changes and loop lock active."""
    sc = ctx.scene
    if getattr(sc, "loop_lock", False) and self.duration:
        q = round(self.frequency * self.duration) / self.duration
        if abs(q - self.frequency) > 1e-6:
            self["frequency"] = q


def update_new_frequency(self, ctx):
    sc = self
    dur = sc.signal_new_duration
    freq = sc.signal_new_frequency
    if getattr(sc, "loop_lock", False) and dur:
        q = round(freq * dur) / dur
        if abs(q - freq) > 1e-6:
            sc["signal_new_frequency"] = q


def update_new_duration(self, ctx):
    sc = self
    dur = sc.signal_new_duration
    freq = sc.signal_new_frequency
    if getattr(sc, "loop_lock", False) and dur:
        q = round(freq * dur) / dur
        if abs(q - freq) > 1e-6:
            sc["signal_new_frequency"] = q


def update_offset(self, ctx):
    """Keep offset within duration when loop lock is active."""
    sc = ctx.scene
    if getattr(sc, "loop_lock", False) and self.duration:
        self["offset"] = int(self.offset) % self.duration


def apply_preset_to_object(obj, preset_data, base_frame=0, mirror=False, offset=0):
    """Load a serialized preset onto obj at base_frame."""
    obj.signal_items.clear()
    for d in preset_data:
        it = obj.signal_items.add()
        for k, v in d.items():
            if k == "amplitude" and mirror:
                v = -v
            setattr(it, k, v)
        it.start_frame = base_frame + offset


def calc_signal(it, obj, frame):
    """Calculate value for it at frame on obj using pure core implementation."""
    params = core_signals.SignalParams(
        signal_type=it.signal_type,
        amplitude=it.amplitude * getattr(obj, "global_amp_scale", 1.0),
        frequency=it.frequency * getattr(obj, "global_freq_scale", 1.0),
        duration=max(1, int(it.duration * getattr(obj, "global_dur_scale", 1.0))),
        offset=it.offset,
        start_frame=it.start_frame,
        phase_offset=it.phase_offset,
        noise_seed=it.noise_seed,
        smoothing=it.smoothing,
        base_value=it.base_value,
        loop_count=it.loop_count,
        use_clamp=it.use_clamp,
        clamp_min=it.clamp_min,
        clamp_max=it.clamp_max,
        blend_frames=getattr(it, "blend_frames", 0),
    )
    loop_lock = getattr(bpy.context.scene, "loop_lock", False)
    return core_signals.calc_signal(params, frame, loop_lock=loop_lock)


def set_channel(obj, ch, v):
    """Write value v to object's channel ch."""
    if ch == 'LOC_X': obj.location.x = v
    if ch == 'LOC_Y': obj.location.y = v
    if ch == 'LOC_Z': obj.location.z = v
    if ch == 'ROT_X': obj.rotation_euler.x = v
    if ch == 'ROT_Y': obj.rotation_euler.y = v
    if ch == 'ROT_Z': obj.rotation_euler.z = v
    if ch == 'SCL_X': obj.scale.x = v
    if ch == 'SCL_Y': obj.scale.y = v
    if ch == 'SCL_Z': obj.scale.z = v
    if ch == 'SCL_ALL': obj.scale = (v, v, v)


def get_channel_value(obj, ch):
    """Return current value of channel ch from obj."""
    if ch == 'LOC_X': return obj.location.x
    if ch == 'LOC_Y': return obj.location.y
    if ch == 'LOC_Z': return obj.location.z
    if ch == 'ROT_X': return obj.rotation_euler.x
    if ch == 'ROT_Y': return obj.rotation_euler.y
    if ch == 'ROT_Z': return obj.rotation_euler.z
    if ch == 'SCL_X': return obj.scale.x
    if ch == 'SCL_Y': return obj.scale.y
    if ch == 'SCL_Z': return obj.scale.z
    if ch == 'SCL_ALL': return obj.scale.x
    return 0.0


def get_materials_list(scene):
    """Return list of materials filtered by scene.vj_only_used."""
    if getattr(scene, "vj_only_used", False):
        return [
            m for m in bpy.data.materials
            if any(
                o for o in bpy.data.objects
                if m.name in [slot.material.name for slot in o.material_slots if slot.material]
            )
        ]
    return list(bpy.data.materials)


def frame_handler(scene):
    """Update object channels for the current frame."""
    f = scene.frame_current
    for obj in scene.objects:
        if hasattr(obj, "signal_items"):
            for it in obj.signal_items:
                if it.enabled:
                    v = calc_signal(it, obj, f)
                    set_channel(obj, it.channel, v)


def draw_preview_callback():
    """Draw signal info overlay in the 3D view."""
    prefs = bpy.context.preferences.addons[__package__].preferences
    if not prefs.use_preview:
        return
    region = bpy.context.region
    rv3d   = bpy.context.region_data
    if not region or not rv3d:
        return
    font_id = 0
    blf.color(font_id, *prefs.brush_color)
    for obj in bpy.context.selected_objects:
        if not getattr(obj, "signal_items", None):
            continue
        it = obj.signal_items[0]
        text = f"{it.signal_type} {it.frequency:.2f}Hz"
        co2d = location_3d_to_region_2d(region, rv3d, obj.location)
        if co2d:
            blf.position(font_id, co2d.x, co2d.y, 0)
            blf.draw(font_id, text)


def preset_brush_handler(scene):
    """Apply the active preset when selecting new objects."""
    global brush_last_obj, brush_counter
    if not scene.preset_brush_active:
        brush_last_obj = None
        brush_counter = 0
        return
    obj = bpy.context.view_layer.objects.active
    if obj and obj != brush_last_obj and hasattr(obj, "signal_items"):
        idx = scene.signal_preset_index
        if idx < len(scene.signal_presets):
            pr = scene.signal_presets[idx]
            if validate_preset(pr.data):
                arr = json.loads(pr.data)
                apply_preset_to_object(
                    obj,
                    arr,
                    scene.frame_current,
                    scene.preset_mirror,
                    brush_counter * scene.brush_offset_step
                )
                brush_counter += 1
    brush_last_obj = obj


def update_signal_markers(scene):
    """Synchronize signal start_frame with timeline markers."""
    for obj in scene.objects:
        if not hasattr(obj, "signal_items"):
            continue
        for it in obj.signal_items:
            if not it.marker_name:
                continue
            mk = scene.timeline_markers.get(it.marker_name)
            if mk:
                if mk.frame != it.start_frame:
                    it.start_frame = mk.frame
                if mk.name != it.name:
                    mk.name = it.name
            else:
                new_mk = scene.timeline_markers.new(it.name, frame=it.start_frame)
                it.marker_name = new_mk.name


def validate_preset(data):
    """Return True if data contains a valid JSON list."""
    try:
        return isinstance(json.loads(data), list)
    except Exception:
        return False


def get_preset_file():
    prefs = bpy.context.preferences.addons[__package__].preferences
    return bpy.path.abspath(prefs.autosave_path)


def save_presets_to_disk():
    """Persist presets to the configured autosave path."""
    sc = bpy.context.scene
    data = [
        {
            "name": p.name,
            "data": json.loads(p.data),
            "preview_icon": p.preview_icon,
            "category": p.category,
        }
        for p in sc.signal_presets
    ]
    path = Path(get_preset_file())
    core_persistence.save_presets(data, path)


def load_presets_from_disk():
    """Load presets from the autosave file if it exists."""
    sc = bpy.context.scene
    path = Path(get_preset_file())
    presets = core_persistence.load_presets(path)
    if presets:
        sc.signal_presets.clear()
        for e in presets:
            p = sc.signal_presets.add()
            p.name = e["name"]
            p.data = json.dumps(e["data"])
            p.preview_icon = e.get("preview_icon", "")
            p.category = e.get("category", "General")


def register():
    bpy.app.handlers.frame_change_pre.append(frame_handler)
    prefs = bpy.context.preferences.addons[__package__].preferences
    global preview_handle
    if prefs.use_preview and preview_handle is None:
        preview_handle = bpy.types.SpaceView3D.draw_handler_add(
            draw_preview_callback, (), 'WINDOW', 'POST_PIXEL')
    if update_signal_markers not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(update_signal_markers)


def unregister():
    if frame_handler in bpy.app.handlers.frame_change_pre:
        bpy.app.handlers.frame_change_pre.remove(frame_handler)
    if preset_brush_handler in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(preset_brush_handler)
    if update_signal_markers in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(update_signal_markers)
    global preview_handle
    if preview_handle is not None:
        bpy.types.SpaceView3D.draw_handler_remove(preview_handle, 'WINDOW')
        preview_handle = None
