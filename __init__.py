bl_info = {
    "name": "VJ Looper",
    "author": Matias Delera",
    "version": (1, 0),
    "blender": (2, 80, 0),
    "location": "View3D > Sidebar > VJ Looper",
    "description": "Addon base para VJ Looper",
    "category": "3D View"
}

import bpy

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

def register():
    panel.register()

def unregister():
    panel.unregister()
