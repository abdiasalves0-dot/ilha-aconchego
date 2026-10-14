"""Villager capivara no mesmo padrao do jogador (Macchiato): cabeca grande e lisa (metaballs),
olhos sonolentos com palpebra, sueter de trico, pernas finas. Exporta assets/models/villager_capy.glb
Uso: blender -b -P build_capybara.py
"""
import bpy, bmesh, os, math, importlib.util
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("ba", os.path.join(HERE, "build_assets.py"))
ba = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ba)
mat, tmat, sphere, cyl, torus, pivot = ba.mat, ba.tmat, ba.sphere, ba.cyl, ba.torus, ba.pivot
OUT = os.path.join(ba.OUT, "villager_capy.glb")


def att(o, p):
    bpy.context.view_layer.update()
    o.parent = p
    o.matrix_parent_inverse = p.matrix_world.inverted()


def select_only(o):
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = o
    o.select_set(True)


def metablob(name, elems, res=0.035):
    mb = bpy.data.metaballs.new(name)
    mb.resolution = res
    mb.render_resolution = res
    mb.threshold = 0.6
    ob = bpy.data.objects.new(name, mb)
    bpy.context.collection.objects.link(ob)
    for co, r, sx, sy, sz in elems:
        e = mb.elements.new(type="ELLIPSOID")
        e.co, e.radius, e.size_x, e.size_y, e.size_z, e.stiffness = co, r, sx, sy, sz, 2.0
    select_only(ob)
    bpy.context.view_layer.update()
    bpy.ops.object.convert(target="MESH")
    out = bpy.context.view_layer.objects.active
    out.name = name
    return out


def fit(ob, xhalf, z0, z1, ycenter=0.0):
    vs = ob.data.vertices
    mnx, mxx = min(v.co.x for v in vs), max(v.co.x for v in vs)
    mnz, mxz = min(v.co.z for v in vs), max(v.co.z for v in vs)
    sx = (2 * xhalf) / (mxx - mnx)
    sz = (z1 - z0) / (mxz - mnz)
    cx = (mnx + mxx) / 2
    for v in vs:
        v.co = Vector(((v.co.x - cx) * sx, v.co.y * sx + ycenter, (v.co.z - mnz) * sz + z0))
    ob.data.update()


def smooth_uv(ob):
    for p in ob.data.polygons:
        p.use_smooth = True
    select_only(ob)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.02)
    bpy.ops.object.mode_set(mode="OBJECT")


def surf(ob, x, z, y0=-4.0):
    bpy.context.view_layer.update()
    hit, loc, nrm, _ = ob.ray_cast(Vector((x, y0, z)), Vector((0, 1, 0)))
    assert hit, (x, z)
    return loc, nrm


def surf_down(ob, x, y):
    bpy.context.view_layer.update()
    hit, loc, nrm, _ = ob.ray_cast(Vector((x, y, 5)), Vector((0, 0, -1)))
    assert hit, (x, y)
    return loc, nrm


def half_arc(name, loc, major, minor, m, yaw=0.0):
    o = torus(name, (0, 0, 0), major, minor, m)
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.y > 0.0001], context="VERTS")
    bm.to_mesh(o.data)
    bm.free()
    o.location = loc
    o.rotation_euler = (math.radians(90), 0, yaw)
    return o


ba.clear()
FUR = tmat("furcapy", "fur", "#a8764c", seed=51, rough=0.95, sheen=0.6)
FURD = tmat("furcapydark", "fur", "#7a5236", seed=52, rough=0.95, sheen=0.6)
KNIT = tmat("knitcapy", "knit", "#e3aa3e", seed=53, rough=0.95, sheen=1.0)
KNIT2 = tmat("knitcapy2", "knit", "#c4862a", seed=54, rough=0.95, sheen=1.0)
NOSE = mat("capynose", "#3a2a22", 0.45, spec=0.7)
EYEW = mat("capyeyewhite", "#fbf6ec", 0.3)
IRIS = mat("capyiris", "#5a3a22", 0.15, spec=1.0)
PUP = mat("capypupil", "#120c09", 0.1, spec=1.0)
WHITE = mat("white", "#ffffff", 0.2)
CHEEK = mat("capycheek", "#eb9c86", 0.9)
YUZU = tmat("yuzu", "fur", "#ffb22e", seed=55, rough=0.45)
LEAF = mat("yuzuleaf", "#4fa64a", 0.6)

root = pivot("Root", (0, 0, 0))
head = pivot("Head", (0, 0, 1.0), root)

# ---- cabeca: cranio + focinho largo + bochechas, fundidos (metaball)
H = metablob("HeadMesh", [
    ((0, 0, 0), 1.0, 1.0, 0.86, 0.9),
    ((0, -0.62, -0.28), 0.82, 0.78, 0.6, 0.52),
    ((0.5, -0.28, -0.3), 0.6, 0.55, 0.55, 0.5),
    ((-0.5, -0.28, -0.3), 0.6, 0.55, 0.55, 0.5),
])
fit(H, 0.56, 1.0, 1.97)
smooth_uv(H)
H.data.materials.append(FUR)
# cor por vertice: focinho mais claro, topo levemente mais escuro
ca = H.data.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
for i, v in enumerate(H.data.vertices):
    c = v.co
    muzzle = max(0.0, min(1.0, (-c.y - 0.3) / 0.25)) * max(0.0, min(1.0, (1.52 - c.z) / 0.15))
    top = max(0.0, min(1.0, (c.z - 1.75) / 0.2))
    k = 0.86 + 0.24 * muzzle - 0.1 * top
    ca.data[i].color = (k, k * 0.98, k * 0.95, 1.0)
att(H, head)

# ---- olhos sonolentos (como o Macchiato): esclera, iris, pupila, brilho e palpebra
for s in (-1, 1):
    loc, n = surf(H, 0.24 * s, 1.67)
    yaw = math.atan2(n.x, -n.y)
    t = Vector((math.cos(yaw), math.sin(yaw), 0))  # tangente horizontal
    att(sphere("EyeWhite", loc - n * 0.03, (0.12, 0.06, 0.108), EYEW, 32, rot=(0, 0, yaw)), head)
    att(sphere("Iris", loc + n * 0.018 + Vector((0, 0, -0.012)), (0.072, 0.03, 0.08), IRIS, 32, rot=(0, 0, yaw)), head)
    att(sphere("Pupil", loc + n * 0.032 + Vector((0, 0, -0.012)), (0.036, 0.016, 0.042), PUP, 24, rot=(0, 0, yaw)), head)
    att(sphere("EyeHL", loc + n * 0.045 + t * (0.022 * s) + Vector((0, 0, 0.012)), (0.018, 0.008, 0.022), WHITE, 12, rot=(0, 0, yaw)), head)
    att(sphere("Lid", loc - n * 0.012 + Vector((0, 0, 0.06)), (0.14, 0.072, 0.072), FUR, 32, rot=(0, 0, yaw)), head)
    att(sphere("LidLine", loc + n * 0.035 + Vector((0, 0, 0.0)), (0.13, 0.03, 0.011), FURD, 20, rot=(0, 0, yaw)), head)
    loc, n = surf(H, 0.37 * s, 1.43)
    att(sphere("Cheek", loc + n * 0.002, (0.085, 0.02, 0.05), CHEEK, 20, rot=(0, 0, math.atan2(n.x, -n.y))), head)

# ---- nariz largo de capivara, narinas e boquinha
loc, n = surf(H, 0.0, 1.47)
att(sphere("NosePad", loc - n * 0.025, (0.2, 0.07, 0.085), NOSE, 32), head)
for s in (-1, 1):
    att(sphere("Nostril", loc + n * 0.035 + Vector((0.075 * s, 0, -0.005)), (0.03, 0.015, 0.018), PUP, 12, rot=(0, 0, 0.3 * s)), head)
loc, n = surf(H, 0.0, 1.29)
for s in (-1, 1):
    att(half_arc("Mouth", loc + n * 0.004 + Vector((0.042 * s, 0, 0)), 0.042, 0.008, FURD), head)

# ---- orelhinhas
for s in (-1, 1):
    loc, n = surf_down(H, 0.4 * s, 0.06)
    att(sphere("Ear", loc + Vector((0.01 * s, 0, 0.03)), (0.1, 0.065, 0.085), FUR, 24, rot=(0, math.radians(-25 * s), 0)), head)
    att(sphere("EarIn", loc + Vector((0.01 * s, -0.04, 0.035)), (0.06, 0.03, 0.05), FURD, 16, rot=(0, math.radians(-25 * s), 0)), head)

# ---- yuzu na cabeca (classico das capivaras)
loc, n = surf_down(H, 0.1, 0.0)
yc = loc + Vector((0, 0, 0.11))
att(sphere("Yuzu", yc, (0.14, 0.14, 0.125), YUZU, 32), head)
att(cyl("YuzuStem", yc + Vector((0, 0, 0.13)), 0.012, 0.01, 0.05, mat("stem", "#5b3d24", 0.8), 8), head)
att(sphere("YuzuLeaf", yc + Vector((0.06, 0, 0.14)), (0.07, 0.032, 0.012), LEAF, 16, rot=(0, -0.4, 0.4)), head)

# ---- corpo de sueter (barra canelada e gola)
att(sphere("Body", (0, 0, 0.74), (0.27, 0.22, 0.31), KNIT, 48), root)
att(torus("Hem", (0, 0, 0.47), 0.235, 0.055, KNIT2, scale=(1, 0.84, 1)), root)
att(torus("Collar", (0, 0, 0.99), 0.16, 0.06, KNIT2, scale=(1, 0.85, 1)), root)
att(sphere("Bottom", (0, 0, 0.47), (0.2, 0.17, 0.1), FUR, 24), root)

# ---- bracos (manga + punho + mao)
for s, nm in ((-1, "ArmL"), (1, "ArmR")):
    p = pivot(nm, (0.25 * s, 0, 0.88), root)
    att(sphere(nm + "Sleeve", (0.31 * s, 0, 0.72), (0.085, 0.085, 0.18), KNIT, 32, rot=(0, math.radians(-10 * s), 0)), p)
    att(torus(nm + "Cuff", (0.345 * s, 0, 0.56), 0.068, 0.026, KNIT2), p)
    att(sphere(nm + "Hand", (0.355 * s, 0, 0.49), (0.07, 0.07, 0.075), FUR, 24), p)

# ---- pernas finas com pezinhos
for s, nm in ((-1, "FootL"), (1, "FootR")):
    p = pivot(nm, (0.12 * s, 0, 0.46), root)
    att(cyl(nm + "Leg", (0.12 * s, 0, 0.26), 0.07, 0.075, 0.42, FUR, 24), p)
    att(sphere(nm + "Mesh", (0.12 * s, -0.04, 0.05), (0.09, 0.13, 0.06), FURD, 24), p)

bpy.ops.object.select_all(action="DESELECT")
stack = [root]
while stack:
    o = stack.pop()
    o.select_set(True)
    stack.extend(o.children)
kw = dict(filepath=OUT, export_format="GLB", use_selection=True, export_apply=True, export_yup=True, export_image_format="AUTO")
try:
    bpy.ops.export_scene.gltf(export_vertex_color="ACTIVE", **kw)
except TypeError:
    bpy.ops.export_scene.gltf(**kw)
print("OK", OUT, "verts cabeca:", len(H.data.vertices))
