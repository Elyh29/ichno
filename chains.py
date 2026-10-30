import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, PointerProperty


class IchnoChain(bpy.types.PropertyGroup):
    collection: PointerProperty(name="Collection", type=bpy.types.Collection)
    view: EnumProperty(name="View", items=[("top", "Top", ""), ("front", "Front", ""), ("side", "Side", "")], default="top")
    ref: EnumProperty(name="Reference", description="Point of each object used as a station", items=[
        ("min", "Left Edge", ""), ("center", "Center", ""), ("max", "Right Edge", ""), ("origin", "Origin", "")], default="min")
    tol: FloatProperty(name="Tolerance", description="Intervals that differ by less than this are merged into “n × pitch” (model imprecision)",
                       default=1, min=0, max=10, subtype="PERCENTAGE", precision=1)
    combine: BoolProperty(name="Combine Equal Spacing", description="Equal intervals in a row written once as “n × pitch = total”; "
                          "off: every interval and every position dimensioned", default=True)
    pos: BoolProperty(name="Positions", description="Write each station's coordinate from the world origin under the chain", default=True)


class ICHNO_UL_chains(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index=0, flt_flag=0):
        row = layout.row(align=True)
        row.prop(item, "collection", text="", icon="OUTLINER_COLLECTION")
        row.prop(item, "view", text="")


class ICHNO_OT_chain_add(bpy.types.Operator):
    """Add a chain dimension"""
    bl_idname = "ichno.chain_add"
    bl_label = "Add Chain"
    bl_options = {"UNDO"}

    def execute(self, context):
        s = context.scene.ichno_settings
        s.chains.add()
        s.chain_index = len(s.chains) - 1
        return {"FINISHED"}


class ICHNO_OT_chain_remove(bpy.types.Operator):
    """Remove the active chain dimension"""
    bl_idname = "ichno.chain_remove"
    bl_label = "Remove Chain"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return len(context.scene.ichno_settings.chains) > 0

    def execute(self, context):
        s = context.scene.ichno_settings
        s.chains.remove(s.chain_index)
        s.chain_index = max(0, min(s.chain_index, len(s.chains) - 1))
        return {"FINISHED"}


def draw(layout, s):
    row = layout.row()
    row.template_list("ICHNO_UL_chains", "", s, "chains", s, "chain_index", rows=2)
    col = row.column(align=True)
    col.operator("ichno.chain_add", icon="ADD", text="")
    col.operator("ichno.chain_remove", icon="REMOVE", text="")
    if s.chains:
        c = s.chains[s.chain_index]
        layout.use_property_split = True
        layout.prop(c, "ref")
        layout.prop(c, "combine")
        row = layout.row()
        row.active = c.combine
        row.prop(c, "tol")
        layout.prop(c, "pos")


def spec(s, shown):
    out = []
    for c in s.chains:
        if c.collection:
            names = sorted({o.name for o in c.collection.all_objects} & shown)
            if len(names) >= 2:
                out.append({"view": c.view, "ref": c.ref, "tol": c.tol, "combine": c.combine, "pos": c.pos, "objects": names})
    return out


DATA = (IchnoChain,)
CLASSES = (ICHNO_UL_chains, ICHNO_OT_chain_add, ICHNO_OT_chain_remove)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
