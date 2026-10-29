import datetime
import json
import collections
import os
import queue
import shutil
import subprocess
import tempfile
import sys
import threading

from mathutils import Vector

import bpy

from .i18n import drawing_lang, rpt, tr
from . import chains, titleblock
from .sheets import objects_to_draw, problems, sheet_objects, sheet_views

HERE = os.path.dirname(os.path.abspath(__file__))
_job = {}


def output_folder(s):
    d = bpy.path.abspath(s.folder) if s.folder else ""
    if not d or (s.folder.startswith("//") and not bpy.data.filepath):
        d = os.path.join(os.path.expanduser("~"), "Plan")
    return d


def redraw():
    for w in bpy.context.window_manager.windows:
        for a in w.screen.areas:
            if a.type == "VIEW_3D":
                a.tag_redraw()


def reader(proc, lines, log):
    for line in proc.stdout:
        if line.startswith("PLAN_PROGRESS\t"):
            _, f, msg = line.rstrip("\n").split("\t", 2)
            lines.put((float(f), msg))
        else:
            log.append(line.rstrip("\n"))


def save_log(res):
    path = os.path.join(_job["folder"], "ichno-log.txt")
    try:
        os.makedirs(_job["folder"], exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"Ichno {_version()} · Blender {bpy.app.version_string} · {sys.platform}\n{res.get('error', '')}\n\n")
            f.write("\n".join(_job.get("log", [])))
        res["error"] = f"{res['error']} — {rpt('log')}: {path}"
    except OSError:
        pass
    return res


def _version():
    try:
        with open(os.path.join(HERE, "blender_manifest.toml"), encoding="utf-8") as f:
            return next(ln.split('"')[1] for ln in f if ln.startswith("version"))
    except (OSError, StopIteration, IndexError):
        return "?"


def start(context):
    s, job = context.scene.ichno_settings, context.window_manager.ichno_job
    names = objects_to_draw(context, s)
    if not names:
        return rpt("Nothing to draw")
    for o in context.objects_in_mode:
        o.update_from_editmode()
    tmp = tempfile.mkdtemp(prefix="plan-")
    blend = os.path.join(tmp, "scene.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend, copy=True, check_existing=False)
    spec = {"only": names, "sheet": s.sheet, "land": s.landscape, "scale": s.scale or "auto",
            "proj": s.projection, "front": s.front, "unit": s.unit, "unit2": s.unit2 if s.unit2 != s.unit else "none", "author": s.author, "rev": s.revision, "logo": bpy.path.abspath(s.logo) if s.logo else "", "iso": s.iso, "hidden": s.hidden, "iso_hidden": s.iso_hidden, "axes": s.axes, "fast": s.fast,
            "weight": s.weight, "angle": s.angle, "title": s.title or "—", "project": s.project or "—", "name": s.number or "plan",
            "file": bpy.path.basename(bpy.data.filepath) or "—", "date": datetime.date.today().strftime("%m/%d/%Y" if s.unit == "in" else "%d/%m/%Y"),
            "brand": s.company, "lang": drawing_lang(s.lang), "brand_sub": ""}
    spec["iso_view"] = s.iso_view
    sp = context.space_data if context.space_data and context.space_data.type == "VIEW_3D" else next(
        (a.spaces[0] for a in context.screen.areas if a.type == "VIEW_3D"), None) if context.screen else None
    r3d = sp.region_3d if sp else None
    if s.iso_view == "viewport" and r3d:
        q = r3d.view_rotation
        spec["iso_dir"], spec["iso_up"] = list(q @ Vector((0, 0, -1))), list(q @ Vector((0, 1, 0)))
    if s.bom_by != "none":
        spec["bom"] = {"by": s.bom_by, "prop": s.bom_prop}
    spec["views"] = [k for k in ("front", "side", "top") if getattr(s, "view_" + k)]
    spec["chains"] = chains.spec(s, set(names))
    spec.update(titleblock.spec(s))
    if s.grid_mode != "none":
        spec["grid"] = {"mode": s.grid_mode, "step": s.grid_step, "views": [v for v in ("top", "front", "side") if getattr(s, "grid_" + v)],
                        "origin": list(s.grid_origin.matrix_world.translation) if s.grid_origin else [0, 0, 0]}
    if s.use_sheets and s.sheets:
        shown = set(names)
        spec["sheets"] = [{"name": sh.name, "only": sheet_objects(sh, shown), "views": sheet_views(sh)} for sh in s.sheets]
        empty = [sh["name"] for sh in spec["sheets"] if not sh["only"]]
        if empty:
            shutil.rmtree(tmp, ignore_errors=True)
            return rpt("Sheet “{}”: {}", empty[0], tr("nothing to draw (check Objects)"))
    with open(os.path.join(tmp, "spec.json"), "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False)
    cmd = [bpy.app.binary_path, "-b", blend, "--factory-startup", "--disable-autoexec", "-noaudio",
           "--python", os.path.join(HERE, "runner.py"), "--", tmp, os.path.join(tmp, "spec.json")]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    lines, log = queue.Queue(), collections.deque(maxlen=400)
    threading.Thread(target=reader, args=(proc, lines, log), daemon=True).start()
    _job.update(proc=proc, tmp=tmp, lines=lines, log=log, cancel=False, folder=output_folder(s), open=s.open_pdf)
    job.running, job.progress, job.message = True, 0, tr("Starting…")
    return None


def collect():
    try:
        with open(os.path.join(_job["tmp"], "result.json"), encoding="utf-8") as f:
            res = json.load(f)
    except (OSError, ValueError):
        last = next((ln for ln in reversed(_job.get("log", [])) if ln.strip()), "")
        return save_log({"ok": False, "error": rpt("Blender stopped before the end (code {})", _job["proc"].returncode) + (f" : {last[:200]}" if last else "")})
    if not res.get("ok"):
        return save_log({"ok": False, "error": res.get("error") or rpt("Error")})
    try:
        os.makedirs(_job["folder"], exist_ok=True)
    except OSError as e:
        return {"ok": False, "error": f"{_job['folder']} : {e.strerror or e}"}
    out = []
    for fn in res["files"]:
        dst = copy_free(os.path.join(_job["tmp"], "out", fn), os.path.join(_job["folder"], fn))
        if not dst:
            return {"ok": False, "error": rpt("Cannot write “{}” in {}", fn, _job["folder"])}
        if os.path.basename(dst) != fn:
            res.setdefault("warnings", []).append(rpt("“{}” is open in another program: saved as “{}”", fn, os.path.basename(dst)))
        out.append(dst)
    res["pdf"] = out[0]
    return res


def copy_free(src, dst):
    base, ext = os.path.splitext(dst)
    for i in range(1, 20):
        path = dst if i == 1 else f"{base} ({i}){ext}"
        try:
            shutil.copy2(src, path)
            return path
        except PermissionError:
            continue
        except OSError:
            return None
    return None


class ICHNO_OT_make(bpy.types.Operator):
    """Draw the plan (PDF and SVG) in the background, without changing the scene"""
    bl_idname = "ichno.make"
    bl_label = "Make Plan"

    @classmethod
    def poll(cls, context):
        if context.window_manager.ichno_job.running:
            return False
        s = context.scene.ichno_settings
        own = s.use_sheets and s.sheets and all(sh.own_views for sh in s.sheets)
        if not own and not (s.iso or s.view_front or s.view_side or s.view_top):
            cls.poll_message_set(tr("No view selected (Views panel)"))
            return False
        bad = problems(context, context.scene.ichno_settings)
        if bad:
            cls.poll_message_set(tr("Sheet “{}”: {}", context.scene.ichno_settings.sheets[bad[0][0]].name, bad[0][1]))
            return False
        return True

    def execute(self, context):
        err = start(context)
        if err:
            self.report({"ERROR"}, err)
            return {"CANCELLED"}
        self._timer = context.window_manager.event_timer_add(0.25, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type != "TIMER":
            return {"PASS_THROUGH"}
        job = context.window_manager.ichno_job
        while not _job["lines"].empty():
            job.progress, job.message = _job["lines"].get()
        if _job["cancel"]:
            _job["proc"].kill()
            return self.finish(context, tr("Cancelled"))
        if _job["proc"].poll() is None:
            redraw()
            return {"PASS_THROUGH"}
        try:
            res = collect()
        except Exception as e:
            res = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        if not res["ok"]:
            self.report({"ERROR"}, res["error"])
            return self.finish(context, res["error"])
        for st in res.get("warnings", []):
            self.report({"WARNING"}, st)
        context.window_manager.ichno_job.last = res["pdf"]
        if _job["open"]:
            bpy.ops.wm.path_open(filepath=res["pdf"])
        n = len(res["files"]) - 1
        return self.finish(context, tr("{} sheets in {} s" if n > 1 else "{} sheet in {} s", n, res.get("seconds", 0)))

    def finish(self, context, msg):
        context.window_manager.event_timer_remove(self._timer)
        shutil.rmtree(_job.get("tmp", ""), ignore_errors=True)
        _job.clear()
        job = context.window_manager.ichno_job
        job.running, job.message = False, msg
        redraw()
        return {"FINISHED"}


class ICHNO_OT_cancel(bpy.types.Operator):
    """Stop the plan being drawn"""
    bl_idname = "ichno.cancel"
    bl_label = "Cancel"

    def execute(self, context):
        if _job:
            _job["cancel"] = True
        return {"FINISHED"}


class ICHNO_OT_open(bpy.types.Operator):
    """Open the last plan"""
    bl_idname = "ichno.open"
    bl_label = "Open Last Plan"
    path: bpy.props.StringProperty()

    def execute(self, context):
        bpy.ops.wm.path_open(filepath=self.path)
        return {"FINISHED"}


CLASSES = (ICHNO_OT_make, ICHNO_OT_cancel, ICHNO_OT_open)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)


def unregister():
    if _job.get("proc"):
        _job["proc"].kill()
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
