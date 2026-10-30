import bpy

from .i18n import rpt, tr
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, IntProperty, PointerProperty, StringProperty


def objects_to_draw(context, s):
    if s.source == "SELECTED":
        objs = context.selected_objects
    elif s.source == "COLLECTION":
        objs = s.collection.all_objects if s.collection else []
    else:
        objs = [o for o in context.scene.objects if o.visible_get()]
    return [o.name for o in objs]


def base_collection(context, s):
    return s.collection if s.source == "COLLECTION" and s.collection else context.scene.collection


def allowed(context, s, c):
    base = base_collection(context, s)
    return c == base or c in base.children_recursive


def poll_collection(self, c):
    return allowed(bpy.context, bpy.context.scene.ichno_settings, c)


def problems(context, s):
    if not (s.use_sheets and s.sheets):
        return []
    shown, out = set(objects_to_draw(context, s)), []
    for i, sh in enumerate(s.sheets):
        cols = [c.collection for c in sh.collections if c.collection]
        if not cols:
            out.append((i, tr("no collection")))
        elif any(not allowed(context, s, c) for c in cols):
            out.append((i, tr("collection outside “{}”", base_collection(context, s).name)))
        elif sh.own_views and not sheet_views(sh):
            out.append((i, tr("no view selected")))
        elif not sheet_objects(sh, shown):
            out.append((i, tr("nothing to draw (check Objects)")))
    return out


class IchnoSheetCollection(bpy.types.PropertyGroup):
    collection: PointerProperty(name="Collection", type=bpy.types.Collection, poll=poll_collection)


class IchnoSheet(bpy.types.PropertyGroup):
    name: StringProperty(name="Name", default="Sheet")
    collections: CollectionProperty(type=IchnoSheetCollection)
    col_index: IntProperty()
    own_views: BoolProperty(name="Own Views", description="This sheet draws its own views instead of those of the Views panel")
    view_front: BoolProperty(name="Front", default=True)
    view_side: BoolProperty(name="Side", default=True)
    view_top: BoolProperty(name="Top", default=True)
    view_iso: BoolProperty(name="Isometric", default=True)


VIEW_KEYS = ("front", "side", "top", "iso")


def sheet_views(sh):
    return [k for k in VIEW_KEYS if getattr(sh, "view_" + k)] if sh.own_views else None


def sheet_objects(sh, shown):
    return sorted({o.name for c in sh.collections if c.collection for o in c.collection.all_objects} & shown)


class ICHNO_UL_sheets(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index=0, flt_flag=0):
        row = layout.row(align=True)
        bad = index in _bad
        row.prop(item, "name", text="", emboss=False, icon="ERROR" if bad else "FILE_BLANK")
        if item.own_views:
            row.label(text=" ".join(k[0].upper() for k in VIEW_KEYS if getattr(item, "view_" + k)) or "—", translate=False)
        n = sum(1 for c in item.collections if c.collection)
        row.label(text=str(n), icon="OUTLINER_COLLECTION")


class ICHNO_UL_sheet_collections(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        s = context.scene.ichno_settings
        ok = item.collection is None or allowed(context, s, item.collection)
        layout.alert = not ok
        layout.prop(item, "collection", text="", emboss=True, icon="OUTLINER_COLLECTION" if ok else "ERROR")


def settings(context):
    return context.scene.ichno_settings


class ICHNO_OT_sheet_add(bpy.types.Operator):
    """Add a sheet"""
    bl_idname = "ichno.sheet_add"
    bl_label = "Add Sheet"
    bl_options = {"UNDO"}

    def execute(self, context):
        s = settings(context)
        sh = s.sheets.add()
        sh.name = f"{tr('Sheet')} {len(s.sheets)}"
        s.sheet_index = len(s.sheets) - 1
        return {"FINISHED"}


class ICHNO_OT_sheet_remove(bpy.types.Operator):
    """Remove the active sheet"""
    bl_idname = "ichno.sheet_remove"
    bl_label = "Remove Sheet"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return len(settings(context).sheets) > 0

    def execute(self, context):
        s = settings(context)
        s.sheets.remove(s.sheet_index)
        s.sheet_index = max(0, min(s.sheet_index, len(s.sheets) - 1))
        return {"FINISHED"}


class ICHNO_OT_sheet_move(bpy.types.Operator):
    """Move the active sheet up or down (order of the pages)"""
    bl_idname = "ichno.sheet_move"
    bl_label = "Move Sheet"
    bl_options = {"UNDO"}
    direction: EnumProperty(items=[("UP", "Up", ""), ("DOWN", "Down", "")])

    @classmethod
    def poll(cls, context):
        return len(settings(context).sheets) > 1

    def execute(self, context):
        s = settings(context)
        to = s.sheet_index + (-1 if self.direction == "UP" else 1)
        if 0 <= to < len(s.sheets):
            s.sheets.move(s.sheet_index, to)
            s.sheet_index = to
        return {"FINISHED"}


class ICHNO_OT_sheet_auto(bpy.types.Operator):
    """One sheet per top-level collection of the scene (replaces the list)"""
    bl_idname = "ichno.sheet_auto"
    bl_label = "One Sheet per Collection"
    bl_options = {"UNDO"}

    def execute(self, context):
        s = settings(context)
        s.sheets.clear()
        excluded = set()

        def walk(lc):
            if lc.exclude:
                excluded.add(lc.collection.name)
            for ch in lc.children:
                walk(ch)
        walk(context.view_layer.layer_collection)
        base = base_collection(context, s)
        for c in base.children or ([base] if base != context.scene.collection else []):
            if c.name in excluded or not c.all_objects:
                continue
            sh = s.sheets.add()
            sh.name = c.name
            sh.collections.add().collection = c
        s.sheet_index = 0
        if not s.sheets:
            self.report({"WARNING"}, rpt("No collection with objects"))
        return {"FINISHED"}


class ICHNO_OT_sheet_col_add(bpy.types.Operator):
    """Add a collection to the active sheet"""
    bl_idname = "ichno.sheet_col_add"
    bl_label = "Add Collection"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return len(settings(context).sheets) > 0

    def execute(self, context):
        sh = settings(context).sheets[settings(context).sheet_index]
        sh.collections.add()
        sh.col_index = len(sh.collections) - 1
        return {"FINISHED"}


class ICHNO_OT_sheet_col_remove(bpy.types.Operator):
    """Remove the collection from the active sheet"""
    bl_idname = "ichno.sheet_col_remove"
    bl_label = "Remove Collection"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        s = settings(context)
        return len(s.sheets) > 0 and len(s.sheets[s.sheet_index].collections) > 0

    def execute(self, context):
        sh = settings(context).sheets[settings(context).sheet_index]
        sh.collections.remove(sh.col_index)
        sh.col_index = max(0, min(sh.col_index, len(sh.collections) - 1))
        return {"FINISHED"}


_bad = set()


def draw(layout, s, context):
    bad = problems(context, s)
    _bad.clear()
    _bad.update(i for i, _ in bad)
    if s.source == "COLLECTION":
        layout.label(text=tr("Sub-collections of “{}” only", s.collection.name if s.collection else "—"), icon="INFO", translate=False)
    row = layout.row()
    row.template_list("ICHNO_UL_sheets", "", s, "sheets", s, "sheet_index", rows=5)
    col = row.column(align=True)
    col.operator("ichno.sheet_add", icon="ADD", text="")
    col.operator("ichno.sheet_remove", icon="REMOVE", text="")
    col.separator()
    col.operator("ichno.sheet_move", icon="TRIA_UP", text="").direction = "UP"
    col.operator("ichno.sheet_move", icon="TRIA_DOWN", text="").direction = "DOWN"
    layout.operator("ichno.sheet_auto", icon="OUTLINER_COLLECTION")
    if s.sheets:
        sh = s.sheets[s.sheet_index]
        layout.label(text=tr("Collections of “{}”", sh.name), translate=False)
        row = layout.row()
        row.template_list("ICHNO_UL_sheet_collections", "", sh, "collections", sh, "col_index", rows=2)
        col = row.column(align=True)
        col.operator("ichno.sheet_col_add", icon="ADD", text="")
        col.operator("ichno.sheet_col_remove", icon="REMOVE", text="")
        row = layout.row(align=True)
        row.prop(sh, "own_views", text="", icon="RESTRICT_VIEW_OFF")
        sub = row.row(align=True)
        sub.active = sh.own_views
        for k in VIEW_KEYS:
            sub.prop(sh, "view_" + k, toggle=True)
        layout.label(text="The title becomes the generic name", icon="INFO")
    for i, why in bad:
        r = layout.row()
        r.alert = True
        r.label(text=tr("Sheet “{}”: {}", s.sheets[i].name, why), icon="ERROR", translate=False)


DATA = (IchnoSheetCollection, IchnoSheet)
CLASSES = (ICHNO_UL_sheets, ICHNO_UL_sheet_collections, ICHNO_OT_sheet_add, ICHNO_OT_sheet_remove, ICHNO_OT_sheet_move, ICHNO_OT_sheet_auto,
           ICHNO_OT_sheet_col_add, ICHNO_OT_sheet_col_remove)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
