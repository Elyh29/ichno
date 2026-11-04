# Ichno PRO

![Ichno PRO: a technical drawing made from a Blender scene, with balloons, bill of materials and title block](images/pro1.png)

**Ichno PRO** is the extended edition of [Ichno](https://extensions.blender.org/add-ons/ichno/), the Blender add-on that turns a scene into a technical drawing in one click. It contains every feature of the free edition and adds:

- **DXF export**: one file per sheet (AutoCAD R12), layers VISIBLE, HIDDEN, DIMENSIONS, TEXT and FRAME, real size 1:1 in millimetres
- **Bill of materials to CSV and Excel**, with headers in the drawing language and a total row
- **Balloons** linked to the bill of materials (ISO 6433)
- **Manual dimensions** between two vertices or two positions of the 3D cursor
- **Title block templates**: company, logo, fields and sheet settings saved under a name, exported and imported as JSON
- **Batch export**: every scene of a file, or every .blend of a folder

**Get Ichno PRO:** https://ely29.gumroad.com/l/ichno-pro

> This repository holds the issue tracker, the release notes and the documentation of Ichno PRO. The add-on itself is delivered through Gumroad.

## Install
1. Disable the free Ichno if it is installed (one edition at a time).
2. Blender ‣ Edit ‣ Preferences ‣ Add-ons ‣ ⌄ ‣ **Install from Disk**, then pick the `ichno_pro-x.y.z.zip` file.
3. The **Ichno** tab appears in the 3D Viewport sidebar (N).

Blender 4.2 or newer. Windows, macOS and Linux.

## Documentation
- [Ichno PRO features](https://github.com/Elyh29/ichno/wiki/Ichno-PRO)
- Everything shared with the free edition (views, sheets, title block, dimensions, bill of materials): [Ichno wiki](https://github.com/Elyh29/ichno/wiki)

## Screenshots
| | |
|---|---|
| ![DXF export with 5 layers at real size](images/pro2.png) | ![Balloons linked to the bill of materials, exported to Excel](images/pro3.png) |
| ![Manual dimensions](images/pro4.png) | ![Ichno vs Ichno PRO feature comparison](images/pro5.png) |

## Coming next
Already built and in testing, out in the next weeks:

![Section views in DXF: the hatching on its own HATCH layer, real size 1:1](images/coming-pro-dxf.png)

![ISO 2768 general tolerances saved in title block templates](images/coming-pro-templates.png)

![Section views: cutting plane placed in the 3D View with a live hatched preview](images/coming-section-views.png)

## Roadmap
**A new version every week**, on Sundays, free and PRO together. Target dates, they may change.

![Ichno roadmap: a new version of Ichno and Ichno PRO every week from Nov 8 to Dec 20, then 2027](images/roadmap.png)

| Date | Version | Free and PRO | PRO only |
|---|---|---|---|
| Nov 8 | 1.0.6 · PRO 1.0.4 | ISO 2768 tolerances with a table of deviations, ISO small dimensions, F1 help, SVG layers | Title block templates save the tolerance classes |
| Nov 15 | 1.0.7 · PRO 1.0.5 | Section views with ISO hatching, cutting plane placed in the 3D View | HATCH layer in DXF, custom BOM columns |
| Nov 22 | 1.0.8 · PRO 1.0.6 | Manual and angle dimensions, Ø, R and □ symbols | Radius and diameter, dimension tolerances |
| Nov 29 | 1.0.9 · PRO 1.0.7 | Notes with leaders, dimension styles, revision table | Free text ("4 ×", "TYP."), reference dimensions |
| Dec 6 | 1.0.10 · PRO 1.0.8 | Centre lines, hole dimensions and spacing, chamfers "C2" | Hole table, ISO fits (H7, g6) |
| Dec 13 | 1.0.11 · PRO 1.0.9 | Views from a Blender camera, shaded views, edge conditions | Half sections, ordinate dimensions, mass and material |
| Dec 20 | 1.0.12 · PRO 1.0.10 | Country setting, first national update for Japan (JIS, Japanese interface and drawings) | Hatching by material |
| 2027 | | More countries (DIN, GB/T, ASME Y14.1) and languages (Spanish, Portuguese) | Broken and local sections, detail views, GD&T and surface finish, title block layouts |

Missing something for your drawings? Open a [feature request](../../issues/new/choose).


## Release notes
See [CHANGELOG.md](CHANGELOG.md). A new version comes out every week.

## Support
- **Bug or idea:** open an [issue](../../issues/new/choose).
- **Purchase, licence or download:** reply to your Gumroad receipt.
