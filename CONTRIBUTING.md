# Contributing to Ichno

Thanks for helping! Bug reports, drawing examples and ideas are the most useful contributions.

## Report a bug
Open an [issue](../../issues/new/choose) with:
- your Blender version and operating system,
- what you expected and what you got (a screenshot of the drawing helps),
- if possible, a small .blend file that shows the problem,
- the `ichno-log.txt` file written next to the drawing when something fails.

## Suggest a feature
Open an issue first and describe the drawing you need (a sketch or an example from a real drawing is perfect).
Ichno follows ISO and ASME drafting standards: please mention the standard if your request is about one.

## Pull requests
- Open an issue before a large change, so we can agree on the approach.
- Keep the add-on compatible with Blender 4.3 to 5.2 (Python 3.11: no nested identical quotes in f-strings).
- extensions.blender.org rules apply: no `sys.path` / `sys.modules` changes, no `threading` or `queue`, no network access.
- New interface texts need a French translation in `ichno/i18n.py`.
- Contributions are accepted under the GPL-3.0-or-later license.
