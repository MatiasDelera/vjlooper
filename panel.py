# vjlooper/panel.py
import bpy


# ─────────────────────────────────────────────────────────────
#   Operadores utilitarios
# ─────────────────────────────────────────────────────────────
class SIGNAL_OT_reload_addon(bpy.types.Operator):
    """Recarga todos los scripts de Python (útil para desarrollo rápido)"""
    bl_idname = "signal.reload_addon"
    bl_label = "Recargar Addon"

    def execute(self, context):
        bpy.ops.script.reload()
        self.report({'INFO'}, "Scripts recargados")
        return {'FINISHED'}


class SIGNAL_OT_connect_debugpy(bpy.types.Operator):
    """Inicia o reconecta debugpy en localhost:5678"""
    bl_idname = "signal.connect_debugpy"
    bl_label = "Conectar debugpy"

    def execute(self, context):
        try:
            import debugpy
            debugpy.listen(("localhost", 5678))
            self.report({'INFO'}, "debugpy escuchando en puerto 5678")
        except Exception as e:
            self.report({'ERROR'}, f"No se pudo iniciar debugpy: {e}")
        return {'FINISHED'}


# ─────────────────────────────────────────────────────────────
#   Panel principal
# ─────────────────────────────────────────────────────────────
class OBJECT_PT_signal_panel(bpy.types.Panel):
    bl_label = "Signal Animator Pro Complete"
    bl_idname = "OBJECT_PT_signal_animator_pro"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Signal'

    @classmethod
    def poll(cls, context):
        return context.object is not None

    def draw(self, context):
        layout = self.layout
        obj = context.object
        sc = context.scene

        # Header ───────────────────────────────────────────────
        box = layout.box()
        active = sum(1 for s in obj.signal_items if s.enabled)
        box.label(text=f"{obj.name}: {active}/{len(obj.signal_items)} signals")
        box.operator("signal.debug_info", icon='INFO')

        # Add Signal ───────────────────────────────────────────
        box = layout.box()
        box.label(text="Add Signal", icon='ADD')
        col = box.column(align=True)
        col.prop(sc, "signal_new_channel", text="Channel")
        col.prop(sc, "signal_new_type", text="Type")
        col.prop(sc, "signal_new_amplitude", text="Amp")
        col.prop(sc, "signal_new_frequency", text="Freq")
        col.prop(sc, "signal_new_phase", text="Phase")
        col.prop(sc, "signal_new_time_offset", text="T-Off")
        col.prop(sc, "signal_new_duration", text="Duration")
        col.prop(sc, "signal_new_offset", text="Offset")
        col.prop(sc, "signal_new_loops", text="Loops")
        col.prop(sc, "signal_new_clamp", text="Clamp")
        if sc.signal_new_clamp:
            sub = col.row(align=True)
            sub.prop(sc, "signal_new_clamp_min", text="Min")
            sub.prop(sc, "signal_new_clamp_max", text="Max")
        col.prop(sc, "signal_new_duty", text="Duty")
        col.prop(sc, "signal_new_noise", text="Noise Seed")
        col.prop(sc, "signal_new_smoothing", text="Smoothing")
        box.operator("signal.add_item", icon='PLUS')

        # Signal List ──────────────────────────────────────────
        for i, it in enumerate(obj.signal_items):
            sb = layout.box()
            row = sb.row(align=True)
            row.prop(it, "enabled", text="")
            row.prop(it, "name", text="")
            row.label(text=f"[{it.signal_type}]")
            ops = row.row(align=True)

            op_up = ops.operator("signal.move_item", icon='TRIA_UP')
            op_up.index = i
            op_up.direction = -1

            op_down = ops.operator("signal.move_item", icon='TRIA_DOWN')
            op_down.index = i
            op_down.direction = 1

            op_del = ops.operator("signal.remove_item", icon='X')
            op_del.index = i

            if it.enabled:
                col = sb.column(align=True)
                col.prop(it, "channel")
                col.prop(it, "signal_type")
                col.prop(it, "amplitude")
                col.prop(it, "frequency")
                col.prop(it, "phase_offset")
                col.prop(it, "time_offset")
                col.prop(it, "duration")
                col.prop(it, "offset")
                col.prop(it, "loop_count")
                col.prop(it, "use_clamp")
                if it.use_clamp:
                    sub = col.row(align=True)
                    sub.prop(it, "clamp_min")
                    sub.prop(it, "clamp_max")
                col.prop(it, "duty_cycle")
                col.prop(it, "noise_seed")
                col.prop(it, "smoothing")

        # Presets ──────────────────────────────────────────────
        box = layout.box()
        box.label(text="Presets", icon='PRESET')
        row = box.row(align=True)
        row.operator("signal.save_preset", icon='FILE_TICK')
        row.operator("signal.load_preset", icon='FILE_FOLDER')
        row.operator("signal.export_presets", icon='EXPORT')
        row.operator("signal.import_presets", icon='IMPORT')
        box.template_list(
            "UI_UL_list", "signal_presets",
            sc, "signal_presets",
            sc, "signal_preset_index",
            rows=3
        )

        # Bake ────────────────────────────────────────────────
        layout.operator("signal.bake_animation", icon='REC')

        # Groups ───────────────────────────────────────────────
        box = layout.box()
        box.label(text="Groups", icon='GROUP')
        box.prop(sc, "new_group_name", text="New Group")
        box.operator("signal.group_create", icon='PLUS')
        box.template_list(
            "UI_UL_list", "signal_groups",
            sc, "signal_groups",
            sc, "signal_group_index",
            rows=3
        )
        if sc.signal_groups:
            idx = sc.signal_group_index
            row = box.row(align=True)
            row.operator("signal.group_select", icon='RESTRICT_SELECT_OFF').index = idx
            row.operator("signal.group_set_origin", icon='CURSOR')
            row.operator("signal.group_remove", icon='TRASH').index = idx

        # Utilidades de desarrollo ────────────────────────────
        layout.separator()
        row = layout.row(align=True)
        row.operator("signal.reload_addon", icon='FILE_REFRESH')
        row.operator("signal.connect_debugpy", icon='PLUGIN')


# ─────────────────────────────────────────────────────────────
#   Registro / desregistro
# ─────────────────────────────────────────────────────────────
classes = (
    OBJECT_PT_signal_panel,
    SIGNAL_OT_reload_addon,
    SIGNAL_OT_connect_debugpy,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
