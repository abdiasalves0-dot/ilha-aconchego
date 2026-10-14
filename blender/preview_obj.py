"""Previa de um OBJ texturizado (frente, lado, 3/4).  Uso: blender -b -P preview_obj.py -- arquivo.obj prefixo"""
import bpy, sys, math
from mathutils import Vector
argv = sys.argv[sys.argv.index("--") + 1:]
src, out = argv[0], argv[1]
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()
bpy.ops.wm.obj_import(filepath=src)
o = [o for o in bpy.context.selected_objects if o.type == "MESH"][0]
bpy.context.view_layer.objects.active = o
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
vs = [v.co for v in o.data.vertices]
mn = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
mx = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
print("INFO bbox", tuple(round(c, 3) for c in mn), tuple(round(c, 3) for c in mx))
sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sc.display.shading.light = "STUDIO"
sc.display.shading.color_type = "TEXTURE"
sc.render.resolution_x, sc.render.resolution_y = 600, 800
cam = bpy.data.objects.new("c", bpy.data.cameras.new("c")); sc.collection.objects.link(cam); sc.camera = cam
cam.data.type = "ORTHO"
size = max(mx - mn); cam.data.ortho_scale = size * 1.15
c = (mn + mx) / 2
for name, ang in (("front", 0), ("side", 90), ("34", 35)):
    a = math.radians(ang)
    cam.location = c + Vector((math.sin(a), -math.cos(a), 0)) * size * 3
    cam.rotation_euler = (math.radians(90), 0, a)
    sc.render.filepath = out + "_" + name + ".png"
    bpy.ops.render.render(write_still=True)
