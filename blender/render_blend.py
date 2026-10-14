import bpy, math, sys
from mathutils import Vector
out = sys.argv[sys.argv.index("--") + 1]
sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items] else "BLENDER_EEVEE"
sc.render.resolution_x, sc.render.resolution_y = 1100, 800
print("INFO cena camera", sc.camera.name if sc.camera else None, "frame", sc.frame_current, sc.frame_start, sc.frame_end)
sc.render.filepath = out + "_cam.png"
bpy.ops.render.render(write_still=True)
# vista frontal e lateral do personagem (sem armas/curvas)
for o in bpy.data.objects:
    if o.name in ("uzi1",) or o.name.startswith(("pCube", "pCyl", "pistol", "barrel", "Base_metal", "Text")) or o.type == "FONT":
        o.hide_render = True
arm = bpy.data.objects["Armature"]
cam = bpy.data.objects.new("c2", bpy.data.cameras.new("c2")); sc.collection.objects.link(cam); sc.camera = cam
cam.data.type = "ORTHO"; cam.data.ortho_scale = 3.2
sc.render.resolution_x, sc.render.resolution_y = 900, 900
for name, loc, rot in (("front", (arm.location.x, -9, 1.5), (math.radians(90), 0, 0)), ("side", (arm.location.x + 9, 0, 1.5), (math.radians(90), 0, math.radians(90)))):
    cam.location = loc; cam.rotation_euler = rot
    sc.render.filepath = out + "_" + name + ".png"
    bpy.ops.render.render(write_still=True)
