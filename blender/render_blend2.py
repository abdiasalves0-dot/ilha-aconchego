import bpy, math, sys
from mathutils import Vector
out = sys.argv[sys.argv.index("--") + 1]
sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items] else "BLENDER_EEVEE"
for o in bpy.data.objects:
    if o.type == "LIGHT" or o.name in ("uzi1",) or o.name.startswith(("pCube", "pCyl", "pistol", "barrel", "Base_metal", "Text")) or o.type in ("FONT", "CURVE"):
        o.hide_render = True
sc.frame_set(1)
w = bpy.data.worlds.new("w2"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.7, 0.75, 0.8, 1); w.node_tree.nodes["Background"].inputs[1].default_value = 1.4
sun = bpy.data.objects.new("s", bpy.data.lights.new("s", "SUN")); sc.collection.objects.link(sun); sun.data.energy = 3; sun.rotation_euler = (math.radians(50), 0, math.radians(-25))
cam = bpy.data.objects.new("c2", bpy.data.cameras.new("c2")); sc.collection.objects.link(cam); sc.camera = cam
cam.data.type = "ORTHO"
sc.render.resolution_x, sc.render.resolution_y = 1400, 700
cam.data.ortho_scale = 5.0
cam.location = (-0.9, -9, 1.5); cam.rotation_euler = (math.radians(90), 0, 0)
sc.render.filepath = out + "_front2.png"; bpy.ops.render.render(write_still=True)
cam.location = (-8, -0.3, 1.5); cam.rotation_euler = (math.radians(90), 0, math.radians(-90))
sc.render.filepath = out + "_side2.png"; bpy.ops.render.render(write_still=True)
