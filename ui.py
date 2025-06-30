"""User interface for the VjLooper add-on."""

import bpy
import os
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
    CollectionProperty,
)
from bpy.types import PropertyGroup, UIList, AddonPreferences, Panel

from . import signals
from . import operators
from . import tunnelfx


class SignalItem(PropertyGroup):
    enabled: BoolProperty(default=True)
    name: StringProperty(default="Animation")
    channel: EnumProperty(items=signals.CHANNEL_ITEMS, default='LOC_X')
    signal_type: EnumProperty(items=[
        ('SINE','Sine',''),('COSINE','Cosine',''),('SQUARE','Square',''),
        ('TRIANGLE','Triangle',''),('SAWTOOTH','Sawtooth',''),('NOISE','Noise','')
    ], default='SINE')
    amplitude: FloatProperty(default=1.0, description="Amplitude in Blender units")
    frequency: FloatProperty(default=1.0, min=0.001, description="Cycles per animation length", update=signals.update_frequency)
    amplitude_min: FloatProperty(default=0.5, description="Minimum random amplitude")
    amplitude_max: FloatProperty(default=1.5, description="Maximum random amplitude")
    frequency_min: FloatProperty(default=0.5, min=0.001, description="Minimum random frequency")
    frequency_max: FloatProperty(default=2.0, min=0.001, description="Maximum random frequency")
    phase_offset: FloatProperty(default=0.0, description="Phase offset in degrees")
    duration: IntProperty(
        default=24,
        min=1,
        description="Frames per cycle",
        update=signals.update_duration,
    )
    offset: IntProperty(default=0, description="Start frame offset", update=signals.update_offset)
    loop_count: IntProperty(default=0, description="Number of loops (0=inf)")
    blend_frames: IntProperty(default=0, description="Blend frames at loop end")
    use_clamp: BoolProperty(default=False, description="Clamp output range")
    clamp_min: FloatProperty(default=-1.0)
    clamp_max: FloatProperty(default=1.0)
    noise_seed: IntProperty(default=0, description="Seed for noise signals")
    smoothing: FloatProperty(default=0.0, min=0.0, max=1.0, description="Smoothing factor")
    base_value: FloatProperty(default=0.0)
    start_frame: IntProperty(default=0)
    marker_name: StringProperty(default="")


class SignalPreset(PropertyGroup):
    name: StringProperty(default="Preset")
    data: StringProperty(default="")
    preview_icon: StringProperty(default="")
    category: StringProperty(default="General")


class VJLOOPER_UL_presets(UIList):
    """List of saved presets with small icons."""
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        icon_map = {
            'SINE': 'IPO_SINE',
            'TRIANGLE': 'IPO_TRI',
            'SQUARE': 'IPO_SQUARE',
            'SAWTOOTH': 'IPO_LIN',
            'COSINE': 'IPO_ELASTIC',
            'NOISE': 'RNDCURVE',
        }
        presets = getattr(data, "signal_presets")
        order = getattr(self, "_cached_order", None)
        prev = None
        if order and index > 0:
            prev = presets[order[index - 1]]
        elif not order and index > 0:
            prev = presets[index - 1]
        if index == 0 or (prev and prev.category != item.category):
            layout.label(text=item.category, icon='FILE_FOLDER')
        row = layout.row()
        if not signals.validate_preset(item.data):
            row.alert = True
        row.label(text="", icon=icon_map.get(item.preview_icon, 'PRESET'))
        row.label(text=item.name)

    def filter_items(self, context, data, propname):
        items = list(getattr(data, propname))
        filt = context.scene.preset_category_filter.lower()
        order = [i for i, it in sorted(enumerate(items), key=lambda e: (e[1].category.lower(), e[1].name.lower()))]
        flags = []
        for i in order:
            it = items[i]
            if filt and filt not in it.category.lower():
                flags.append(self.bitflag_filter_item)
            else:
                flags.append(0)
        self._cached_order = order
        return flags, order


class VJMaterialItem(PropertyGroup):
    material: PointerProperty(type=bpy.types.Material)


class VJLOOPER_UL_materials(UIList):
    """List UI for available materials."""
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        mat = item if isinstance(item, bpy.types.Material) else item.material
        if mat:
            layout.template_preview(mat, show_buttons=False)
            layout.label(text=mat.name)


class VJLOOPER_Preferences(AddonPreferences):
    bl_idname = __package__

    use_keymaps: BoolProperty(name="Enable Default Shortcuts", default=True)
    brush_color: FloatVectorProperty(name="Brush Color", subtype='COLOR', size=4, default=(1.0, 0.5, 0.2, 1.0))
    autosave_path: StringProperty(name="Autosave Path", subtype='FILE_PATH', default=os.path.join(os.path.dirname(__file__), "presets.json"))
    use_preview: BoolProperty(name="3D Preview", default=False)
    hue_shift_range: FloatProperty(name="Hue Shift Range", default=0.1, min=0.0, max=1.0)

    def draw(self, context):
        self.layout.prop(self, "use_keymaps")
        self.layout.prop(self, "brush_color")
        self.layout.prop(self, "autosave_path")
        self.layout.prop(self, "use_preview")
        self.layout.prop(self, "hue_shift_range")


class VJLOOPER_PT_panel(Panel):
    bl_label = "Animator"
    bl_idname = "VJLOOPER_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Animator"

    def draw(self, ctx):
        layout = self.layout
        sc = ctx.scene
        obj = ctx.object

        row = layout.row(align=True)
        anim_count = len(obj.signal_items) if obj else 0
        row.label(text=f"{anim_count} anim", icon='ACTION')
        row.label(text=f"{len(sc.signal_presets)} preset", icon='PRESET')
        row.operator('vjlooper.toggle_preset_brush', text='', icon='BRUSH_DATA', depress=sc.preset_brush_active)
        if sc.preset_brush_active:
            row.alert = True
        layout.separator()

        col = layout.column()
        col.use_property_split = True

        h = col.row()
        h.prop(sc, "ui_show_create", text="", icon='TRIA_DOWN' if sc.ui_show_create else 'TRIA_RIGHT', emboss=False)
        h.label(text="Create")
        if sc.ui_show_create:
            self.draw_create_ui(col, ctx)

        h = col.row()
        h.prop(sc, "ui_show_items", text="", icon='TRIA_DOWN' if sc.ui_show_items else 'TRIA_RIGHT', emboss=False)
        h.label(text="Animations")
        if sc.ui_show_items:
            self.draw_items_ui(col, ctx)

        h = col.row()
        h.prop(sc, "ui_show_presets", text="", icon='TRIA_DOWN' if sc.ui_show_presets else 'TRIA_RIGHT', emboss=False)
        h.label(text="Presets")
        if sc.ui_show_presets:
            self.draw_presets_ui(col, ctx)

        h = col.row()
        h.prop(sc, "ui_show_bake", text="", icon='TRIA_DOWN' if sc.ui_show_bake else 'TRIA_RIGHT', emboss=False)
        h.label(text="Bake")
        if sc.ui_show_bake:
            self.draw_bake_ui(col)



    def draw_create_ui(self, L, ctx):
        sc = ctx.scene
        obj = ctx.object
        if not obj:
            return
        col = L.column()
        col.use_property_split = True

        box = col.box()
        box.label(text="Create Animation")
        box.prop(sc, "signal_new_channel", text="Channel", expand=True)
        box.template_icon_view(sc, "signal_new_type", show_labels=True, scale=5.0)
        row = box.row()
        col1, col2 = row.column(), row.column()
        col1.prop(sc, "signal_new_amplitude", text="Amplitude")
        rowf = col1.row(align=True)
        rowf.prop(sc, "signal_new_frequency", text="Frequency")
        perfect = abs(round(sc.signal_new_frequency * sc.signal_new_duration) - sc.signal_new_frequency * sc.signal_new_duration) < 1e-4
        rowf.alert = not perfect
        rowf.label(icon='CHECKMARK' if perfect else 'ERROR')
        col2.prop(sc, "signal_new_phase", text="Phase")
        col2.prop(sc, "signal_new_duration", text="Duration")
        box.prop(sc, "signal_new_offset", text="Frame Offset")
        box.prop(sc, "signal_new_loops", text="Loop Count")
        box.operator("vjlooper.add_signal", text="Add Animation")

        boxg = col.box()
        boxg.label(text="Global Scales")
        boxg.prop(obj, "global_amp_scale", text="Amplitude Scale")
        boxg.prop(obj, "global_freq_scale", text="Frequency Scale")
        boxg.prop(obj, "global_dur_scale", text="Duration Scale")

    def draw_items_ui(self, L, ctx):
        obj = ctx.object
        if obj and obj.signal_items:
            col = L.column()
            col.use_property_split = True
            box2 = col.box()
            box2.label(text="Animations")
            for i, it in enumerate(obj.signal_items):
                sub = box2.box()
                sub.alert = not it.enabled
                header = sub.row(align=True)
                header.prop(it, "enabled", text="")
                header.prop(it, "name", text="")
                header.operator("vjlooper.remove_signal", icon='X', text="").index = i
                sub.template_icon_view(it, "signal_type", scale=5.0)
                sub.prop(it, "channel", expand=True)
                row = sub.row()
                c1, c2 = row.column(), row.column()
                c1.prop(it, "amplitude")
                rowf = c1.row(align=True)
                rowf.prop(it, "frequency")
                perfect = abs(round(it.frequency * it.duration) - it.frequency * it.duration) < 1e-4
                rowf.alert = not perfect
                rowf.label(icon='CHECKMARK' if perfect else 'ERROR')
                c2.prop(it, "phase_offset")
                c2.prop(it, "duration")
                r = sub.row()
                c3, c4 = r.column(), r.column()
                c3.prop(it, "amplitude_min", text="Amp Min")
                c3.prop(it, "frequency_min", text="Freq Min")
                c4.prop(it, "amplitude_max", text="Amp Max")
                c4.prop(it, "frequency_max", text="Freq Max")
                sub.operator("vjlooper.randomize_signal", text="Randomize").index = i
                sub.prop(it, "offset")
                sub.prop(it, "loop_count")
                sub.prop(it, "blend_frames")
                sub.prop(it, "use_clamp")
                if it.use_clamp:
                    r = sub.row(align=True)
                    r.prop(it, "clamp_min")
                    r.prop(it, "clamp_max")

    def draw_presets_ui(self, L, ctx):
        sc = ctx.scene
        col = L.column()
        col.use_property_split = True
        col.operator("vjlooper.add_preset", text="Save Preset")
        col.operator("vjlooper.load_preset", text="Load Preset")
        col.operator("vjlooper.export_presets", text="Export Presets")
        col.operator("vjlooper.import_presets", text="Import Presets")
        col.prop(sc, "preset_category_filter", text="Category Filter")
        rown = col.row(align=True)
        rown.prop(sc, "category_rename_from", text="Old")
        rown.prop(sc, "category_rename_to", text="New")
        rown.operator("vjlooper.rename_category", text="Rename")
        if getattr(sc, "signal_presets", None) and len(sc.signal_presets) > 0:
            col.template_list("VJLOOPER_UL_presets", "", sc, "signal_presets", sc, "signal_preset_index")
            col.prop(sc.signal_presets[sc.signal_preset_index], "category", text="Category")
            row = col.row(align=True)
            row.prop(sc, "multi_offset_frames", text="Step")
            row.operator("vjlooper.apply_preset_multi", text="Apply to Selection")
            row2 = col.row(align=True)
            row2.prop(sc, "offset_mode", text="Mode")
            row2.operator("vjlooper.apply_preset_offset", text="Apply with Offset")
            col.prop(sc, "offset_radial_factor")
            col.prop(sc, "offset_bpm")
            col.prop(sc, "preset_mirror", text="Mirror")
            col.prop(sc, "brush_offset_step", text="Brush Step")
            col.operator("vjlooper.toggle_preset_brush", text="Toggle Preset Brush", depress=sc.preset_brush_active)

    def draw_bake_ui(self, L):
        L.separator()
        col = L.column()
        col.use_property_split = True
        col.operator("vjlooper.bake_settings", icon='REC', text="Bake Settings")
        col.operator("vjlooper.bake_animation", text="Bake Animation")

    def draw_materials_ui(self, L, ctx):
        sc = ctx.scene
        box = L.box()
        box.label(text="Materials")
        if sc.vj_only_used:
            used = signals.get_materials_list(sc)
            sc.vj_filtered_materials.clear()
            for m in used:
                item = sc.vj_filtered_materials.add()
                item.material = m
            data_src, prop = sc, "vj_filtered_materials"
        else:
            data_src, prop = bpy.data, "materials"
        box.template_list("VJLOOPER_UL_materials", "", data_src, prop, sc, "vj_material_index", rows=4)
        row = box.row(align=True)
        row.operator("vjlooper.apply_mat_sel", text="Apply to Selection")
        row.operator("vjlooper.apply_mat_coll", text="Apply to Collection")
        rowc = box.row()
        rowc.prop(sc, "vj_target_collection", text="", icon='OUTLINER_COLLECTION')
        box.prop(sc, "vj_only_used", text="Show only used")
        tunnelfx.draw_ui(box, ctx)

    def draw_tools_ui(self, L, ctx):
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
        L.prop(ctx.scene, "loop_lock", text="Loop Lock")
        L.operator("vjlooper.hot_reload", icon='FILE_REFRESH', text="Reload Addon")


class VJLOOPER_PT_tools(Panel):
    bl_label = "Tools"
    bl_idname = "VJLOOPER_PT_tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Animator"

    def draw(self, ctx):
        VJLOOPER_PT_panel.draw_tools_ui(self, self.layout, ctx)


class VJLOOPER_PT_materials(Panel):
    bl_label = "Materials"
    bl_idname = "VJLOOPER_PT_materials"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Animator"

    def draw(self, ctx):
        VJLOOPER_PT_panel.draw_materials_ui(self, self.layout, ctx)


addon_keymaps = []


def register_keymaps():
    prefs = signals._prefs()
    if not prefs or not prefs.use_keymaps:
        return
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        kmi = km.keymap_items.new('vjlooper.load_preset', 'P', 'PRESS', ctrl=True, shift=True)
        addon_keymaps.append((km, kmi))
        kmi = km.keymap_items.new('vjlooper.toggle_preset_brush', 'L', 'PRESS', shift=True)
        addon_keymaps.append((km, kmi))


def unregister_keymaps():
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        for km, kmi in addon_keymaps:
            km.keymap_items.remove(kmi)
    addon_keymaps.clear()


property_classes = (
    SignalItem,
    SignalPreset,
    VJMaterialItem,
)

classes = (
    VJLOOPER_Preferences,
    VJLOOPER_UL_presets,
    VJLOOPER_UL_materials,
    VJLOOPER_PT_panel,
    VJLOOPER_PT_tools,
    VJLOOPER_PT_materials,
)


def register_props():
    """Register custom properties for Object and Scene types."""
    for c in property_classes:
        # remove any previously registered class with the same name
        while hasattr(bpy.types, c.__name__):
            try:
                bpy.utils.unregister_class(getattr(bpy.types, c.__name__))
            except Exception:
                break
        bpy.utils.register_class(c)

    if hasattr(bpy.types.Object, "signal_items"):
        del bpy.types.Object.signal_items
    bpy.types.Object.signal_items = CollectionProperty(type=SignalItem)
    if hasattr(bpy.types.Object, "global_amp_scale"):
        del bpy.types.Object.global_amp_scale
    bpy.types.Object.global_amp_scale = FloatProperty(default=1.0, description="Amplitude multiplier")
    if hasattr(bpy.types.Object, "global_freq_scale"):
        del bpy.types.Object.global_freq_scale
    bpy.types.Object.global_freq_scale = FloatProperty(default=1.0, description="Frequency multiplier")
    if hasattr(bpy.types.Object, "global_dur_scale"):
        del bpy.types.Object.global_dur_scale
    bpy.types.Object.global_dur_scale = FloatProperty(default=1.0, description="Duration multiplier")

    sc = bpy.types.Scene
    if hasattr(sc, "signal_new_channel"):
        delattr(sc, "signal_new_channel")
    sc.signal_new_channel = EnumProperty(items=signals.CHANNEL_ITEMS, default='LOC_X')
    if hasattr(sc, "signal_new_type"):
        delattr(sc, "signal_new_type")
    sc.signal_new_type = EnumProperty(items=[
        ('SINE', 'Sine', ''), ('COSINE', 'Cosine', ''), ('SQUARE', 'Square', ''),
        ('TRIANGLE', 'Triangle', ''), ('SAWTOOTH', 'Sawtooth', ''), ('NOISE', 'Noise', '')
    ], default='SINE')
    if hasattr(sc, "signal_new_amplitude"):
        delattr(sc, "signal_new_amplitude")
    sc.signal_new_amplitude = FloatProperty(default=1.0, description="Default amplitude")
    if hasattr(sc, "signal_new_frequency"):
        delattr(sc, "signal_new_frequency")
    sc.signal_new_frequency = FloatProperty(
        default=1.0,
        description="Default frequency",
        update=signals.update_new_frequency,
    )
    if hasattr(sc, "signal_new_phase"):
        delattr(sc, "signal_new_phase")
    sc.signal_new_phase = FloatProperty(default=0.0, description="Default phase")
    if hasattr(sc, "signal_new_duration"):
        delattr(sc, "signal_new_duration")
    sc.signal_new_duration = IntProperty(
        default=24,
        description="Default duration",
        update=signals.update_new_duration,
    )
    if hasattr(sc, "signal_new_offset"):
        delattr(sc, "signal_new_offset")
    sc.signal_new_offset = IntProperty(default=0, description="Frame offset when creating")
    if hasattr(sc, "signal_new_loops"):
        delattr(sc, "signal_new_loops")
    sc.signal_new_loops = IntProperty(default=0, description="Loop count")
    if hasattr(sc, "signal_new_clamp"):
        delattr(sc, "signal_new_clamp")
    sc.signal_new_clamp = BoolProperty(default=False, description="Use clamp")
    if hasattr(sc, "signal_new_clamp_min"):
        delattr(sc, "signal_new_clamp_min")
    sc.signal_new_clamp_min = FloatProperty(default=-1.0, description="Clamp min")
    if hasattr(sc, "signal_new_clamp_max"):
        delattr(sc, "signal_new_clamp_max")
    sc.signal_new_clamp_max = FloatProperty(default=1.0, description="Clamp max")
    if hasattr(sc, "signal_new_noise"):
        delattr(sc, "signal_new_noise")
    sc.signal_new_noise = IntProperty(default=0, description="Noise seed")
    if hasattr(sc, "signal_new_smoothing"):
        delattr(sc, "signal_new_smoothing")
    sc.signal_new_smoothing = FloatProperty(default=0.0, description="Smoothing")

    if hasattr(sc, "signal_presets"):
        delattr(sc, "signal_presets")
    sc.signal_presets = CollectionProperty(type=SignalPreset)
    if hasattr(sc, "signal_preset_index"):
        delattr(sc, "signal_preset_index")
    sc.signal_preset_index = IntProperty(default=0)
    if hasattr(sc, "preset_category_filter"):
        delattr(sc, "preset_category_filter")
    sc.preset_category_filter = StringProperty(default="", description="Filter presets by category")
    if hasattr(sc, "category_rename_from"):
        delattr(sc, "category_rename_from")
    sc.category_rename_from = StringProperty(default="")
    if hasattr(sc, "category_rename_to"):
        delattr(sc, "category_rename_to")
    sc.category_rename_to = StringProperty(default="")
    if hasattr(sc, "ui_show_create"):
        delattr(sc, "ui_show_create")
    sc.ui_show_create = BoolProperty(default=True)
    if hasattr(sc, "ui_show_items"):
        delattr(sc, "ui_show_items")
    sc.ui_show_items = BoolProperty(default=True)
    if hasattr(sc, "ui_show_presets"):
        delattr(sc, "ui_show_presets")
    sc.ui_show_presets = BoolProperty(default=True)
    if hasattr(sc, "ui_show_bake"):
        delattr(sc, "ui_show_bake")
    sc.ui_show_bake = BoolProperty(default=True)
    if hasattr(sc, "ui_show_materials"):
        delattr(sc, "ui_show_materials")
    sc.ui_show_materials = BoolProperty(default=True)
    if hasattr(sc, "ui_show_misc"):
        delattr(sc, "ui_show_misc")
    sc.ui_show_misc = BoolProperty(default=True)

    if hasattr(sc, "multi_offset_frames"):
        delattr(sc, "multi_offset_frames")
    sc.multi_offset_frames = IntProperty(default=0, description="Frame offset between objects")
    if hasattr(sc, "offset_mode"):
        delattr(sc, "offset_mode")
    sc.offset_mode = EnumProperty(items=[
        ('LINEAR', 'Linear', ''),
        ('RADIAL', 'Radial', ''),
        ('BPM', 'Beat', '')
    ], default='LINEAR')
    if hasattr(sc, "offset_radial_factor"):
        delattr(sc, "offset_radial_factor")
    sc.offset_radial_factor = FloatProperty(default=1.0, description="Frames per unit for radial offset")
    if hasattr(sc, "offset_bpm"):
        delattr(sc, "offset_bpm")
    sc.offset_bpm = IntProperty(default=120, description="BPM for beat grid")
    if hasattr(sc, "preset_mirror"):
        delattr(sc, "preset_mirror")
    sc.preset_mirror = BoolProperty(default=False, description="Mirror amplitude when loading")
    if hasattr(sc, "loop_lock"):
        delattr(sc, "loop_lock")
    sc.loop_lock = BoolProperty(default=False, description="Quantize signals for perfect loops")
    if hasattr(sc, "preset_brush_active"):
        delattr(sc, "preset_brush_active")
    sc.preset_brush_active = BoolProperty(default=False, description="Enable preset brush mode")
    if hasattr(sc, "brush_offset_step"):
        delattr(sc, "brush_offset_step")
    sc.brush_offset_step = IntProperty(default=0, description="Frame step when using preset brush")

    if hasattr(sc, "bake_start"):
        delattr(sc, "bake_start")
    sc.bake_start = IntProperty(default=1)
    if hasattr(sc, "bake_end"):
        delattr(sc, "bake_end")
    sc.bake_end = IntProperty(default=250)
    if hasattr(sc, "bake_channel"):
        delattr(sc, "bake_channel")
    sc.bake_channel = EnumProperty(items=signals.CHANNEL_BAKE, default='LOC')

    if hasattr(sc, "vj_material_index"):
        delattr(sc, "vj_material_index")
    sc.vj_material_index = IntProperty(default=0)
    if hasattr(sc, "vj_target_collection"):
        delattr(sc, "vj_target_collection")
    sc.vj_target_collection = PointerProperty(type=bpy.types.Collection, name="Target Collection")
    if hasattr(sc, "vj_only_used"):
        delattr(sc, "vj_only_used")
    sc.vj_only_used = BoolProperty(name="Only used", default=False)
    if hasattr(sc, "vj_filtered_materials"):
        delattr(sc, "vj_filtered_materials")
    sc.vj_filtered_materials = CollectionProperty(type=VJMaterialItem)


def unregister_props():
    """Remove custom properties from Blender data-blocks."""
    if hasattr(bpy.types.Object, "signal_items"):
        del bpy.types.Object.signal_items
    if hasattr(bpy.types.Object, "global_amp_scale"):
        del bpy.types.Object.global_amp_scale
    if hasattr(bpy.types.Object, "global_freq_scale"):
        del bpy.types.Object.global_freq_scale
    if hasattr(bpy.types.Object, "global_dur_scale"):
        del bpy.types.Object.global_dur_scale

    for prop in [
        "signal_new_channel", "signal_new_type", "signal_new_amplitude",
        "signal_new_frequency", "signal_new_phase", "signal_new_duration",
        "signal_new_offset", "signal_new_loops", "signal_new_clamp",
        "signal_new_clamp_min", "signal_new_clamp_max", "signal_new_noise",
        "signal_new_smoothing", "signal_presets", "signal_preset_index",
        "preset_category_filter", "category_rename_from", "category_rename_to",
        "ui_show_create", "ui_show_items", "ui_show_presets", "ui_show_bake", "ui_show_materials", "ui_show_misc",
        "multi_offset_frames", "offset_mode", "offset_radial_factor", "offset_bpm",
        "preset_mirror", "preset_brush_active", "brush_offset_step",
        "loop_lock",
        "bake_start", "bake_end", "bake_channel",
        "vj_material_index", "vj_target_collection", "vj_only_used", "vj_filtered_materials",
    ]:
        if hasattr(bpy.types.Scene, prop):
            delattr(bpy.types.Scene, prop)
    for c in reversed(property_classes):
        # remove any lingering class definitions with this name
        while hasattr(bpy.types, c.__name__):
            try:
                bpy.utils.unregister_class(getattr(bpy.types, c.__name__))
            except Exception:
                break


def register():
    for c in classes:
        bpy.utils.register_class(c)
    register_keymaps()
    signals.load_presets_from_disk()


def unregister():
    signals.save_presets_to_disk()
    unregister_keymaps()

    for c in reversed(classes):
        bpy.utils.unregister_class(c)
