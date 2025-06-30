"""Utilities and UI for animating Blender text objects."""

import bpy
import math
import random
from mathutils import Vector
try:
    from mathutils.kdtree import KDTree  # type: ignore
except Exception:  # pragma: no cover - absent when testing
    class KDTree:  # minimal stub for tests
        def __init__(self, size):
            pass

        def insert(self, co, index):
            pass

        def balance(self):
            pass

        def find_range(self, co, dist):
            return []

import json


# -----------------------------------------------------------------------------
# Utility functions
# -----------------------------------------------------------------------------

def geometry_center(obj):
    """Return the geometric center of obj in world space."""
    verts = [obj.matrix_world @ v.co for v in obj.data.vertices]
    return sum(verts, Vector()) / len(verts) if verts else obj.location


def set_origin_to_center(obj):
    """Place the origin of obj at its geometry center."""
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')


def animate_ctrl(ctrl, start, duration, rot_z, scale_start, direction_factor=1):
    """Animate ctrl with a rotation around Z and scaling."""
    end = start + duration
    o_s = ctrl.scale.copy()
    o_r = ctrl.rotation_euler.copy()

    ctrl.scale = (scale_start,) * 3
    ctrl.rotation_euler.z = o_r.z + math.radians(rot_z * direction_factor)
    ctrl.keyframe_insert("scale", frame=start)
    ctrl.keyframe_insert("rotation_euler", frame=start)

    ctrl.scale = o_s
    ctrl.rotation_euler = o_r
    ctrl.keyframe_insert("scale", frame=end)
    ctrl.keyframe_insert("rotation_euler", frame=end)


def safe_parent_with_transform(child, parent):
    """Parent child to parent preserving world transforms."""
    world_matrix = child.matrix_world.copy()
    child.parent = parent
    if parent:
        child.matrix_parent_inverse = parent.matrix_world.inverted()
    child.matrix_world = world_matrix


# -----------------------------------------------------------------------------
# Property definitions
# -----------------------------------------------------------------------------

class LetterAnimProperties(bpy.types.PropertyGroup):
    start_frame: bpy.props.IntProperty(name="Start Frame", default=1, min=0)
    duration: bpy.props.IntProperty(name="Duration", default=50, min=1)
    overlap: bpy.props.IntProperty(name="Overlap", default=5, min=0)
    rot_z: bpy.props.FloatProperty(name="Rotate Z", default=360.0)
    scale_start: bpy.props.FloatProperty(name="Start Scale", default=0.0, min=0.0, max=2.0)
    direction: bpy.props.EnumProperty(
        name="Direction",
        items=[
            ('FORWARD', "First → Last", "Animate left to right"),
            ('REVERSE', "Last → First", "Animate right to left"),
            ('RANDOM', "Random", "Random order"),
        ],
        default='FORWARD',
    )
    grouping_tolerance: bpy.props.FloatProperty(name="Grouping Tolerance", default=0.5, min=0.1, max=2.0)


class TextAnimPreset(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(default="Preset")
    data: bpy.props.StringProperty(default="")


# -----------------------------------------------------------------------------
# Letter utilities
# -----------------------------------------------------------------------------

def separate_and_group(txt, tolerance=0.5):
    """Separate text object into individual letters."""

    original_matrix = txt.matrix_world.copy()
    original_name = txt.name

    bpy.ops.object.select_all(action='DESELECT')
    txt.select_set(True)
    bpy.context.view_layer.objects.active = txt
    bpy.ops.object.duplicate()
    backup = bpy.context.active_object
    backup.name = original_name + "_original"
    backup.hide_viewport = True
    backup.hide_render = True

    bpy.ops.object.select_all(action='DESELECT')
    txt.select_set(True)
    bpy.context.view_layer.objects.active = txt

    bpy.ops.object.convert(target='MESH', keep_original=False)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.separate(type='LOOSE')
    bpy.ops.object.mode_set(mode='OBJECT')

    pieces = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']
    if not pieces:
        return [], original_matrix

    centers = [geometry_center(obj) for obj in pieces]
    tree = KDTree(len(centers))
    for i, center in enumerate(centers):
        tree.insert(center, i)
    tree.balance()

    avg_size = sum(obj.dimensions.length for obj in pieces) / len(pieces)
    grouping_distance = avg_size * tolerance

    visited = set()
    letters = []
    for i, obj in enumerate(pieces):
        if i in visited:
            continue
        group = [obj]
        visited.add(i)
        nearby = tree.find_range(centers[i], grouping_distance)
        for (_, idx, _) in nearby:
            if idx not in visited and idx != i:
                group.append(pieces[idx])
                visited.add(idx)
        if len(group) > 1:
            bpy.ops.object.select_all(action='DESELECT')
            for part in group:
                part.select_set(True)
            bpy.context.view_layer.objects.active = group[0]
            bpy.ops.object.join()
            letters.append(bpy.context.active_object)
        else:
            letters.append(obj)

    for letter in letters:
        set_origin_to_center(letter)

    return letters, original_matrix


# -----------------------------------------------------------------------------
# Operators
# -----------------------------------------------------------------------------

class OBJECT_OT_separate_letters(bpy.types.Operator):
    bl_idname = "type_animator.separate_letters"
    bl_label = "Separate Letters"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        txt = context.active_object
        if not txt or txt.type != 'FONT':
            self.report({'ERROR'}, "Select a text object")
            return {'CANCELLED'}
        props = context.scene.letter_anim_props
        letters, original_matrix = separate_and_group(txt, props.grouping_tolerance)
        if not letters:
            self.report({'ERROR'}, "Could not separate text")
            return {'CANCELLED'}

        original_name = txt.name
        controllers = []
        for i, letter in enumerate(letters):
            ctrl = bpy.data.objects.new(f"CTRL_{original_name}_Letter_{i+1:02d}", None)
            context.collection.objects.link(ctrl)
            ctrl.empty_display_type = 'PLAIN_AXES'
            ctrl.empty_display_size = 0.5
            ctrl.matrix_world = letter.matrix_world.copy()
            safe_parent_with_transform(letter, ctrl)
            controllers.append(ctrl)

        main_ctrl = bpy.data.objects.new(f"CTRL_{original_name}_Main", None)
        context.collection.objects.link(main_ctrl)
        main_ctrl.empty_display_type = 'CUBE'
        main_ctrl.empty_display_size = 1.0
        main_ctrl.matrix_world = original_matrix

        for ctrl in controllers:
            safe_parent_with_transform(ctrl, main_ctrl)

        bpy.ops.object.select_all(action='DESELECT')
        main_ctrl.select_set(True)
        context.view_layer.objects.active = main_ctrl
        self.report({'INFO'}, f"Separated into {len(letters)} letters")
        return {'FINISHED'}


class OBJECT_OT_animate_letters(bpy.types.Operator):
    bl_idname = "type_animator.animate_letters"
    bl_label = "Separate and Animate"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.letter_anim_props
        txt = context.active_object
        if not txt or txt.type != 'FONT':
            self.report({'ERROR'}, "Select a text object")
            return {'CANCELLED'}

        letters, original_matrix = separate_and_group(txt, props.grouping_tolerance)
        if not letters:
            self.report({'ERROR'}, "Could not separate text")
            return {'CANCELLED'}

        original_name = txt.name
        controllers = []
        for i, letter in enumerate(letters):
            ctrl = bpy.data.objects.new(f"CTRL_{original_name}_Letter_{i+1:02d}", None)
            context.collection.objects.link(ctrl)
            ctrl.empty_display_type = 'PLAIN_AXES'
            ctrl.empty_display_size = 0.5
            ctrl.matrix_world = letter.matrix_world.copy()
            safe_parent_with_transform(letter, ctrl)
            controllers.append(ctrl)

        if props.direction == 'FORWARD':
            anim_order = list(range(len(controllers)))
        elif props.direction == 'REVERSE':
            anim_order = list(range(len(controllers) - 1, -1, -1))
        else:
            anim_order = list(range(len(controllers)))
            random.shuffle(anim_order)

        for anim_index, ctrl_index in enumerate(anim_order):
            ctrl = controllers[ctrl_index]
            start = props.start_frame + anim_index * props.overlap
            direction_factor = 1 if (ctrl_index % 2 == 0) else -1
            animate_ctrl(ctrl, start, props.duration, props.rot_z, props.scale_start, direction_factor)

        main_ctrl = bpy.data.objects.new(f"CTRL_{original_name}_Main", None)
        context.collection.objects.link(main_ctrl)
        main_ctrl.empty_display_type = 'CUBE'
        main_ctrl.empty_display_size = 1.0
        main_ctrl.matrix_world = original_matrix

        for ctrl in controllers:
            safe_parent_with_transform(ctrl, main_ctrl)

        bpy.ops.object.select_all(action='DESELECT')
        main_ctrl.select_set(True)
        context.view_layer.objects.active = main_ctrl

        total_frames = props.start_frame + len(controllers) * props.overlap + props.duration
        context.scene.frame_end = max(context.scene.frame_end, total_frames)

        self.report({'INFO'}, f"Animated {len(letters)} letters")
        return {'FINISHED'}


class TYPE_ANIMATOR_OT_save_preset(bpy.types.Operator):
    bl_idname = "type_animator.save_preset"
    bl_label = "Save Preset"

    name: bpy.props.StringProperty(default="Preset")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        props = context.scene.letter_anim_props
        data = {p.identifier: getattr(props, p.identifier) for p in props.bl_rna.properties if not p.is_readonly}
        pr = context.scene.text_anim_presets.add()
        pr.name = self.name
        pr.data = json.dumps(data)
        context.scene.text_anim_preset_index = len(context.scene.text_anim_presets) - 1
        return {'FINISHED'}


class TYPE_ANIMATOR_OT_load_preset(bpy.types.Operator):
    bl_idname = "type_animator.load_preset"
    bl_label = "Load Preset"

    def execute(self, context):
        sc = context.scene
        idx = sc.text_anim_preset_index
        if idx >= len(sc.text_anim_presets):
            return {'CANCELLED'}
        data = json.loads(sc.text_anim_presets[idx].data)
        props = sc.letter_anim_props
        for k, v in data.items():
            if hasattr(props, k):
                setattr(props, k, v)
        return {'FINISHED'}


class TYPE_ANIMATOR_OT_remove_preset(bpy.types.Operator):
    bl_idname = "type_animator.remove_preset"
    bl_label = "Remove Preset"

    def execute(self, context):
        sc = context.scene
        idx = sc.text_anim_preset_index
        if idx < len(sc.text_anim_presets):
            sc.text_anim_presets.remove(idx)
            sc.text_anim_preset_index = min(idx, len(sc.text_anim_presets) - 1)
        return {'FINISHED'}


class TYPE_ANIMATOR_UL_presets(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.label(text=item.name, icon='PRESET')


# -----------------------------------------------------------------------------
# Panel
# -----------------------------------------------------------------------------

class VIEW3D_PT_type_animator(bpy.types.Panel):
    bl_label = "TypeAnimator"
    bl_idname = "VIEW3D_PT_type_animator"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Animator'

    def draw(self, context):
        layout = self.layout
        props = context.scene.letter_anim_props

        obj = context.active_object
        box = layout.box()
        if obj and obj.type == 'FONT':
            box.label(text=f"Text: {obj.name}", icon='FONT_DATA')
        else:
            box.label(text="Select a text object", icon='ERROR')

        layout.separator()
        col = layout.column(align=True)
        col.operator("type_animator.separate_letters", text="Separate", icon='MESH_DATA')
        col.operator("type_animator.animate_letters", text="Separate & Animate", icon='PLAY')
        layout.separator()

        box = layout.box()
        box.label(text="Animation Settings", icon='SETTINGS')
        col = box.column()
        col.prop(props, "start_frame")
        col.prop(props, "duration")
        col.prop(props, "overlap")
        col.prop(props, "rot_z")
        col.prop(props, "scale_start")
        col.prop(props, "direction")
        col.prop(props, "grouping_tolerance")

        layout.separator()
        box = layout.box()
        box.label(text="Presets")
        row = box.row(align=True)
        row.operator("type_animator.save_preset", icon='PLUS', text="")
        row.operator("type_animator.remove_preset", icon='TRASH', text="")
        box.operator("type_animator.load_preset", text="Load Preset")
        if context.scene.text_anim_presets:
            box.template_list("TYPE_ANIMATOR_UL_presets", "", context.scene, "text_anim_presets", context.scene, "text_anim_preset_index")


# -----------------------------------------------------------------------------
# Registration helpers
# -----------------------------------------------------------------------------

classes = (
    LetterAnimProperties,
    TextAnimPreset,
    OBJECT_OT_separate_letters,
    OBJECT_OT_animate_letters,
    TYPE_ANIMATOR_OT_save_preset,
    TYPE_ANIMATOR_OT_load_preset,
    TYPE_ANIMATOR_OT_remove_preset,
    TYPE_ANIMATOR_UL_presets,
    VIEW3D_PT_type_animator,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.letter_anim_props = bpy.props.PointerProperty(type=LetterAnimProperties)
    bpy.types.Scene.text_anim_presets = bpy.props.CollectionProperty(type=TextAnimPreset)
    bpy.types.Scene.text_anim_preset_index = bpy.props.IntProperty(default=0)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    if hasattr(bpy.types.Scene, 'letter_anim_props'):
        del bpy.types.Scene.letter_anim_props
    if hasattr(bpy.types.Scene, 'text_anim_presets'):
        del bpy.types.Scene.text_anim_presets
    if hasattr(bpy.types.Scene, 'text_anim_preset_index'):
        del bpy.types.Scene.text_anim_preset_index


if __name__ == "__main__":
    register()
