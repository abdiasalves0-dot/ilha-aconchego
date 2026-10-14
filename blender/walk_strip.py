"""Tira de quadros do ciclo de caminhada (mesma IK do jogo) para conferir o desenho do passo.
Uso: blender -b -P walk_strip.py -- saida.png"""
import bpy, sys, os, math
out = sys.argv[sys.argv.index("--") + 1]
ROOT = r"C:\Users\sambalele\animalcrossing"
D = os.path.join(ROOT, "assets", "models", "char2")
bpy.ops.object.select_all(action="SELECT"); bpy.ops.object.delete()
def hexlin(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return [((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c] + [1]
PIECES = ["body", "top_moletom:#f4f1ea", "bottom_calca:#6fa8dc", "shoes_tenis"]
N = 8
objs_by_frame = []
for i in range(N):
    before = set(bpy.data.objects)
    for piece in PIECES:
        pid, _, color = piece.partition(":")
        mb = set(bpy.data.materials)
        bpy.ops.import_scene.gltf(filepath=os.path.join(D, pid + ".glb"))
        if color:
            for m in set(bpy.data.materials) - mb:
                b = m.node_tree.nodes.get("Principled BSDF"); mix = m.node_tree.nodes.new("ShaderNodeMix")
                mix.data_type = "RGBA"; mix.blend_type = "MULTIPLY"; mix.inputs["Factor"].default_value = 1.0; mix.inputs[7].default_value = hexlin(color)
                if b.inputs["Base Color"].links: m.node_tree.links.new(b.inputs["Base Color"].links[0].from_socket, mix.inputs[6])
                m.node_tree.links.new(mix.outputs[2], b.inputs["Base Color"])
    new = set(bpy.data.objects) - before
    for o in new:
        if o.parent is None: o.location.y -= i * 0.9
    objs_by_frame.append(new)

def foot(phi):
    phi %= 1.0
    ease = lambda x: x * x * (3 - 2 * x)
    if phi < 0.55:
        u = phi / 0.55; return 1 - 2 * u, 0.0, -0.15 + (0.4 + 0.15) * u * u
    s = (phi - 0.55) / 0.45
    return -1 + 2 * ease(s), math.sin(math.pi * s) ** 0.9, 0.4 + (-0.15 - 0.4) * ease(min(1, s * 1.3))

# medidas do esqueleto de uma das armaduras
a0 = [o for o in objs_by_frame[0] if o.type == "ARMATURE"][0]
bpy.context.view_layer.update()
bone = lambda n: a0.data.bones[n]
Wm = a0.matrix_world
hip = Wm @ bone("FootL").head_local; knee = Wm @ bone("KneeL").head_local; ank = Wm @ bone("AnkleL").head_local
L1 = (hip - knee).length; L2 = (knee - ank).length; H = hip.z - ank.z
print("INFO L1 %.3f L2 %.3f H %.3f" % (L1, L2, H))
a = 1.0; run = 0.0
for i, objs in enumerate(objs_by_frame):
    ph = i / N
    arm = [o for o in objs if o.type == "ARMATURE"]
    dip = (1 - math.cos(4 * math.pi * ph)) * 0.5
    crouch = H * a * (0.05 + 0.11 * (1 - dip)); reach = H * 0.5 * a; liftH = H * 0.22 * a
    for ar in arm:
        ar.location.z += -crouch
        pb = ar.pose.bones
        for side, off in (("L", 0.0), ("R", 0.5)):
            f, up, pitch = foot(ph + off)
            zf = f * reach; h = max(0.05, H - crouch - up * liftH)
            d = min(math.hypot(zf, h), (L1 + L2) * 0.999)
            cosK = max(-1, min(1, (L1 * L1 + L2 * L2 - d * d) / (2 * L1 * L2))); beta = math.pi - math.acos(cosK)
            alpha = math.acos(max(-1, min(1, (L1 * L1 + d * d - L2 * L2) / (2 * L1 * d))))
            gamma = math.atan2(zf, h) + alpha
            for n, ang in (("Foot" + side, -gamma), ("Knee" + side, beta), ("Ankle" + side, pitch * a - (-gamma + beta))):
                b = pb[n]; b.rotation_mode = "XYZ"; b.rotation_euler = (ang, 0, 0)
        g = math.cos(2 * math.pi * (ph - 0.07)); armA = 0.6
        swL, swR = armA * g, -armA * g
        for n, ang in (("ArmL", swL), ("ArmR", swR), ("ElbowL", -(0.18 + max(0, -swL) * 0.9)), ("ElbowR", -(0.18 + max(0, -swR) * 0.9))):
            b = pb[n]; b.rotation_mode = "XYZ"; b.rotation_euler = (ang, 0, 0)
bpy.context.view_layer.update()
sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items] else "BLENDER_EEVEE"
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.55, 0.58, 0.62, 1)
sun = bpy.data.objects.new("s", bpy.data.lights.new("s", "SUN")); sc.collection.objects.link(sun); sun.data.energy = 3; sun.rotation_euler = (math.radians(50), 0, math.radians(-30))
cam = bpy.data.objects.new("c", bpy.data.cameras.new("c")); sc.collection.objects.link(cam); sc.camera = cam
cam.data.type = "ORTHO"; cam.data.ortho_scale = N * 0.9 + 0.2
sc.render.resolution_x, sc.render.resolution_y = 1900, 520
cam.location = (10, -(N - 1) * 0.9 / 2, 0.5); cam.rotation_euler = (math.radians(90), 0, math.radians(90))
sc.render.filepath = out; bpy.ops.render.render(write_still=True)
