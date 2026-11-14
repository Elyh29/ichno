# Changelog

All notable changes to Ichno. Each version ships when it is ready.

## 1.0.7 — 2026-11-12

### Annotations
- Manual dimensions between 2 vertices (Edit Mode), drawn at true length on the views parallel to them; order adjustable in the list
- Angle dimensions from 3 vertices: dimension arc centred on the vertex, value in degrees (ISO 129-1)
- Symbols before the value of manual dimensions: Ø, R, SØ, SR, □, t= (ISO 129-1)
- Hole dimensions: on the view showing the most holes, "4 × Ø8" per diameter on a leader, spacing as chain dimensions; exact values taken from the model
- Centre lines on holes and shafts (ISO 128-2), found automatically from circular edges
- 45° chamfers found on the model and dimensioned "2 × 45°" (ISO 129-1)
- Overall size without handles: body width, depth and height first, full size in brackets, e.g. 45.0 then (47.2); handles found by name or in a "Hors encombrement" collection
- Marked edges: edges you choose are always drawn, even on smooth surfaces (seams, joints, folds); Mark / Clear / Select in Edit Mode
- Edge condition (ISO 13715), e.g. "−0.3", in the title block


### Viewer and output
- Viewer inside Blender (button next to Make Plan): the last drawing sheet by sheet in an "Ichno" workspace, thumbnails, layers on/off, Fit / Paper size, Draft / Normal / High quality, save a sheet as PNG, back to your workspace; reloads after each drawing
- Output: one checkbox per file (PDF, SVG); "When done": open the PDF, show it in the viewer, or nothing
- Layer colours (one per layer) in the SVG and the viewer, optional in the PDF
- SVG: one group per layer (Inkscape layers, named groups in Illustrator and Affinity), same drawing order as the PDF
- PDF: title, author, project and revision in the document properties; one bookmark per sheet
- Sheets per collection: two sheets with the same bill of materials share one annex sheet
- Panel reorganised in working order, two levels at most; closed headers say what is on


### Works with Talos (fasteners)
- Screws, nuts and washers drawn from their description in front, side and top views; in sections they stay whole (ISO), hatching stops at their outline
- Holes dimensioned in full (ISO 129-1): "4 × Ø6.6 ⌴ Ø11 ↧ 6.4", "Ø5.5 ⌵ Ø11.6 × 90°", "M5 ↧ 8", inserts, blind hole depth; ⌴ ⌵ ↧ drawn in the PDF and written in the SVG
- Threads (ISO 6410-1): three-quarter circles at the nominal diameter seen end-on, thread root seen from the side, hidden tapped holes dashed
- Bill of materials: full designations in the drawing's language ("ISO 4762 M6 × 20 – 10.9 screw", nuts, washers, inserts, pins)


### Fixes
- Hidden lines: overlapping pieces of an edge joined before dashing (no more solid hidden lines), small isolated bits removed, no stray triangles or hatching behind touching parts
- Stacked holes: grouped by distance and dimensioned once, with the hole you actually see
- Section caps hide without drawing (no more diagonal lines across a section); hidden lines joined into regular dashes
- Chain dimensions that don't overlap share one row; the reference is named after the model side (Front (-Y), Back (+Y), Left (-X)…)
- A drawing started in Edit Mode is no longer empty; a view with no line is re-evaluated, with a warning if it stays empty
- Untitled drawing: no more two lone dashes at the top of the sheet

## 1.0.6 — 2026-11-08

### Section views
- New **Section Views** panel: up to three sections, one per view (front, side, top), by planes parallel to the views, placed in the 3D View (G, or the Position field); cut faces capped and hatched (ISO 128-50, spacing varied from part to part), titled “SECTION A–A”
- Each cutting plane shown edge-on on a neighbouring view: chain line, thick ends, arrows in the viewing direction and letters (ISO 128-3)
- Cutting planes page: one isometric view per plane, cut (material in front of the plane removed) or whole; or all planes on the isometric view of the drawing; or none
- Coloured cutting planes (A red, B blue, C green…, editable) in the 3D View, cutting lines, titles and a light fill under the hatching; unticked: ISO black and white
- Live preview in the 3D View: planes, arrows, hatched cut, material in front of the active plane hidden; selecting a plane makes it the active cut
- Heavy scenes (over 1.5 million triangles): cutting planes shown on whole isometric views, faster; only the parts crossed by a plane are cut

### Standards
- **ISO 2768 general tolerances**: length and angle class (f, m, c, v), geometric class (H, K, L) and envelope requirement (E); the title block shows e.g. `ISO 2768-mK-(E)`
- Table of permissible deviations (optional), above the title block: the ± limits of the chosen class for the dimensions on the sheet
- Small dimensions (ISO 129-1): the value moves outside the extension lines when it does not fit, arrowheads go outside pointing in

### Also
- Help: right-click ‣ Online Manual (F1) on any Ichno setting or button opens its section of the wiki; “?” button in the Ichno panel header
- SVG: every element carries its layer (`class` = VISIBLE, HIDDEN, DIMENSIONS, TEXT or FRAME), to filter it in an editor or a viewer
- The title block's “Generated by” line gives the Ichno and Blender versions
- Fixed scale too large for the sheet (a view does not fit, even alone): that sheet switches to Auto with an info line instead of stopping the drawing; with sheets per collection, the other sheets keep the chosen scale
- Fixed scale: views that do not fit together are split over two sheets (front and side, or front and top, then the remaining view with the isometric) instead of one sheet per view
- A drawing without a title, with sheets per collection: the sheet name is used as the title (no more “— — Sheet 1”)
- Tight chain dimensions: positions too close to each other are no longer written on top of each other; tight values are shifted with a short leader
- Disabling Ichno while a drawing is being computed stops the background Blender and removes its temporary files
- Reinstalling Ichno without restarting Blender now loads the new version completely
- License: GPL text included in the zip, copyright notice in the code; PDF and SVG files carry it in their metadata, invisible on the drawing

## 1.0.5 — 2026-11-01
- Reorganised panel: Files (Output) and Style collapsed, Dimensions and Bill of Materials as main panels, Approval and Manufacturing on their own; the header of a closed panel says what is turned on
- ISO or ASME standard (Views panel, “Auto” follows the projection): dimension text (ISO: above the line, vertical ones on the left, read from below; ASME: horizontal, in a break of the line), arrowheads (30° in ISO, 3:1 in ASME), extension line gaps
- Each size dimensioned once: width and height on the front view, depth on the side view (previous behaviour: “Overall Dimensions on Every View”)
- Dimensions 10 mm from the view, 3.5 mm text (2.5 mm on A4 / Letter), 3 mm arrowheads, also on chain dimensions (oblique ticks as an option, or where arrows do not fit)
- ISO 3098 text heights on the whole drawing; dimension values on a white background
- Line weights in a 2:1 ratio (ISO 128): edges and hidden lines thin, dashes proportional to the line weight
- Border and centring marks at 0.7 mm, 20 mm filing margin on the left (ISO 5457, can be turned off)
- Title block: Checked, Approved, General Tolerances (ISO 2768, ISO 22081 or free text) and Material fields
- Optional view titles
- Bill of materials above the title block, read from the bottom up (ISO 7573); or on a separate sheet (Auto above 30 rows, Always, Never), with a reference on the drawing
- Bill of materials: choice of the collections counted and of the sheets that show it

## 1.0.4 — 2026-11-01
- One folder per drawing (option, on by default): all files in `<Folder>/<Drawing No.>/`
- Drawing numbers with characters Windows refuses (`: ? *`…): file and folder names cleaned, no more failure
- Website: the Ichno GitHub repository

## 1.0.3 — 2026-10-30
- Simplified hidden lines reported by a single info line per sheet (instead of one warning per view)

## 1.0.2 — 2026-10-30
- extensions.blender.org review: no more `threading` / `queue` (the background Blender's output is read from a file), no more `sys.path` changes
- Tags: “3D View” and “Render” instead of “Import-Export”

## 1.0.1 — 2026-10-29
- Copyright in the manifest, reason for the “files” permission completed (extensions.blender.org rules)

## 1.0.0 — 2026-10-28
- First public version, on extensions.blender.org

## 0.x — 2026-10-27 / 2026-10-28 (before the public release)
- 0.7: compatible with Blender 4.3 to 5.2; Fast mode; chain dimensions with “Combine Equal Spacing”; views chosen per sheet; abbreviation legend; sheet order; linked and instanced collections; bill of materials; A0 and choice of views; coordinate ruler or architect grid; revisions, custom fields, remarks, ownership notice; `ichno-log.txt` log on failure; a PDF open elsewhere (Windows) saved as “name (2).pdf”
- 0.6: chain dimensions, with tolerance, positions and dual dimensioning; inches with their symbol (")
- 0.5: French interface, drawing language (auto / English / French), engine warnings shown; dual dimensioning
- 0.4: one sheet per collection (with checks), collapsible sub-panels, axes triad next to the view titles, first / third angle shown
- 0.3: choice of the front view, simplified hidden lines, optional hidden lines on the isometric view
- 0.2: third-angle projection, US and A2 / A1 sizes, inches and imperial scales; title block with logo, author, revision
- 0.1: first add-on, drawing computed in the background on a copy, progress and cancel
