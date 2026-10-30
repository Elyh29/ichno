import importlib.util
import json
import os
import sys
import traceback

argv = sys.argv[sys.argv.index("--") + 1:]
OUT = argv[0]


def progress(frac, msg):
    print(f"PLAN_PROGRESS\t{frac:.3f}\t{msg}", flush=True)


try:
    def load(name, **given):
        spec = importlib.util.spec_from_file_location(name, os.path.join(os.path.dirname(os.path.abspath(__file__)), name + ".py"))
        mod = importlib.util.module_from_spec(spec)
        mod.__dict__.update(given)
        spec.loader.exec_module(mod)
        return mod
    planengine = load("planengine", planlayout=load("planlayout"))
    with open(argv[1], encoding="utf-8") as f:
        SPEC = json.load(f)
    res = {"ok": True, **planengine.run(SPEC, OUT, progress)}
except BaseException as e:
    traceback.print_exc()
    sys.stdout.flush()
    res = {"ok": False, "error": (f"{type(e).__name__}: {e}")[:500]}
with open(os.path.join(OUT, "result.json"), "w", encoding="utf-8") as f:
    json.dump(res, f, ensure_ascii=False)
