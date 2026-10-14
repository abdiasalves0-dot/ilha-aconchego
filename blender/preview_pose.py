"""Pose extrema (passo + bracos) para procurar costuras/deformacoes. Uso: blender -b -P preview_pose.py -- saida.png peca,peca:cor ..."""
import bpy, sys, os, math
argv = sys.argv[sys.argv.index("--") + 1:]
out, pieces = argv[0], argv[1:]
ROOT = r"C:\Users\sambalele\animalcrossing"
D = os.path.join(ROOT, "assets", "models", "char2")
bpy.ops.object.select_all(action="SELECT"); bpy.ops.object.delete()
def hexlin(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return [((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c] + [1]
first = True
for piece in ["body"] + pieces:
    pid, _, color = piece.partition(":")
    before = set(bpy.data.materials)
    bpy.ops.import_scene.gltf(filepath=os.path.join(D, pid + ".glb"))
    if color:
        for m in set(bpy.data.materials) - before:
            b = m.node_tree.nodes.get("Principled BSDF"); mix = m.node_tree.nodes.new("ShaderNodeMix")
            mix.data_type = "RGBA"; mix.blend_type = "MULTIPLY"; mix.inputs["Factor"].default_value = 1.0; mix.inputs[7].default_value = hexlin(color)
            if b.inputs["Base Color"].links: m.node_tree.links.new(b.inputs["Base Color"].links[0].from_socket, mix.inputs[6])
            m.node_tree.links.new(mix.outputs[2], b.inputs["Base Color"])
# poses: gira os OSSOS (todas as armaduras importadas recebem a mesma pose)
arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
print("INFO armaduras", len(arms))
POSE = {"FootL": (-35, 0, 0), "FootR": (30, 0, 0), "KneeL": (10, 0, 0), "KneeR": (60, 0, 0), "AnkleL": (30, 0, 0), "AnkleR": (-35, 0, 0),
        "ArmL": (-35, 0, 0), "ArmR": (35, 0, 0), "ElbowL": (-20, 0, 0), "ElbowR": (-70, 0, 0)}
if os.environ.get("POSE_EXTRA"):
    POSE = {"FootL": (-50, 0, 0), "FootR": (40, 0, 0), "KneeL": (5, 0, 0), "KneeR": (90, 0, 0), "AnkleL": (40, 0, 0), "AnkleR": (-60, 0, 0), "ArmL": (-60, 0, 0), "ArmR": (60, 0, 0), "ElbowL": (-30, 0, 0), "ElbowR": (-100, 0, 0)}
for a_ in arms:
    for pb in a_.pose.bones:
        base = pb.name.split(".")[0]
        if base in POSE:
            print("POSE", base)
            pb.rotation_mode = "XYZ"
            pb.rotation_euler = tuple(math.radians(c) for c in POSE[base])
bpy.context.view_layer.update()
sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items] else "BLENDER_EEVEE"
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.45, 0.46, 0.5, 1)
sun = bpy.data.objects.new("s", bpy.data.lights.new("s", "SUN")); sc.collection.objects.link(sun); sun.data.energy = 3; sun.rotation_euler = (math.radians(50), 0, math.radians(-30))
cam = bpy.data.objects.new("c", bpy.data.cameras.new("c")); sc.collection.objects.link(cam); sc.camera = cam
cam.data.type = "ORTHO"; cam.data.ortho_scale = 2.0
sc.render.resolution_x, sc.render.resolution_y = 600, 700
for nm, ang, cz, sc_ in (("side", 90, 0.7, 2.0), ("34", 35, 0.7, 2.0), ("legs", 90, 0.35, 1.0)):
    a = math.radians(ang); cam.data.ortho_scale = sc_
    cam.location = (math.sin(a) * 10, -math.cos(a) * 10, cz); cam.rotation_euler = (math.radians(90), 0, a)
    sc.render.filepath = out.replace(".png", "_" + nm + ".png"); bpy.ops.render.render(write_still=True)
