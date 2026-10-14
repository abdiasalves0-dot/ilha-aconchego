"""Close dos pes (lado e 3/4). Uso: blender -b -P preview_feet.py -- saida.png peca1,peca2 [peca1,...]"""
import bpy, sys, os, math
argv = sys.argv[sys.argv.index("--") + 1:]
out, combos = argv[0], argv[1:]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "assets", "models", "char")
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()
for i, combo in enumerate(combos):
    before = set(bpy.data.objects)
    for pid in ["body"] + [c for c in combo.split(",") if c]:
        bpy.ops.import_scene.gltf(filepath=os.path.join(D, pid + ".glb"))
    for o in set(bpy.data.objects) - before:
        if o.parent is None:
            o.location.y -= i * 1.2
sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items] else "BLENDER_EEVEE"
sc.render.resolution_x, sc.render.resolution_y = 420 * len(combos), 420
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.45, 0.45, 0.47, 1)
sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); sc.collection.objects.link(sun)
sun.data.energy = 3.0; sun.rotation_euler = (math.radians(50), 0, math.radians(-30))
cam = bpy.data.objects.new("c", bpy.data.cameras.new("c")); sc.collection.objects.link(cam); sc.camera = cam
cam.data.type = "ORTHO"; cam.data.ortho_scale = 1.2 * len(combos)
cy = -(len(combos) - 1) * 1.2 / 2
for name, ang in (("side", 90),):
    a = math.radians(ang)
    cam.location = (math.sin(a) * 10, cy - math.cos(a) * 10, 0.35)
    cam.rotation_euler = (math.radians(90), 0, a)
    sc.render.filepath = out.replace(".png", "_" + name + ".png")
    bpy.ops.render.render(write_still=True)
