"""Personagem-base padrao (chibi estilo ACNH) a partir da folha de turnaround do Meshy.
Extrai o boneco de FRENTE da folha, mantem malha e textura originais, separa cabeca/bracos/pernas,
baixa os bracos da T-pose e exporta um .glb com os pivos usados pelo jogo (Root, Head, ArmL/R, FootL/R).
Uso: blender -b -P build_base_character.py -- [saida.glb]
"""
import bpy, bmesh, os, sys, math
from mathutils import Vector, Matrix
from collections import defaultdict

ROOTDIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOTDIR, "vendor_ref", "chibi_base", "Meshy_AI_Chibi_Base_Model_Turn_1013010524_texture.obj")
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[0] if argv else os.path.join(ROOTDIR, "assets", "models", "player.glb")
H_FINAL = 2.3

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()
bpy.ops.wm.obj_import(filepath=SRC)
src = [o for o in bpy.context.selected_objects if o.type == "MESH"][0]
bpy.context.view_layer.objects.active = src
src.select_set(True)
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
me = src.data

# ---------------------------------------------------------------- 1) ilhas (pecas soltas) da folha
bm = bmesh.new()
bm.from_mesh(me)
bm.verts.ensure_lookup_table()
seen, islands = set(), []
for v in bm.verts:
    if v.index in seen:
        continue
    stack, isl = [v], []
    seen.add(v.index)
    while stack:
        a = stack.pop()
        isl.append(a.index)
        for e in a.link_edges:
            b = e.other_vert(a)
            if b.index not in seen:
                seen.add(b.index)
                stack.append(b)
    islands.append(isl)
bm.free()
info = []
for isl in islands:
    pts = [me.vertices[i].co for i in isl]
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    info.append((isl, mn, mx))
info.sort(key=lambda t: -len(t[0]))
for isl, mn, mx in info[:12]:
    print("ILHA", len(isl), tuple(round(c, 3) for c in mn), tuple(round(c, 3) for c in mx))

# boneco de corpo inteiro = ilhas altas (fileira de cima); o de FRENTE e o mais a esquerda
tall = [t for t in info if (t[2].z - t[1].z) > 0.75 * max(i[2].z - i[1].z for i in info)]
front = min(tall, key=lambda t: (t[1].x + t[2].x) / 2)
fx0, fx1 = front[1].x, front[2].x
fz0, fz1 = front[1].z, front[2].z
# inclui pecas pequenas (olhos, orelhas...) que estejam dentro da caixa do boneco de frente
keep = set()
for isl, mn, mx in info:
    c = (mn + mx) / 2
    if fx0 - 0.02 <= c.x <= fx1 + 0.02 and fz0 - 0.02 <= c.z <= fz1 + 0.02:
        keep.update(isl)
print("FRENTE bbox x", round(fx0, 3), round(fx1, 3), "z", round(fz0, 3), round(fz1, 3), "verts", len(keep))

bm = bmesh.new()
bm.from_mesh(me)
bm.verts.ensure_lookup_table()
bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.index not in keep], context="VERTS")
bm.to_mesh(me)
bm.free()

vs = [v.co for v in me.vertices]
mn = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
mx = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
HT = mx.z - mn.z
me.transform(Matrix.Translation((-(mn.x + mx.x) / 2, -(mn.y + mx.y) / 2, -mn.z)))
vs = [v.co for v in me.vertices]

# confere orientacao: o rosto deve olhar para -Y (frente no jogo)
head_pts = [v for v in vs if v.z > 0.75 * HT]
front_dir = sum((v.y for v in head_pts), 0.0) / len(head_pts)
print("ALTURA", round(HT, 3), "LARGURA", round(mx.x - mn.x, 3))

# ---------------------------------------------------------------- 2) medidas do corpo (largura por faixa de altura)
def width_at(zf, band=0.02):
    sel = [abs(v.x) for v in vs if abs(v.z - zf * HT) < band * HT]
    return max(sel) if sel else 0.0


for zf in (0.1, 0.2, 0.3, 0.4, 0.45, 0.5, 0.53, 0.56, 0.6, 0.7, 0.8, 0.9):
    print("LARG z=%.2f  %.3f" % (zf, width_at(zf) / HT))

# barriga (abaixo dos bracos) define a meia-largura do tronco
TORSO_HALF = max(width_at(0.4), width_at(0.45)) * 1.1
Z_NECK = 0.585 * HT
Z_HIP = 0.37 * HT
ARM_Z = 0.53 * HT
print("TORSO_HALF", round(TORSO_HALF / HT, 3))

for m in me.materials:
    m.use_backface_culling = False
    b = m.node_tree.nodes.get("Principled BSDF")
    if b:
        b.inputs["Roughness"].default_value = 0.7
        b.inputs["Metallic"].default_value = 0.0
        for k in ("Specular IOR Level", "Specular"):
            if k in b.inputs:
                b.inputs[k].default_value = 0.3
for p in me.polygons:
    p.use_smooth = True

# dobra suave do ombro: o giro cresce de 0 (no tronco) ate ARM_ANGLE (no braco), mantendo a malha conectada
ARM_ANGLE = math.radians(70)
# borda real do ombro: largura do corpo logo acima/abaixo da linha dos bracos (sem contar os bracos)
arm_zs = [v.z for v in vs if abs(v.x) > 0.2 * HT and v.z < Z_NECK]
ARM_Z = (min(arm_zs) + max(arm_zs)) / 2
ARM_R = (max(arm_zs) - min(arm_zs)) / 2
X0 = max(width_at((ARM_Z - ARM_R * 1.3) / HT, 0.01), TORSO_HALF) * 0.82  # onde a dobra comeca (borda do ombro)
BLEND = ARM_R * 2.6           # faixa curta: so a "articulacao" curva, o resto do braco fica reto
print("OMBRO X0", round(X0 / HT, 3), "ARM_Z", round(ARM_Z / HT, 3), "ARM_R", round(ARM_R / HT, 3))
SH_Z = ARM_Z
PIV = {"Head": (0, 0, Z_NECK), "ArmL": (-X0, 0, SH_Z), "ArmR": (X0, 0, SH_Z),
       "FootL": (-0.06 * HT, 0, Z_HIP), "FootR": (0.06 * HT, 0, Z_HIP)}


def part_of(c):
    x, y, z = c
    if z >= Z_NECK:
        return "Head"
    if abs(x) > X0 + BLEND * 0.6 and z > 0.44 * HT:
        return "ArmL" if x < 0 else "ArmR"
    if z < Z_HIP - 0.02 * HT:
        return "FootL" if x < 0 else "FootR"
    return "Root"


groups = defaultdict(list)
for p in me.polygons:
    groups[part_of(p.center)].append(p.index)
print("PARTES", {k: len(v) for k, v in groups.items()})


def smooth01(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


bent = 0
for v in me.vertices:
    x, y, z = v.co
    if not (0.42 * HT < z < Z_NECK + 0.01 * HT) or abs(x) <= X0:
        continue
    s_ = 1 if x > 0 else -1
    t = smooth01((abs(x) - X0) / BLEND)
    ang = ARM_ANGLE * t * s_
    px = X0 * s_
    dx, dz = x - px, z - SH_Z
    ca, sa = math.cos(ang), math.sin(ang)
    # rotacao em torno do eixo Y passando pelo ombro: braco desce
    v.co.x = px + dx * ca - dz * sa * (-1)
    v.co.z = SH_Z - dx * sa + dz * ca
    bent += 1
me.update()
print("DOBRA vertices:", bent)


def extract(name, idxs):
    b = bmesh.new()
    b.from_mesh(me)
    b.faces.ensure_lookup_table()
    keepf = set(idxs)
    bmesh.ops.delete(b, geom=[f for f in b.faces if f.index not in keepf], context="FACES")
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
for name, idxs in groups.items():
    ob = extract(name, idxs)
    ob.data.transform(Matrix.Scale(S, 4))
    if name == "Root":
        att(ob, root)
    else:
        px, py, pz = PIV[name]
        att(ob, pivot(name, (px * S, py * S, pz * S), root))
bpy.data.objects.remove(src)

bpy.ops.object.select_all(action="DESELECT")
stack = [root]
while stack:
    ob = stack.pop()
    ob.select_set(True)
    stack.extend(ob.children)
bpy.ops.export_scene.gltf(filepath=OUT, export_format="GLB", use_selection=True, export_apply=True, export_yup=True, export_image_format="AUTO")
print("OK", OUT)
