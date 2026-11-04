# SPDX-License-Identifier: GPL-3.0-or-later
# Ichno: sidebar panels
import bpy

from . import chains, help, sheets, titleblock
from .i18n import tr


class IchnoPanel:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Ichno"

    def setup(self, context):
        lay = self.layout
        lay.use_property_split = True
        lay.use_property_decorate = False
        return lay, context.scene.ichno_settings


VIEWS = ("front", "side", "top")


def view_row(lay, s, prefix, iso=None):
    row = lay.row(heading="Views", align=True)
    for k in VIEWS:
        row.prop(s, prefix + k, toggle=True)
    if iso:
        row.prop(s, iso, text="Isometric", toggle=True)


class VIEW3D_PT_ichno(IchnoPanel, bpy.types.Panel):
    bl_label = "Ichno"

    def draw_header_preset(self, context):
        self.layout.operator("wm.url_open", text="", icon="HELP", emboss=False).url = help.WIKI

    def draw(self, context):
        lay, s = self.setup(context)
        job = context.window_manager.ichno_job
        lay.prop(s, "source")
        if s.source == "COLLECTION":
            lay.prop(s, "collection")
        if job.running:
            row = lay.row(align=True)
            row.progress(factor=job.progress, text=job.message or "…")
            row.operator("ichno.cancel", text="", icon="CANCEL")
        else:
            row = lay.row(align=True)
            row.scale_y = 1.4
            row.operator("ichno.make", icon="FILE")
            if hasattr(context.scene, "ichno_pro"):
                row.menu("ICHNO_MT_batch", text="", icon="DOCUMENTS")
            if job.last:
                row.operator("ichno.open", text="", icon="FILE_FOLDER").path = job.last
            if job.message:
                lay.label(text=job.message)


class VIEW3D_PT_ichno_output(IchnoPanel, bpy.types.Panel):
    bl_label = "Output"
    bl_parent_id = "VIEW3D_PT_ichno"
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header_preset(self, context):
        pro = getattr(context.scene, "ichno_pro", None)
        self.layout.label(text="PDF, SVG" + (", DXF" if pro and pro.dxf else ""), translate=False)

    def draw(self, context):
        lay, s = self.setup(context)
        lay.prop(s, "folder")
        lay.prop(s, "subfolder")
        lay.prop(s, "open_pdf")
        if hasattr(context.scene, "ichno_pro"):
            row = lay.row(align=True)
            row.prop(context.scene.ichno_pro, "dxf", toggle=True)
            sub = row.row(align=True)
            sub.active = context.scene.ichno_pro.dxf
            sub.prop(context.scene.ichno_pro, "dxf_real", toggle=True)


class VIEW3D_PT_ichno_views(IchnoPanel, bpy.types.Panel):
    bl_label = "Views"
    bl_parent_id = "VIEW3D_PT_ichno"

    def draw(self, context):
        lay, s = self.setup(context)
        view_row(lay, s, "view_", "iso")
        row = lay.row()
        row.active = s.iso
        row.prop(s, "iso_view")
        lay.prop(s, "front")
        lay.prop(s, "projection")
        lay.prop(s, "standard")


class VIEW3D_PT_ichno_lines(IchnoPanel, bpy.types.Panel):
    bl_label = "Style"
    bl_parent_id = "VIEW3D_PT_ichno_views"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        lay, s = self.setup(context)
        lay.prop(s, "fast")
        lay.prop(s, "weight")
        lay.prop(s, "angle")
        col = lay.column(heading="Hidden lines")
        col.prop(s, "hidden", text="Front, Side, Top")
        sub = col.column()
        sub.active = s.hidden and s.iso
        sub.prop(s, "iso_hidden", text="Isometric")
        lay.separator()
        lay.prop(s, "axes")
        lay.prop(s, "view_titles")
        lay.prop(s, "dims_all")
        row = lay.row()
        row.active = s.standard == "iso" or (s.standard == "auto" and s.projection == "first")
        row.prop(s, "filing_margin")


class VIEW3D_PT_ichno_paper(IchnoPanel, bpy.types.Panel):
    bl_label = "Sheet"
    bl_parent_id = "VIEW3D_PT_ichno"

    def draw(self, context):
        lay, s = self.setup(context)
        lay.prop(s, "sheet")
        lay.prop(s, "landscape")
        lay.prop(s, "scale")
        lay.separator()
        lay.prop(s, "unit")
        lay.prop(s, "unit2")
        lay.prop(s, "lang")


class VIEW3D_PT_ichno_sheets(IchnoPanel, bpy.types.Panel):
    bl_label = "Sheets by Collection"
    bl_parent_id = "VIEW3D_PT_ichno"
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        self.layout.prop(context.scene.ichno_settings, "use_sheets", text="")

    def draw(self, context):
        s = context.scene.ichno_settings
        self.layout.active = s.use_sheets
        sheets.draw(self.layout, s, context)


class VIEW3D_PT_ichno_title(IchnoPanel, bpy.types.Panel):
    bl_label = "Title Block"
    bl_parent_id = "VIEW3D_PT_ichno"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        lay, s = self.setup(context)
        if hasattr(context.scene, "ichno_pro"):
            from .pro import templates
            templates.draw(lay)
        for k in ("title", "project", "number", "author", "revision", None, "company", "logo", "owner"):
            if k is None:
                lay.separator()
            elif k == "revision" and s.revisions:
                row = lay.row()
                row.enabled = False
                row.prop(s.revisions[-1], "rev", text="Revision")
            else:
                lay.prop(s, k)


class VIEW3D_PT_ichno_approval(IchnoPanel, bpy.types.Panel):
    bl_label = "Approval and Manufacturing"
    bl_parent_id = "VIEW3D_PT_ichno_title"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        lay, s = self.setup(context)
        for k in ("checked", "approved", "material", "tolerances"):
            lay.prop(s, k)
        if s.tolerances == "ISO 2768":
            row = lay.row(align=True)
            row.prop(s, "tol_class")
            row.prop(s, "tol_geo")
            lay.prop(s, "tol_envelope")
            lay.prop(s, "tol_table")
        elif s.tolerances == "custom":
            lay.prop(s, "tolerances_text")


class VIEW3D_PT_ichno_revisions(IchnoPanel, bpy.types.Panel):
    bl_label = "Revisions"
    bl_parent_id = "VIEW3D_PT_ichno_title"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        titleblock.draw_list(self.layout, context.scene.ichno_settings, "revisions", "ICHNO_UL_revisions")


class VIEW3D_PT_ichno_fields(IchnoPanel, bpy.types.Panel):
    bl_label = "Custom Fields"
    bl_parent_id = "VIEW3D_PT_ichno_title"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        titleblock.draw_list(self.layout, context.scene.ichno_settings, "fields", "ICHNO_UL_fields")


class VIEW3D_PT_ichno_legend(IchnoPanel, bpy.types.Panel):
    bl_label = "Legend"
    bl_parent_id = "VIEW3D_PT_ichno_title"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        titleblock.draw_list(self.layout, context.scene.ichno_settings, "legend", "ICHNO_UL_legend")


class VIEW3D_PT_ichno_remarks(IchnoPanel, bpy.types.Panel):
    bl_label = "Remarks"
    bl_parent_id = "VIEW3D_PT_ichno_title"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        s = context.scene.ichno_settings
        self.layout.template_ID(s, "remarks", new="text.new", open="text.open")
        self.layout.label(text="Write the remarks in the Text Editor", icon="INFO")


class VIEW3D_PT_ichno_notes(IchnoPanel, bpy.types.Panel):
    bl_label = "Dimensions"
    bl_parent_id = "VIEW3D_PT_ichno"
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header_preset(self, context):
        s = context.scene.ichno_settings
        pro = getattr(context.scene, "ichno_pro", None)
        on = [n for n, ok in (("Chains", any(c.collection for c in s.chains)), ("Manual", bool(pro and pro.dims)),
                              ("Grid", s.grid_mode != "none")) if ok]
        self.layout.label(text=", ".join(tr(n) for n in on), translate=False)

    def draw(self, context):
        self.layout.label(text="Overall dimensions are always drawn", icon="INFO")


class VIEW3D_PT_ichno_chains(IchnoPanel, bpy.types.Panel):
    bl_label = "Chain Dimensions"
    bl_parent_id = "VIEW3D_PT_ichno_notes"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        chains.draw(self.layout, context.scene.ichno_settings)
        self.layout.prop(context.scene.ichno_settings, "chain_ticks")


class VIEW3D_PT_ichno_grid(IchnoPanel, bpy.types.Panel):
    bl_label = "Coordinate Grid"
    bl_parent_id = "VIEW3D_PT_ichno_notes"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        lay, s = self.setup(context)
        lay.prop(s, "grid_mode")
        col = lay.column()
        col.active = s.grid_mode != "none"
        col.prop(s, "grid_step")
        col.prop(s, "grid_origin")
        view_row(col, s, "grid_")


class VIEW3D_PT_ichno_mdims(IchnoPanel, bpy.types.Panel):
    bl_label = "Manual Dimensions"
    bl_parent_id = "VIEW3D_PT_ichno_notes"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return hasattr(context.scene, "ichno_pro")

    def draw(self, context):
        from .pro import dims
        dims.draw(self.layout, context)


class VIEW3D_PT_ichno_bom(IchnoPanel, bpy.types.Panel):
    bl_label = "Bill of Materials"
    bl_parent_id = "VIEW3D_PT_ichno"
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header_preset(self, context):
        s = context.scene.ichno_settings
        if s.bom_by != "none":
            self.layout.label(text=tr("On"), translate=False)

    def draw(self, context):
        lay, s = self.setup(context)
        lay.prop(s, "bom_by")
        if s.bom_by == "property":
            lay.prop(s, "bom_prop")
        col = lay.column()
        col.active = s.bom_by != "none"
        col.prop(s, "bom_annex")
        sheets.draw_bom_cols(col, s)
        if hasattr(context.scene, "ichno_pro"):
            col = lay.column()
            col.active = s.bom_by != "none"
            col.prop(context.scene.ichno_pro, "balloons")
            col.prop(context.scene.ichno_pro, "bom_files")


CLASSES = (VIEW3D_PT_ichno, VIEW3D_PT_ichno_output, VIEW3D_PT_ichno_views, VIEW3D_PT_ichno_lines, VIEW3D_PT_ichno_paper, VIEW3D_PT_ichno_sheets,
           VIEW3D_PT_ichno_title, VIEW3D_PT_ichno_approval, VIEW3D_PT_ichno_revisions, VIEW3D_PT_ichno_fields, VIEW3D_PT_ichno_legend, VIEW3D_PT_ichno_remarks,
           VIEW3D_PT_ichno_notes, VIEW3D_PT_ichno_chains, VIEW3D_PT_ichno_grid, VIEW3D_PT_ichno_mdims, VIEW3D_PT_ichno_bom)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
