# SPDX-License-Identifier: GPL-3.0-or-later
# Ichno: registration of the add-on
import bpy

from . import chains, help, i18n, ops, props, sheets, titleblock, ui

try:
    from . import pro
except ImportError:
    pro = None

MODULES = (pro,) * bool(pro) + (i18n, props, sheets, chains, titleblock, ops, ui, help)


def register():
    me = __package__.rsplit(".", 1)[-1]
    other = [k for k in bpy.context.preferences.addons.keys() if k.rsplit(".", 1)[-1] in ("ichno", "ichno_pro") and k.rsplit(".", 1)[-1] != me]
    if other:
        raise RuntimeError(f"Another edition of Ichno is enabled ({other[0].rsplit('.', 1)[-1]}): disable it first (Preferences ‣ Add-ons)")
    for m in MODULES:
        m.register()


def unregister():
    for m in reversed(MODULES):
        m.unregister()
