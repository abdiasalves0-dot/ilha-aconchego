import bpy, math, sys
out = sys.argv[sys.argv.index("--") + 1]
hide = sys.argv[sys.argv.index("--") + 2].split(",") if len(sys.argv) > sys.argv.index("--") + 2 else []
sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items] else "BLENDER_EEVEE"
for o in bpy.data.objects:
    if o.name in hide or o.name in ("nose0", "sphere"): o.hide_render = True
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.4, 0.4, 0.42, 1)
sun = bpy.data.objects.new("s", bpy.data.lights.new("s", "SUN")); sc.collection.objects.link(sun); sun.data.energy = 3; sun.rotation_euler = (math.radians(55), 0, math.radians(160))
cam = bpy.data.objects.new("c", bpy.data.cameras.new("c")); sc.collection.objects.link(cam); sc.camera = cam
cam.data.type = "ORTHO"; cam.data.ortho_scale = 2.4
sc.render.resolution_x, sc.render.resolution_y = 1500, 800
for nm, loc, rot in (("front", (0, 12, 1.45), (math.radians(90), 0, math.radians(180))), ("side", (12, 0, 1.45), (math.radians(90), 0, math.radians(90)))):
    cam.location = loc; cam.rotation_euler = rot
    sc.render.filepath = out + "_" + nm + ".png"; bpy.ops.render.render(write_still=True)
