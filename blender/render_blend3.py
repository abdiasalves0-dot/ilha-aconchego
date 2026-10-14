import bpy, math, sys
out = sys.argv[sys.argv.index("--") + 1]
sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items] else "BLENDER_EEVEE"
for o in bpy.data.objects:
    if o.type == "ARMATURE":
        o.data.pose_position = "REST"
    if o.type == "LIGHT" or o.name in ("uzi1",) or o.name.startswith(("pCube", "pCyl", "pistol", "barrel", "Base_metal", "Text")) or o.type in ("FONT", "CURVE"):
        o.hide_render = True
sc.frame_set(1)
w = bpy.data.worlds.new("w2"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.35, 0.35, 0.37, 1); w.node_tree.nodes["Background"].inputs[1].default_value = 1.0
sun = bpy.data.objects.new("s", bpy.data.lights.new("s", "SUN")); sc.collection.objects.link(sun); sun.data.energy = 3; sun.rotation_euler = (math.radians(50), 0, math.radians(-25))
cam = bpy.data.objects.new("c2", bpy.data.cameras.new("c2")); sc.collection.objects.link(cam); sc.camera = cam
cam.data.type = "ORTHO"; cam.data.ortho_scale = 6.0
sc.render.resolution_x, sc.render.resolution_y = 1400, 900
cam.location = (-0.3, -12, 1.4); cam.rotation_euler = (math.radians(90), 0, 0)
sc.render.filepath = out + "_rest.png"; bpy.ops.render.render(write_still=True)
# lista quem aparece onde (bbox mundial) em repouso
bpy.context.view_layer.update()
for o in bpy.data.objects:
    if o.type == "MESH" and not o.hide_render and o.dimensions.length > 0:
        from mathutils import Vector
        bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
        print("POS", o.name, "x[%.2f,%.2f] z[%.2f,%.2f]" % (min(v.x for v in bb), max(v.x for v in bb), min(v.z for v in bb), max(v.z for v in bb)))
