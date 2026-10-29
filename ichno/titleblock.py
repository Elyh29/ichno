import datetime

import bpy
from bpy.props import EnumProperty, StringProperty


class IchnoRevision(bpy.types.PropertyGroup):
    rev: StringProperty(name="Rev.", default="A")
    description: StringProperty(name="Description")
    date: StringProperty(name="Date")


class IchnoField(bpy.types.PropertyGroup):
    key: StringProperty(name="Field", default="Field")
    value: StringProperty(name="Value")


class IchnoAbbr(bpy.types.PropertyGroup):
    code: StringProperty(name="Abbreviation", default="ABBR")
    description: StringProperty(name="Description")


class ICHNO_UL_revisions(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index=0, flt_flag=0):
        row = layout.row(align=True)
        r = row.row(align=True)
        r.ui_units_x = 2
        r.prop(item, "rev", text="", emboss=False)
        row.prop(item, "description", text="", emboss=False)
        r = row.row(align=True)
        r.ui_units_x = 4
        r.prop(item, "date", text="", emboss=False)


class ICHNO_UL_fields(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index=0, flt_flag=0):
        row = layout.row(align=True)
        row.prop(item, "key", text="", emboss=False)
        row.prop(item, "value", text="", emboss=False)


class ICHNO_UL_legend(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index=0, flt_flag=0):
        row = layout.row(align=True)
        r = row.row(align=True)
        r.ui_units_x = 3
        r.prop(item, "code", text="", emboss=False)
        row.prop(item, "description", text="", emboss=False)


LISTS = [("revisions", "Revisions", ""), ("fields", "Custom Fields", ""), ("legend", "Legend", "")]
INDEX = {"revisions": "revision_index", "fields": "field_index", "legend": "legend_index"}


def next_rev(rev):
    if rev.isdigit():
        return str(int(rev) + 1)
    if rev.isalpha() and rev.isupper():
        return "A" * (len(rev) + 1) if set(rev) == {"Z"} else rev[:-1] + chr(ord(rev[-1]) + 1)
    return rev


class ICHNO_OT_tb_add(bpy.types.Operator):
    """Add a row"""
    bl_idname = "ichno.tb_add"
    bl_label = "Add"
    bl_options = {"UNDO"}
    target: EnumProperty(items=LISTS)

    def execute(self, context):
        s = context.scene.ichno_settings
        coll = getattr(s, self.target)
        it = coll.add()
        if self.target == "revisions":
            it.rev = next_rev(coll[-2].rev) if len(coll) > 1 else (s.revision or "A")
            it.date = datetime.date.today().strftime("%m/%d/%Y" if s.unit == "in" else "%d/%m/%Y")
        setattr(s, INDEX[self.target], len(coll) - 1)
        return {"FINISHED"}


class ICHNO_OT_tb_remove(bpy.types.Operator):
    """Remove the active row"""
    bl_idname = "ichno.tb_remove"
    bl_label = "Remove"
    bl_options = {"UNDO"}
    target: EnumProperty(items=LISTS)

    def execute(self, context):
        s = context.scene.ichno_settings
        coll, key = getattr(s, self.target), INDEX[self.target]
        if len(coll):
            coll.remove(getattr(s, key))
            setattr(s, key, max(0, min(getattr(s, key), len(coll) - 1)))
        return {"FINISHED"}


def draw_list(layout, s, target, ul):
    row = layout.row()
    row.template_list(ul, "", s, target, s, INDEX[target], rows=3)
    col = row.column(align=True)
    col.operator("ichno.tb_add", icon="ADD", text="").target = target
    col.operator("ichno.tb_remove", icon="REMOVE", text="").target = target


def spec(s):
    return {"revisions": [{"rev": r.rev, "desc": r.description, "date": r.date} for r in s.revisions],
            "fields": [{"key": f.key, "value": f.value} for f in s.fields],
            "legend": [{"code": a.code, "desc": a.description} for a in s.legend],
            "remarks": s.remarks.as_string() if s.remarks else "", "owner": s.owner}


DATA = (IchnoRevision, IchnoField, IchnoAbbr)
CLASSES = (ICHNO_UL_revisions, ICHNO_UL_fields, ICHNO_UL_legend, ICHNO_OT_tb_add, ICHNO_OT_tb_remove)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
