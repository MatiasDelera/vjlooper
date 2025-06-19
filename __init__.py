bl_info = {
    "name": "VJ Looper",
    "author": "Matias Delera",
    "version": (1, 0),
    "blender": (2, 80, 0),
    "location": "View3D > Sidebar > VJ Looper",
    "description": "Addon base para VJ Looper",
    "category": "3D View"
}

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    StringProperty,
)


class SignalItem(bpy.types.PropertyGroup):
    """Placeholder signal item properties"""

    name: StringProperty(name="Name")
    enabled: BoolProperty(name="Enabled", default=True)
    channel: StringProperty(name="Channel")
    signal_type: EnumProperty(
        name="Type",
        items=[
            ("SINE", "Sine", "Sine wave"),
            ("SAW", "Saw", "Saw wave"),
            ("SQUARE", "Square", "Square wave"),
        ],
        default="SINE",
    )
    amplitude: FloatProperty(name="Amplitude", default=1.0)
    frequency: FloatProperty(name="Frequency", default=1.0)
    phase_offset: FloatProperty(name="Phase", default=0.0)
    time_offset: FloatProperty(name="Time Offset", default=0.0)
    duration: FloatProperty(name="Duration", default=1.0)
    offset: FloatProperty(name="Offset", default=0.0)
    loop_count: IntProperty(name="Loops", default=1)
    use_clamp: BoolProperty(name="Clamp", default=False)
    clamp_min: FloatProperty(name="Min", default=0.0)
    clamp_max: FloatProperty(name="Max", default=1.0)
    duty_cycle: FloatProperty(name="Duty", default=0.5)
    noise_seed: IntProperty(name="Noise", default=0)
    smoothing: FloatProperty(name="Smoothing", default=0.0)


class SignalPreset(bpy.types.PropertyGroup):
    name: StringProperty(name="Name")


class SignalGroup(bpy.types.PropertyGroup):
    name: StringProperty(name="Name")

# Activar depuración remota
try:
    import debugpy
    debugpy.listen(("localhost", 5678))
    print("✅ Esperando depurador VSCode en puerto 5678...")
    # debugpy.wait_for_client()  # Descomentá si querés detener Blender hasta que VSCode se conecte
except Exception as e:
    print("⚠️ No se pudo iniciar debugpy:", e)

# Importar módulos del addon
from . import panel


classes = (
    SignalItem,
    SignalPreset,
    SignalGroup,
)


def register_properties():
    bpy.types.Object.signal_items = CollectionProperty(type=SignalItem)

    bpy.types.Scene.signal_new_channel = StringProperty(name="Channel")
    bpy.types.Scene.signal_new_type = StringProperty(name="Type")
    bpy.types.Scene.signal_new_amplitude = FloatProperty(name="Amp", default=1.0)
    bpy.types.Scene.signal_new_frequency = FloatProperty(name="Freq", default=1.0)
    bpy.types.Scene.signal_new_phase = FloatProperty(name="Phase", default=0.0)
    bpy.types.Scene.signal_new_time_offset = FloatProperty(name="T-Off", default=0.0)
    bpy.types.Scene.signal_new_duration = FloatProperty(name="Duration", default=1.0)
    bpy.types.Scene.signal_new_offset = FloatProperty(name="Offset", default=0.0)
    bpy.types.Scene.signal_new_loops = IntProperty(name="Loops", default=1)
    bpy.types.Scene.signal_new_clamp = BoolProperty(name="Clamp", default=False)
    bpy.types.Scene.signal_new_clamp_min = FloatProperty(name="Min", default=0.0)
    bpy.types.Scene.signal_new_clamp_max = FloatProperty(name="Max", default=1.0)
    bpy.types.Scene.signal_new_duty = FloatProperty(name="Duty", default=0.5)
    bpy.types.Scene.signal_new_noise = IntProperty(name="Noise Seed", default=0)
    bpy.types.Scene.signal_new_smoothing = FloatProperty(name="Smoothing", default=0.0)

    bpy.types.Scene.signal_presets = CollectionProperty(type=SignalPreset)
    bpy.types.Scene.signal_preset_index = IntProperty(name="Preset Index")

    bpy.types.Scene.new_group_name = StringProperty(name="New Group")
    bpy.types.Scene.signal_groups = CollectionProperty(type=SignalGroup)
    bpy.types.Scene.signal_group_index = IntProperty(name="Group Index")


def unregister_properties():
    del bpy.types.Object.signal_items

    del bpy.types.Scene.signal_new_channel
    del bpy.types.Scene.signal_new_type
    del bpy.types.Scene.signal_new_amplitude
    del bpy.types.Scene.signal_new_frequency
    del bpy.types.Scene.signal_new_phase
    del bpy.types.Scene.signal_new_time_offset
    del bpy.types.Scene.signal_new_duration
    del bpy.types.Scene.signal_new_offset
    del bpy.types.Scene.signal_new_loops
    del bpy.types.Scene.signal_new_clamp
    del bpy.types.Scene.signal_new_clamp_min
    del bpy.types.Scene.signal_new_clamp_max
    del bpy.types.Scene.signal_new_duty
    del bpy.types.Scene.signal_new_noise
    del bpy.types.Scene.signal_new_smoothing

    del bpy.types.Scene.signal_presets
    del bpy.types.Scene.signal_preset_index

    del bpy.types.Scene.new_group_name
    del bpy.types.Scene.signal_groups
    del bpy.types.Scene.signal_group_index


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    register_properties()
    panel.register()


def unregister():
    panel.unregister()
    unregister_properties()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
