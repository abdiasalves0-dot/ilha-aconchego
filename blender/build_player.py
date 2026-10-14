"""Monta o jogador a partir do modelo 'Macchiato' (OBJ fornecido pelo usuario):
separa cabeca / bracos / pernas, baixa os bracos (T-pose -> repouso) e exporta player.glb com os pivos usados pelo jogo.
Uso: blender -b -P build_player.py
"""
import bpy, bmesh, os, math
from mathutils import Vector, Matrix

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEXD = os.path.join(ROOT, "assets", "textures", "macchiato")
OUT = os.path.join(ROOT, "assets", "models", "player.glb")
S = 2.35 / 17.56  # altura final ~2.35 unidades (orelhas incluidas)
TEXSIZE = 1024

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()
bpy.ops.wm.obj_import(filepath=os.path.join(ROOT, "vendor_ref", "macchiato", "Macchiato.obj"))
src = [o for o in bpy.context.scene.objects if o.type == "MESH"][0]
bpy.context.view_layer.objects.active = src
src.select_set(True)
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
me = src.data
zmin = min(v.co.z for v in me.vertices)

# ---------------------------------------------------------------- materiais com textura
for slot in me.materials:
    m = slot
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != "BSDF_PRINCIPLED" and n.type != "OUTPUT_MATERIAL":
            nt.nodes.remove(n)
    b = nt.nodes["Principled BSDF"]

    def load(suffix, nc=False):
        for ext in ("jpg", "png"):
            p = os.path.join(TEXD, "%s_%s.%s" % (m.name, suffix, ext))
            if os.path.exists(p):
                img = bpy.data.images.load(p)
                img.scale(TEXSIZE, TEXSIZE)
                if nc:
                    img.colorspace_settings.name = "Non-Color"
                t = nt.nodes.new("ShaderNodeTexImage")
                t.image = img
                return t
        return None
    a = load("albedo")
    if a:
        nt.links.new(a.outputs["Color"], b.inputs["Base Color"])
    nm = load("normal", True)
    if nm:
        nn = nt.nodes.new("ShaderNodeNormalMap")
        nn.inputs["Strength"].default_value = 0.8
        nt.links.new(nm.outputs["Color"], nn.inputs["Color"])
        nt.links.new(nn.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Roughness"].default_value = 0.85
    b.inputs["Metallic"].default_value = 0.0
    print("MAT", m.name, bool(a), bool(nm))

# ---------------------------------------------------------------- classificacao das faces
SWEATER = [i for i, m in enumerate(me.materials) if m.name == "lambert3SG"][0]


def part_of(p):
    c = sum((me.vertices[v].co for v in p.vertices), Vector()) / len(p.vertices)
    x, y, z = c
    if p.material_index == SWEATER:
        if abs(x) > 1.9 and z > 4.6:
            return "ArmL" if x < 0 else "ArmR"
        return "Root"
    if abs(x) > 1.9 and 4.6 < z < 8.0:
        return "ArmL" if x < 0 else "ArmR"
    if z > 7.5:
        return "Head"
    if z < 3.45 and y < 1.2:
        return "FootL" if x < 0 else "FootR"
    return "Root"


groups = {k: [] for k in ("Root", "Head", "ArmL", "ArmR", "FootL", "FootR")}
for p in me.polygons:
    groups[part_of(p)].append(p.index)
print("PARTES", {k: len(v) for k, v in groups.items()})

ARM_DOWN = math.radians(72)
PIV = {"Head": (0, 0, 7.5), "ArmL": (-1.9, 0, 6.3), "ArmR": (1.9, 0, 6.3), "FootL": (-0.9, 0, 3.4), "FootR": (0.9, 0, 3.4)}


def extract(name, idxs):
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    keep = set(idxs)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.index not in keep], context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    new = bpy.data.meshes.new(name)
    bm.to_mesh(new)
    bm.free()
    for m in me.materials:
        new.materials.append(m)
    for p in new.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name + "Mesh", new)
    bpy.context.collection.objects.link(ob)
    return ob


def pivot(name, loc, parent=None):
    e = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(e)
    e.location = loc
    if parent:
        bpy.context.view_layer.update()
        e.parent = parent
        e.matrix_parent_inverse = parent.matrix_world.inverted()
    bpy.context.view_layer.update()
    return e


def attach(o, parent):
    bpy.context.view_layer.update()
    o.parent = parent
    o.matrix_parent_inverse = parent.matrix_world.inverted()


root = pivot("Root", (0, 0, 0))
for name, idxs in groups.items():
    ob = extract(name, idxs)
    t = Matrix.Translation((0, 0, -zmin))  # pes no chao
    if name in ("ArmL", "ArmR"):
        px, py, pz = PIV[name]
        ang = -ARM_DOWN if name == "ArmL" else ARM_DOWN
        ob.data.transform(Matrix.Translation((px, py, pz)) @ Matrix.Rotation(ang, 4, "Y") @ Matrix.Translation((-px, -py, -pz)))
    ob.data.transform(t)
    ob.data.transform(Matrix.Scale(S, 4))
    if name == "Root":
        attach(ob, root)
    else:
        px, py, pz = PIV[name]
        pv = pivot(name, ((px) * S, py * S, (pz - zmin) * S), root)
        attach(ob, pv)

bpy.data.objects.remove(src)
bpy.ops.object.select_all(action="DESELECT")
stack = [root]
while stack:
    o = stack.pop()
    o.select_set(True)
    stack.extend(o.children)
bpy.ops.export_scene.gltf(filepath=OUT, export_format="GLB", use_selection=True, export_apply=True, export_yup=True, export_image_format="AUTO")
print("OK", OUT)
