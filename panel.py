# panel.py
# -*- coding: utf-8 -*-
#
# VjLooper – Panel principal
# Archivo unificado tras resolver conflictos entre ramas "main" y
# "implementar-mejoras-clave-en-animaciones".
#
# ---------------------------------------------------------------------------
import bpy
import importlib
import json
import math
import os
import random
import sys
from mathutils import Vector
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    StringProperty,
    CollectionProperty,
)
from bpy_extras.view3d_utils import location_3d_to_region_2d
import blf

# ---------------------------------------------------------------------------
#   LOGICA: cache, calculo de señal y frame handler
# ---------------------------------------------------------------------------
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
# store smoothed values per signal id
smoothing_cache = {}

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
    """Calculate value for it at frame on obj."""
    sf = it.start_frame + it.offset
    if frame < sf:
        return it.base_value
    rel = frame - sf
    dur_scale = getattr(obj, "global_dur_scale", 1.0)
    amp_scale = getattr(obj, "global_amp_scale", 1.0)
    freq_scale = getattr(obj, "global_freq_scale", 1.0)
    duration = max(1, int(it.duration * dur_scale))
    amplitude = it.amplitude * amp_scale
    frequency = it.frequency * freq_scale
    if it.loop_count and rel >= duration * it.loop_count:
        return it.base_value
    cycle = rel % duration
    t = (cycle / duration) * frequency + it.phase_offset / 360.0
    if   it.signal_type == 'SINE':      wave = math.sin(2 * math.pi * t)
    elif it.signal_type == 'COSINE':    wave = math.cos(2 * math.pi * t)
    elif it.signal_type == 'SQUARE':    wave = 1.0 if math.sin(2 * math.pi * t) >= 0 else -1.0
    elif it.signal_type == 'TRIANGLE':
        p = t % 1.0
        wave = 4 * p - 1 if p < 0.5 else 3 - 4 * p
    elif it.signal_type == 'SAWTOOTH':  wave = 2 * (t % 1.0) - 1
    elif it.signal_type == 'NOISE':
        random.seed(it.noise_seed + frame)
        wave = random.uniform(-1, 1)
    else:                               wave = 0.0
    last = smoothing_cache.get(id(it), wave)
    val  = last * it.smoothing + wave * (1 - it.smoothing) if it.smoothing else wave
    smoothing_cache[id(it)] = val
    out = it.base_value + amplitude * val
    if it.use_clamp:
        out = max(it.clamp_min, min(it.clamp_max, out))
    return out

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

def frame_handler(scene):
    """Update object channels for the current frame."""
    f = scene.frame_current
    for obj in scene.objects:
        if hasattr(obj, "signal_items"):
            for it in obj.signal_items:
                if it.enabled:
                    v = calc_signal(it, obj, f)
                    set_channel(obj, it.channel, v)

brush_last_obj = None
preview_handle  = None

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
    global brush_last_obj
    if not scene.preset_brush_active:
        brush_last_obj = None
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
                    scene.preset_mirror
                )
    brush_last_obj = obj

# ---------------------------------------------------------------------------
#   PRESETS: validacion JSON
# ---------------------------------------------------------------------------
def validate_preset(data):
    """Return True if data contains a valid JSON list."""
    try:
        return isinstance(json.loads(data), list)
    except:
        return False

def get_preset_file():
    prefs = bpy.context.preferences.addons[__package__].preferences
    return bpy.path.abspath(prefs.autosave_path)

def save_presets_to_disk():
    """Persist presets to the configured autosave path."""
    sc = bpy.context.scene
    data = [
        {"name": p.name, "data": json.loads(p.data), "preview_icon": p.preview_icon}
        for p in sc.signal_presets
    ]
    path = get_preset_file()
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def load_presets_from_disk():
    """Load presets from the autosave file if it exists."""
    sc = bpy.context.scene
    path = get_preset_file()
    if os.path.exists(path):
        arr = json.load(open(path))
        sc.signal_presets.clear()
        for e in arr:
            p = sc.signal_presets.add()
            p.name = e["name"]
            p.data = json.dumps(e["data"])
            p.preview_icon = e.get("preview_icon", "")

# ---------------------------------------------------------------------------
#   BAKING
# ---------------------------------------------------------------------------
CHANNEL_BAKE = [
    ('LOC', 'Location', ''),
    ('ROT', 'Rotation', ''),
    ('SCL', 'Scale',   ''),
]

# ---------------------------------------------------------------------------
#   UI ITEMS
# ---------------------------------------------------------------------------
CHANNEL_ITEMS = [
    ('LOC_X', "Posicion X", ""),
    ('LOC_Y', "Posicion Y", ""),
    ('LOC_Z', "Posicion Z", ""),
    ('ROT_X', "Rotacion X", ""),
    ('ROT_Y', "Rotacion Y", ""),
    ('ROT_Z', "Rotacion Z", ""),
    ('SCL_X', "Escala X",   ""),
    ('SCL_Y', "Escala Y",   ""),
    ('SCL_Z', "Escala Z",   ""),
    ('SCL_ALL', "Escala Uniforme", ""),
]

# ---------------------------------------------------------------------------
#   PROPERTY GROUP: SignalItem
# ---------------------------------------------------------------------------
class SignalItem(bpy.types.PropertyGroup):
    enabled:      BoolProperty(default=True)
    name:         StringProperty(default="Animation")
    channel:      EnumProperty(items=CHANNEL_ITEMS, default='LOC_X')
    signal_type:  EnumProperty(items=[
        ('SINE','Sine',''),('COSINE','Cosine',''),('SQUARE','Square',''),
        ('TRIANGLE','Triangle',''),('SAWTOOTH','Sawtooth',''),('NOISE','Noise','')
    ], default='SINE')
    amplitude:    FloatProperty(default=1.0, description="Amplitude in Blender units")
    frequency:    FloatProperty(default=1.0, min=0.001, description="Cycles per animation length")
    phase_offset: FloatProperty(default=0.0, description="Phase offset in degrees")
    duration:     IntProperty(default=24, min=1, description="Frames per cycle")
    offset:       IntProperty(default=0, description="Start frame offset")
    loop_count:   IntProperty(default=0, description="Number of loops (0=inf)")
    use_clamp:    BoolProperty(default=False, description="Clamp output range")
    clamp_min:    FloatProperty(default=-1.0)
    clamp_max:    FloatProperty(default=1.0)
    noise_seed:   IntProperty(default=0, description="Seed for noise signals")
    smoothing:    FloatProperty(default=0.0, min=0.0, max=1.0, description="Smoothing factor")
    base_value:   FloatProperty(default=0.0)
    start_frame:  IntProperty(default=0)

# ---------------------------------------------------------------------------
#   PROPERTY GROUP: SignalPreset
# ---------------------------------------------------------------------------
class SignalPreset(bpy.types.PropertyGroup):
    name: StringProperty(default="Preset")
    data: StringProperty(default="")
    preview_icon: StringProperty(default="")

class VJLOOPER_UL_presets(bpy.types.UIList):
    """List of saved presets with small icons."""
    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname, index
    ):
        icon_map = {
            'SINE':     'IPO_SINE',
            'TRIANGLE': 'IPO_TRI',
            'SQUARE':   'IPO_SQUARE',
            'SAWTOOTH': 'IPO_LIN',
            'COSINE':   'IPO_ELASTIC',
            'NOISE':    'RNDCURVE',
        }
        if not validate_preset(item.data):
            layout.alert = True
        layout.label(text="", icon=icon_map.get(item.preview_icon, 'PRESET'))
        layout.label(text=item.name)

class VJLOOPER_Preferences(bpy.types.AddonPreferences):
    """Addon preferences for VjLooper."""
    bl_idname = __package__

    use_keymaps: BoolProperty(
        name="Enable Default Shortcuts",
        default=True,
    )
    brush_color: FloatVectorProperty(
        name="Brush Color",
        subtype='COLOR',
        size=4,
        default=(1.0, 0.5, 0.2, 1.0),
    )
    autosave_path: StringProperty(
        name="Autosave Path",
        subtype='FILE_PATH',
        default=os.path.join(os.path.dirname(__file__), "presets.json"),
    )
    use_preview: BoolProperty(
        name="3D Preview",
        default=False,
    )

    def draw(self, context):
        self.layout.prop(self, "use_keymaps")
        self.layout.prop(self, "brush_color")
        self.layout.prop(self, "autosave_path")
        self.layout.prop(self, "use_preview")

# ---------------------------------------------------------------------------
#   OPERATORS
# ---------------------------------------------------------------------------
class VJLOOPER_OT_hot_reload(bpy.types.Operator):
    """Reload the add-on modules."""
    bl_idname = "vjlooper.hot_reload"
    bl_label  = "Reload Addon"
    bl_description = "Recarga VjLooper sin reiniciar Blender"

    def execute(self, context):
        addon = sys.modules.get(__package__)
        if addon:
            if hasattr(addon, 'unregister'):
                addon.unregister()
            importlib.reload(addon.panel)
            importlib.reload(addon)
            if hasattr(addon, 'register'):
                addon.register()
        self.report({'INFO'}, "VjLooper recargado")
        return {'FINISHED'}

class VJLOOPER_OT_add_signal(bpy.types.Operator):
    """Create a new SignalItem on the active object."""
    bl_idname  = "vjlooper.add_signal"
    bl_label   = "Add Animation"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, ctx):
        o  = ctx.object
        sc = ctx.scene
        if not o:
            return {'CANCELLED'}
        it = o.signal_items.add()
        it.name         = f"Animation{len(o.signal_items)+1:02d}"
        it.channel      = sc.signal_new_channel
        it.signal_type  = sc.signal_new_type
        it.amplitude    = sc.signal_new_amplitude
        it.frequency    = sc.signal_new_frequency
        it.phase_offset = sc.signal_new_phase
        it.duration     = sc.signal_new_duration
        it.offset       = sc.signal_new_offset
        it.loop_count   = sc.signal_new_loops
        it.use_clamp    = sc.signal_new_clamp
        it.clamp_min    = sc.signal_new_clamp_min
        it.clamp_max    = sc.signal_new_clamp_max
        it.noise_seed   = sc.signal_new_noise
        it.smoothing    = sc.signal_new_smoothing
        it.base_value   = get_channel_value(o, it.channel)
        it.start_frame  = sc.frame_current
        return {'FINISHED'}

class VJLOOPER_OT_remove_signal(bpy.types.Operator):
    """Delete a SignalItem from the active object."""
    bl_idname  = "vjlooper.remove_signal"
    bl_label   = "Remove Animation"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty()

    def execute(self, ctx):
        o = ctx.object
        if not o or self.index >= len(o.signal_items):
            return {'CANCELLED'}
        o.signal_items.remove(self.index)
        return {'FINISHED'}

class VJLOOPER_OT_add_preset(bpy.types.Operator):
    """Store current object signals as a new preset."""
    bl_idname = "vjlooper.add_preset"
    bl_label  = "Save Preset"

    name: StringProperty(default="Preset")

    def invoke(self, ctx, ev):
        return ctx.window_manager.invoke_props_dialog(self)

    def execute(self, ctx):
        sc   = ctx.scene
        data = []
        for it in ctx.object.signal_items:
            data.append({
                p.identifier: getattr(it, p.identifier)
                for p in it.bl_rna.properties if not p.is_readonly
            })
        pr = sc.signal_presets.add()
        pr.name = self.name
        pr.data = json.dumps(data)
        if ctx.object.signal_items:
            pr.preview_icon = ctx.object.signal_items[0].signal_type
        return {'FINISHED'}

class VJLOOPER_OT_load_preset(bpy.types.Operator):
    """Apply the selected preset to the active object."""
    bl_idname = "vjlooper.load_preset"
    bl_label  = "Load Preset"

    def execute(self, ctx):
        sc = ctx.scene
        idx = sc.signal_preset_index
        pr  = sc.signal_presets[idx]
        if not validate_preset(pr.data):
            self.report({'ERROR'}, "Preset invalido")
            return {'CANCELLED'}
        arr = json.loads(pr.data)
        apply_preset_to_object(ctx.object, arr, sc.frame_current, sc.preset_mirror)
        return {'FINISHED'}

class VJLOOPER_OT_apply_preset_multi(bpy.types.Operator):
    """Apply the active preset to all selected objects."""
    bl_idname = "vjlooper.apply_preset_multi"
    bl_label  = "Apply Preset to Selection"

    def execute(self, ctx):
        sc = ctx.scene
        idx = sc.signal_preset_index
        if idx >= len(sc.signal_presets):
            return {'CANCELLED'}
        pr = sc.signal_presets[idx]
        if not validate_preset(pr.data):
            self.report({'ERROR'}, "Preset invalido")
            return {'CANCELLED'}
        arr    = json.loads(pr.data)
        offset = sc.multi_offset_frames
        selected = [o for o in ctx.selected_objects if o != ctx.object]
        for i, obj in enumerate(selected):
            apply_preset_to_object(
                obj,
                arr,
                sc.frame_current,
                sc.preset_mirror,
                i * offset
            )
        return {'FINISHED'}

class VJLOOPER_OT_remove_preset(bpy.types.Operator):
    """Delete the selected preset from the list."""
    bl_idname = "vjlooper.remove_preset"
    bl_label  = "Remove Preset"

    def execute(self, ctx):
        sc = ctx.scene
        sc.signal_presets.remove(sc.signal_preset_index)
        return {'FINISHED'}

class VJLOOPER_OT_export_presets(bpy.types.Operator, bpy.types.ExportHelper):
    """Export all presets to a JSON file."""
    bl_idname    = "vjlooper.export_presets"
    bl_label     = "Export Presets"
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'})

    def execute(self, ctx):
        data = [
            {
                "name": p.name,
                "data": json.loads(p.data),
                "preview_icon": p.preview_icon,
            }
            for p in ctx.scene.signal_presets
        ]
        with open(self.filepath, 'w') as f:
            json.dump(data, f, indent=2)
        return {'FINISHED'}

class VJLOOPER_OT_import_presets(bpy.types.Operator, bpy.types.ImportHelper):
    """Load presets from a JSON file."""
    bl_idname    = "vjlooper.import_presets"
    bl_label     = "Import Presets"
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'})

    def execute(self, ctx):
        arr = json.load(open(self.filepath))
        sc  = ctx.scene
        sc.signal_presets.clear()
        for e in arr:
            p = sc.signal_presets.add()
            p.name = e["name"]
            p.data = json.dumps(e["data"])
            p.preview_icon = e.get("preview_icon", "")
        return {'FINISHED'}

class VJLOOPER_OT_bake_settings(bpy.types.Operator):
    """Configure bake range and channel."""
    bl_idname = "vjlooper.bake_settings"
    bl_label  = "Bake Settings"

    start:   IntProperty(default=1)
    end:     IntProperty(default=250)
    channel: EnumProperty(items=CHANNEL_BAKE, default='LOC')

    def invoke(self, ctx, ev):
        return ctx.window_manager.invoke_props_dialog(self)

    def execute(self, ctx):
        sc = ctx.scene
        sc.bake_start   = self.start
        sc.bake_end     = self.end
        sc.bake_channel = self.channel
        return {'FINISHED'}

class VJLOOPER_OT_bake_animation(bpy.types.Operator):
    """Bake procedural signals to keyframes."""
    bl_idname = "vjlooper.bake_animation"
    bl_label  = "Bake Animation"

    def execute(self, ctx):
        sc = ctx.scene
        for f in range(sc.bake_start, sc.bake_end + 1):
            sc.frame_set(f)
            for it in ctx.object.signal_items:
                if not it.enabled:
                    continue
                v = calc_signal(it, ctx.object, f)
                if sc.bake_channel == 'LOC':
                    ctx.object.location = Vector((v,)*3)
                if sc.bake_channel == 'ROT':
                    ctx.object.rotation_euler = Vector((v,)*3)
                if sc.bake_channel == 'SCL':
                    ctx.object.scale = Vector((v,)*3)
                ctx.object.keyframe_insert(data_path=sc.bake_channel.lower())
        return {'FINISHED'}

class VJLOOPER_OT_toggle_preset_brush(bpy.types.Operator):
    """Enable or disable preset brush mode."""
    bl_idname = "vjlooper.toggle_preset_brush"
    bl_label  = "Toggle Preset Brush"

    def execute(self, ctx):
        sc = ctx.scene
        sc.preset_brush_active = not sc.preset_brush_active
        if sc.preset_brush_active:
            if preset_brush_handler not in bpy.app.handlers.depsgraph_update_post:
                bpy.app.handlers.depsgraph_update_post.append(preset_brush_handler)
        else:
            if preset_brush_handler in bpy.app.handlers.depsgraph_update_post:
                bpy.app.handlers.depsgraph_update_post.remove(preset_brush_handler)
        return {'FINISHED'}

class VJLOOPER_OT_set_pivot(bpy.types.Operator):
    """Move object origins to preset pivot positions."""
    bl_idname = "vjlooper.set_pivot"
    bl_label  = "Set Pivot"

    location: EnumProperty(
        name="Pivot",
        items=[
            ('CENTER', "Center", ""),
            ('TL',     "Top Left", ""),
            ('TR',     "Top Right", ""),
            ('BL',     "Bottom Left", ""),
            ('BR',     "Bottom Right", ""),
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
            else:  # BR
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

# ---------------------------------------------------------------------------
#   PANEL UI
# ---------------------------------------------------------------------------
class VJLOOPER_PT_panel(bpy.types.Panel):
    bl_label       = "VjLooper"
    bl_idname      = "VJLOOPER_PT_panel"
    bl_space_type  = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category    = "VjLooper"

    # ---------------------------------------------------------------------
    def draw(self, ctx):
        layout = self.layout
        sc = ctx.scene
        obj = ctx.object

        row = layout.row(align=True)
        anim_count = len(obj.signal_items) if obj else 0
        row.label(text=f"{anim_count} anim", icon='ACTION')
        row.label(text=f"{len(sc.signal_presets)} preset", icon='PRESET')
        row.operator(
            'vjlooper.toggle_preset_brush',
            text='',
            icon='BRUSH_DATA',
            depress=sc.preset_brush_active
        )
        if sc.preset_brush_active:
            row.alert = True
        layout.separator()

        self.draw_create_ui(layout, ctx)
        self.draw_items_ui(layout, ctx)
        self.draw_presets_ui(layout, ctx)
        self.draw_bake_ui(layout)
        self.draw_misc_ui(layout, ctx)

    # ---------------------------------------------------------------------
    #   Seccion CREAR / EDITAR animaciones
    # ---------------------------------------------------------------------
    def draw_create_ui(self, L, ctx):
        sc  = ctx.scene
        obj = ctx.object
        if not obj:
            return
        col = L.column()
        col.use_property_split = True

        box = col.box()
        box.label(text="Crear animacion")
        box.prop(sc, "signal_new_channel", text="Channel", expand=True)
        box.template_icon_view(sc, "signal_new_type", show_labels=True, scale=5.0)
        row = box.row()
        col1, col2 = row.column(), row.column()
        col1.prop(sc, "signal_new_amplitude", text="Amplitude")
        col1.prop(sc, "signal_new_frequency", text="Frequency")
        col2.prop(sc, "signal_new_phase", text="Phase")
        col2.prop(sc, "signal_new_duration", text="Duration")
        box.prop(sc, "signal_new_offset", text="Frame Offset")
        box.prop(sc, "signal_new_loops", text="Loop Count")
        box.operator("vjlooper.add_signal", text="Add Animation")

        boxg = col.box()
        boxg.label(text="Escalas globales")
        boxg.prop(obj, "global_amp_scale",  text="Amplitude Scale")
        boxg.prop(obj, "global_freq_scale", text="Frequency Scale")
        boxg.prop(obj, "global_dur_scale",  text="Duration Scale")

    # ---------------------------------------------------------------------
    #   Lista de animaciones del objeto activo
    # ---------------------------------------------------------------------
    def draw_items_ui(self, L, ctx):
        obj = ctx.object
        if obj and obj.signal_items:
            col = L.column()
            col.use_property_split = True
            box2 = col.box()
            box2.label(text="Animaciones")
            for i, it in enumerate(obj.signal_items):
                sub = box2.box()
                sub.alert = not it.enabled
                header = sub.row(align=True)
                header.prop(it, "enabled", text="")
                header.prop(it, "name", text="")
                header.operator(
                    "vjlooper.remove_signal",
                    icon='X',
                    text=""
                ).index = i
                sub.template_icon_view(it, "signal_type", scale=5.0)
                sub.prop(it, "channel", expand=True)
                row = sub.row()
                c1, c2 = row.column(), row.column()
                c1.prop(it, "amplitude")
                c1.prop(it, "frequency")
                c2.prop(it, "phase_offset")
                c2.prop(it, "duration")
                sub.prop(it, "offset")
                sub.prop(it, "loop_count")
                sub.prop(it, "use_clamp")
                if it.use_clamp:
                    r = sub.row(align=True)
                    r.prop(it, "clamp_min")
                    r.prop(it, "clamp_max")

    # ---------------------------------------------------------------------
    #   Gestion de PRESETS
    # ---------------------------------------------------------------------
    def draw_presets_ui(self, L, ctx):
        sc = ctx.scene
        col = L.column()
        col.use_property_split = True
        col.operator("vjlooper.add_preset", text="Save Preset")
        col.operator("vjlooper.load_preset", text="Load Preset")
        col.operator("vjlooper.export_presets", text="Export Presets")
        col.operator("vjlooper.import_presets", text="Import Presets")
        if sc.signal_presets:
            col.template_list(
                "VJLOOPER_UL_presets",
                "",
                sc, "signal_presets",
                sc, "signal_preset_index"
            )
            row = col.row(align=True)
            row.prop(sc, "multi_offset_frames", text="Offset")
            row.operator("vjlooper.apply_preset_multi", text="Apply to Selection")
            col.prop(sc, "preset_mirror", text="Mirror")
            col.operator(
                "vjlooper.toggle_preset_brush",
                text="Toggle Preset Brush",
                depress=sc.preset_brush_active
            )

    # ---------------------------------------------------------------------
    #   Baking
    # ---------------------------------------------------------------------
    def draw_bake_ui(self, L):
        L.separator()
        col = L.column()
        col.use_property_split = True
        col.operator("vjlooper.bake_settings", icon='REC', text="Bake Settings")
        col.operator("vjlooper.bake_animation", text="Bake Animation")

    # ---------------------------------------------------------------------
    #   Miscelaneas
    # ---------------------------------------------------------------------
    def draw_misc_ui(self, L, ctx):
        L.separator()
        box_p = L.box()
        box_p.label(text="Set Pivot")
        row = box_p.row(align=True)
        row.operator("vjlooper.set_pivot", text="Center").location = 'CENTER'
        row.operator("vjlooper.set_pivot", text="TL").location = 'TL'
        row.operator("vjlooper.set_pivot", text="TR").location = 'TR'
        row2 = box_p.row(align=True)
        row2.operator("vjlooper.set_pivot", text="BL").location = 'BL'
        row2.operator("vjlooper.set_pivot", text="BR").location = 'BR'

        L.separator()
        L.operator("vjlooper.hot_reload", icon='FILE_REFRESH', text="Reload Addon")

# ---------------------------------------------------------------------------
#   KEYMAPS
# ---------------------------------------------------------------------------
addon_keymaps = []

def register_keymaps():
    """Register default keymaps if enabled in preferences."""
    prefs = bpy.context.preferences.addons[__package__].preferences
    if not prefs.use_keymaps:
        return
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km  = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        kmi = km.keymap_items.new('vjlooper.load_preset', 'P', 'PRESS', ctrl=True, shift=True)
        addon_keymaps.append((km, kmi))
        kmi = km.keymap_items.new('vjlooper.toggle_preset_brush', 'L', 'PRESS', shift=True)
        addon_keymaps.append((km, kmi))

def unregister_keymaps():
    """Remove registered keymaps."""
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        for km, kmi in addon_keymaps:
            km.keymap_items.remove(kmi)
    addon_keymaps.clear()

# ---------------------------------------------------------------------------
#   REGISTER / UNREGISTER
# ---------------------------------------------------------------------------
classes = (
    VJLOOPER_Preferences,
    SignalItem,
    SignalPreset,
    VJLOOPER_UL_presets,
    VJLOOPER_OT_hot_reload,
    VJLOOPER_OT_add_signal,
    VJLOOPER_OT_remove_signal,
    VJLOOPER_OT_add_preset,
    VJLOOPER_OT_load_preset,
    VJLOOPER_OT_apply_preset_multi,
    VJLOOPER_OT_remove_preset,
    VJLOOPER_OT_export_presets,
    VJLOOPER_OT_import_presets,
    VJLOOPER_OT_bake_settings,
    VJLOOPER_OT_bake_animation,
    VJLOOPER_OT_toggle_preset_brush,
    VJLOOPER_OT_set_pivot,
    VJLOOPER_PT_panel,
)

def register():
    """Register all classes and properties for the add-on."""
    global preview_handle
    for c in classes:
        bpy.utils.register_class(c)

    # Object props
    bpy.types.Object.signal_items      = CollectionProperty(type=SignalItem)
    bpy.types.Object.global_amp_scale  = FloatProperty(default=1.0, description="Amplitude multiplier")
    bpy.types.Object.global_freq_scale = FloatProperty(default=1.0, description="Frequency multiplier")
    bpy.types.Object.global_dur_scale  = FloatProperty(default=1.0, description="Duration multiplier")

    # Handlers
    bpy.app.handlers.frame_change_pre.append(frame_handler)

    prefs = bpy.context.preferences.addons[__package__].preferences
    if prefs.use_preview and preview_handle is None:
        preview_handle = bpy.types.SpaceView3D.draw_handler_add(
            draw_preview_callback, (), 'WINDOW', 'POST_PIXEL')

    # Scene props
    sc = bpy.types.Scene
    sc.signal_new_channel   = EnumProperty(items=CHANNEL_ITEMS, default='LOC_X')
    sc.signal_new_type      = EnumProperty(items=[
        ('SINE','Sine',''),('COSINE','Cosine',''),('SQUARE','Square',''),
        ('TRIANGLE','Triangle',''),('SAWTOOTH','Sawtooth',''),('NOISE','Noise','')
    ], default='SINE')
    sc.signal_new_amplitude = FloatProperty(default=1.0, description="Default amplitude")
    sc.signal_new_frequency = FloatProperty(default=1.0, description="Default frequency")
    sc.signal_new_phase     = FloatProperty(default=0.0, description="Default phase")
    sc.signal_new_duration  = IntProperty(default=24,  description="Default duration")
    sc.signal_new_offset    = IntProperty(default=0,   description="Frame offset when creating")
    sc.signal_new_loops     = IntProperty(default=0,   description="Loop count")
    sc.signal_new_clamp     = BoolProperty(default=False, description="Use clamp")
    sc.signal_new_clamp_min = FloatProperty(default=-1.0, description="Clamp min")
    sc.signal_new_clamp_max = FloatProperty(default=1.0,  description="Clamp max")
    sc.signal_new_noise     = IntProperty(default=0,   description="Noise seed")
    sc.signal_new_smoothing = FloatProperty(default=0.0, description="Smoothing")

    sc.signal_presets       = CollectionProperty(type=SignalPreset)
    sc.signal_preset_index  = IntProperty(default=0)

    sc.multi_offset_frames  = IntProperty(default=0, description="Frame offset between objects")
    sc.preset_mirror        = BoolProperty(default=False, description="Mirror amplitude when loading")
    sc.preset_brush_active  = BoolProperty(default=False, description="Enable preset brush mode")

    sc.bake_start   = IntProperty(default=1)
    sc.bake_end     = IntProperty(default=250)
    sc.bake_channel = EnumProperty(items=CHANNEL_BAKE, default='LOC')

    register_keymaps()
    load_presets_from_disk()

def unregister():
    """Unregister classes and clean up properties."""
    save_presets_to_disk()
    unregister_keymaps()
    bpy.app.handlers.frame_change_pre.remove(frame_handler)
    if preset_brush_handler in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(preset_brush_handler)

    global preview_handle
    if preview_handle is not None:
        bpy.types.SpaceView3D.draw_handler_remove(preview_handle, 'WINDOW')
        preview_handle = None

    for c in reversed(classes):
        bpy.utils.unregister_class(c)

    del bpy.types.Object.signal_items
    del bpy.types.Object.global_amp_scale
    del bpy.types.Object.global_freq_scale
    del bpy.types.Object.global_dur_scale

    for prop in [
        "signal_new_channel", "signal_new_type", "signal_new_amplitude",
        "signal_new_frequency", "signal_new_phase", "signal_new_duration",
        "signal_new_offset", "signal_new_loops", "signal_new_clamp",
        "signal_new_clamp_min", "signal_new_clamp_max", "signal_new_noise",
        "signal_new_smoothing", "signal_presets", "signal_preset_index",
        "multi_offset_frames", "preset_mirror", "preset_brush_active",
        "bake_start", "bake_end", "bake_channel"
    ]:
        delattr(bpy.types.Scene, prop)
