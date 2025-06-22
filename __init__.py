"""Addon entry point for VjLooper."""

bl_info = {
    "name": "VjLooper",
    "author": "Matias Delera",
    "version": (1, 3, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > VjLooper",
    "description": (
        "Advanced procedural animation with presets, bake, preview and hot-"
        "reload"
    ),
    "category": "Animation",
}

import os
if os.environ.get("VJ_TESTING"):
    import types
    bpy = types.SimpleNamespace(app=types.SimpleNamespace(version=(3, 6, 0)))
else:
    import bpy

if bpy.app.version < (3, 6, 0):
    bl_info["warning"] = "Limited support for Blender versions before 3.6"
else:
    bl_info["warning"] = ""

translation_dict = {
    "es_ES": {
        ("*", "Reload Addon"): "Recargar Addon",
        (
            "*",
            "Reload VjLooper without restarting Blender",
        ): "Recarga VjLooper sin reiniciar Blender",
        ("*", "VjLooper reloaded"): "VjLooper recargado",
        ("*", "Invalid preset"): "Preset invalido",
        ("*", "Create Animation"): "Crear animacion",
        ("*", "Global Scales"): "Escalas globales",
        ("*", "Animations"): "Animaciones",
        (
            "*",
            "Advanced procedural animation with presets, bake, preview and hot-"
            "reload",
        ): "Animación procedural avanzada con presets, bake, preview y hot-reload",
        ("*", "Position X"): "Posicion X",
        ("*", "Position Y"): "Posicion Y",
        ("*", "Position Z"): "Posicion Z",
        ("*", "Rotation X"): "Rotacion X",
        ("*", "Rotation Y"): "Rotacion Y",
        ("*", "Rotation Z"): "Rotacion Z",
        ("*", "Scale X"): "Escala X",
        ("*", "Scale Y"): "Escala Y",
        ("*", "Scale Z"): "Escala Z",
        ("*", "Uniform Scale"): "Escala Uniforme",
    }
}

if not os.environ.get("VJ_TESTING"):
    from . import signals, operators, ui, tunnelfx


def register():
    bpy.app.translations.register(__package__, translation_dict)
    signals.register()
    operators.register()
    tunnelfx.register()
    ui.register()


def unregister():
    ui.unregister()
    operators.unregister()
    signals.unregister()
    tunnelfx.unregister()
    bpy.app.translations.unregister(__package__)


if __name__ == "__main__":
    register()
