# Ichno — technical drawings for Blender

**Free Blender add-on: turn your 3D scene into a technical drawing in one click.**
Orthographic views, isometric view, dimensions, title block and bill of materials, exported as vector **PDF** and **SVG**.

*Featured on [BlenderNation](https://www.blendernation.com/2026/11/01/ichno-free-one-click-technical-drawings-from-blender-scenes/).*

![Ichno: a Blender model turned into a dimensioned technical drawing with front, side, top and isometric views](images/free1.png)

Ichno makes **blueprints and shop drawings** straight from Blender: furniture and woodworking plans, interior layouts,
product and 3D printing parts, mechanical assemblies. The drawings are ready to print, to send to a client or a workshop,
or to open in Illustrator, Inkscape, Affinity or a CAD tool.

## Install
- **Recommended:** Blender ‣ Edit ‣ Preferences ‣ Get Extensions, search for **Ichno**.
- Or download the zip from [Releases](../../releases) and use *Install from Disk*.

Requires Blender 4.3 or newer (tested up to 5.2). Windows, macOS and Linux.

## Quick start
1. 3D Viewport ‣ Sidebar (N) ‣ **Ichno** tab.
2. Choose what to draw: visible objects, selection or one collection.
3. Click **Make Plan**. The PDF opens when it's done.

The drawing is computed by a second Blender in the background, from a copy of your file:
**your scene is never modified**, you can keep working, and you can cancel at any time.

## Features

### Orthographic and isometric views
- Front, side and top views, **first-angle (ISO E) or third-angle (ISO A) projection**
- Isometric view from any corner, or from your current viewport angle
- Clean visible lines from Line Art, optional dashed hidden lines, three line weights
- Automatic standard scale (metric or imperial), or a fixed one

### Dimensions
- **ISO or ASME** dimensioning: text placement, arrowheads and extension lines follow each standard
- Overall dimensions, each shown once (width and height on the front view, depth on the side view), in mm, cm, m or inches
- Dual dimensioning, e.g. `254.0 [10.00"]`
- Chain dimensions for rows of objects, equal spacing combined as `5 × 600 = 3000`
- Coordinate ruler or architect grid (A, B, C / 1, 2, 3)

### Sheets, title block and bill of materials
- A4 to A0, Letter, Tabloid, ANSI C and D, portrait or landscape
- **One sheet per collection** in a single multi-page PDF, each with its own views and scale
- Title block with company name and logo, drawing number, author, date, revision table, custom fields
- Checked, Approved, **general tolerances** (ISO 2768, ISO 22081 or custom) and material
- ISO 128 line weights, ISO 5457 border with optional filing margin, ISO 3098 text heights
- **Bill of materials (BOM)** counted by object name, collection or custom property, on the drawing or on a separate sheet
- Abbreviation legend, remarks and ownership notice

### Practical
- Linked and instanced collections drawn and counted as one part
- Fast mode for drafts of heavy models
- Interface and drawings in English and French

| | |
|---|---|
| ![Front, side, top and isometric views on an A3 sheet](images/free2.png) | ![Overall and chain dimensions with equal spacing combined](images/free3.png) |
| ![Title block with revisions, custom fields, legend and bill of materials](images/free4.png) | ![Isometric view chosen from any corner of the model](images/free5.png) |

## Coming next
Already built and in testing, out in the next weeks. Want to try 1.0.6 now? The **beta** is in [Releases](../../releases).

![Section views: cutting plane placed in the 3D View with a live hatched preview, and the ISO 128 section A–A on the drawing](images/coming-section-views.png)

![ISO 2768 general tolerances: table of deviations above the title block, ISO 2768-mK-(E) in the title block](images/coming-iso-2768.png)

![Also in 1.0.6: ISO small dimensions, SVG with layers, F1 help](images/coming-1-0-6.png)

## Roadmap
**A new version every week**, on Sundays. Target dates, they may change.

![Ichno roadmap: a new version every week from Nov 8 to Dec 20, then more countries in 2027](images/ichno-roadmap-free.png)

- **1.0.6 (Nov 8)**: ISO 2768 general tolerances with a table of deviations, ISO small dimensions, F1 help, SVG layers
- **1.0.7 (Nov 15)**: section views with ISO hatching, cutting plane placed in the 3D View
- **1.0.8 (Nov 22)**: manual and angle dimensions, Ø, R and □ symbols
- **1.0.9 (Nov 29)**: notes with leaders, dimension styles, revision table
- **1.0.10 (Dec 6)**: centre lines, hole dimensions and spacing, chamfers “C2”
- **1.0.11 (Dec 13)**: views from a Blender camera, shaded views, edge conditions
- **1.0.12 (Dec 20)**: country setting, first national update for Japan (JIS standard, Japanese interface and drawings)
- **2027**: more countries (DIN, GB/T, ASME Y14.1, Spanish, Portuguese) and more languages

Missing something for your drawings? Open a [feature request](../../issues/new/choose).


## FAQ
**Can I open the drawing in AutoCAD or another CAD tool?**
Yes, through the SVG or PDF export (most CAD tools import one of them).

**Does it modify my scene?**
No. Ichno works on a temporary copy of your file, in a second Blender running in the background.

**Does it work with heavy models?**
Yes. Models with millions of triangles take a few minutes; use Fast mode for drafts, or one sheet per sub-assembly.

## Bugs and ideas
Open an [issue](../../issues), with your Blender version and, if possible, a small .blend file.

## License
GPL-3.0-or-later, see [LICENSE](LICENSE).
