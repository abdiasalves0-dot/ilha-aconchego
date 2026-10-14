"""Gera os modelos 3D detalhados (alta resolução + texturas procedurais) e exporta .glb.
Uso:  blender -b -P build_assets.py
"""
import bpy, math, os, bmesh, random
import numpy as np
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "models")
TEX = os.path.join(ROOT, "assets", "textures")
os.makedirs(OUT, exist_ok=True)
os.makedirs(TEX, exist_ok=True)

# ------------------------------------------------------------------ texturas procedurais (numpy)
N = 512


def hexrgb(h):
    return np.array([int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)])


def _up(grid, n):
    gy, gx = grid.shape
    def ax(g):
        xs = np.arange(n) / n * g
        i0 = np.floor(xs).astype(int) % g
        f = xs - np.floor(xs)
        f = f * f * (3 - 2 * f)
        return i0, (i0 + 1) % g, f
    y0, y1, fy = ax(gy)
    x0, x1, fx = ax(gx)
    fy, fx = fy[:, None], fx[None, :]
    return (grid[np.ix_(y0, x0)] * (1 - fy) * (1 - fx) + grid[np.ix_(y0, x1)] * (1 - fy) * fx
            + grid[np.ix_(y1, x0)] * fy * (1 - fx) + grid[np.ix_(y1, x1)] * fy * fx)


def fbm(seed, base=4, octs=4, aniso=(1, 1)):
    rs = np.random.RandomState(seed)
    out, amp, tot = np.zeros((N, N)), 1.0, 0.0
    for o in range(octs):
        g = base * 2 ** o
        out += amp * _up(rs.rand(max(1, g * aniso[0]), max(1, g * aniso[1])), N)
        tot += amp
        amp *= 0.5
    return out / tot


_tex = {}


def save_tex(name, rgb):
    path = os.path.join(TEX, name + ".png")
    img = bpy.data.images.new(name, N, N, alpha=False)
    a = np.ones((N, N, 4), dtype=np.float32)
    a[..., :3] = np.clip(rgb, 0, 1)
    img.pixels.foreach_set(a.ravel())
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)
    return path


def save_rgba(name, rgba):
    path = os.path.join(TEX, name + ".png")
    img = bpy.data.images.new(name, N, N, alpha=True)
    img.pixels.foreach_set(np.clip(rgba, 0, 1).astype(np.float32).ravel())
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)
    return path


def maple_leaf(c_dark, c_light, seed=1):
    """Folha de bordo (RGBA) estilo Animal Crossing."""
    yy, xx = np.mgrid[0:N, 0:N]
    dx, dy = (xx - N / 2) / (N / 2), (yy - N * 0.45) / (N / 2)
    th = np.arctan2(dx, dy)
    rho = np.hypot(dx, dy)
    lobes = np.abs(np.cos(2.5 * th)) ** 0.7
    r = (0.42 + 0.5 * lobes) * (0.93 + 0.07 * np.abs(np.sin(11 * th))) * 0.98
    mask = (rho < r) & (dy > -0.62)
    f = fbm(seed, 6, 3)
    t = np.clip(rho / 0.95, 0, 1)
    col = c_light[None, None, :] * (1 - t[..., None] * 0.55) + c_dark[None, None, :] * (t[..., None] * 0.55)
    col = col * (0.92 + 0.16 * f[..., None])
    vein = np.zeros_like(rho)
    for a in (0, 0.75, -0.75, 1.5, -1.5):
        d = np.abs(np.sin(th - a)) * rho
        vein = np.maximum(vein, (d < 0.012) * 1.0)
    col = np.where(vein[..., None] > 0, col * 1.15, col)
    rgba = np.zeros((N, N, 4))
    rgba[..., :3] = col
    rgba[..., 3] = mask
    edge = mask & (rho > r - 0.05)
    rgba[edge, :3] *= 0.8
    return rgba


def make_tex(kind, base, base2=None, seed=1):
    key = (kind, base, base2, seed)
    if key in _tex:
        return _tex[key]
    c1 = hexrgb(base)
    c2 = hexrgb(base2) if base2 else c1
    yy, xx = np.mgrid[0:N, 0:N]
    if kind == "fur":
        v = 0.86 + 0.2 * fbm(seed, 5, 3) + 0.1 * (fbm(seed + 7, 64, 1) - 0.5)
        rgb = c1 * v[..., None]
    elif kind == "leaf":
        f = fbm(seed, 6, 4)
        rgb = (c1 * (1 - f[..., None]) + c2 * f[..., None]) * (0.85 + 0.3 * fbm(seed + 3, 24, 2)[..., None])
        spots = fbm(seed + 5, 16, 1) > 0.78
        rgb[spots] *= 1.12
    elif kind == "bark":
        f = fbm(seed, 3, 4, aniso=(1, 6))
        rgb = c1 * (0.6 + 0.7 * f[..., None])
    elif kind == "planks":
        h = 85
        row = yy // h
        rs = np.random.RandomState(seed)
        shade = (0.9 + 0.12 * rs.rand(10))[row]
        grain = 0.92 + 0.16 * fbm(seed, 2, 3, aniso=(8, 1))
        v = shade * grain
        edge = (yy % h) < 4
        rgb = c1 * v[..., None]
        rgb[edge] *= 0.55
    elif kind == "shingle":
        h, w = 64, 64
        row = yy // h
        xo = (xx + (row % 2) * (w // 2)) % w
        col = (xx + (row % 2) * (w // 2)) // w
        rs = np.random.RandomState(seed)
        br = (0.85 + 0.25 * rs.rand(16, 16))[row % 16, col % 16]
        ym = yy % h
        scallop = 50 + 8 * np.cos((xo - w / 2) / (w / 2) * math.pi / 2) ** 2 * 0
        rgb = c1 * br[..., None] * (0.92 + 0.1 * fbm(seed, 24, 2)[..., None])
        rgb[ym > scallop + 6] *= 0.6
        rgb[(xo < 2)] *= 0.7
        rgb[ym < 10] *= 1.0 - 0.0
    elif kind == "brick":
        h, w = 64, 128
        row = yy // h
        xo = (xx + (row % 2) * (w // 2)) % w
        rs = np.random.RandomState(seed)
        br = (0.85 + 0.25 * rs.rand(16, 16))[row % 16, ((xx + (row % 2) * (w // 2)) // w) % 16]
        rgb = c1 * br[..., None]
        mortar = ((yy % h) < 5) | (xo < 5)
        rgb[mortar] = c2
    elif kind == "plaster":
        f = fbm(seed, 5, 4)
        rgb = c1 * (0.93 + 0.12 * f[..., None])
    elif kind == "stripes":
        s = ((yy // 64) % 2).astype(float)
        weave = 0.93 + 0.08 * (((xx // 2 + yy // 2) % 2))
        rgb = (c1 * (1 - s[..., None]) + c2 * s[..., None]) * weave[..., None]
    elif kind == "dots":
        gx, gy = (xx % 64) - 32, (yy % 64) - 32
        d = (gx ** 2 + gy ** 2) < 11 ** 2
        weave = 0.94 + 0.07 * (((xx // 2 + yy // 2) % 2))
        rgb = np.where(d[..., None], c2, c1) * weave[..., None]
    elif kind == "rock":
        f = fbm(seed, 4, 5)
        rgb = c1 * (0.7 + 0.55 * f[..., None])
    elif kind == "tartan":
        f = 0.93 + 0.1 * fbm(seed, 48, 1)
        rgb = c1 * f[..., None]
        lx = (xx % 64) < 3
        ly = (yy % 64) < 3
        lx2 = ((xx + 32) % 64) < 1
        ly2 = ((yy + 32) % 64) < 1
        rgb[lx | ly] = c2 * 0.95
        rgb[lx2 | ly2] = (c1 * 0.6 + c2 * 0.4)
        weave = 0.94 + 0.07 * (((xx // 2 + yy // 2) % 2))
        rgb = rgb * weave[..., None]
    elif kind == "knit":
        sx = np.abs(((xx % 24) - 12) / 12.0)
        row = ((yy + sx * 10) % 16) / 16.0
        v = 0.78 + 0.26 * np.sin(row * math.pi) + 0.05 * (fbm(seed, 32, 1) - 0.5)
        rib = ((yy // 16) % 2) * 0.0
        rgb = c1 * v[..., None]
    elif kind == "plaid":
        a = ((xx // 48) % 2).astype(float)
        b = ((yy // 48) % 2).astype(float)
        m = 1 - 0.25 * a - 0.25 * b
        weave = 0.94 + 0.07 * (((xx // 2 + yy // 2) % 2))
        rgb = (c1 * m[..., None] + c2 * (a * b)[..., None] * 0.6) * weave[..., None]
    elif kind == "stone":
        f = fbm(seed, 6, 4)
        rgb = c1 * (0.85 + 0.2 * f[..., None])
        rgb[((yy % 128) < 4) | (((xx + (yy // 128) * 64) % 128) < 4)] *= 0.7
    else:
        rgb = np.ones((N, N, 3)) * c1
    if kind == "mapleleaf":
        p = save_rgba("%s_%s_%d" % (kind, base[1:], seed), maple_leaf(c1, c2, seed))
        _tex[key] = p
        return p
    p = save_tex("%s_%s_%d" % (kind, base[1:], seed), rgb)
    _tex[key] = p
    return p


# ------------------------------------------------------------------ utilidades Blender
_mats = {}


def clear():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    for m in list(bpy.data.meshes):
        bpy.data.meshes.remove(m)
    for m in list(bpy.data.materials):
        bpy.data.materials.remove(m)
    _mats.clear()


def lin(c):
    return ((c + 0.055) / 1.055) ** 2.4 if c > 0.04045 else c / 12.92


def mat(name, color, rough=0.85, tex=None, spec=0.4, sheen=0.0, emit=None):
    key = name
    if key in _mats:
        return _mats[key]
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    r, g, b = [lin(int(color[i:i + 2], 16) / 255) for i in (1, 3, 5)]
    bsdf.inputs["Base Color"].default_value = (r, g, b, 1)
    bsdf.inputs["Roughness"].default_value = rough
    for k in ("Specular IOR Level", "Specular"):
        if k in bsdf.inputs:
            bsdf.inputs[k].default_value = spec
    if sheen and "Sheen Weight" in bsdf.inputs:
        bsdf.inputs["Sheen Weight"].default_value = sheen
    if tex:
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(tex)
        nt.links.new(t.outputs["Color"], bsdf.inputs["Base Color"])
        if "mapleleaf" in tex:
            nt.links.new(t.outputs["Alpha"], bsdf.inputs["Alpha"])
    if emit:
        er, eg, eb = [lin(int(emit[i:i + 2], 16) / 255) for i in (1, 3, 5)]
        bsdf.inputs["Emission Color"].default_value = (er, eg, eb, 1)
        bsdf.inputs["Emission Strength"].default_value = 1.0
    _mats[key] = m
    return m


def tmat(name, kind, base, base2=None, seed=1, rough=0.85, **kw):
    return mat(name, base, rough, tex=make_tex(kind, base, base2, seed), **kw)


def uv(o, size=1.6):
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.cube_project(cube_size=size)
    bpy.ops.object.mode_set(mode="OBJECT")


def _fin(o, name, m, smooth=True):
    o.name = name
    if m:
        o.data.materials.append(m)
    if smooth:
        for p in o.data.polygons:
            p.use_smooth = True
    return o


def sphere(name, loc, scale, m, seg=48, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1, segments=seg, ring_count=seg // 2, location=loc, rotation=rot)
    o = bpy.context.object
    o.scale = scale
    return _fin(o, name, m)


def cyl(name, loc, r1, r2, h, m, seg=32, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cone_add(radius1=r1, radius2=r2, depth=h, vertices=seg, location=loc, rotation=rot)
    return _fin(bpy.context.object, name, m)


def cone(name, loc, r, h, m, seg=32):
    return cyl(name, loc, r, 0.0, h, m, seg)


def torus(name, loc, major, minor, m, rot=(0, 0, 0), scale=(1, 1, 1)):
    bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor, major_segments=32, minor_segments=12, location=loc, rotation=rot)
    o = bpy.context.object
    o.scale = scale
    return _fin(o, name, m)


def box(name, loc, size, m, bevel=0.04, uvsize=1.6):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object
    o.scale = size
    bpy.ops.object.transform_apply(scale=True)
    if bevel:
        bv = o.modifiers.new("b", "BEVEL")
        bv.width = bevel
        bv.segments = 4
        bpy.ops.object.modifier_apply(modifier="b")
    _fin(o, name, m)
    uv(o, uvsize)
    return o


def join(objs, name):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    o = bpy.context.object
    o.name = name
    return o


def export(name, objs):
    bpy.ops.object.select_all(action="DESELECT")
    stack = list(objs)
    while stack:
        o = stack.pop()
        o.select_set(True)
        stack.extend(o.children)
    path = os.path.join(OUT, name + ".glb")
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_apply=True, export_yup=True,
                              export_image_format="AUTO")
    print("OK", path)


def pivot(name, loc, parent=None):
    e = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(e)
    e.location = loc
    if parent:
        e.parent = parent
        e.matrix_parent_inverse = parent.matrix_world.inverted()
    return e


def attach(o, parent):
    o.parent = parent
    o.matrix_parent_inverse = parent.matrix_world.inverted()


def noisy(o, amt, seed=3):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    random.seed(seed)
    for v in bm.verts:
        v.co += v.normal * random.uniform(-amt, amt)
    bm.to_mesh(o.data)
    bm.free()


def half_torus(name, loc, major, minor, m, rot=(0, 0, 0)):
    """Meia-lua (sorriso)."""
    o = torus(name, loc, major, minor, m, rot)
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z > 0.0001], context="VERTS")
    bm.to_mesh(o.data)
    bm.free()
    return o


# ------------------------------------------------------------------ personagens
def animal(file, fur, belly, ears, shirt=None, shirt2=None, pattern="stripes", cheek="#ff9fb0", seed=1, snout_size=1.0, hat=None):
    clear()
    F = tmat("fur" + file, "fur", fur, seed=seed, rough=0.95, sheen=0.6)
    B = tmat("belly" + file, "fur", belly, seed=seed + 1, rough=0.95, sheen=0.6)
    EYE = mat("eye", "#16100f", 0.12, spec=1.0)
    WHITE = mat("white", "#ffffff", 0.2)
    NOSE = mat("nose" + file, "#2b1c1c", 0.25, spec=1.0)
    CH = mat("cheek", cheek, 0.9)
    BROW = mat("brow" + file, "#3a2a24", 0.9)
    root = pivot("Root", (0, 0, 0))
    body_m = tmat("shirt" + file, pattern, shirt, shirt2 or "#ffffff", seed=2, rough=0.95, sheen=1.0) if shirt else F
    body = sphere("Body", (0, 0, 0.55), (0.5, 0.43, 0.52), body_m)
    attach(body, root)
    if not shirt:
        attach(sphere("Belly", (0, -0.22, 0.52), (0.34, 0.25, 0.37), B), root)
    else:
        attach(torus("Collar", (0, -0.02, 0.97), 0.3, 0.05, mat("collar", "#ffffff", 0.9), scale=(1, 0.9, 0.8)), root)
        for i in range(3):
            attach(sphere("Button", (0, -0.435, 0.8 - i * 0.16), (0.035, 0.02, 0.035), mat("btn", "#fff3c4", 0.3), 16), root)
    head = pivot("Head", (0, 0, 1.2), root)
    attach(sphere("HeadMesh", (0, 0, 1.45), (0.68, 0.6, 0.57), F), head)
    for s in (-1, 1):
        attach(sphere("Eye", (0.23 * s, -0.5, 1.5), (0.075, 0.05, 0.11), EYE, 32), head)
        attach(sphere("EyeHL", (0.245 * s, -0.545, 1.55), (0.026, 0.014, 0.036), WHITE, 16), head)
        attach(sphere("EyeHL2", (0.215 * s, -0.54, 1.46), (0.012, 0.008, 0.016), WHITE, 12), head)
        attach(sphere("Brow", (0.24 * s, -0.5, 1.66), (0.075, 0.025, 0.02), BROW, 16, rot=(0, math.radians(-12 * s), 0)), head)
        attach(sphere("Cheek", (0.38 * s, -0.43, 1.36), (0.11, 0.03, 0.07), CH, 20), head)
    attach(sphere("Snout", (0, -0.5, 1.32), (0.2 * snout_size, 0.15, 0.14 * snout_size), B, 32), head)
    attach(sphere("Nose", (0, -0.645, 1.38), (0.065, 0.04, 0.048), NOSE, 24), head)
    attach(half_torus("Mouth", (0, -0.6, 1.3), 0.06, 0.008, BROW, rot=(math.radians(90), 0, 0)), head)
    for s in (-1, 1):
        if ears == "round":
            e = sphere("Ear", (0.5 * s, 0, 1.93), (0.18, 0.11, 0.18), F, 32)
            attach(sphere("EarIn", (0.5 * s, -0.075, 1.93), (0.1, 0.05, 0.1), B, 24), head)
        elif ears == "pointy":
            e = cone("Ear", (0.4 * s, 0, 2.0), 0.21, 0.4, F, 4)
            e.rotation_euler = (0, math.radians(18 * s), math.radians(45))
            for p in e.data.polygons:
                p.use_smooth = False
            sb = e.modifiers.new("s", "SUBSURF")
            sb.levels = 2
            bpy.ops.object.select_all(action="DESELECT")
            bpy.context.view_layer.objects.active = e
            bpy.ops.object.modifier_apply(modifier="s")
            for p in e.data.polygons:
                p.use_smooth = True
            attach(cone("EarIn", (0.4 * s, -0.06, 1.98), 0.12, 0.28, mat("earin2", "#ffc2cc", 0.9), 4), head)
        else:
            e = sphere("Ear", (0.2 * s, 0, 2.22), (0.13, 0.075, 0.42), F, 32, rot=(0, math.radians(10 * s), 0))
            attach(sphere("EarIn", (0.2 * s, -0.05, 2.22), (0.065, 0.03, 0.31), mat("earin", "#ffc2cc", 0.9), 24, rot=(0, math.radians(10 * s), 0)), head)
        attach(e, head)
    for s, nm in ((-1, "ArmL"), (1, "ArmR")):
        p = pivot(nm, (0.5 * s, 0, 0.8), root)
        attach(sphere(nm + "Mesh", (0.58 * s, 0, 0.62), (0.14, 0.14, 0.31), body_m, 32, rot=(0, math.radians(-12 * s), 0)), p)
        attach(sphere(nm + "Hand", (0.63 * s, 0, 0.36), (0.125, 0.125, 0.125), F, 24), p)
        attach(sphere(nm + "Thumb", (0.63 * s, -0.1, 0.38), (0.05, 0.05, 0.06), F, 16), p)
    for s, nm in ((-1, "FootL"), (1, "FootR")):
        p = pivot(nm, (0.2 * s, 0, 0.25), root)
        shoe = mat("shoe" + file, "#7a4b34", 0.5, spec=0.6)
        attach(sphere(nm + "Mesh", (0.2 * s, -0.08, 0.13), (0.18, 0.28, 0.13), shoe, 32), p)
        attach(sphere(nm + "Sole", (0.2 * s, -0.08, 0.03), (0.185, 0.29, 0.04), mat("sole", "#fff5e6", 0.8), 24), p)
    attach(sphere("Tail", (0, 0.44, 0.45), (0.15, 0.15, 0.15), B if ears == "long" else F, 24), root)
    if hat:
        attach(cyl("Hat", (0, 0, 1.97), 0.34, 0.3, 0.2, mat("hat" + file, hat, 0.9), 40), head)
        attach(cyl("HatBrim", (0, 0, 1.88), 0.5, 0.5, 0.04, mat("hat" + file, hat, 0.9), 40), head)
    export(file, [root])


# ------------------------------------------------------------------ árvores e plantas
def ac_trunk(name, mat_, height=1.7, rings=16, segs=44, lobes=5, base=0.5, flare=0.55):
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    grid = []
    for i in range(rings):
        t = i / (rings - 1)
        z = t * height
        row = []
        for j in range(segs):
            a = j / segs * math.tau
            lobe = max(0.0, math.cos(lobes * a)) ** 1.5
            r = base * (1 - 0.22 * t) + flare * math.exp(-z * 3.4) * (0.15 + 0.85 * lobe)
            zz = z - 0.12 * lobe * math.exp(-z * 4)
            row.append(bm.verts.new((math.cos(a) * r, math.sin(a) * r, zz)))
        grid.append(row)
    for i in range(rings - 1):
        for j in range(segs):
            j2 = (j + 1) % segs
            f = bm.faces.new([grid[i][j], grid[i][j2], grid[i + 1][j2], grid[i + 1][j]])
            for lp, (u, v) in zip(f.loops, [(j / segs, i / rings), ((j + 1) / segs, i / rings), ((j + 1) / segs, (i + 1) / rings), (j / segs, (i + 1) / rings)]):
                lp[uvl].uv = (u * 3, v * 2)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(o)
    return _fin(o, name, mat_)


def leaf_lump(name, center, radius, n, card, mat_, core_mat, seed=1, squash=0.9):
    """Esfera coberta por folhas-cartao sobrepostas (como as arvores do AC)."""
    rs = random.Random(seed)
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    cx, cy, cz = center
    normals = []
    for _ in range(n):
        while True:
            d = Vector((rs.gauss(0, 1), rs.gauss(0, 1), rs.gauss(0, 1) * squash))
            if d.length > 0.01:
                break
        d.normalize()
        if d.z < -0.35:
            d.z = -0.35 + abs(d.z) * 0.2
            d.normalize()
        p = Vector((cx, cy, cz)) + Vector((d.x * radius, d.y * radius, d.z * radius * squash)) * rs.uniform(0.96, 1.06)
        nrm = (d + Vector((0, 0, 0.45))).normalized()
        up = Vector((0, 0, 1)) - nrm * nrm.z
        if up.length < 0.2:
            up = Vector((1, 0, 0)) - nrm * nrm.x
        up.normalize()
        roll = rs.uniform(-0.9, 0.9)
        right = up.cross(nrm).normalized()
        up2 = (up * math.cos(roll) + right * math.sin(roll))
        right2 = up2.cross(nrm).normalized()
        s_ = card * rs.uniform(0.85, 1.2)
        cs = [p - right2 * s_ - up2 * s_, p + right2 * s_ - up2 * s_, p + right2 * s_ + up2 * s_, p - right2 * s_ + up2 * s_]
        vs = [bm.verts.new(c) for c in cs]
        f = bm.faces.new(vs)
        for lp, uvp in zip(f.loops, [(0, 0), (1, 0), (1, 1), (0, 1)]):
            lp[uvl].uv = uvp
        normals += [d.copy()] * 4
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    try:
        me.normals_split_custom_set_from_vertices([tuple(v) for v in normals])
    except Exception as ex:
        print("normais custom falharam:", ex)
    o = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(o)
    o.data.materials.append(mat_)
    core = sphere(name + "Core", center, (radius * 0.9, radius * 0.9, radius * 0.9 * squash), core_mat, 24)
    return [o, core]


def tree(file, leaf="#2f8a3e", leaf2="#8fd45a", bark="#e7a050"):
    clear()
    B = tmat("bark" + file, "bark", bark, seed=2, rough=0.95)
    parts = [ac_trunk("Trunk", B)]
    LC = tmat("leafcard" + file, "mapleleaf", leaf, leaf2, seed=4, rough=0.85)
    CORE = mat("leafcore" + file, "#2a6f35", 0.9)
    lumps = [((0, 0, 3.0), 1.6, 1.0), ((-1.2, 0.2, 2.55), 1.05, 0.75), ((1.15, -0.1, 2.7), 1.1, 0.8), ((0.1, 0.95, 2.6), 0.95, 0.7), ((-0.1, -0.2, 3.7), 0.85, 0.55)]
    for k, (c, r, w) in enumerate(lumps):
        parts += leaf_lump("Lump%d" % k, c, r, int(r * r * 210), 0.34, LC, CORE, seed=20 + k)
    export(file, parts)


def cedar(file):
    clear()
    bark = tmat("bark", "bark", "#8d6040", seed=5, rough=1.0)
    parts = [cyl("Trunk", (0, 0, 0.6), 0.24, 0.17, 1.2, bark, 24)]
    G = tmat("cedar", "leaf", "#3f8f55", "#62b774", seed=6, rough=0.9, sheen=0.5)
    for i in range(6):
        c = cone("Tier%d" % i, (0, 0, 1.15 + i * 0.62), 1.35 - i * 0.2, 1.25, G, 40)
        noisy(c, 0.035, i)
        parts.append(c)
    export(file, [join(parts, file)])


def fruit_model(file, color):
    clear()
    a = sphere("Fruit", (0, 0, 0.18), (0.18, 0.18, 0.17), mat("fr" + file, color, 0.3, spec=0.8), 40)
    dent = sphere("Dent", (0, 0, 0.34), (0.06, 0.06, 0.03), mat("fr" + file, color, 0.3), 12)
    s = cyl("Stem", (0, 0, 0.4), 0.014, 0.012, 0.1, mat("stem", "#5b3d24", 0.8), 8, rot=(0.2, 0, 0))
    lf = sphere("Leaf", (0.07, 0, 0.42), (0.09, 0.04, 0.012), mat("leafg", "#5fbf5a", 0.7), 16, rot=(0, -0.3, 0.3))
    hl = sphere("Shine", (-0.07, -0.08, 0.26), (0.03, 0.02, 0.05), mat("shine", "#ffffff", 0.4), 10)
    export(file, [join([a, s, lf], file)])


def house(file, wall, roof, door, wall_kind="planks", roof_tint="#ffffff"):
    clear()
    W = tmat("wall" + file, wall_kind, wall, seed=3, rough=0.9)
    R = tmat("roof" + file, "shingle", roof, seed=7, rough=0.8)
    D = tmat("door" + file, "planks", door, seed=8, rough=0.7)
    WD = tmat("trimwood", "planks", "#f6f1e6", seed=9, rough=0.7)
    BR = tmat("brick", "brick", "#c98b6b", "#e8dccb", seed=10, rough=0.95)
    ST = tmat("stone", "stone", "#d7d0c2", seed=11, rough=0.95)
    parts = [box("Walls", (0, 0, 1.25), (3.6, 3.1, 2.5), W, 0.08, 2.4), box("Base", (0, 0, 0.12), (3.8, 3.3, 0.26), ST, 0.05, 2.4)]
    # telhado de duas águas com beiral
    bm = bmesh.new()
    hw, hd, h0, h1 = 2.55, 2.1, 2.5, 4.1
    v = [bm.verts.new(p) for p in [(-hw, -hd, h0), (hw, -hd, h0), (hw, hd, h0), (-hw, hd, h0), (-hw - .12, 0, h1), (hw + .12, 0, h1)]]
    # inclinado: as águas descem para o eixo y
    bm.faces.new([v[0], v[1], v[5], v[4]])
    bm.faces.new([v[3], v[4], v[5], v[2]])
    bm.faces.new([v[0], v[4], v[3]])
    bm.faces.new([v[1], v[2], v[5]])
    bm.faces.new([v[0], v[3], v[2], v[1]])
    me = bpy.data.meshes.new("RoofMesh")
    bm.to_mesh(me)
    bm.free()
    ro = bpy.data.objects.new("Roof", me)
    bpy.context.collection.objects.link(ro)
    bpy.context.view_layer.objects.active = ro
    ro.data.materials.append(R)
    sd = ro.modifiers.new("sol", "SOLIDIFY")
    sd.thickness = 0.16
    sd.offset = 1
    bv = ro.modifiers.new("bev", "BEVEL")
    bv.width = 0.05
    bv.segments = 3
    for p in ro.data.polygons:
        p.use_smooth = False
    bpy.ops.object.modifier_apply(modifier="sol")
    bpy.ops.object.modifier_apply(modifier="bev")
    uv(ro, 2.0)
    parts.append(ro)
    parts.append(cyl("Ridge", (0, 0, 4.18), 0.09, 0.09, 5.4, R, 12, rot=(0, math.radians(90), 0)))
    # porta com arco
    parts.append(box("DoorFrame", (0, -1.56, 0.95), (1.1, 0.12, 1.9), WD, 0.04, 1.5))
    parts.append(box("Door", (0, -1.62, 0.85), (0.9, 0.12, 1.7), D, 0.05, 1.2))
    parts.append(cyl("DoorArch", (0, -1.62, 1.7), 0.45, 0.45, 0.12, D, 32, rot=(math.radians(90), 0, 0)))
    parts.append(sphere("Knob", (0.28, -1.72, 0.85), (0.06, 0.06, 0.06), mat("knob", "#f2c744", 0.25, spec=1.0), 16))
    parts.append(box("Step", (0, -2.0, 0.13), (1.6, 0.8, 0.26), ST, 0.06, 1.2))
    WN = mat("window", "#bfe8ff", 0.05, spec=1.0)
    CT = tmat("curtain", "stripes", "#ffe9ee", "#ffc6d3", seed=12, rough=0.95)
    for x in (-1.2, 1.2):
        parts.append(box("WinFrame", (x, -1.56, 1.55), (0.95, 0.1, 0.95), WD, 0.04, 1.5))
        parts.append(box("Win", (x, -1.62, 1.55), (0.75, 0.06, 0.75), WN, 0.02))
        parts.append(box("MullV", (x, -1.66, 1.55), (0.05, 0.05, 0.78), WD, 0.01, 1))
        parts.append(box("MullH", (x, -1.66, 1.55), (0.78, 0.05, 0.05), WD, 0.01, 1))
        parts.append(box("Curtain", (x - 0.28, -1.64, 1.6), (0.18, 0.04, 0.6), CT, 0.02, 1))
        parts.append(box("Curtain", (x + 0.28, -1.64, 1.6), (0.18, 0.04, 0.6), CT, 0.02, 1))
        parts.append(box("Sill", (x, -1.72, 1.04), (1.1, 0.2, 0.08), WD, 0.03, 1.5))
        pot = box("FlowerBox", (x, -1.8, 0.92), (0.95, 0.2, 0.2), tmat("planks2", "planks", "#9b6b45", seed=13), 0.04, 1.2)
        parts.append(pot)
        for i in range(5):
            parts.append(sphere("Fl", (x - 0.36 + i * 0.18, -1.8, 1.08), (0.08, 0.08, 0.06), mat("fl%d" % (i % 3), ["#ff7fa8", "#ffd23f", "#ffffff"][i % 3], 0.7), 12))
        parts.append(box("Shutter", (x - 0.62, -1.6, 1.55), (0.22, 0.05, 0.9), D, 0.02, 1))
        parts.append(box("Shutter", (x + 0.62, -1.6, 1.55), (0.22, 0.05, 0.9), D, 0.02, 1))
    parts.append(box("Chimney", (1.2, 0.5, 4.0), (0.7, 0.7, 1.5), BR, 0.04, 1.2))
    parts.append(box("ChimneyTop", (1.2, 0.5, 4.8), (0.85, 0.85, 0.12), ST, 0.03, 1.2))
    # lanterna na porta
    parts.append(sphere("PorchLamp", (0.85, -1.7, 1.9), (0.1, 0.1, 0.13), mat("porchglow", "#fff0b0", 0.2, emit="#ffd878"), 16))
    # caixa de correio
    parts.append(cyl("MailPost", (-1.5, -2.6, 0.5), 0.05, 0.05, 1.0, WD, 8))
    parts.append(box("Mailbox", (-1.5, -2.6, 1.1), (0.4, 0.55, 0.3), mat("mail", "#e85a5a", 0.5), 0.08, 1))
    export(file, [join(parts, file)])


def flower(file, petal, petals=8):
    clear()
    parts = [cyl("Stem", (0, 0, 0.2), 0.022, 0.018, 0.4, mat("stemg", "#4fa64a", 0.7), 10)]
    P = mat("pet" + file, petal, 0.55, sheen=0.5)
    for ring, (rad, sc, z) in enumerate([(0.12, 1.0, 0.43), (0.07, 0.8, 0.455)]):
        n = petals if ring == 0 else petals - 2
        for i in range(n):
            a = i * math.tau / n + ring * 0.3
            parts.append(sphere("Petal", (math.cos(a) * rad, math.sin(a) * rad, z), (0.1 * sc, 0.05 * sc, 0.025), P, 20, rot=(0, 0, a)))
    parts.append(sphere("Center", (0, 0, 0.47), (0.07, 0.07, 0.05), mat("ctr", "#ffc21f", 0.5), 20))
    for s in (-1, 1):
        parts.append(sphere("Leaf", (0.1 * s, 0, 0.14), (0.11, 0.035, 0.015), mat("leafg", "#5fbf5a", 0.7), 16, rot=(0, math.radians(-25 * s), 0)))
    export(file, [join(parts, file)])


def weed(file):
    clear()
    M = tmat("weedmat", "leaf", "#3f9a45", "#9bdc62", seed=12, rough=0.8)
    parts = []
    for ring, (n, ln, tilt) in enumerate([(7, 0.34, 0.55), (5, 0.26, 0.95)]):
        for i in range(n):
            a = i * math.tau / n + ring * 0.4
            lf = sphere("Blade", (math.cos(a) * ln * 0.55, math.sin(a) * ln * 0.55, 0.06 + ring * 0.07), (ln * 0.55, 0.075, 0.018), M, 16)
            lf.rotation_euler = (0, -tilt * 0.6, a)
            parts.append(lf)
    parts.append(sphere("Bud", (0, 0, 0.17), (0.05, 0.05, 0.14), M, 12))
    export(file, [join(parts, file)])


def rock(file):
    clear()
    bpy.ops.mesh.primitive_ico_sphere_add(radius=1, subdivisions=4, location=(0, 0, 0.45))
    o = bpy.context.object
    o.scale = (0.8, 0.62, 0.52)
    noisy(o, 0.07, 4)
    _fin(o, file, tmat("rock", "rock", "#858a93", seed=14, rough=0.95), True)
    uv(o, 1.2)
    export(file, [o])


def bush(file):
    clear()
    LC = tmat("leafcardbush", "mapleleaf", "#2f8a3e", "#8fd45a", seed=9, rough=0.85)
    CORE = mat("leafcorebush", "#2a6f35", 0.9)
    parts = []
    for k, (c, r) in enumerate([((0, 0, 0.5), 0.62), ((0.55, 0.1, 0.38), 0.42), ((-0.55, -0.05, 0.38), 0.44)]):
        parts += leaf_lump("L%d" % k, c, r, int(r * r * 230), 0.22, LC, CORE, seed=40 + k, squash=0.8)
    berry = mat("berry", "#ff5a6a", 0.35, spec=0.9)
    rs = random.Random(3)
    for i in range(7):
        a = rs.uniform(0, 6.28)
        parts.append(sphere("Berry", (math.cos(a) * 0.68, math.sin(a) * 0.55, 0.3 + rs.uniform(0, .4)), (0.05, 0.05, 0.05), berry, 12))
    export(file, parts)


def bench(file):
    clear()
    W = tmat("wood", "planks", "#c9955e", seed=16, rough=0.7)
    W2 = tmat("wood2", "planks", "#a97a48", seed=17, rough=0.7)
    parts = [box("Seat%d" % i, (0, -0.2 + i * 0.2, 0.52), (1.7, 0.18, 0.1), W, 0.03, 1.2) for i in range(3)]
    for i in range(3):
        parts.append(box("Back%d" % i, (0, 0.3, 0.8 + i * 0.17), (1.7, 0.06, 0.14), W, 0.03, 1.2))
    for x in (-0.75, 0.75):
        parts.append(box("Leg", (x, 0, 0.26), (0.12, 0.6, 0.52), W2, 0.03, 1.2))
        parts.append(box("BackLeg", (x, 0.3, 0.75), (0.1, 0.1, 0.9), W2, 0.03, 1.2))
        parts.append(box("Arm", (x, 0, 0.78), (0.1, 0.6, 0.08), W2, 0.03, 1.2))
    export(file, [join(parts, file)])


def lamp(file):
    clear()
    iron = mat("iron", "#33414a", 0.45, spec=0.8)
    parts = [cyl("Base", (0, 0, 0.12), 0.18, 0.12, 0.24, iron, 24), cyl("Pole", (0, 0, 1.1), 0.065, 0.055, 2.0, iron, 24),
             sphere("Bulb", (0, 0, 2.2), (0.24, 0.24, 0.3), mat("glow", "#fff3b0", 0.2, emit="#ffe27a"), 32),
             cyl("Cap", (0, 0, 2.5), 0.3, 0.05, 0.14, iron, 24), torus("Ring", (0, 0, 1.9), 0.17, 0.03, iron)]
    export(file, [join(parts, file)])


def sign(file):
    clear()
    W = tmat("wood", "planks", "#c9955e", seed=16, rough=0.7)
    W2 = tmat("wood2", "planks", "#a97a48", seed=17, rough=0.7)
    parts = [box("Post", (0, 0, 0.6), (0.12, 0.12, 1.2), W2, 0.02, 1), box("Board", (0, -0.02, 1.15), (0.95, 0.09, 0.55), W, 0.04, 1.2),
             sphere("Nail", (-0.4, -0.08, 1.3), (0.025, 0.02, 0.025), mat("nail", "#444444", 0.4), 8), sphere("Nail", (0.4, -0.08, 1.3), (0.025, 0.02, 0.025), mat("nail", "#444444", 0.4), 8)]
    export(file, [join(parts, file)])


def human(file, skin="#ffd9bf", hair="#3fb5a5", shirt="#ee9b45", shirt2="#fff4e0", pants="#4a79c9", seed=1):
    clear()
    SK = mat("skin" + file, skin, 0.7, spec=0.35)
    HR = tmat("hair" + file, "fur", hair, seed=seed + 5, rough=0.6, sheen=0.8)
    SH = tmat("shirt" + file, "plaid", shirt, shirt2, seed=2, rough=0.95, sheen=1.0)
    PN = tmat("pants" + file, "stripes", pants, pants, seed=3, rough=0.95)
    SOCK = tmat("sock" + file, "stripes", "#fff1d6", "#ee9b45", seed=4, rough=0.95)
    EYE = mat("eye", "#16100f", 0.1, spec=1.0)
    WHITE = mat("white", "#ffffff", 0.2)
    CH = mat("cheek", "#ff9fa8", 0.9)
    MOUTH = mat("mouth" + file, "#b5545a", 0.6)
    root = pivot("Root", (0, 0, 0))
    attach(sphere("Body", (0, 0, 0.62), (0.44, 0.38, 0.5), SH), root)
    attach(sphere("Shorts", (0, 0, 0.34), (0.43, 0.37, 0.26), PN), root)
    head = pivot("Head", (0, 0, 1.2), root)
    attach(sphere("HeadMesh", (0, 0, 1.45), (0.7, 0.64, 0.62), SK), head)
    # orelhas
    for s in (-1, 1):
        attach(sphere("Ear", (0.68 * s, 0, 1.4), (0.08, 0.06, 0.12), SK, 20), head)
    # olhos: ovais pretos com brilho grande (marca registrada)
    for s in (-1, 1):
        attach(sphere("Eye", (0.25 * s, -0.575, 1.41), (0.085, 0.05, 0.125), EYE, 32), head)
        attach(sphere("EyeHL", (0.272 * s, -0.617, 1.47), (0.034, 0.016, 0.046), WHITE, 16), head)
        attach(sphere("EyeHL2", (0.23 * s, -0.617, 1.36), (0.014, 0.008, 0.018), WHITE, 12), head)
        attach(sphere("Cheek", (0.4 * s, -0.51, 1.3), (0.085, 0.025, 0.05), CH, 20), head)
    attach(sphere("Nose", (0, -0.64, 1.33), (0.05, 0.04, 0.04), SK, 20), head)
    attach(sphere("Mouth", (0, -0.572, 1.2), (0.055, 0.02, 0.022), MOUTH, 16), head)
    # cabelo: calota + franja + rabo
    attach(sphere("Hair", (0, 0.1, 1.62), (0.77, 0.7, 0.6), HR), head)
    attach(sphere("HairBack", (0, 0.32, 1.42), (0.74, 0.5, 0.62), HR), head)
    for i, x in enumerate((-0.5, -0.25, 0.0, 0.25, 0.5)):
        attach(sphere("Bang", (x, -0.46, 1.78 - abs(x) * 0.28), (0.18, 0.12, 0.17), HR, 24, rot=(0, 0, math.radians(-x * 40))), head)
    attach(sphere("TailA", (0, 0.72, 1.55), (0.2, 0.2, 0.2), HR, 24), head)
    attach(sphere("TailB", (0, 0.8, 1.25), (0.18, 0.17, 0.3), HR, 24), head)
    # braços e pernas
    for s, nm in ((-1, "ArmL"), (1, "ArmR")):
        p = pivot(nm, (0.46 * s, 0, 0.88), root)
        attach(sphere(nm + "Sleeve", (0.54 * s, 0, 0.78), (0.15, 0.15, 0.17), SH, 24), p)
        attach(sphere(nm + "Mesh", (0.58 * s, 0, 0.58), (0.11, 0.11, 0.25), SK, 24, rot=(0, math.radians(-10 * s), 0)), p)
        attach(sphere(nm + "Hand", (0.62 * s, 0, 0.36), (0.12, 0.12, 0.12), SK, 24), p)
    for s, nm in ((-1, "FootL"), (1, "FootR")):
        p = pivot(nm, (0.2 * s, 0, 0.25), root)
        attach(cyl(nm + "Sock", (0.2 * s, 0, 0.17), 0.1, 0.09, 0.26, SOCK, 24), p)
        attach(sphere(nm + "Mesh", (0.2 * s, -0.08, 0.07), (0.15, 0.24, 0.09), mat("shoe" + file, "#a5693f", 0.55, spec=0.5), 32), p)
        attach(sphere(nm + "Sole", (0.2 * s, -0.08, 0.02), (0.155, 0.25, 0.03), mat("sole", "#fff5e6", 0.8), 24), p)
    export(file, [root])


if __name__ == "__main__":
    human("player_human")
    animal("villager_bear", "#a8754f", "#e8c9a0", "round", shirt="#f4a259", shirt2="#fff1d6", pattern="dots", seed=21, snout_size=1.15)
    animal("villager_cat", "#f0a654", "#fff0d9", "pointy", shirt="#b79ced", shirt2="#efe6ff", pattern="stripes", seed=31)
    tree("tree_round")
    tree("tree_fruit", leaf="#2f8a3e", leaf2="#9be060")
    cedar("tree_cedar")
    fruit_model("fruit_apple", "#e8454b")
    fruit_model("fruit_orange", "#ffa233")
    house("house_player", "#fff3da", "#ee7b6d", "#6f9fd8", "planks")
    house("house_shop", "#e9f6ff", "#5fb7a6", "#f2b84b", "plaster")
    house("house_neighbor", "#ffeaf0", "#ffffff", "#c46a76", "plaster")
    for n, c in (("white", "#ffffff"), ("red", "#ee5a6f"), ("yellow", "#ffd23f"), ("pink", "#ff9fd0"), ("blue", "#7fa8ff")):
        flower("flower_" + n, c)
    weed("weed")
    rock("rock")
    bush("bush")
    bench("bench")
    lamp("lamp")
    sign("sign")
    print("TODOS OS MODELOS GERADOS")
