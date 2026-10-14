import bpy, sys, math
from mathutils import Vector
argv = sys.argv[sys.argv.index("--") + 1:]
src, out = argv[0], argv[1]
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()
bpy.ops.wm.stl_import(filepath=src)
o = bpy.context.selected_objects[0]
me = o.data
vs = [o.matrix_world @ v.co for v in me.vertices]
mn = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
mx = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
print("INFO verts", len(me.vertices), "faces", len(me.polygons), "min", tuple(round(c, 3) for c in mn), "max", tuple(round(c, 3) for c in mx))
print("INFO attrs", [a.name for a in me.attributes], "uv", [u.name for u in me.uv_layers])
sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sc.display.shading.light = "STUDIO"
sc.render.resolution_x, sc.render.resolution_y = 600, 800
cam = bpy.data.objects.new("c", bpy.data.cameras.new("c")); sc.collection.objects.link(cam); sc.camera = cam
cam.data.type = "ORTHO"
size = max(mx - mn)
cam.data.ortho_scale = size * 1.15
c = (mn + mx) / 2
for name, (d, rot) in {"front_y": (Vector((0, -1, 0)), (math.radians(90), 0, 0)), "front_x": (Vector((1, 0, 0)), (math.radians(90), 0, math.radians(90))),
                       "top": (Vector((0, 0, 1)), (0, 0, 0))}.items():
    cam.location = c + d * size * 3
    cam.rotation_euler = rot
    sc.render.filepath = out + "_" + name + ".png"
    bpy.ops.render.render(write_still=True)
