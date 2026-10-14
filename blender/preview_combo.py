"""Renderiza combinacoes do guarda-roupa lado a lado.
Uso: blender -b -P preview_combo.py -- saida.png "hair_curto:#7a4a2c,top_tee_estrela,bottom_short_jeans,shoes_tenis" "..."
"""
import bpy, sys, os, math
from mathutils import Vector
argv = sys.argv[sys.argv.index("--") + 1:]
out, combos = argv[0], argv[1:]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "assets", "models", os.environ.get("CHAR_DIR", "char"))
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()


def hexlin(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return [((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c] + [1]


for i, combo in enumerate(combos):
    before = set(bpy.data.objects)
    for piece in ["body"] + combo.split(","):
        pid, _, color = piece.partition(":")
        mats_before = set(bpy.data.materials)
        bpy.ops.import_scene.gltf(filepath=os.path.join(D, pid + ".glb"))
        if color:
            for m in set(bpy.data.materials) - mats_before:
                nt = m.node_tree
                b = nt.nodes.get("Principled BSDF")
                link = b.inputs["Base Color"].links[0] if b.inputs["Base Color"].links else None
                mix = nt.nodes.new("ShaderNodeMix")
                mix.data_type = "RGBA"
                mix.blend_type = "MULTIPLY"
                mix.inputs["Factor"].default_value = 1.0
                mix.inputs[7].default_value = hexlin(color)
                if link:
                    nt.links.new(link.from_socket, mix.inputs[6])
                nt.links.new(mix.outputs[2], b.inputs["Base Color"])
    new = set(bpy.data.objects) - before
    for o in new:
        if o.parent is None:
            o.location.x += i * 2.2
sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items] else "BLENDER_EEVEE"
sc.render.resolution_x, sc.render.resolution_y = 380 * len(combos), 620
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.8, 0.88, 1.0, 1); w.node_tree.nodes["Background"].inputs[1].default_value = 1.1
sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); sc.collection.objects.link(sun)
sun.data.energy = 3.2; sun.rotation_euler = (math.radians(45), 0, math.radians(-25))
cam = bpy.data.objects.new("c", bpy.data.cameras.new("c")); sc.collection.objects.link(cam); sc.camera = cam
CS = float(os.environ.get("CAM_S", 2.2)); CZ = float(os.environ.get("CAM_Z", 1.2))
cam.data.type = "ORTHO"; cam.data.ortho_scale = CS * len(combos) * 1.02
cx = (len(combos) - 1) * 2.2 / 2
for name, ang in (("front", 0), ("34", 30), ("side", 90), ("back", 180)):
    a = math.radians(ang)
    cam.location = (cx + math.sin(a) * 12, -math.cos(a) * 12, CZ)
    cam.rotation_euler = (math.radians(90), 0, a)
    sc.render.filepath = out.replace(".png", "_" + name + ".png")
    bpy.ops.render.render(write_still=True)
