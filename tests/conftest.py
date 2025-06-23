import os
import sys
import types

os.environ["VJ_TESTING"] = "1"
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
sys.path.insert(0, ROOT)

bpy_stub = types.ModuleType('bpy')
bpy_stub.app = types.SimpleNamespace(
    version=(3, 6, 0),
    translations=types.SimpleNamespace(register=lambda *a, **k: None, unregister=lambda *a, **k: None),
    handlers=types.SimpleNamespace(frame_change_pre=[], depsgraph_update_post=[]),
)
context_stub = types.SimpleNamespace(
    preferences=types.SimpleNamespace(addons={}),
    window_manager=types.SimpleNamespace(keyconfigs=types.SimpleNamespace(addon=None)),
    region=None,
    region_data=None,
    scene=None,
    view_layer=types.SimpleNamespace(objects=types.SimpleNamespace(active=None)),
    selected_objects=[],
)
bpy_stub.context = context_stub
bpy_stub.data = types.SimpleNamespace(scenes=[])
utils_stub = types.SimpleNamespace(register_class=lambda *a, **k: None, unregister_class=lambda *a, **k: None)
bpy_stub.utils = utils_stub
types_mod = types.SimpleNamespace(
    Object=type('Object', (), {}),
    Scene=type('Scene', (), {}),
    Material=type('Material', (), {}),
    Collection=type('Collection', (), {}),
    Operator=type('Operator', (), {}),
    Panel=type('Panel', (), {}),
    UIList=type('UIList', (), {}),
    AddonPreferences=type('AddonPreferences', (), {}),
    PropertyGroup=type('PropertyGroup', (), {}),
    SpaceView3D=type('SpaceView3D', (), {
        'draw_handler_add': lambda *a, **k: None,
        'draw_handler_remove': lambda *a, **k: None,
    }),
)
bpy_stub.types = types_mod
sys.modules.setdefault('bpy.types', types_mod)
props_mod = types.ModuleType('bpy.props')
for name in ['BoolProperty', 'EnumProperty', 'FloatProperty', 'FloatVectorProperty',
             'IntProperty', 'PointerProperty', 'StringProperty', 'CollectionProperty']:
    setattr(props_mod, name, lambda *a, **k: None)
bpy_stub.props = props_mod
sys.modules.setdefault('bpy', bpy_stub)
sys.modules.setdefault('bpy.props', props_mod)
mathutils_stub = types.ModuleType('mathutils')
mathutils_stub.Vector = lambda *a, **kw: None
sys.modules.setdefault('mathutils', mathutils_stub)
bx = types.ModuleType('bpy_extras')
bx.view3d_utils = types.SimpleNamespace(location_3d_to_region_2d=lambda *a, **k: None)
bx.io_utils = types.SimpleNamespace(ExportHelper=object, ImportHelper=object)
sys.modules.setdefault('bpy_extras', bx)
sys.modules.setdefault('bpy_extras.view3d_utils', bx.view3d_utils)
sys.modules.setdefault('bpy_extras.io_utils', bx.io_utils)
sys.modules.setdefault('blf', types.ModuleType('blf'))
