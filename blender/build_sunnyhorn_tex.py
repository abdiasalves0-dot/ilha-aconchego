"""Protagonista a partir do OBJ texturizado 'Sunnyhorn Meadow' (Meshy, fornecido pelo usuario).
Mantem malha e textura originais (sem decimar), remove a haste de suporte, separa cabeca/bracos/pernas,
baixa os bracos da T-pose e exporta assets/models/player.glb.
Uso: blender -b -P build_sunnyhorn_tex.py
"""
import bpy, bmesh, os, math
from mathutils import Vector, Matrix
from collections import defaultdict

ROOTDIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOTDIR, "vendor_ref", "sunnyhorn_tex", "Meshy_AI_Sunnyhorn_Meadow_1013005653_texture.obj")
OUT = os.path.join(ROOTDIR, "assets", "models", "player.glb")
H_FINAL = 2.35

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()
bpy.ops.wm.obj_import(filepath=SRC)
src = [o for o in bpy.context.selected_objects if o.type == "MESH"][0]
bpy.context.view_layer.objects.active = src
src.select_set(True)
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
me = src.data

vs = [v.co for v in me.vertices]
mn = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
mx = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
print("BBOX bruto", tuple(round(c, 3) for c in mn), tuple(round(c, 3) for c in mx))
HT = mx.z - mn.z
u = HT / 50.0  # medidas abaixo seguem a escala de 50 de altura
me.transform(Matrix.Translation((-(mn.x + mx.x) / 2, -(mn.y + mx.y) / 2, -mn.z)))

# haste de suporte colada nas costas
bm = bmesh.new()
bm.from_mesh(me)
rod = []
for f in bm.faces:
    c = f.calc_center_median()
    if c.y > 1.6 * u and c.z < 24.0 * u and abs(c.x) < 3.0 * u:
        rod.append(f)
bmesh.ops.delete(bm, geom=rod, context="FACES")
bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
bm.to_mesh(me)
bm.free()
print("SUPORTE removido faces:", len(rod))

# material: mantem a textura do Meshy, ajusta para visual macio
for m in me.materials:
    m.use_backface_culling = False
    b = m.node_tree.nodes.get("Principled BSDF")
    if b:
        b.inputs["Roughness"].default_value = 0.75
        b.inputs["Metallic"].default_value = 0.0
        for k in ("Specular IOR Level", "Specular"):
            if k in b.inputs:
                b.inputs[k].default_value = 0.3
for p in me.polygons:
    p.use_smooth = True

Z_PANTS, Z_NECK = 15.4 * u, 25.7 * u
TORSO_HALF = 5.7 * u
PIV = {"Head": (0, 0, Z_NECK), "ArmL": (-TORSO_HALF, 0, 24.3 * u), "ArmR": (TORSO_HALF, 0, 24.3 * u),
       "FootL": (-2.4 * u, 0, Z_PANTS), "FootR": (2.4 * u, 0, Z_PANTS)}


def part_of(c):
    x, y, z = c
    if z >= Z_NECK and abs(x) < TORSO_HALF * 1.9:
        return "Head"
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
