"""Puntuación SL Ready y certificado HTML."""

import datetime
import html
import os

import bpy

from . import edition
from .skeleton import SL_MAX_JOINTS_PER_MESH
from .weights import SL_MAX_MATERIALS, validate_object


def score(stats):
    """Puntuación 0–100 y lista de (penalización, motivo)."""
    pen = []
    if stats["materials"] > SL_MAX_MATERIALS:
        pen.append((25, f"Más de {SL_MAX_MATERIALS} materiales"))
    if not stats["uv"]:
        pen.append((10, "Sin mapa UV"))
    if not stats["scale_ok"]:
        pen.append((8, "Escala sin aplicar"))
    if stats["tris"] > 100000:
        pen.append((12, "Más de 100.000 triángulos (pesado para SL)"))
    elif stats["tris"] > 50000:
        pen.append((5, "Más de 50.000 triángulos"))
    if stats["rigged"]:
        if stats["unweighted"]:
            pen.append((35, f"{stats['unweighted']} vértices sin peso"))
        if stats["joints"] > SL_MAX_JOINTS_PER_MESH:
            pen.append((35, f"{stats['joints']} articulaciones (máx. {SL_MAX_JOINTS_PER_MESH})"))
        if stats["over"]:
            pen.append((5, f"{stats['over']} vértices con más de 4 huesos"))
    return max(0, 100 - sum(p for p, _ in pen)), pen


def grade(value):
    if value >= 95:
        return "S", "Perfecto"
    if value >= 85:
        return "A", "Listo para SL"
    if value >= 70:
        return "B", "Casi listo"
    if value >= 50:
        return "C", "Necesita ajustes"
    return "D", "No se subirá bien"


def text_bar(value, width=20):
    filled = int(round(value / 100 * width))
    return "█" * filled + "░" * (width - filled)


_CSS = """
body{margin:0;background:#05070d;color:#d8e6f3;font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
.wrap{max-width:860px;margin:40px auto;padding:0 20px}
.card{border:1px solid #00e5ff55;border-radius:14px;padding:28px;background:linear-gradient(160deg,#0b1424,#070a12);
box-shadow:0 0 40px #00e5ff22}
h1{margin:0;font-size:26px;letter-spacing:.08em;color:#00e5ff}
.sub{color:#7f93a8;font-size:13px;letter-spacing:.2em;text-transform:uppercase}
.grade{float:right;font-size:64px;font-weight:800;line-height:1;color:#00e5ff;text-shadow:0 0 18px #00e5ff88}
.bar{height:10px;border-radius:6px;background:#132033;overflow:hidden;margin:14px 0 22px}
.bar i{display:block;height:100%;background:linear-gradient(90deg,#00e5ff,#7cff6b)}
table{width:100%;border-collapse:collapse;margin:8px 0 20px}
td{padding:6px 8px;border-bottom:1px solid #18263a}td:first-child{color:#7f93a8}
.ERROR{color:#ff5468}.WARNING{color:#ffc14d}.INFO{color:#7cff6b}
footer{color:#56677a;font-size:12px;margin-top:18px}
"""


def certificate_html(objs, stats_list):
    rows = []
    total = []
    for obj, st in zip(objs, stats_list):
        sc, pen = score(st)
        total.append(sc)
        letter, label = grade(sc)
        checks = validate_object(obj)
        items = "".join(f'<li class="{lvl}">{html.escape(msg)}</li>' for lvl, msg in checks)
        info = [("Triángulos", f"{st['tris']:,}".replace(",", ".")), ("Vértices", f"{st['verts']:,}".replace(",", ".")),
                ("Materiales (caras)", f"{st['materials']} / {SL_MAX_MATERIALS}"), ("UV", "Sí" if st["uv"] else "No")]
        if st["rigged"]:
            info += [("Esqueleto", st["rig"]), ("Articulaciones", f"{st['joints']} / {SL_MAX_JOINTS_PER_MESH}"),
                     ("Vértices sin peso", st["unweighted"])]
        table = "".join(f"<tr><td>{html.escape(str(k))}</td><td>{html.escape(str(v))}</td></tr>" for k, v in info)
        rows.append(f'<div class="card" style="margin-top:22px"><div class="grade">{letter}</div>'
                    f'<div class="sub">{html.escape(label)}</div><h1>{html.escape(obj.name)}</h1>'
                    f'<div class="bar"><i style="width:{sc}%"></i></div><b>{sc}/100</b>'
                    f'<table>{table}</table><ul>{items}</ul></div>')
    avg = int(sum(total) / len(total)) if total else 0
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    return (f"<!doctype html><html lang='es'><meta charset='utf-8'><title>Certificado SL Ready</title>"
            f"<style>{_CSS}</style><div class='wrap'><div class='sub'>SL Rigger · {edition.EDITION_LABEL}</div>"
            f"<h1>CERTIFICADO SL READY · {avg}/100</h1>{''.join(rows)}"
            f"<footer>Generado el {now} · Comprobaciones según los límites del visor de Second Life "
            f"(8 caras, 4 huesos por vértice, {SL_MAX_JOINTS_PER_MESH} articulaciones por malla).</footer></div></html>")


class SLR_OT_certificate(bpy.types.Operator):
    """Genera un certificado HTML con la puntuación y las comprobaciones de las mallas seleccionadas"""
    bl_idname = "slr.certificate"
    bl_label = "Certificado SL Ready"

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    open_after: bpy.props.BoolProperty(name="Abrir al terminar", default=True)

    @classmethod
    def poll(cls, context):
        if not any(o.type == "MESH" for o in context.selected_objects):
            cls.poll_message_set("Selecciona al menos una malla")
            return False
        return True

    def invoke(self, context, event):
        self.filepath = bpy.path.abspath("//") + "certificado_sl.html" if bpy.data.filepath else "certificado_sl.html"
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        from . import hud
        objs = [o for o in context.selected_objects if o.type == "MESH"]
        stats = [hud.analyze(o)[0] for o in objs]
        path = bpy.path.ensure_ext(self.filepath, ".html")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(certificate_html(objs, stats))
        if self.open_after and not bpy.app.background:
            bpy.ops.wm.url_open(url="file://" + os.path.abspath(path))
        self.report({"INFO"}, f"Certificado: {path}")
        return {"FINISHED"}


classes = (SLR_OT_certificate,)
