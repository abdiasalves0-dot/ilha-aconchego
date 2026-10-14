"""Gera vendor_ref/base_blend/clean.blend: so o boneco do centro, com modificadores aplicados (pose de repouso),
sem esqueleto/armas/luzes. Uso: blender -b vendor_ref/base_blend/base.blend -P blender/clean_base_blend.py"""
import bpy, math
from mathutils import Vector
ROOT = r"C:\Users\sambalele\animalcrossing"
import sys
ARM_DEG = float(sys.argv[sys.argv.index("--") + 1]) if "--" in sys.argv else 62.0
arm = bpy.data.objects["Armature"]
arm.data.pose_position = "POSE"
bpy.context.scene.frame_set(1)
if arm.animation_data:
    arm.animation_data.action = None
for pb in arm.pose.bones:   # zera qualquer pose de animacao (os bracos seguravam armas)
    pb.rotation_mode = "XYZ"
    pb.rotation_euler = (0, 0, 0); pb.location = (0, 0, 0); pb.scale = (1, 1, 1)
bpy.context.view_layer.update()


def tip(bn):
    return arm.matrix_world @ arm.pose.bones[bn].tail


def lower(root_bone, hand_bone, sign):
    """Gira o osso do ombro para baixar o braco: escolhe o eixo/sinal que leva a mao para baixo, no plano do corpo."""
    pb = arm.pose.bones[root_bone]
    base = tip(hand_bone)
    best = None
    for ax in range(3):
        for sg in (-1, 1):
            e = [0.0, 0.0, 0.0]; e[ax] = sg * math.radians(ARM_DEG)
            pb.rotation_euler = tuple(e)
            bpy.context.view_layer.update()
            t = tip(hand_bone)
            score = (base.z - t.z) - 3.0 * abs(t.y - base.y)
            if best is None or score > best[0]:
                best = (score, tuple(e))
    pb.rotation_euler = best[1]
    bpy.context.view_layer.update()
    print("OSSO", root_bone, "rot", [round(math.degrees(c)) for c in best[1]], "mao", tuple(round(c, 2) for c in tip(hand_bone)), flush=True)


lower("Bone.021", "Bone.023", 1)
lower("Bone.024", "Bone.026", -1)
dg = bpy.context.evaluated_depsgraph_get()
KEEP = {"Cube.005": "head", "Circle.003": "ears", "Cube.006": "nose", "Circle.004": "hands", "Cube.008": "hoodie", "Cube.007": "pants",
        "Plane.003": "shoeL", "Plane.004": "shoeR", "Cube.010": "cap", "Circle.005": "strap", "Cube.009": "bag", "Sphere": "sphere", "Cube.001": "nose0"}
made = {}


def evaluate(o):
    ev = o.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=bpy.context.evaluated_depsgraph_get())
    me.transform(o.matrix_world)
    return me


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


# 1) avalia tudo na pose dos bracos baixos
posed = {}
for name, role in KEEP.items():
    posed[role] = evaluate(bpy.data.objects[name])
# 2) avalia de novo em repouso (T-pose) com a MESMA pilha de modificadores -> mesma topologia, vertice a vertice
saved = {pb.name: tuple(pb.rotation_euler) for pb in arm.pose.bones}
for pb in arm.pose.bones:
    pb.rotation_euler = (0, 0, 0)
bpy.context.view_layer.update()
rest = {}
for name, role in KEEP.items():
    rest[role] = evaluate(bpy.data.objects[name])
for role in KEEP.values():
    me_p, me_r = posed[role], rest[role]
    assert len(me_p.vertices) == len(me_r.vertices), (role, len(me_p.vertices), len(me_r.vertices))
    if role == "hoodie":
        # tronco fica em repouso (sem o "afunilamento" causado pelos pesos do braco); so a regiao do braco acompanha a pose
        for vp, vr in zip(me_p.vertices, me_r.vertices):
            f = smooth((abs(vr.co.x) - 0.20) / 0.10)
            vp.co = vr.co.lerp(vp.co, f)
        me_p.update()
    elif role not in ("hands", "strap", "bag"):
        for vp, vr in zip(me_p.vertices, me_r.vertices):
            vp.co = vr.co
        me_p.update()
    # guarda a posicao em T-pose de cada vertice: os pesos de skinning usam ela (manga x tronco ficam inequivocos)
    att = me_p.attributes.new("restpos", "FLOAT_VECTOR", "POINT")
    for i, vr in enumerate(me_r.vertices):
        att.data[i].vector = vr.co
    made[role] = (me_p, [m.name if m else None for m in bpy.data.objects[[k for k, v in KEEP.items() if v == role][0]].data.materials])
# nova cena limpa
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
for role, (me, mats) in made.items():
    ob = bpy.data.objects.new(role, me)
    bpy.context.scene.collection.objects.link(ob)
    bb = [Vector(c) for c in ob.bound_box]
    print("PARTE", role, "verts", len(me.vertices), "x[%.3f,%.3f] y[%.3f,%.3f] z[%.3f,%.3f]" % (min(v.x for v in bb), max(v.x for v in bb), min(v.y for v in bb), max(v.y for v in bb), min(v.z for v in bb), max(v.z for v in bb)), "mats", mats)
bpy.ops.wm.save_as_mainfile(filepath=ROOT + r"\vendor_ref\base_blend\clean.blend")
print("OK clean.blend")
