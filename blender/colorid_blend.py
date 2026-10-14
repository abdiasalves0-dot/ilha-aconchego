import bpy, math, colorsys, sys
from mathutils import Vector
out = sys.argv[sys.argv.index("--") + 1]
sc = bpy.context.scene
for o in bpy.data.objects:
    if o.type == "ARMATURE": o.data.pose_position = "REST"
sc.frame_set(1)
names = []
for o in bpy.data.objects:
    if o.type == "MESH" and o.dimensions.length > 0:
        bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
        cx = sum(v.x for v in bb) / 8
        if abs(cx) < 1.0 and not o.name.startswith(("pCube", "pCyl", "pistol", "barrel", "Base_metal", "uzi", "Text", "Material_Preview")):
            names.append(o.name)
        else:
            o.hide_render = True
    elif o.type in ("LIGHT", "CURVE", "FONT"):
        o.hide_render = True
for i, n in enumerate(names):
    o = bpy.data.objects[n]
    r, g, b = colorsys.hsv_to_rgb(i / len(names), 0.85, 0.95)
    o.color = (r, g, b, 1)
    print("COR", n, "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255)))
sc.render.engine = "BLENDER_WORKBENCH"
sc.display.shading.light = "FLAT"; sc.display.shading.color_type = "OBJECT"
w = bpy.data.worlds.new("w"); sc.world = w
cam = bpy.data.objects.new("c", bpy.data.cameras.new("c")); sc.collection.objects.link(cam); sc.camera = cam
cam.data.type = "ORTHO"; cam.data.ortho_scale = 2.7
sc.render.resolution_x, sc.render.resolution_y = 900, 1000
for nm, loc, rot in (("front", (0, -12, 1.55), (math.radians(90), 0, 0)), ("side", (12, 0, 1.55), (math.radians(90), 0, math.radians(90)))):
    cam.location = loc; cam.rotation_euler = rot
    sc.render.filepath = out + "_" + nm + ".png"; bpy.ops.render.render(write_still=True)
