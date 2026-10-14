"""Protagonista: garoto de cabelo branco espetado, chifres dourados, pele morena,
camisa branca com mangas dobradas, gravata vermelha, colete preto, suspensorios amarelos,
calca xadrez escura com barra dobrada e mocassins pretos. Exporta assets/models/player.glb
Uso: blender -b -P build_hero.py
"""
import bpy, bmesh, os, math, random, importlib.util
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("ba", os.path.join(HERE, "build_assets.py"))
ba = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ba)
mat, tmat, sphere, cyl, torus, pivot, box = ba.mat, ba.tmat, ba.sphere, ba.cyl, ba.torus, ba.pivot, ba.box
OUT = os.path.join(ba.OUT, "player.glb")


def att(o, p):
    bpy.context.view_layer.update()
    o.parent = p
    o.matrix_parent_inverse = p.matrix_world.inverted()


def surf(ob, x, z):
    bpy.context.view_layer.update()
    mw = ob.matrix_world
    inv = mw.inverted()
    o_l = inv @ Vector((x, -4.0, z))
    d_l = (inv.to_3x3() @ Vector((0, 1, 0))).normalized()
    hit, loc, nrm, _ = ob.ray_cast(o_l, d_l)
    assert hit, (x, z)
    return mw @ loc, (inv.transposed().to_3x3() @ nrm).normalized()


def bez(p0, p1, p2, n=12):
    return [p0 * (1 - t) ** 2 + p1 * 2 * (1 - t) * t + p2 * t * t for t in (i / (n - 1) for i in range(n))]


def tube(name, pts, radii, m, segs=12, flat=1.0, side=None):
    """Tubo afilado ao longo de uma curva (mechas de cabelo, chifres)."""
    bm = bmesh.new()
    rings = []
    n = len(pts)
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
        a = side.normalized() if side is not None else Vector((0, 0, 1))
        if abs(t.dot(a)) > 0.95:
            a = Vector((1, 0, 0)) if abs(t.x) < 0.9 else Vector((0, 1, 0))
        u = t.cross(a).normalized()
        v = t.cross(u).normalized()
        if radii[i] <= 1e-4:
            rings.append([bm.verts.new(p)])
            continue
        rings.append([bm.verts.new(p + u * math.cos(k / segs * math.tau) * radii[i] + v * math.sin(k / segs * math.tau) * radii[i] * flat) for k in range(segs)])
    for i in range(n - 1):
        A, B = rings[i], rings[i + 1]
        if len(B) == 1:
            for k in range(segs):
                bm.faces.new([A[k], A[(k + 1) % segs], B[0]])
        else:
            for k in range(segs):
                bm.faces.new([A[k], A[(k + 1) % segs], B[(k + 1) % segs], B[k]])
    c = bm.verts.new(pts[0])
    for k in range(segs):
        bm.faces.new([rings[0][(k + 1) % segs], rings[0][k], c])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(o)
    o.data.materials.append(m)
    for p in me.polygons:
        p.use_smooth = True
    return o


def strand(name, root, mid, tip, r0, m, flat=0.45, side=None, n=12):
    pts = bez(Vector(root), Vector(mid), Vector(tip), n)
    radii = [r0 * (1 - i / (n - 1)) ** 0.75 for i in range(n)]
    return tube(name, pts, radii, m, 10, flat, side)


def half_arc(name, loc, major, minor, m, rot_extra=0.0):
    o = torus(name, (0, 0, 0), major, minor, m)
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.y > 0.0001], context="VERTS")
    bm.to_mesh(o.data)
    bm.free()
    o.location = loc
    o.rotation_euler = (math.radians(90), rot_extra, 0)
    return o


ba.clear()
SKIN = mat("heroskin", "#c78559", 0.6, spec=0.35, sheen=0.3)
HAIR = tmat("herohair", "fur", "#f4f1ea", seed=71, rough=0.55, sheen=0.6)
HORN = mat("herohorn", "#d9a42c", 0.28, spec=0.9)
SHIRT = tmat("heroshirt", "plaster", "#f6f3ee", seed=72, rough=0.9, sheen=0.8)
VEST = tmat("herovest", "plaster", "#27221f", seed=73, rough=0.75, sheen=0.4)
TIE = mat("herotie", "#c81f2a", 0.55, sheen=0.5)
SUSP = mat("herosusp", "#e7b52c", 0.55)
METAL = mat("herometal", "#7b736a", 0.3, spec=1.0)
PANTS = tmat("heropants", "tartan", "#2b2421", "#7b5a3b", seed=74, rough=0.9, sheen=0.6)
SHOE = mat("heroshoe", "#2a1c17", 0.2, spec=1.0)
SOLE = mat("herosole", "#1a1210", 0.6)
EYEW = mat("heroeyewhite", "#fbf8f2", 0.3)
IRIS = mat("heroiris", "#6b3d1d", 0.15, spec=1.0)
PUP = mat("heropupil", "#1f120b", 0.1, spec=1.0)
LASH = mat("herolash", "#2c1a12", 0.6)
WHITE = mat("white", "#ffffff", 0.2)
NOSE = mat("heronose", "#d9764a", 0.6)
MOUTH = mat("heromouth", "#4a2a1e", 0.6)

root = pivot("Root", (0, 0, 0))
head = pivot("Head", (0, 0, 1.0), root)

# ------------------------------------------------------------------ cabeça
H = sphere("HeadMesh", (0, 0, 1.47), (0.62, 0.56, 0.55), SKIN, 64)
att(H, head)
for s in (-1, 1):
    att(sphere("Ear", (0.6 * s, 0.02, 1.42), (0.08, 0.06, 0.12), SKIN, 24), head)
    att(sphere("EarIn", (0.63 * s, 0.0, 1.42), (0.04, 0.03, 0.07), mat("heroearin", "#b56f48", 0.7), 16), head)
# olhos grandes estilo ACNH: esclera, íris castanha, pupila, brilho e cílio superior grosso
for s in (-1, 1):
    loc, n = surf(H, 0.24 * s, 1.45)
    yaw = math.atan2(n.x, -n.y)
    t = Vector((math.cos(yaw), math.sin(yaw), 0))
    att(sphere("EyeWhite", loc - n * 0.03, (0.125, 0.06, 0.115), EYEW, 32, rot=(0, 0, yaw)), head)
    att(sphere("Iris", loc + n * 0.018 + t * (-0.015 * s) + Vector((0, 0, -0.008)), (0.088, 0.03, 0.1), IRIS, 32, rot=(0, 0, yaw)), head)
    att(sphere("Pupil", loc + n * 0.032 + t * (-0.015 * s) + Vector((0, 0, -0.008)), (0.045, 0.016, 0.055), PUP, 24, rot=(0, 0, yaw)), head)
    att(sphere("EyeHL", loc + n * 0.046 + t * (0.01 * s) + Vector((0, 0, 0.03)), (0.022, 0.008, 0.026), WHITE, 12, rot=(0, 0, yaw)), head)
    att(sphere("Lash", loc + n * 0.02 + Vector((0, 0, 0.088)), (0.14, 0.04, 0.03), LASH, 24, rot=(0, math.radians(-8 * s), yaw)), head)
    att(sphere("LashTip", loc + n * 0.015 + t * (0.13 * s) + Vector((0, 0, 0.075)), (0.035, 0.025, 0.018), LASH, 12, rot=(0, math.radians(-30 * s), yaw)), head)
    bl, bn = surf(H, 0.25 * s, 1.63)
    att(sphere("Brow", bl + bn * 0.004, (0.085, 0.02, 0.016), HAIR, 16, rot=(0, math.radians(-10 * s), math.atan2(bn.x, -bn.y))), head)
loc, n = surf(H, 0.0, 1.33)
nose = ba.cone("Nose", (0, 0, 0), 0.045, 0.07, NOSE, 3)
nose.location = loc + n * 0.012
nose.rotation_euler = (math.radians(180), 0, math.radians(30))
nose.scale = (1, 0.5, 1)
att(nose, head)
loc, n = surf(H, 0.0, 1.22)
att(half_arc("Mouth", loc + n * 0.003, 0.055, 0.007, MOUTH), head)

# ------------------------------------------------------------------ cabelo branco espetado
HC = Vector((0, 0.04, 1.5))
att(sphere("HairCap", (0, 0.05, 1.62), (0.66, 0.61, 0.5), HAIR, 48), head)
att(sphere("HairBack", (0, 0.2, 1.45), (0.64, 0.46, 0.5), HAIR, 48), head)
random.seed(7)


def dir_of(az, el):
    return Vector((math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)))


k = 0
# coroa: mechas grossas e fofas, varrendo para os lados e levemente para cima (pontas caem um pouco)
for i in range(22):
    az = i / 22 * math.tau + random.uniform(-0.12, 0.12)
    el = random.uniform(0.3, 0.85)
    radial = Vector((math.cos(az), math.sin(az), 0))
    d = dir_of(az, el)
    rootp = HC + Vector((d.x * 0.5, d.y * 0.46, d.z * 0.4 + 0.12))
    ln = random.uniform(0.22, 0.34)
    mid = rootp + radial * ln * 0.45 + Vector((0, 0, ln * 0.38))
    tip = rootp + radial * ln * 0.95 + Vector((0, 0, ln * random.uniform(0.05, 0.3)))
    att(strand("Lock%d" % k, rootp, mid, tip, random.uniform(0.13, 0.17), HAIR, flat=0.55, side=d), head)
    k += 1
# topo: algumas mechas apontando para cima/trás com curva
for i in range(6):
    x = random.uniform(-0.25, 0.25)
    rootp = Vector((x, random.uniform(-0.1, 0.2), 2.02))
    mid = rootp + Vector((x * 0.4, 0.05, 0.16))
    tip = rootp + Vector((x * 0.9, random.uniform(0.05, 0.2), 0.24))
    att(strand("Top%d" % k, rootp, mid, tip, 0.13, HAIR, flat=0.55, side=Vector((1, 0, 0))), head)
    k += 1
# laterais: mechas descendo até perto das orelhas
for s in (-1, 1):
    for j in range(4):
        z0 = 1.66 - j * 0.08
        rootp = Vector((0.56 * s, -0.16 + j * 0.12, z0))
        tip = rootp + Vector((0.13 * s, random.uniform(-0.04, 0.06), -0.28 - j * 0.03))
        mid = rootp + Vector((0.15 * s, 0, -0.08))
        att(strand("Side%d" % k, rootp, mid, tip, 0.13, HAIR, flat=0.5, side=Vector((s, 0, 0))), head)
        k += 1
# franja: mechas grossas caindo na testa, de comprimentos diferentes, rente ao rosto
for x0, x1, zt in [(-0.46, -0.5, 1.56), (-0.28, -0.24, 1.5), (-0.1, -0.03, 1.53), (0.08, 0.02, 1.47), (0.26, 0.2, 1.54), (0.44, 0.49, 1.58)]:
    rootp = Vector((x0, -0.3, 2.0))
    mid = Vector((x0 * 1.08, -0.64, 1.82))
    tip = Vector((x1, -0.565, zt))
    att(strand("Bang%d" % k, rootp, mid, tip, 0.14, HAIR, flat=0.4, side=Vector((0, -1, 0.3))), head)
    k += 1
# nuca
for j in range(5):
    x = -0.36 + j * 0.18
    rootp = Vector((x, 0.42, 1.55))
    att(strand("Nape%d" % k, rootp, rootp + Vector((x * 0.2, 0.16, -0.1)), rootp + Vector((x * 0.35, 0.12, -0.3)), 0.13, HAIR, flat=0.5, side=Vector((0, 1, 0))), head)
    k += 1

# chifres dourados curvos, saindo pela frente do cabelo
for s in (-1, 1):
    rootp = Vector((0.36 * s, -0.3, 1.86))
    att(strand("Horn", rootp, rootp + Vector((0.14 * s, -0.06, 0.2)), rootp + Vector((0.06 * s, -0.1, 0.4)), 0.11, HORN, flat=1.0, side=Vector((0, 1, 0)), n=16), head)

# ------------------------------------------------------------------ tronco: camisa, colete, gravata, suspensórios
att(sphere("Shirt", (0, 0, 0.8), (0.27, 0.2, 0.25), SHIRT, 48), root)
att(sphere("Vest", (0, -0.008, 0.76), (0.272, 0.205, 0.22), VEST, 48), root)
# abertura em V da camisa
bm = bmesh.new()
vs = [bm.verts.new(v) for v in [(-0.13, -0.205, 0.99), (0.13, -0.205, 0.99), (0, -0.22, 0.72)]]
bm.faces.new(vs)
me = bpy.data.meshes.new("ShirtV")
bm.to_mesh(me)
bm.free()
sv = bpy.data.objects.new("ShirtV", me)
bpy.context.collection.objects.link(sv)
sv.data.materials.append(SHIRT)
att(sv, root)
for s in (-1, 1):  # gola
    att(sphere("Collar", (0.08 * s, -0.15, 1.0), (0.09, 0.05, 0.035), SHIRT, 16, rot=(0, math.radians(25 * s), math.radians(-20 * s))), root)
att(sphere("TieKnot", (0, -0.2, 0.97), (0.04, 0.03, 0.035), TIE, 16), root)
tie = ba.cone("Tie", (0, -0.218, 0.84), 0.06, 0.22, TIE, 4)
tie.rotation_euler = (math.radians(180), 0, math.radians(45))
tie.scale = (1, 0.25, 1)
att(tie, root)
for i in range(2):
    att(sphere("VestBtn", (0.02, -0.215, 0.7 - i * 0.07), (0.016, 0.01, 0.016), mat("btn", "#14110f", 0.3), 12), root)
for s in (-1, 1):  # suspensórios na frente e atrás, com fivelas
    for side in (-1, 1):
        st = sphere("Susp", (0.14 * s, 0.2 * side, 0.82), (0.032, 0.012, 0.21), SUSP, 16, rot=(math.radians(-8 * side), math.radians(6 * s), 0))
        att(st, root)
    att(box("Buckle", (0.14 * s, -0.213, 0.88), (0.05, 0.01, 0.035), METAL, 0.004, 1), root)
    att(box("Clip", (0.14 * s, -0.205, 0.6), (0.045, 0.012, 0.04), mat("clip", "#8a6a3a", 0.4, spec=0.8), 0.004, 1), root)
    att(sphere("SuspTop", (0.15 * s, 0.0, 1.0), (0.04, 0.2, 0.02), SUSP, 16), root)

# ------------------------------------------------------------------ quadril e pernas
att(sphere("Hips", (0, 0, 0.58), (0.25, 0.19, 0.13), PANTS, 40), root)
for s, nm in ((-1, "FootL"), (1, "FootR")):
    p = pivot(nm, (0.13 * s, 0, 0.56), root)
    att(cyl(nm + "Leg", (0.13 * s, 0, 0.36), 0.105, 0.1, 0.42, PANTS, 32), p)
    att(cyl(nm + "Cuff", (0.13 * s, 0, 0.17), 0.118, 0.118, 0.07, PANTS, 32), p)
    att(cyl(nm + "Ankle", (0.13 * s, 0, 0.12), 0.06, 0.06, 0.06, SKIN, 16), p)
    att(sphere(nm + "Mesh", (0.13 * s, -0.05, 0.075), (0.11, 0.18, 0.07), SHOE, 32), p)
    att(sphere(nm + "Sole", (0.13 * s, -0.05, 0.022), (0.115, 0.185, 0.025), SOLE, 24), p)
    att(sphere(nm + "Strap", (0.13 * s, -0.13, 0.12), (0.07, 0.03, 0.012), SOLE, 16), p)

# ------------------------------------------------------------------ braços: manga dobrada, antebraço, mão redonda
for s, nm in ((-1, "ArmL"), (1, "ArmR")):
    p = pivot(nm, (0.26 * s, 0, 0.92), root)
    att(sphere(nm + "Sleeve", (0.32 * s, 0, 0.83), (0.1, 0.1, 0.13), SHIRT, 32, rot=(0, math.radians(-12 * s), 0)), p)
    att(torus(nm + "Cuff", (0.345 * s, 0, 0.72), 0.085, 0.032, SHIRT), p)
    att(cyl(nm + "Mesh", (0.355 * s, 0, 0.62), 0.06, 0.055, 0.2, SKIN, 20), p)
    att(sphere(nm + "Hand", (0.365 * s, 0, 0.49), (0.1, 0.1, 0.1), SKIN, 32), p)

bpy.ops.object.select_all(action="DESELECT")
stack = [root]
while stack:
    o = stack.pop()
    o.select_set(True)
    stack.extend(o.children)
bpy.ops.export_scene.gltf(filepath=OUT, export_format="GLB", use_selection=True, export_apply=True, export_yup=True, export_image_format="AUTO")
print("OK", OUT, "mechas:", k)
