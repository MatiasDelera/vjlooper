import os
import sys
import types

os.environ["VJ_TESTING"] = "1"
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
sys.path.insert(0, ROOT)

bpy_stub = types.ModuleType('bpy')
bpy_stub.app = types.SimpleNamespace(version=(3, 6, 0))
sys.modules.setdefault('bpy', bpy_stub)
mathutils_stub = types.ModuleType('mathutils')
mathutils_stub.Vector = lambda *a, **kw: None
sys.modules.setdefault('mathutils', mathutils_stub)
bx = types.ModuleType('bpy_extras')
bx.view3d_utils = types.SimpleNamespace(location_3d_to_region_2d=lambda *a, **k: None)
sys.modules.setdefault('bpy_extras', bx)
