import bpy, sys, math
argv = sys.argv[sys.argv.index("--") + 1:]
src, out = argv
bpy.ops.object.select_all(action="SELECT"); bpy.ops.object.delete()
bpy.ops.import_scene.gltf(filepath=src)
arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
print("INFO armaduras", len(arms), "ossos", sum(len(a.data.bones) for a in arms), "malhas", [o.name for o in bpy.data.objects if o.type == "MESH"])
sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items] else "BLENDER_EEVEE"
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.3, 0.3, 0.32, 1)
sun = bpy.data.objects.new("s", bpy.data.lights.new("s", "SUN")); sc.collection.objects.link(sun); sun.data.energy = 3; sun.rotation_euler = (math.radians(50), 0, math.radians(-25))
cam = bpy.data.objects.new("c", bpy.data.cameras.new("c")); sc.collection.objects.link(cam); sc.camera = cam
cam.data.type = "ORTHO"; cam.data.ortho_scale = 2.4
sc.render.resolution_x, sc.render.resolution_y = 700, 800
cam.location = (0, -9, 0.95); cam.rotation_euler = (math.radians(90), 0, 0)
sc.render.filepath = out; bpy.ops.render.render(write_still=True)
