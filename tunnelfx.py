"""Simple Geometry Nodes tunnel effect loader."""

import bpy
from pathlib import Path

_GROUP = 'TunnelFX_CYL'
_PATH = Path(__file__).parent / 'assets' / 'gn' / 'TunnelFX_CYL.blend'


def load_group():
    if not hasattr(bpy.data, 'node_groups'):
        return None
    if _GROUP in bpy.data.node_groups:
        return bpy.data.node_groups[_GROUP]
    if _PATH.exists():
        with bpy.data.libraries.load(str(_PATH), link=False) as (data_from, data_to):
            if _GROUP in data_from.node_groups:
                data_to.node_groups.append(_GROUP)
    return bpy.data.node_groups.get(_GROUP)


def update_scroll(self, ctx):
    sc = ctx.scene
    if getattr(sc, 'loop_lock', False) and sc.frame_end > 0:
        dur = sc.frame_end
        q = round(self.tfx_scroll_speed * dur) / dur
        self['tfx_scroll_speed'] = q


class VJLOOPER_OT_add_tunnel(bpy.types.Operator):
    bl_idname = 'vjlooper.add_tunnel'
    bl_label = 'Add Tunnel'

    preset: bpy.props.EnumProperty(items=[('CYL', 'Cylinder', '')], default='CYL')

    def execute(self, ctx):
        group = load_group()
        obj = ctx.object
        if not obj or not group:
            return {'CANCELLED'}
        mod = obj.modifiers.new('TunnelFX', 'NODES')
        mod.node_group = group
        obj.tfx_radius = 1.0
        obj.tfx_length = 5.0
        obj.tfx_scroll_speed = 0.0
        it = obj.signal_items.add()
        it.name = 'GN Scroll'
        it.channel = 'GN_SCROLL'
        return {'FINISHED'}


def draw_ui(layout, ctx):
    box = layout.box()
    box.label(text='TunnelFX')
    box.operator('vjlooper.add_tunnel')
    obj = ctx.object
    if obj and hasattr(obj, 'tfx_radius'):
        box.prop(obj, 'tfx_radius')
        box.prop(obj, 'tfx_length')
        box.prop(obj, 'tfx_scroll_speed')


def register():
    bpy.types.Object.tfx_radius = bpy.props.FloatProperty(default=1.0)
    bpy.types.Object.tfx_length = bpy.props.FloatProperty(default=5.0)
    bpy.types.Object.tfx_scroll_speed = bpy.props.FloatProperty(default=0.0, update=update_scroll)
    bpy.utils.register_class(VJLOOPER_OT_add_tunnel)


def unregister():
    bpy.utils.unregister_class(VJLOOPER_OT_add_tunnel)
    if hasattr(bpy.types.Object, 'tfx_radius'):
        del bpy.types.Object.tfx_radius
    if hasattr(bpy.types.Object, 'tfx_length'):
        del bpy.types.Object.tfx_length
    if hasattr(bpy.types.Object, 'tfx_scroll_speed'):
        del bpy.types.Object.tfx_scroll_speed