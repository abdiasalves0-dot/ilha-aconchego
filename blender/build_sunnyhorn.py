"""Protagonista a partir do STL 'Sunnyhorn' (Meshy, fornecido pelo usuario).
STL nao tem cor: limpa o suporte, reduz poligonos, pinta por regioes (materiais), adiciona olhos/boca,
separa cabeca/bracos/pernas (baixa os bracos da T-pose) e exporta assets/models/player.glb.
Uso: blender -b -P build_sunnyhorn.py
"""
import bpy, bmesh, os, math, importlib.util
from mathutils import Vector, Matrix
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("ba", os.path.join(HERE, "build_assets.py"))
ba = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ba)
ROOTDIR = ba.ROOT
SRC = os.path.join(ROOTDIR, "vendor_ref", "sunnyhorn", "sunnyhorn.stl")
OUT = os.path.join(ba.OUT, "player.glb")
H_FINAL = 2.35
DECIMATE = 0.5

ba.clear()
bpy.ops.wm.stl_import(filepath=SRC)
src = bpy.context.selected_objects[0]
bpy.context.view_layer.objects.active = src
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# ---------------------------------------------------------------- 1) remove pecas soltas pequenas (suporte de impressao)
bm = bmesh.new()
bm.from_mesh(src.data)
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
bm.verts.ensure_lookup_table()
seen = set()
islands = []
for v in bm.verts:
    if v.index in seen:
        continue
    stack, isl = [v], []
    seen.add(v.index)
    while stack:
        a = stack.pop()
        isl.append(a)
        for e in a.link_edges:
            b = e.other_vert(a)
            if b.index not in seen:
                seen.add(b.index)
                stack.append(b)
    islands.append(isl)
islands.sort(key=len, reverse=True)
total = len(bm.verts)
kill = []
for isl in islands:
    ys = [v.co.y for v in isl]
    zs = [v.co.z for v in isl]
    behind_support = min(ys) > 4.0 and max(zs) < 26
    if len(isl) < total * 0.003 or behind_support:
        kill += isl
print("ILHAS", len(islands), [len(i) for i in islands[:8]], "removendo verts:", len(kill))
bmesh.ops.delete(bm, geom=kill, context="VERTS")
bm.to_mesh(src.data)
bm.free()

# ---------------------------------------------------------------- 2) reduz poligonos
dm = src.modifiers.new("dec", "DECIMATE")
dm.ratio = DECIMATE
bpy.ops.object.modifier_apply(modifier="dec")
me = src.data
for p in me.polygons:
    p.use_smooth = True
vs = [v.co for v in me.vertices]
mn = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
mx = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
cx, cy = (mn.x + mx.x) / 2, (mn.y + mx.y) / 2
me.transform(Matrix.Translation((-cx, -cy, -mn.z)))
HT = mx.z - mn.z
u0 = HT / 50.0
bm = bmesh.new()
bm.from_mesh(me)
rod = [f for f in bm.faces if f.calc_center_median().y > 1.6 * u0 and f.calc_center_median().z < 24.0 * u0 and abs(f.calc_center_median().x) < 3.0 * u0]
bmesh.ops.delete(bm, geom=rod, context="FACES")
bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
bm.to_mesh(me)
bm.free()
print("SUPORTE removido faces:", len(rod))
print("BBOX", tuple(round(c, 2) for c in mn), tuple(round(c, 2) for c in mx), "faces", len(me.polygons))

# ---------------------------------------------------------------- 3) materiais por regiao
MATS = {
    "skin": ba.mat("sh_skin", "#c78559", 0.6, spec=0.35, sheen=0.3),
    "hair": ba.tmat("sh_hair", "fur", "#f2efe8", seed=81, rough=0.55, sheen=0.6),
    "horn": ba.mat("sh_horn", "#d9a42c", 0.28, spec=0.9),
    "shirt": ba.tmat("sh_shirt", "plaster", "#f5f2ec", seed=82, rough=0.9, sheen=0.8),
    "vest": ba.tmat("sh_vest", "plaster", "#2a2522", seed=83, rough=0.75, sheen=0.4),
    "tie": ba.mat("sh_tie", "#c81f2a", 0.55, sheen=0.5),
    "susp": ba.mat("sh_susp", "#e7b52c", 0.55),
    "metal": ba.mat("sh_metal", "#8a7f70", 0.3, spec=1.0),
    "pants": ba.tmat("sh_pants", "tartan", "#2b2421", "#7b5a3b", seed=84, rough=0.9, sheen=0.6),
    "shoe": ba.mat("sh_shoe", "#2a1c17", 0.22, spec=1.0),
}
ORDER = list(MATS)
for k in ORDER:
    me.materials.append(MATS[k])

# medidas relativas (o STL tem 50 de altura; tudo em fracao da altura)
u = HT / 50.0
Z_SHOE, Z_PANTS, Z_NECK, Z_HEADTOP = 3.4 * u, 15.4 * u, 25.7 * u, 50 * u
TORSO_HALF = 5.7 * u
CUFF_X = 9.7 * u

# mapa de profundidade do rosto: para cada celula (x,z), a superficie frontal mais "funda" (y maior) e o rosto
cell = 0.5 * u
deep = defaultdict(lambda: -1e9)
cent = [p.center.copy() for p in me.polygons]
nrm = [p.normal.copy() for p in me.polygons]
for c, n in zip(cent, nrm):
    if c.z > Z_NECK and n.y < -0.2 and abs(c.x) < 7.5 * u and c.y < -3.0 * u:
        key = (int(c.x // cell), int(c.z // cell))
        deep[key] = max(deep[key], c.y)


def region(c, n):
    x, y, z = c
    ax = abs(x)
    if z < Z_SHOE:
        return "shoe"
    if z < 14.9 * u and ax < TORSO_HALF:
        return "pants"
    if z < Z_NECK + 1.2 * u and ax > TORSO_HALF:  # bracos em T
        return "shirt" if ax < CUFF_X else "skin"
    if z < Z_NECK:
        front = n.y < -0.25
        if z < 15.6 * u:
            return "shirt"  # barra da camisa abaixo do colete
        if front and ax < 0.9 * u and 19.8 * u < z < 24.6 * u and y < -2.0 * u:
            return "tie"
        if front and z > 20.3 * u and ax < 0.25 * u + (z - 20.3 * u) * 0.55:
            return "shirt"  # abertura em V
        if z > 24.3 * u and ax < 2.8 * u:
            return "shirt"  # gola
        if ax > 4.9 * u and z > 19.0 * u:
            return "shirt"  # ombros/mangas fora do colete
        if abs(n.y) > 0.25 and (-4.6 * u < x < -3.3 * u or 2.4 * u < x < 3.7 * u):
            if 16.2 * u < z < 17.4 * u or 21.6 * u < z < 22.6 * u:
                return "metal"
            return "susp"
        return "vest"
    # cabeca: chifres = parte mais a frente, nas laterais altas
    if 4.0 * u < ax < 8.3 * u and y < -8.6 * u and 37.5 * u < z < 46.0 * u:
        return "horn"
    if z < Z_NECK + 0.8 * u:
        return "skin"
    inside_face = (x / (6.9 * u)) ** 2 + ((z - 30.2 * u) / (4.9 * u)) ** 2 < 1.0
    if inside_face and n.y < -0.15 and z < 34.2 * u and y < -3.0 * u:
        key = (int(x // cell), int(z // cell))
        if y >= deep[key] - 0.9 * u:
            return "skin"
    if 7.2 * u < ax < 10.5 * u and 26.8 * u < z < 31.8 * u and abs(y) < 2.8 * u and abs(n.x) > 0.3:
        return "skin"  # orelhas
    return "hair"


cnt = defaultdict(int)
for p, c, n in zip(me.polygons, cent, nrm):
    r = region(c, n)
    p.material_index = ORDER.index(r)
    cnt[r] += 1
print("REGIOES", dict(cnt))

# UV para texturas (xadrez/cabelo)
bpy.ops.object.select_all(action="DESELECT")
bpy.context.view_layer.objects.active = src
src.select_set(True)
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.uv.cube_project(cube_size=6.0 * u)
bpy.ops.object.mode_set(mode="OBJECT")

# ---------------------------------------------------------------- 4) separa partes para animacao
PIV = {"Head": (0, 0, Z_NECK), "ArmL": (-TORSO_HALF, 0, 24.3 * u), "ArmR": (TORSO_HALF, 0, 24.3 * u),
       "FootL": (-2.4 * u, 0, Z_PANTS), "FootR": (2.4 * u, 0, Z_PANTS)}


def part_of(c):
    x, y, z = c
    if z >= Z_NECK and abs(x) < TORSO_HALF * 1.9:
        return "Head"
    if z >= Z_NECK - 0.6 * u and abs(x) < TORSO_HALF:
        return "Head" if z >= Z_NECK else "Root"
    if abs(x) > TORSO_HALF and Z_PANTS < z < Z_NECK + 2.0 * u:
        return "ArmL" if x < 0 else "ArmR"
    if z < Z_PANTS:
        return "FootL" if x < 0 else "FootR"
    return "Root"


groups = defaultdict(list)
for p in me.polygons:
    groups[part_of(p.center)].append(p.index)
print("PARTES", {k: len(v) for k, v in groups.items()})


def extract(name, idxs):
    b = bmesh.new()
    b.from_mesh(me)
    b.faces.ensure_lookup_table()
    keep = set(idxs)
    bmesh.ops.delete(b, geom=[f for f in b.faces if f.index not in keep], context="FACES")
    bmesh.ops.delete(b, geom=[v for v in b.verts if not v.link_faces], context="VERTS")
    m2 = bpy.data.meshes.new(name)
    b.to_mesh(m2)
    b.free()
    for m in me.materials:
        m2.materials.append(m)
    for p in m2.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name + "Mesh", m2)
    bpy.context.collection.objects.link(ob)
    return ob


def pivot(name, loc, parent=None):
    e = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(e)
    e.location = loc
    bpy.context.view_layer.update()
    if parent:
        e.parent = parent
        e.matrix_parent_inverse = parent.matrix_world.inverted()
    bpy.context.view_layer.update()
    return e


def att(o, p):
    bpy.context.view_layer.update()
    o.parent = p
    o.matrix_parent_inverse = p.matrix_world.inverted()


S = H_FINAL / HT
root = pivot("Root", (0, 0, 0))
pivots = {}
head_mesh = None
for name, idxs in groups.items():
    ob = extract(name, idxs)
    if name in ("ArmL", "ArmR"):
        px, py, pz = PIV[name]
        ang = -math.radians(72) if name == "ArmL" else math.radians(72)
        ob.data.transform(Matrix.Translation((px, py, pz)) @ Matrix.Rotation(ang, 4, "Y") @ Matrix.Translation((-px, -py, -pz)))
    ob.data.transform(Matrix.Scale(S, 4))
    if name == "Root":
        att(ob, root)
    else:
        px, py, pz = PIV[name]
        pv = pivot(name, (px * S, py * S, pz * S), root)
        pivots[name] = pv
        att(ob, pv)
    if name == "Head":
        head_mesh = ob
bpy.data.objects.remove(src)

# ---------------------------------------------------------------- 5) olhos e boca (o STL nao tem olhos esculpidos)
head = pivots["Head"]


def surf(x, z):
    bpy.context.view_layer.update()
    best = None
    for o in [head_mesh]:
        inv = o.matrix_world.inverted()
        hit, loc, n, _ = o.ray_cast(inv @ Vector((x, -10, z)), (inv.to_3x3() @ Vector((0, 1, 0))).normalized())
        if hit:
            w = o.matrix_world @ loc
            if best is None or w.y < best[0].y:
                best = (w, (inv.transposed().to_3x3() @ n).normalized())
    assert best, (x, z)
    return best


EYEW = ba.mat("sh_eyewhite", "#fbf8f2", 0.3)
IRIS = ba.mat("sh_iris", "#6b3d1d", 0.15, spec=1.0)
PUP = ba.mat("sh_pupil", "#1f120b", 0.1, spec=1.0)
LASH = ba.mat("sh_lash", "#2c1a12", 0.6)
WHITE = ba.mat("white", "#ffffff", 0.2)
MOUTH = ba.mat("sh_mouth", "#4a2a1e", 0.6)
k = S * u  # 1 "unidade do STL" em metros finais
for s in (-1, 1):
    loc, n = surf(2.85 * k * s, 31.0 * k)
    yaw = math.atan2(n.x, -n.y)
    t = Vector((math.cos(yaw), math.sin(yaw), 0))
    att(ba.sphere("EyeWhite", loc - n * 0.012, (0.1, 0.03, 0.095), EYEW, 32, rot=(0, 0, yaw)), head)
    att(ba.sphere("Iris", loc + n * 0.012 + t * (-0.012 * s) + Vector((0, 0, -0.006)), (0.072, 0.02, 0.083), IRIS, 32, rot=(0, 0, yaw)), head)
    att(ba.sphere("Pupil", loc + n * 0.022 + t * (-0.012 * s) + Vector((0, 0, -0.006)), (0.037, 0.012, 0.046), PUP, 24, rot=(0, 0, yaw)), head)
    att(ba.sphere("EyeHL", loc + n * 0.032 + t * (0.008 * s) + Vector((0, 0, 0.025)), (0.018, 0.006, 0.022), WHITE, 12, rot=(0, 0, yaw)), head)
    att(ba.sphere("Lash", loc + n * 0.016 + Vector((0, 0, 0.072)), (0.115, 0.03, 0.024), LASH, 24, rot=(0, math.radians(-8 * s), yaw)), head)
loc, n = surf(0.0, 28.4 * k)
o = ba.torus("Mouth", (0, 0, 0), 0.045, 0.006, MOUTH)
b = bmesh.new()
b.from_mesh(o.data)
bmesh.ops.delete(b, geom=[v for v in b.verts if v.co.y > 0.0001], context="VERTS")
b.to_mesh(o.data)
b.free()
o.location = loc + n * 0.004
o.rotation_euler = (math.radians(90), 0, 0)
att(o, head)

bpy.ops.object.select_all(action="DESELECT")
stack = [root]
while stack:
    ob = stack.pop()
    ob.select_set(True)
    stack.extend(ob.children)
bpy.ops.export_scene.gltf(filepath=OUT, export_format="GLB", use_selection=True, export_apply=True, export_yup=True, export_image_format="AUTO")
print("OK", OUT)
