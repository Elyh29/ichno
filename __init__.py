from . import chains, i18n, ops, props, sheets, titleblock, ui

MODULES = (i18n, props, sheets, chains, titleblock, ops, ui)


def register():
    for m in MODULES:
        m.register()


def unregister():
    for m in reversed(MODULES):
        m.unregister()
