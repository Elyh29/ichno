# Ichno — technical drawings for Blender

**Free Blender add-on: turn your 3D scene into a technical drawing in one click.**
Orthographic views, isometric view, section views, dimensions, title block and bill of materials, exported as vector **PDF** and **SVG**.

*Featured on [BlenderNation](https://www.blendernation.com/2026/11/01/ichno-free-one-click-technical-drawings-from-blender-scenes/).*

![Ichno: a Blender model turned into a dimensioned technical drawing with front, side, top and isometric views](images/free1.png)

Ichno makes **blueprints and shop drawings** straight from Blender: furniture and woodworking plans, interior layouts,
product and 3D printing parts, mechanical assemblies. The drawings are ready to print, to send to a client or a workshop,
or to open in Illustrator, Inkscape, Affinity or a CAD tool.

## Install
- **Recommended:** Blender ‣ Edit ‣ Preferences ‣ Get Extensions, search for **Ichno** (updates are then automatic).
- Or download the zip from [Releases](../../releases) and use *Install from Disk*.

Requires Blender 4.3 or newer (tested up to 5.2). Windows, macOS and Linux.

## Quick start
1. 3D Viewport ‣ Sidebar (N) ‣ **Ichno** tab.
2. Choose what to draw: visible objects, selection or one collection.
3. Click **Make Plan**. The PDF opens when it's done.

The drawing is computed by a second Blender in the background, from a copy of your file:
**your scene is never modified**, you can keep working, and you can cancel at any time.

Right-click any Ichno setting ‣ **Online Manual** (F1) opens its page in the [wiki](../../wiki).

## Features

### Orthographic and isometric views
- Front, side and top views, **first-angle (ISO E) or third-angle (ISO A) projection**
- Isometric view from any corner, or from your current viewport angle
- Clean visible lines from Line Art, optional dashed hidden lines, three line weights
- Automatic standard scale (metric or imperial), or a fixed one

### Section views
- Up to three sections (front, side, top), each **cutting plane placed in the 3D View** with a live hatched preview
- Cut faces capped and hatched to **ISO 128-50**, a different spacing for each part, titled “SECTION A–A”
- Cutting plane shown edge-on on the neighbouring view: chain line, thick ends, viewing arrows and letters (ISO 128-3)
- Optional page with one isometric view per plane, cut or whole
- Coloured planes (A red, B blue, C green…) or plain black and white ISO

![Section views: cutting plane placed in the 3D View with a live hatched preview, and the ISO 128 sections A–A and B–B on the drawing](images/section-views.png)

![Cutting planes page: one isometric view per plane, cut, in the colour of its section](images/cutting-planes.png)

### Dimensions and tolerances
- **ISO or ASME** dimensioning: text placement, arrowheads and extension lines follow each standard
- Overall dimensions, each shown once (width and height on the front view, depth on the side view), in mm, cm, m or inches
- **ISO small dimensions**: text and arrows moved outside when they don't fit (ISO 129-1)
- Dual dimensioning, e.g. `254.0 [10.00"]`
- Chain dimensions for rows of objects, equal spacing combined as `5 × 600 = 3000`
- Coordinate ruler or architect grid (A, B, C / 1, 2, 3)
- **ISO 2768 general tolerances**: length class (f, m, c, v), geometric class (H, K, L) and envelope requirement, e.g. `ISO 2768-mK-(E)`,
  with an optional **table of deviations** for the dimensions on the sheet

![ISO 2768 general tolerances: table of deviations above the title block, ISO 2768-mK-(E) in the title block](images/coming-iso-2768.png)

### Sheets, title block and bill of materials
- A4 to A0, Letter, Tabloid, ANSI C and D, portrait or landscape
- **One sheet per collection** in a single multi-page PDF, each with its own views and scale
- A fixed scale too large for one sheet: views spread over two sheets, or that sheet switches to automatic scale
- Title block with company name and logo, drawing number, author, date, revision table, custom fields
- Checked, Approved, **general tolerances** (ISO 2768, ISO 22081 or custom) and material
- ISO 128 line weights, ISO 5457 border with optional filing margin, ISO 3098 text heights
- **Bill of materials (BOM)** counted by object name, collection or custom property, on the drawing or on a separate sheet
- Abbreviation legend, remarks and ownership notice

### Practical
- **SVG with layers** (VISIBLE, HIDDEN, DIMENSIONS, TEXT, FRAME) to filter in Illustrator, Inkscape or a viewer
- Linked and instanced collections drawn and counted as one part
- Fast mode for drafts of heavy models
- Interface and drawings in English and French

| | |
|---|---|
| ![Front, side, top and isometric views on an A3 sheet](images/free2.png) | ![Overall and chain dimensions with equal spacing combined](images/free3.png) |
| ![Title block with revisions, custom fields, legend and bill of materials](images/free4.png) | ![Isometric view chosen from any corner of the model](images/free5.png) |

## Roadmap
Each version ships **when it is ready**, no fixed dates; the order may change.

![Ichno roadmap: 1.0.6 now, then dimensions and holes, notes and views, Japan, then more countries](images/ichno-roadmap-free.png)

- **Now — 1.0.6**: section views with ISO hatching, ISO 2768 tolerances with a table of deviations, ISO small dimensions, F1 help, SVG layers
- **Next — 1.0.7**: manual and angle dimensions, Ø, R and □ symbols, hole dimensions and spacing, centre lines, chamfers “C2”, the drawing viewed inside Blender
- **Then — 1.0.8**: notes with leaders, dimension styles, revision table, views from a camera, shaded views, edge conditions, material colours on the drawing
- **Then — 1.0.9**: country setting, first national update for Japan (JIS standard, Japanese interface and drawings)
- **Later**: more countries (DIN, GB/T, ASME Y14.1, Spanish, Portuguese) and more languages

Missing something for your drawings? Open a [feature request](../../issues/new/choose).

## FAQ
**Can I open the drawing in AutoCAD or another CAD tool?**
Yes, through the SVG or PDF export (most CAD tools import one of them).

**Does it modify my scene?**
No. Ichno works on a temporary copy of your file, in a second Blender running in the background.

**Does it work with heavy models?**
Yes. Models with millions of triangles take a few minutes; use Fast mode for drafts, or one sheet per sub-assembly.
Section views of very heavy scenes are shown on whole isometric views, which is faster.

**When is the next version out?**
When it is ready: no fixed dates. Watch the repository (Watch ‣ Custom ‣ Releases) to be told.

## Bugs and ideas
Open an [issue](../../issues), with your Blender version and, if possible, a small .blend file.

## License
GPL-3.0-or-later, see [LICENSE](LICENSE).
