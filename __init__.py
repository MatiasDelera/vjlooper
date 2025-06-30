"""Addon entry point for VjLooper."""

bl_info = {
    "name": "VjLooper",
    "author": "Matias Delera",
    "version": (1, 3, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > Animator",
    "description": (
        "Advanced procedural animation with presets, bake, preview and hot-"
        "reload"
    ),
    "category": "Animation",
}

import os
if os.environ.get("VJ_TESTING"):
    import sys, types
    bpy = sys.modules.get("bpy")
    if bpy is None:
        bpy = types.ModuleType("bpy")
        bpy.app = types.SimpleNamespace(version=(3, 6, 0))
        sys.modules["bpy"] = bpy
else:
    import bpy


def _scene():
    """Return the current scene or first available scene if accessible."""
    ctx = getattr(bpy, "context", None)
    if ctx and getattr(ctx, "scene", None):
        return ctx.scene
    data = getattr(bpy, "data", None)
    if data and hasattr(data, "scenes") and data.scenes:
        return data.scenes[0]
    return None

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
        ("*", "GN Scroll"): "Desplazamiento GN",
    }
}

from . import signals, operators, ui, tunnelfx, type_animator


def register():
    """Register addon and roll back on failure."""
    steps = []
    try:
        ui.register_props()
        steps.append("props")
        sc = _scene()
        if sc and not sc.signal_presets:
            p = sc.signal_presets.add()
            p.name = "Empty"
            p.data = "[]"
        operators.register()
        steps.append("operators")
        tunnelfx.register()
        steps.append("tunnelfx")
        type_animator.register()
        steps.append("type_animator")
        ui.register()
        steps.append("ui")
        try:
            bpy.app.translations.register(__package__, translation_dict)
        except ValueError:
            bpy.app.translations.unregister(__package__)
            bpy.app.translations.register(__package__, translation_dict)
        steps.append("translations")
        signals.register()
        steps.append("signals")
    except Exception:
        if "signals" in steps:
            signals.unregister()
        if "translations" in steps:
            try:
                bpy.app.translations.unregister(__package__)
            except Exception:
                pass
        if "ui" in steps:
            ui.unregister()
        if "tunnelfx" in steps:
            tunnelfx.unregister()
        if "type_animator" in steps:
            type_animator.unregister()
        if "operators" in steps:
            operators.unregister()
        if "props" in steps:
            ui.unregister_props()
        raise


def unregister():
    signals.unregister()
    try:
        bpy.app.translations.unregister(__package__)
    except KeyError:
        pass
    ui.unregister()
    tunnelfx.unregister()
    type_animator.unregister()
    operators.unregister()
    ui.unregister_props()


if __name__ == "__main__":
    register()
