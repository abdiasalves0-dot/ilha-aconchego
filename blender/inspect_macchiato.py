import bpy, os
from mathutils import Vector
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()
bpy.ops.wm.obj_import(filepath=os.path.join(ROOT, "vendor_ref", "macchiato", "Macchiato.obj"))
for o in bpy.context.scene.objects:
    if o.type != "MESH":
        continue
    vs = [o.matrix_world @ v.co for v in o.data.vertices]
    mn = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
    mx = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
    print("OBJ", o.name, len(vs), "min", tuple(round(c, 3) for c in mn), "max", tuple(round(c, 3) for c in mx), [m.name for m in o.data.materials], "uv", [u.name for u in o.data.uv_layers])
    # histogramas por Z
    import collections
    h = collections.Counter(int((v.z - mn.z) / (mx.z - mn.z) * 20) for v in vs)
    print("  z-hist", sorted(h.items()))

o = [o for o in bpy.context.scene.objects if o.type == "MESH"][0]
me = o.data
import math
for mi in range(3):
    ps = [Vector(sum((me.vertices[v].co for v in p.vertices), Vector())) / len(p.vertices) for p in me.polygons if p.material_index == mi]
    c = sum(ps, Vector()) / len(ps)
    print("MATCENTER", mi, len(ps), tuple(round(x, 2) for x in c))
print("BAND (z0..z1, min x, max x, min y, max y)")
vs = [v.co for v in me.vertices]
for b in range(0, 18):
    z0, z1 = b, b + 1
    sel = [v for v in vs if z0 <= v.z < z1]
    if sel:
        print("B", z0, round(min(v.x for v in sel), 2), round(max(v.x for v in sel), 2), round(min(v.y for v in sel), 2), round(max(v.y for v in sel), 2), len(sel))
