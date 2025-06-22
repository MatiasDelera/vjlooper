import bpy
import importlib
import json
import math
import random
import sys
from mathutils import Vector
from bpy.props import (
    BoolProperty, EnumProperty, FloatProperty, IntProperty,
    StringProperty, CollectionProperty
)

# ─────────────────────────────────────────────────────────────────────────────
#   LÓGICA: cache, cálculo de señal y frame handler
# ─────────────────────────────────────────────────────────────────────────────
class SignalCache:
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
    obj.signal_items.clear()
    for d in preset_data:
        it = obj.signal_items.add()
        for k, v in d.items():
            if k == "amplitude" and mirror:
                v = -v
            setattr(it, k, v)
        it.start_frame = base_frame + offset


def calc_signal(it, obj, frame):
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
    t = (cycle / duration) * frequency + it.phase_offset/360.0
    if it.signal_type=='SINE':      wave = math.sin(2*math.pi*t)
    elif it.signal_type=='COSINE':  wave = math.cos(2*math.pi*t)
    elif it.signal_type=='SQUARE':  wave = 1.0 if math.sin(2*math.pi*t)>=0 else -1.0
    elif it.signal_type=='TRIANGLE':
        p=t%1.0; wave=4*p-1 if p<0.5 else 3-4*p
    elif it.signal_type=='SAWTOOTH':wave=2*(t%1.0)-1
    elif it.signal_type=='NOISE':
        random.seed(it.noise_seed+frame); wave=random.uniform(-1,1)
    else:                           wave=0.0
    last = smoothing_cache.get(id(it), wave)
    val  = last*it.smoothing + wave*(1-it.smoothing) if it.smoothing else wave
    smoothing_cache[id(it)] = val
    out  = it.base_value + amplitude*val
    if it.use_clamp:
        out = max(it.clamp_min, min(it.clamp_max, out))
    return out

def set_channel(obj, ch, v):
    if ch=='LOC_X': obj.location.x=v
    if ch=='LOC_Y': obj.location.y=v
    if ch=='LOC_Z': obj.location.z=v
    if ch=='ROT_X': obj.rotation_euler.x=v
    if ch=='ROT_Y': obj.rotation_euler.y=v
    if ch=='ROT_Z': obj.rotation_euler.z=v
    if ch=='SCL_X': obj.scale.x=v
    if ch=='SCL_Y': obj.scale.y=v
    if ch=='SCL_Z': obj.scale.z=v
    if ch=='SCL_ALL': obj.scale=(v,v,v)

def get_channel_value(obj, ch):
    if ch=='LOC_X': return obj.location.x
    if ch=='LOC_Y': return obj.location.y
    if ch=='LOC_Z': return obj.location.z
    if ch=='ROT_X': return obj.rotation_euler.x
    if ch=='ROT_Y': return obj.rotation_euler.y
    if ch=='ROT_Z': return obj.rotation_euler.z
    if ch=='SCL_X': return obj.scale.x
    if ch=='SCL_Y': return obj.scale.y
    if ch=='SCL_Z': return obj.scale.z
    if ch=='SCL_ALL': return obj.scale.x
    return 0.0

def frame_handler(scene):
    f = scene.frame_current
    for obj in scene.objects:
        if hasattr(obj, "signal_items"):
            for it in obj.signal_items:
                if it.enabled:
                    v = calc_signal(it, obj, f)
                    set_channel(obj, it.channel, v)

brush_last_obj = None
def preset_brush_handler(scene):
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
                apply_preset_to_object(obj, arr, scene.frame_current,
                                       scene.preset_mirror)
    brush_last_obj = obj

# ─────────────────────────────────────────────────────────────────────────────
#   PRESETS: validación JSON
# ─────────────────────────────────────────────────────────────────────────────
def validate_preset(data):
    try:
        return isinstance(json.loads(data), list)
    except:
        return False

# ─────────────────────────────────────────────────────────────────────────────
#   BAKING
# ─────────────────────────────────────────────────────────────────────────────
CHANNEL_BAKE = [
    ('LOC', 'Location', ''),
    ('ROT', 'Rotation', ''),
    ('SCL', 'Scale', ''),
]

# ─────────────────────────────────────────────────────────────────────────────
#   UI ITEMS
# ─────────────────────────────────────────────────────────────────────────────
CHANNEL_ITEMS = [
    ('LOC_X', "Posición X", ""),
    ('LOC_Y', "Posición Y", ""),
    ('LOC_Z', "Posición Z", ""),
    ('ROT_X', "Rotación X", ""),
    ('ROT_Y', "Rotación Y", ""),
    ('ROT_Z', "Rotación Z", ""),
    ('SCL_X', "Escala X", ""),
    ('SCL_Y', "Escala Y", ""),
    ('SCL_Z', "Escala Z", ""),
    ('SCL_ALL', "Escala Uniforme", ""),
]

# ─────────────────────────────────────────────────────────────────────────────
#   PROPERTY GROUP: SignalItem
# ─────────────────────────────────────────────────────────────────────────────
class SignalItem(bpy.types.PropertyGroup):
    enabled:      BoolProperty(default=True)
    name:         StringProperty(default="Animation")
    channel:      EnumProperty(items=CHANNEL_ITEMS, default='LOC_X')
    signal_type:  EnumProperty(items=[
        ('SINE','Sine',''),('COSINE','Cosine',''),('SQUARE','Square',''),
        ('TRIANGLE','Triangle',''),('SAWTOOTH','Sawtooth',''),('NOISE','Noise','')
    ], default='SINE')
    amplitude:    FloatProperty(default=1.0)
    frequency:    FloatProperty(default=1.0, min=0.001)
    phase_offset: FloatProperty(default=0.0)
    duration:     IntProperty(default=24, min=1)
    offset:       IntProperty(default=0)
    loop_count:   IntProperty(default=0)
    use_clamp:    BoolProperty(default=False)
    clamp_min:    FloatProperty(default=-1.0)
    clamp_max:    FloatProperty(default=1.0)
    noise_seed:   IntProperty(default=0)
    smoothing:    FloatProperty(default=0.0, min=0.0, max=1.0)
    base_value:   FloatProperty(default=0.0)
    start_frame:  IntProperty(default=0)

# ─────────────────────────────────────────────────────────────────────────────
#   PROPERTY GROUP: SignalPreset
# ─────────────────────────────────────────────────────────────────────────────
class SignalPreset(bpy.types.PropertyGroup):
    name: StringProperty(default="Preset")
    data: StringProperty(default="")

# ─────────────────────────────────────────────────────────────────────────────
#   OPERATORS
# ─────────────────────────────────────────────────────────────────────────────
class VJLOOPER_OT_hot_reload(bpy.types.Operator):
    bl_idname = "vjlooper.hot_reload"
    bl_label = "Reload Addon"
    bl_description = "Recarga VjLooper sin reiniciar Blender"
    def execute(self, context):
        import sys
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
    bl_idname    = "vjlooper.add_signal"
    bl_label     = "Add Animation"
    bl_options   = {'REGISTER','UNDO'}
    def execute(self, ctx):
        o = ctx.object; sc = ctx.scene
        if not o: return {'CANCELLED'}
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
    bl_idname = "vjlooper.remove_signal"
    bl_label    = "Remove Animation"
    bl_options  = {'REGISTER','UNDO'}
    index: IntProperty()
    def execute(self, ctx):
        o = ctx.object
        if not o or self.index>=len(o.signal_items):
            return {'CANCELLED'}
        o.signal_items.remove(self.index)
        return {'FINISHED'}

class VJLOOPER_OT_add_preset(bpy.types.Operator):
    bl_idname = "vjlooper.add_preset"
    bl_label    = "Save Preset"
    name: StringProperty(default="Preset")
    def invoke(self, ctx, ev): return ctx.window_manager.invoke_props_dialog(self)
    def execute(self, ctx):
        sc = ctx.scene; data=[]
        for it in ctx.object.signal_items:
            data.append({p.identifier:getattr(it,p.identifier)
                         for p in it.bl_rna.properties if not p.is_readonly})
        pr = sc.signal_presets.add()
        pr.name = self.name
        pr.data = json.dumps(data)
        return {'FINISHED'}

class VJLOOPER_OT_load_preset(bpy.types.Operator):
    bl_idname = "vjlooper.load_preset"
    bl_label    = "Load Preset"
    def execute(self, ctx):
        sc = ctx.scene; idx = sc.signal_preset_index
        pr = sc.signal_presets[idx]
        if not validate_preset(pr.data):
            self.report({'ERROR'},"Preset inválido"); return {'CANCELLED'}
        arr = json.loads(pr.data)
        apply_preset_to_object(ctx.object, arr, sc.frame_current,
                               sc.preset_mirror)
        return {'FINISHED'}

class VJLOOPER_OT_apply_preset_multi(bpy.types.Operator):
    bl_idname = "vjlooper.apply_preset_multi"
    bl_label  = "Apply Preset to Selection"

    def execute(self, ctx):
        sc = ctx.scene; idx = sc.signal_preset_index
        if idx >= len(sc.signal_presets):
            return {'CANCELLED'}
        pr = sc.signal_presets[idx]
        if not validate_preset(pr.data):
            self.report({'ERROR'}, "Preset inválido")
            return {'CANCELLED'}
        arr = json.loads(pr.data)
        offset = sc.multi_offset_frames
        selected = [o for o in ctx.selected_objects if o != ctx.object]
        for i, obj in enumerate(selected):
            apply_preset_to_object(obj, arr, sc.frame_current,
                                   sc.preset_mirror, i * offset)
        return {'FINISHED'}

class VJLOOPER_OT_remove_preset(bpy.types.Operator):
    bl_idname = "vjlooper.remove_preset"
    bl_label    = "Remove Preset"
    def execute(self, ctx):
        sc = ctx.scene; sc.signal_presets.remove(sc.signal_preset_index)
        return {'FINISHED'}

class VJLOOPER_OT_export_presets(bpy.types.Operator, bpy.types.ExportHelper):
    bl_idname     = "vjlooper.export_presets"
    bl_label      = "Export Presets"
    filename_ext  = ".json"
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'})
    def execute(self, ctx):
        data = [{"name":p.name,"data":json.loads(p.data)} for p in ctx.scene.signal_presets]
        with open(self.filepath,'w') as f: json.dump(data,f,indent=2)
        return {'FINISHED'}

class VJLOOPER_OT_import_presets(bpy.types.Operator, bpy.types.ImportHelper):
    bl_idname     = "vjlooper.import_presets"
    bl_label      = "Import Presets"
    filename_ext  = ".json"
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'})
    def execute(self, ctx):
        arr = json.load(open(self.filepath))
        sc = ctx.scene; sc.signal_presets.clear()
        for e in arr:
            p = sc.signal_presets.add()
            p.name = e["name"]
            p.data = json.dumps(e["data"])
        return {'FINISHED'}

class VJLOOPER_OT_bake_settings(bpy.types.Operator):
    bl_idname = "vjlooper.bake_settings"
    bl_label    = "Bake Settings"
    start: IntProperty(default=1)
    end:   IntProperty(default=250)
    channel: EnumProperty(items=CHANNEL_BAKE, default='LOC')
    def invoke(self, ctx, ev): return ctx.window_manager.invoke_props_dialog(self)
    def execute(self, ctx):
        sc = ctx.scene
        sc.bake_start   = self.start
        sc.bake_end     = self.end
        sc.bake_channel = self.channel
        return {'FINISHED'}

class VJLOOPER_OT_bake_animation(bpy.types.Operator):
    bl_idname = "vjlooper.bake_animation"
    bl_label    = "Bake Animation"
    def execute(self, ctx):
        sc = ctx.scene
        for f in range(sc.bake_start, sc.bake_end+1):
            sc.frame_set(f)
            for it in ctx.object.signal_items:
                if not it.enabled: continue
                v = calc_signal(it, ctx.object, f)
                if sc.bake_channel=='LOC': ctx.object.location=Vector((v,)*3)
                if sc.bake_channel=='ROT': ctx.object.rotation_euler=Vector((v,)*3)
                if sc.bake_channel=='SCL': ctx.object.scale=Vector((v,)*3)
                ctx.object.keyframe_insert(data_path=sc.bake_channel.lower())
        return {'FINISHED'}

class VJLOOPER_OT_toggle_preset_brush(bpy.types.Operator):
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
    bl_idname = "vjlooper.set_pivot"
    bl_label  = "Set Pivot"

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
                loc = Vector((sum(xs)/8, sum(ys)/8, sum(zs)/8))
            elif self.location == 'TL':
                loc = Vector((min(xs), max(ys), max(zs)))
            elif self.location == 'TR':
                loc = Vector((max(xs), max(ys), max(zs)))
            elif self.location == 'BL':
                loc = Vector((min(xs), min(ys), min(zs)))
            else:  # BR
                loc = Vector((max(xs), min(ys), min(zs)))

            ctx.scene.cursor.location = loc
            bpy.ops.object.origin_set({'object': obj, 'selected_objects':[obj], 'active_object': obj}, type='ORIGIN_CURSOR')
        ctx.scene.cursor.location = cursor
        return {'FINISHED'}

# ─────────────────────────────────────────────────────────────────────────────
#   PANEL UI
# ─────────────────────────────────────────────────────────────────────────────
class VJLOOPER_PT_panel(bpy.types.Panel):
    bl_label      = "VjLooper"
    bl_idname     = "VJLOOPER_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type= 'UI'
    bl_category   = "VjLooper"

    def draw(self, ctx):
        L = self.layout; sc = ctx.scene; obj = ctx.object
        L.label(text="VjLooper Controls")
        L.separator()

        if obj:
            box = L.box(); box.label(text="Crear Animación")
            col = box.column(align=True)
            col.prop(sc, "signal_new_channel", text="Propiedad")
            col.prop(sc, "signal_new_type",    text="Tipo")
            col.prop(sc, "signal_new_amplitude")
            col.prop(sc, "signal_new_frequency")
            col.prop(sc, "signal_new_phase", text="Phase Offset")
            col.prop(sc, "signal_new_duration", text="Duration")
            col.prop(sc, "signal_new_offset", text="Frame Offset")
            col.prop(sc, "signal_new_loops", text="Loop Count")
            box.operator("vjlooper.add_signal", text="Add Animation")

            boxg = L.box(); boxg.label(text="Global Scales")
            boxg.prop(obj, "global_amp_scale", text="Amplitude Scale")
            boxg.prop(obj, "global_freq_scale", text="Frequency Scale")
            boxg.prop(obj, "global_dur_scale", text="Duration Scale")

            if obj.signal_items:
                box2 = L.box(); box2.label(text="Animaciones")
                for i,it in enumerate(obj.signal_items):
                    row = box2.row(align=True)
                    row.prop(it, "enabled", text="")
                    row.label(text=it.name)
                    row.operator("vjlooper.remove_signal", icon='X', text="").index = i

        L.separator()
        L.operator("vjlooper.add_preset",   text="Save Preset")
        L.operator("vjlooper.load_preset",  text="Load Preset")
        L.operator("vjlooper.export_presets",text="Export Presets")
        L.operator("vjlooper.import_presets",text="Import Presets")
        if sc.signal_presets:
            L.template_list("UI_UL_list", "vjlooper_presets", sc, "signal_presets", sc, "signal_preset_index")
            row = L.row(align=True)
            row.prop(sc, "multi_offset_frames", text="Offset")
            row.operator("vjlooper.apply_preset_multi", text="Apply to Selection")
            L.prop(sc, "preset_mirror", text="Mirror")
            L.operator("vjlooper.toggle_preset_brush", text="Toggle Preset Brush", depress=sc.preset_brush_active)

        L.separator()
        L.operator("vjlooper.bake_settings",icon='REC',text="Bake Settings")
        L.operator("vjlooper.bake_animation",text="Bake Animation")

        L.separator()
        box_p = L.box(); box_p.label(text="Set Pivot")
        row = box_p.row(align=True)
        row.operator("vjlooper.set_pivot", text="Center").location='CENTER'
        row.operator("vjlooper.set_pivot", text="TL").location='TL'
        row.operator("vjlooper.set_pivot", text="TR").location='TR'
        row2 = box_p.row(align=True)
        row2.operator("vjlooper.set_pivot", text="BL").location='BL'
        row2.operator("vjlooper.set_pivot", text="BR").location='BR'

        L.separator()
        L.operator("vjlooper.hot_reload",   icon='FILE_REFRESH', text="Reload Addon")

# ─────────────────────────────────────────────────────────────────────────────
#   REGISTER / UNREGISTER
# ─────────────────────────────────────────────────────────────────────────────
classes = (
    SignalItem,
    SignalPreset,
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
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Object.signal_items = CollectionProperty(type=SignalItem)
    bpy.types.Object.global_amp_scale  = FloatProperty(default=1.0)
    bpy.types.Object.global_freq_scale = FloatProperty(default=1.0)
    bpy.types.Object.global_dur_scale  = FloatProperty(default=1.0)
    bpy.app.handlers.frame_change_pre.append(frame_handler)

    sc = bpy.types.Scene
    sc.signal_new_channel   = EnumProperty(items=CHANNEL_ITEMS, default='LOC_X')
    sc.signal_new_type      = EnumProperty(items=[
        ('SINE','Sine',''),('COSINE','Cosine',''),('SQUARE','Square',''),
        ('TRIANGLE','Triangle',''),('SAWTOOTH','Sawtooth',''),('NOISE','Noise','')
    ], default='SINE')
    sc.signal_new_amplitude = FloatProperty(default=1.0)
    sc.signal_new_frequency = FloatProperty(default=1.0)
    sc.signal_new_phase     = FloatProperty(default=0.0)
    sc.signal_new_duration  = IntProperty(default=24)
    sc.signal_new_offset    = IntProperty(default=0)
    sc.signal_new_loops     = IntProperty(default=0)
    sc.signal_new_clamp     = BoolProperty(default=False)
    sc.signal_new_clamp_min = FloatProperty(default=-1.0)
    sc.signal_new_clamp_max = FloatProperty(default=1.0)
    sc.signal_new_noise     = IntProperty(default=0)
    sc.signal_new_smoothing = FloatProperty(default=0.0)
    sc.signal_presets       = CollectionProperty(type=SignalPreset)
    sc.signal_preset_index  = IntProperty(default=0)
    sc.multi_offset_frames  = IntProperty(default=0)
    sc.preset_mirror        = BoolProperty(default=False)
    sc.preset_brush_active  = BoolProperty(default=False)
    sc.bake_start           = IntProperty(default=1)
    sc.bake_end             = IntProperty(default=250)
    sc.bake_channel         = EnumProperty(items=CHANNEL_BAKE, default='LOC')

def unregister():
    bpy.app.handlers.frame_change_pre.remove(frame_handler)
    if preset_brush_handler in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(preset_brush_handler)
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
    del bpy.types.Object.signal_items
    del bpy.types.Object.global_amp_scale
    del bpy.types.Object.global_freq_scale
    del bpy.types.Object.global_dur_scale
    for prop in [
        "signal_new_channel","signal_new_type","signal_new_amplitude","signal_new_frequency",
        "signal_new_phase","signal_new_duration","signal_new_offset",
        "signal_new_loops","signal_new_clamp","signal_new_clamp_min","signal_new_clamp_max",
        "signal_new_noise","signal_new_smoothing",
        "signal_presets","signal_preset_index","multi_offset_frames","preset_mirror","preset_brush_active",
        "bake_start","bake_end","bake_channel"
    ]:
        delattr(bpy.types.Scene, prop)
