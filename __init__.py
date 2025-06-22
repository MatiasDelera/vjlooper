bl_info = {
    "name": "VjLooper",
    "author": "Tu Nombre",
    "version": (1, 3, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > VjLooper",
    "description": "Animación procedural avanzada con presets, bake, preview y hot-reload",
    "category": "Animation",
}

import bpy
from . import panel

def register():
    panel.register()

def unregister():
    panel.unregister()

if __name__ == "__main__":
    register()
