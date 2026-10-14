import bpy
from mathutils import Vector
arm = bpy.data.objects["Armature"]
arm.data.pose_position = "REST"
bpy.context.view_layer.update()
mw = arm.matrix_world
for b in arm.data.bones:
    h = mw @ b.head_local; t = mw @ b.tail_local
    print("BONE", b.name, "pai", b.parent.name if b.parent else None, "head (%.2f,%.2f,%.2f) tail (%.2f,%.2f,%.2f)" % (h.x, h.y, h.z, t.x, t.y, t.z))
for n in ("Cube.008", "Circle.004", "Cube.007", "Cube.005"):
    o = bpy.data.objects[n]
    print("VG", n, [g.name for g in o.vertex_groups][:40], "mods", [(m.type, getattr(m, "object", None) and m.object.name) for m in o.modifiers])
