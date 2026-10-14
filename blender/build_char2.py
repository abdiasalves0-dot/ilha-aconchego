"""Novo personagem-base (do base.blend do usuario): corpo + roupas do proprio arquivo + rosto/pele pintados estilo ACNH
+ penteados esculpidos. Cada peca vira um .glb com os pivos do jogo (Root, Head, ArmL, ArmR, FootL, FootR).
Saida: assets/models/char2/*.glb + wardrobe2.json
Uso:   blender -b -P blender/build_char2.py [-- id_da_peca ...]
"""
import bpy, bmesh, os, sys, math, json, random
import numpy as np
from mathutils import Vector, Matrix
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import char_lib as cl
ba = cl.ba
ROOT = cl.ROOTDIR
OUTD = os.path.join(ROOT, "assets", "models", "char2")
os.makedirs(OUTD, exist_ok=True)
ONLY = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
try:
    bpy.context.preferences.edit.undo_steps = 0
    bpy.context.preferences.edit.use_global_undo = False
except Exception:
    pass

bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, "vendor_ref", "base_blend", "clean.blend"))
ba._mats.clear()
O = {o.name: o for o in bpy.data.objects}
for n in ("sphere", "nose0", "nose"):
    bpy.data.objects.remove(O[n])
    del O[n]

# ---------------------------------------------------------------- orientacao: frente em -y, pes no chao, centrado
rot = Matrix.Rotation(math.pi, 4, "Z")
for o in O.values():
    o.data.transform(rot)


def bbox(o):
    vs = [v.co for v in o.data.vertices]
    return (Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs))), Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs))))


yc = sum(bbox(O["hoodie"])[i].y for i in (0, 1)) / 2
zmin = min(bbox(O["shoeL"])[0].z, bbox(O["shoeR"])[0].z)
T = Matrix.Translation((0, -yc, -zmin))
for o in O.values():
    o.data.transform(T)
BV = {k: [v.co.copy() for v in o.data.vertices] for k, o in O.items()}
hmn, hmx = bbox(O["head"])
HC = Vector(((hmn.x + hmx.x) / 2, (hmn.y + hmx.y) / 2, (hmn.z + hmx.z) / 2))
HR = Vector(((hmx.x - hmn.x) / 2, (hmx.y - hmn.y) / 2, (hmx.z - hmn.z) / 2))
HT = hmx.z                                   # altura do boneco sem cabelo
NECK = hmn.z
TH = 0.245                                   # meia-largura do tronco do moletom (bracos ja vem posados pelo esqueleto)
SHX, SHZ, SHY = 0.13, 1.51 - zmin, 0.06 - yc  # articulacao do ombro (osso Bone.021/024 do arquivo)
AZ = SHZ
X0 = SHX
cz = [v.z for v in BV["pants"] if abs(v.x) < 0.02]
CROTCH = min(cz) if cz else 0.5
S = 2.3 / HT
print("MEDIDAS HT %.3f NECK %.3f TH %.3f AZ %.3f CROTCH %.3f S %.3f HC %s HR %s" % (HT, NECK, TH, AZ, CROTCH, S, tuple(round(c, 3) for c in HC), tuple(round(c, 3) for c in HR)), flush=True)
rx, ry, rz = HR
UP = (0, 0, 1)

# ---------------------------------------------------------------- materiais (cores padrao; o jogo recolore pelo nome)
def tex_white(kind, seed):
    return ba.make_tex(kind, "#ffffff", None, seed)


SKIN = ba.mat("c2_skin", "#e8955c", 0.78, sheen=0.5)   # mesmo acabamento aveludado do corpo do Meshy
NOSEM = ba.mat("c2_nose", "#d9743f", 0.7, sheen=0.4)
IRIS = ba.mat("c2_iris", "#5a3216", 0.15, spec=1.0)
SCLERA = ba.mat("c2_sclera", "#fbf8f2", 0.3)
PUPIL = ba.mat("c2_pupil", "#1a100b", 0.1, spec=1.0)
WHITE = ba.mat("c2_hl", "#ffffff", 0.2)
BROW = ba.mat("c2_brow", "#f3e6cf", 0.85)   # sobrancelhas claras, como na referencia do Meshy
MOUTH = ba.mat("c2_mouth", "#7a3a2a", 0.6)
BLUSH = ba.mat("blush", "#ff8a8a", 0.9)
HOODIE = ba.mat("c2_hoodie", "#f4f1ea", 0.9, tex=tex_white("plaster", 301), sheen=0.8)
PANTS = ba.mat("c2_pants", "#5a86c8", 0.9, tex=tex_white("plaster", 302), sheen=0.6)
SHOE = ba.mat("c2_shoe", "#6cc070", 0.55, sheen=0.3)
SOLE = ba.mat("c2_sole", "#ffffff", 0.7)
CAPM = ba.mat("c2_cap", "#3a3a3e", 0.8, tex=tex_white("plaster", 303), sheen=0.8)
STRAP = ba.mat("c2_strap", "#e8c15a", 0.8, sheen=0.5)
BAGM = ba.mat("c2_bag", "#6ab0e6", 0.8, sheen=0.5)

def setmats(role, mats, remap=None):
    me = O[role].data
    idx = [p.material_index for p in me.polygons]       # guardar ANTES de limpar (clear() zera os indices)
    me.materials.clear()
    for m in mats:
        me.materials.append(m)
    for p, i in zip(me.polygons, idx):
        p.material_index = remap.get(i, 0) if remap else 0
        p.use_smooth = True


for r in ("head", "ears", "hands"):
    setmats(r, [SKIN])
setmats("hoodie", [HOODIE])
setmats("pants", [PANTS])
for r in ("shoeL", "shoeR"):
    setmats(r, [SHOE, SOLE], {0: 1, 1: 0, 2: 0, 3: 0, 4: 0, 5: 1})
setmats("cap", [CAPM])
setmats("strap", [STRAP])
setmats("bag", [BAGM])
for r in ("hoodie", "pants", "cap", "head"):
    pass

# ---------------------------------------------------------------- rosto estilo ACNH (geometria sobre a cabeca)
head_obj = O["head"]


def front_hit(x, z):
    bpy.context.view_layer.update()
    hit, loc, n, _ = head_obj.ray_cast(Vector((x, -5.0, z)), Vector((0, 1, 0)))
    assert hit, (x, z)
    return loc, n


NOSE_Z = HC.z - 0.03
face = []
loc, n = front_hit(0.0, NOSE_Z)
yb, yt = loc.y + 0.012, loc.y - 0.075
nose = ba.cyl("nose", (0, (yb + yt) / 2, NOSE_Z), 0.036, 0.0, yb - yt, NOSEM, 32, rot=(math.pi / 2, 0, 0))
face.append(nose)
EZ = NOSE_Z + 0.055
for s in (-1, 1):
    ex = 0.172 * s
    loc, n = front_hit(ex, EZ)
    yaw = math.atan2(n.x, -n.y)
    t = Vector((math.cos(yaw), math.sin(yaw), 0))
    face.append(ba.sphere("sclera", loc - n * 0.012, (0.074, 0.03, 0.094), SCLERA, 32, rot=(0, 0, yaw)))
    face.append(ba.sphere("iris", loc + n * 0.002 + Vector((0, 0, -0.004)), (0.064, 0.03, 0.082), IRIS, 32, rot=(0, 0, yaw)))
    face.append(ba.sphere("pupil", loc + n * 0.016 + Vector((0, 0, -0.004)), (0.036, 0.016, 0.047), PUPIL, 24, rot=(0, 0, yaw)))
    face.append(ba.sphere("hl1", loc + n * 0.026 + t * (0.018 * s) + Vector((0, 0, 0.026)), (0.02, 0.01, 0.026), WHITE, 12, rot=(0, 0, yaw)))
    face.append(ba.sphere("hl2", loc + n * 0.024 - t * (0.02 * s) + Vector((0, 0, -0.03)), (0.009, 0.006, 0.011), WHITE, 12, rot=(0, 0, yaw)))
    face.append(ba.sphere("lash", loc + n * 0.008 + Vector((0, 0, 0.082)), (0.07, 0.018, 0.009), PUPIL, 24, rot=(0, math.radians(8 * s), yaw)))
    bl, bn = front_hit(0.18 * s, EZ + 0.135)
    face.append(ba.sphere("brow", bl + bn * 0.003, (0.072, 0.012, 0.014), BROW, 16, rot=(0, math.radians(9 * s), math.atan2(bn.x, -bn.y))))
    cl_, cn = front_hit(0.265 * s, NOSE_Z - 0.065)
    face.append(ba.sphere("blush", cl_ + cn * 0.003, (0.085, 0.014, 0.05), BLUSH, 24, rot=(0, 0, math.atan2(cn.x, -cn.y))))
ml, mn = front_hit(0.0, NOSE_Z - 0.115)
mo = ba.torus("mouth", (0, 0, 0), 0.056, 0.0075, MOUTH)
b_ = bmesh.new(); b_.from_mesh(mo.data)
bmesh.ops.delete(b_, geom=[v for v in b_.verts if v.co.y > 0.0001], context="VERTS")
b_.to_mesh(mo.data); b_.free()
mo.location = ml + mn * 0.004
mo.rotation_euler = (math.radians(90), 0, 0)
face.append(mo)

# ---------------------------------------------------------------- partes do rig
def part_of(role, c):
    if role in ("head", "ears", "cap"):
        return "Head"
    if role == "hands":
        return "ArmR" if c.x > 0 else "ArmL"
    if role == "hoodie":
        return ("ArmR" if c.x > 0 else "ArmL") if abs(c.x) > TH * 1.08 and c.z < SHZ + 0.1 else "Root"
    if role == "pants":
        return ("FootR" if c.x > 0 else "FootL") if c.z < CROTCH else "Root"
    if role in ("shoeL", "shoeR"):
        return "FootR" if c.x > 0 else "FootL"
    return "Root"


def smooth01(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def bend_arms(me):
    for v in me.vertices:
        x, y, z = v.co
        if abs(x) <= X0 - BL:
            continue
        s = 1 if x > 0 else -1
        a = ANG * smooth01((abs(x) - (X0 - BL)) / BL) * s
        dx, dz = x - X0 * s, z - AZ
        v.co.x = X0 * s + dx * math.cos(a) + dz * math.sin(a)
        v.co.z = AZ - dx * math.sin(a) + dz * math.cos(a)
    me.update()


PIV = {"Head": (0, 0, NECK), "ArmL": (-SHX, SHY, SHZ), "ArmR": (SHX, SHY, SHZ), "FootL": (-0.11, 0, CROTCH + 0.05), "FootR": (0.11, 0, CROTCH + 0.05)}
ARM_ROLES = ("hoodie", "hands")


def mkpivot(name, loc, parent=None):
    e = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(e)
    e.location = loc
    bpy.context.view_layer.update()
    if parent:
        e.parent = parent
        e.matrix_parent_inverse = parent.matrix_world.inverted()
    bpy.context.view_layer.update()
    return e


EXPORTED = []
MANI = os.path.join(OUTD, "wardrobe2.json")


BONES = ["Root", "Head", "ArmL", "ArmR", "FootL", "FootR", "KneeL", "KneeR", "AnkleL", "AnkleR", "ElbowL", "ElbowR"]
PARENT = {"Head": "Root", "ArmL": "Root", "ArmR": "Root", "FootL": "Root", "FootR": "Root", "KneeL": "FootL", "KneeR": "FootR", "AnkleL": "KneeL", "AnkleR": "KneeR", "ElbowL": "ArmL", "ElbowR": "ArmR"}
HIPZ = CROTCH + 0.05
HIPX = 0.11
ARM_DIR = (math.cos(math.radians(62)), -math.sin(math.radians(62)))   # direcao do braco ja posado (x, z)
KNEEZ = 0.30            # altura do joelho (metade da perna)
ANKLEZ = 0.115          # altura do tornozelo (topo do tenis)
ELB_LEN = 0.30          # distancia ombro -> cotovelo (ao longo do braco ja posado)
ELB_REST_X = SHX + ELB_LEN   # posicao do cotovelo na T-pose (x), usada nos pesos
EX, EZ = SHX + ELB_LEN * ARM_DIR[0], SHZ + ELB_LEN * ARM_DIR[1]
JOINT = {"Root": (0, 0, HIPZ), "Head": (0, 0, NECK), "ArmL": (-SHX, SHY, SHZ), "ArmR": (SHX, SHY, SHZ), "FootL": (-HIPX, 0, HIPZ), "FootR": (HIPX, 0, HIPZ),
         "KneeL": (-HIPX, 0, KNEEZ), "KneeR": (HIPX, 0, KNEEZ), "AnkleL": (-HIPX, 0, ANKLEZ), "AnkleR": (HIPX, 0, ANKLEZ),
         "ElbowL": (-EX, SHY, EZ), "ElbowR": (EX, SHY, EZ)}


def sstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def weights_at(co, mode):
    """Pesos de skinning por posicao EM T-POSE: iguais para todas as pecas (roupa e corpo deformam juntos).
    Cabeca no pescoco; braco: ombro -> cotovelo; perna: quadril -> joelho -> tornozelo; resto no Root."""
    x, y, z = co
    side = 1 if x > 0 else -1
    S_ = "R" if side > 0 else "L"
    if mode == "Head":
        return {"Head": 1.0}
    if mode == "arms":
        return {"Elbow" + S_: 1.0}
    wh = sstep((z - (NECK - 0.04)) / 0.07)
    wa = sstep((abs(x) - (TH - 0.01)) / 0.065) * (1.0 - wh)
    wl = sstep((HIPZ + 0.06 - z) / 0.12) * (1.0 - wh)
    out = {}
    if wh > 0:
        out["Head"] = wh
    if wa > 0:
        we = sstep((abs(x) - (ELB_REST_X - 0.05)) / 0.10)
        out["Arm" + S_] = wa * (1 - we)
        if we > 0:
            out["Elbow" + S_] = wa * we
    if wl > 0:
        wk = sstep((KNEEZ + 0.05 - z) / 0.10)           # abaixo do joelho
        wn = sstep((ANKLEZ + 0.035 - z) / 0.07)         # abaixo do tornozelo
        out["Foot" + S_] = wl * (1 - wk)
        if wk - wn > 0:
            out["Knee" + S_] = wl * (wk - wn)
        if wn > 0:
            out["Ankle" + S_] = wl * wn
    rest = 1.0 - sum(out.values())
    if rest > 1e-6:
        out["Root"] = rest
    tot = sum(out.values())
    return {k: v / tot for k, v in out.items() if v > 1e-6}


def make_armature():
    ad = bpy.data.armatures.new("Armature")
    ao = bpy.data.objects.new("Armature", ad)
    bpy.context.collection.objects.link(ao)
    bpy.context.view_layer.objects.active = ao
    ao.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    eb = {}
    for name in BONES:
        e = ad.edit_bones.new(name)
        e.head = Vector(JOINT[name]) * S
        e.tail = e.head + Vector((0, 0.1, 0))              # todos apontam para +Y: giro identico, sem "roll"
        e.roll = 0.0
        eb[name] = e
    for name in BONES[1:]:
        eb[name].parent = eb[PARENT[name]]
    bpy.ops.object.mode_set(mode="OBJECT")
    return ao


EXPORTED = []
MANI = os.path.join(OUTD, "wardrobe2.json")


def export_piece(pid, slot, name_pt, items, extra=None):
    """items: lista de (objeto, papel): papel 'Head' prende tudo na cabeca, 'arms' nas maos, o resto usa pesos por posicao."""
    if ONLY and pid not in ONLY:
        for o, _ in items:
            if o.name in bpy.data.objects:
                bpy.data.objects.remove(o)
        return
    ao = make_armature()
    objs = []
    for ob, role in items:
        bpy.context.view_layer.update()
        ob.data.transform(ob.matrix_world)
        ob.matrix_world = Matrix.Identity(4)
        me = ob.data
        mode = "Head" if role in ("head", "ears", "Head") else ("arms" if role == "hands" else "auto")
        rp = me.attributes.get("restpos")
        if rp is not None:      # posicao de T-pose, na mesma transformacao aplicada as malhas (giro de 180 graus em Z + deslocamento)
            W = [weights_at((-rp.data[i].vector.x, -rp.data[i].vector.y - yc, rp.data[i].vector.z - zmin), mode) for i in range(len(me.vertices))]
        else:
            W = [weights_at((v.co.x, v.co.y, v.co.z), mode) for v in me.vertices]
        me.transform(Matrix.Scale(S, 4))
        ob.name = pid + "_" + ob.name
        vgs = {n: ob.vertex_groups.new(name=n) for n in BONES}
        for i, w in enumerate(W):
            for n, val in w.items():
                if val > 1e-4:
                    vgs[n].add([i], val, "REPLACE")
        for p in me.polygons:
            p.use_smooth = True
        ob.parent = ao
        md = ob.modifiers.new("Armature", "ARMATURE")
        md.object = ao
        objs.append(ob)
    bpy.ops.object.select_all(action="DESELECT")
    ao.select_set(True)
    for o in objs:
        o.select_set(True)
    path = os.path.join(OUTD, pid + ".glb")
    kw = dict(filepath=path, export_format="GLB", use_selection=True, export_apply=False, export_skins=True, export_yup=True, export_image_format="AUTO")
    try:
        bpy.ops.export_scene.gltf(export_vertex_color="ACTIVE", **kw)
    except TypeError:
        bpy.ops.export_scene.gltf(**kw)
    for o in objs + [ao]:
        bpy.data.objects.remove(o)
    item = {"id": pid, "slot": slot, "name": name_pt, "file": "assets/models/char2/" + pid + ".glb"}
    if extra:
        item.update(extra)
    EXPORTED.append(item)
    print("PECA", pid, flush=True)


def dup(role):
    o = O[role]
    o2 = bpy.data.objects.new(role + "_x", o.data.copy())
    bpy.context.collection.objects.link(o2)
    return o2


# ---------------------------------------------------------------- pecas
export_piece("body", "body", "Corpo", [(dup("head"), "head"), (dup("ears"), "ears"), (dup("hands"), "hands")] + [(f, "Head") for f in face] + [])
export_piece("top_moletom", "top", "Moletom", [(dup("hoodie"), "hoodie")], extra={"tint": "hoodie"})
export_piece("bottom_calca", "bottom", "Calça", [(dup("pants"), "pants")], extra={"tint": "pants"})
export_piece("shoes_tenis", "shoes", "Tênis", [(dup("shoeL"), "shoeL"), (dup("shoeR"), "shoeR")], extra={"tint": "shoes"})
export_piece("hair_tigela", "hair", "Tigela (original)", [(dup("cap"), "Head")], extra={"tint": "hair"})
export_piece("acc_bolsa", "bag", "Bolsa a tiracolo", [(dup("strap"), "strap"), (dup("bag"), "bag")], extra={"tint": "bag"})

# ====================================================================== penteados (volumes lisos esculpidos, sobre a cabeca nova)
CAPC = HC + Vector((0, 0.02 * ry, 0.03 * rz))
CAPR = Vector((rx * 1.07, ry * 1.07, rz * 1.05))


def hair_tex():
    n = ba.N
    g = ba.fbm(61, 2, 3, aniso=(1, 24))
    yy, xx = np.mgrid[0:n, 0:n]
    vv = yy / n
    uu = xx / n
    strands = 0.84 + 0.2 * g
    hl = np.exp(-((vv - 0.72 - 0.03 * np.sin(uu * math.tau * 3)) / 0.06) ** 2) * 0.16
    rgb = np.ones((n, n, 3)) * (strands + hl)[..., None]
    return ba.save_tex("c2_hair_strands", np.clip(rgb, 0, 1))


HAIRTEX = hair_tex()


def hsurf(lx, ly, lz, push=1.0):
    d = Vector((lx, ly, lz)).normalized()
    return CAPC + Vector((d.x * CAPR.x, d.y * CAPR.y, d.z * CAPR.z)) * push, Vector((d.x / CAPR.x, d.y / CAPR.y, d.z / CAPR.z)).normalized()


def hair_cap(name, fl, sl, bl, mat):
    o = ba.sphere(name, tuple(CAPC), tuple(CAPR), mat, 64)
    bpy.context.view_layer.update()
    o.data.transform(o.matrix_world)
    o.matrix_world = Matrix.Identity(4)
    bm = bmesh.new()
    bm.from_mesh(o.data)
    dead = []
    for f in bm.faces:
        c = f.calc_center_median()
        lx, ly, lz = (c.x - CAPC.x) / CAPR.x, (c.y - CAPC.y) / CAPR.y, (c.z - CAPC.z) / CAPR.z
        lim = fl if ly < -0.3 else (bl if ly > 0.35 else sl)
        if lz < lim:
            dead.append(f)
    bmesh.ops.delete(bm, geom=dead, context="FACES")
    bm.to_mesh(o.data)
    bm.free()
    so = o.modifiers.new("s", "SOLIDIFY")
    so.thickness = 0.03 * HT
    so.offset = -0.3
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    bpy.ops.object.modifier_apply(modifier="s")
    return o


def lobe(name, lx, ly, lz, scale, mat, drop=0.0, out=0.02, tilt=0.0):
    p, n = hsurf(lx, ly, lz)
    p = p + n * out * HT + Vector((0, 0, -drop * rz))
    yaw = math.atan2(n.x, -n.y)
    return ba.sphere(name, tuple(p), (scale[0] * rx, scale[1] * ry, scale[2] * rz), mat, 32, rot=(0, tilt, yaw))


def sculpt(name, parts, mat, cuts=()):
    bpy.ops.object.select_all(action="DESELECT")
    for o in parts:
        bpy.context.view_layer.update()
        o.data.transform(o.matrix_world)
        o.matrix_world = Matrix.Identity(4)
        o.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    h = bpy.context.view_layer.objects.active
    h.name = name
    rm = h.modifiers.new("rm", "REMESH")
    rm.mode = "VOXEL"
    rm.voxel_size = 0.0065 * HT
    bpy.ops.object.modifier_apply(modifier="rm")
    sm = h.modifiers.new("sm", "SMOOTH")
    sm.factor = 0.6
    sm.iterations = 8
    bpy.ops.object.modifier_apply(modifier="sm")
    if cuts:
        bm = bmesh.new()
        bm.from_mesh(h.data)
        for co, no, keep in cuts:
            bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-6, plane_co=co, plane_no=no,
                                   clear_outer=(keep == "below"), clear_inner=(keep == "above"))
        bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary], sides=0)
        bm.to_mesh(h.data)
        bm.free()
    dc = h.modifiers.new("dc", "DECIMATE")
    dc.ratio = 0.45
    bpy.ops.object.modifier_apply(modifier="dc")
    for p in h.data.polygons:
        p.use_smooth = True
    # UV esferica (fios descem do topo) + sombreamento por vertice (mais escuro junto a cabeca)
    me = h.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    uvl = me.uv_layers.active.data
    zs = [v.co.z for v in me.vertices]
    zmin, zmax = min(zs), max(zs)
    for p in me.polygons:
        cu = (math.atan2(p.center.x - CAPC.x, -(p.center.y - CAPC.y)) / math.tau + 0.5)
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            u = (math.atan2(co.x - CAPC.x, -(co.y - CAPC.y)) / math.tau + 0.5)
            if abs(u - cu) > 0.5:
                u += 1 if u < cu else -1
            uvl[li].uv = (u * 6, (co.z - zmin) / (zmax - zmin))
    ca = me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
    for i, v in enumerate(me.vertices):
        q = Vector(((v.co.x - HC.x) / rx, (v.co.y - HC.y) / ry, (v.co.z - HC.z) / rz))
        k = 0.8 + 0.2 * max(0.0, min(1.0, (q.length - 1.0) / 0.3))
        ca.data[i].color = (k, k, k, 1.0)
    me.materials.clear()
    me.materials.append(mat)
    print("CABELO", name, len(me.polygons), flush=True)
    return h



def hair_style(pid, name_pt, builder):
    if ONLY and pid not in ONLY:
        return
    hm = ba.mat("c2_hair", "#7a4a2c", 0.5, tex=HAIRTEX, sheen=0.6)
    parts, cuts = builder(hm)
    h = sculpt(pid, parts, hm, cuts)
    export_piece(pid, "hair", name_pt, [(h, "Head")], extra={"tint": "hair"})


def b_short(m):
    p = [hair_cap("c", 0.42, 0.12, -0.5, m)]
    for i, lx in enumerate((-0.62, -0.25, 0.12, 0.5)):  # franja de lado
        p.append(lobe("b%d" % i, lx, -0.85, 0.42, (0.3, 0.13, 0.3), m, drop=0.12 + 0.03 * (i % 2), tilt=0.35))
    for i, (lx, ly) in enumerate(((-0.3, -0.2), (0.25, -0.1), (0.0, 0.25), (-0.45, 0.3), (0.45, 0.3))):
        p.append(lobe("t%d" % i, lx, ly, 0.85, (0.32, 0.32, 0.22), m, out=0.03))
    for s in (-1, 1):
        p.append(lobe("s%d" % s, 0.95 * s, -0.05, 0.25, (0.16, 0.3, 0.32), m, drop=0.12))
    for i, lx in enumerate((-0.4, 0.0, 0.4)):
        p.append(lobe("n%d" % i, lx, 0.9, -0.2, (0.28, 0.16, 0.28), m, drop=0.05))
    return p, ()


def cut_obj(o, co, no, keep):
    bpy.context.view_layer.update()
    o.data.transform(o.matrix_world)
    o.matrix_world = Matrix.Identity(4)
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-6, plane_co=co, plane_no=no,
                           clear_outer=(keep == "below"), clear_inner=(keep == "above"))
    bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary], sides=0)
    bm.to_mesh(o.data)
    bm.free()
    return o


def b_bob(m):
    p = [hair_cap("c", 0.42, -0.45, -0.6, m)]
    brow = HC.z + 0.22 * rz
    fr = lobe("fr", 0.0, -0.9, 0.42, (0.95, 0.32, 0.45), m, out=0.0)
    p.append(cut_obj(fr, (0, 0, brow), UP, "above"))          # franja reta, cortada so na frente
    for s in (-1, 1):
        sd = lobe("sd%d" % s, 0.9 * s, 0.0, -0.05, (0.3, 0.8, 0.72), m, out=0.0)
        p.append(sd)
    p.append(lobe("bk", 0.0, 0.92, -0.2, (0.9, 0.35, 0.62), m, out=0.0))
    return p, [cl.cut((0, 0, HC.z - 0.6 * rz), UP, "above")]


def b_ponytail(m):
    p = [hair_cap("c", 0.42, 0.15, -0.35, m)]
    for i, lx in enumerate((-0.55, -0.15, 0.25, 0.6)):
        p.append(lobe("b%d" % i, lx, -0.85, 0.45, (0.28, 0.12, 0.28), m, drop=0.1, tilt=-0.3))
    root, n = hsurf(0.0, 0.85, 0.4, 1.02)
    p.append(ba.sphere("pt0", tuple(root), (0.28 * rx, 0.24 * ry, 0.26 * rz), m, 32))
    p.append(cl.lock("pt", root + Vector((0, 0.05 * ry, 0)), root + Vector((0, 0.5 * ry, -0.25 * rz)), root + Vector((0, 0.35 * ry, -1.05 * rz)), 0.3 * rx, m, flat=0.8, side=Vector((1, 0, 0)), n=18))
    return p, ()


def b_bun(m):
    p = [hair_cap("c", 0.45, 0.15, -0.4, m)]
    for i, lx in enumerate((-0.45, 0.0, 0.45)):
        p.append(lobe("b%d" % i, lx, -0.85, 0.48, (0.33, 0.12, 0.25), m, drop=0.08))
    top, n = hsurf(0.0, 0.15, 1.0, 1.05)
    p.append(ba.sphere("bun", tuple(top + Vector((0, 0, 0.18 * rz))), (0.42 * rx, 0.42 * ry, 0.36 * rz), m, 40))
    return p, ()


def b_spiky(m):
    p = [hair_cap("c", 0.5, 0.15, -0.45, m)]
    random.seed(4)
    for i, (lx, ly, L) in enumerate(((-0.35, -0.55, 0.55), (0.0, -0.6, 0.7), (0.35, -0.55, 0.55), (-0.5, -0.15, 0.45), (0.5, -0.15, 0.45), (-0.2, 0.15, 0.5), (0.2, 0.15, 0.5))):
        root, n = hsurf(lx, ly, 0.8, 0.98)
        tip = root + n * 0.22 * rx * L / 0.5 + Vector((lx * 0.1 * rx, 0.55 * ry * L, 0.32 * rz * L))  # topete: sobe e vai para tras
        mid = root + (tip - root) * 0.5 + Vector((0, -0.05 * ry, 0.12 * rz))
        p.append(cl.lock("sp%d" % i, root, mid, tip, 0.3 * rx, m, flat=0.6, side=n, n=14))
    for i, lx in enumerate((-0.4, 0.0, 0.4)):
        p.append(lobe("n%d" % i, lx, 0.9, -0.15, (0.28, 0.16, 0.26), m))
    return p, ()



hair_style("hair_curto", "Cachinhos", b_short)
hair_style("hair_chanel", "Chanel com Franja", b_bob)
hair_style("hair_rabo", "Rabo de Cavalo", b_ponytail)
hair_style("hair_coque", "Coque", b_bun)
hair_style("hair_topete", "Topete Espetado", b_spiky)

old_items = []
if ONLY and os.path.exists(MANI):
    old_items = [i for i in json.load(open(MANI, encoding="utf-8"))["items"] if i["id"] not in {e["id"] for e in EXPORTED}]
json.dump({"items": old_items + EXPORTED}, open(MANI, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("CHAR2 OK", len(EXPORTED), "pecas", flush=True)
