"""Guarda-roupa estilo Animal Crossing: corpo-base + pecas separadas (cada uma em seu .glb) + penteados.
Todas as pecas compartilham os mesmos pivos (Root/Head/ArmL/ArmR/FootL/FootR), entao o jogo encaixa
qualquer combinacao no corpo. Saida: assets/models/char/*.glb + wardrobe.json
Uso: blender -b -P build_wardrobe.py [-- so_esta_peca]
"""
import bpy, bmesh, os, sys, math, json, random
import numpy as np
from mathutils import Vector, Matrix
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import char_lib as cl
ba = cl.ba
OUTD = os.path.join(cl.ROOTDIR, "assets", "models", "char")
os.makedirs(OUTD, exist_ok=True)
ONLY = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []

body, M = cl.load_base()
cl.improve_skin(body)
HT, ZN, ZH, TH, X0, AR = M["HT"], M["Z_NECK"], M["Z_HIP"], M["TORSO_HALF"], M["X0"], M["ARM_R"]
HC, HR = M["HC"], M["HR"]
HAND_X = M["ARM_END"] - 2.1 * AR
UP = (0, 0, 1)
BV = [v.co.copy() for v in body.data.vertices]


def ext(z, band=0.012):
    sel = [v for v in BV if abs(v.z - z) < band * HT and abs(v.x) < TH * 1.6]
    return max(abs(v.x) for v in sel), min(v.y for v in sel), max(v.y for v in sel)


# ====================================================================== texturas de tecido (numpy)
N = ba.N
YY, XX = np.mgrid[0:N, 0:N]
UU, VV = XX / N, YY / N  # linha 0 = v 0 (base da imagem no Blender)


def weave(amp=0.06):
    return 1.0 + amp * ((((XX // 2) + (YY // 2)) % 2) - 0.5)


def fabric(name, kind, c1, c2="#ffffff", seed=1, extra=None):
    a, b = ba.hexrgb(c1), ba.hexrgb(c2)
    f = ba.fbm(seed, 6, 3)
    if kind == "cotton":
        rgb = a * (weave(0.05) * (0.96 + 0.08 * f))[..., None]
    elif kind == "denim":
        tw = 0.9 + 0.14 * (((XX + YY) % 6) < 3)
        wear = ba.fbm(seed + 3, 3, 3)
        rgb = a * (tw * (0.92 + 0.1 * f))[..., None]
        rgb = rgb + (np.array([0.85, 0.9, 1.0]) - rgb) * (np.clip(wear - 0.55, 0, 1) * 0.6)[..., None]
    elif kind == "stripes":
        band = ((YY // 48) % 2).astype(float)
        rgb = (a * (1 - band)[..., None] + b * band[..., None]) * weave(0.05)[..., None]
    elif kind == "knit":
        sx = np.abs(((XX % 24) - 12) / 12.0)
        row = ((YY + sx * 10) % 16) / 16.0
        rgb = a * (0.8 + 0.24 * np.sin(row * math.pi) + 0.04 * (f - 0.5))[..., None]
    elif kind == "pleat":
        pl = 0.86 + 0.14 * np.abs(np.sin(UU * math.pi * 16))
        rgb = a * (pl * weave(0.04))[..., None]
    elif kind == "hair":
        g = ba.fbm(seed, 2, 3, aniso=(1, 24))       # fios: listras finas ao longo de v
        strands = 0.84 + 0.2 * g
        hl = np.exp(-((VV - 0.72 - 0.03 * np.sin(UU * math.tau * 3)) / 0.06) ** 2) * 0.16  # faixa de brilho
        rgb = np.ones((N, N, 3)) * (strands + hl)[..., None]
    else:
        rgb = np.ones((N, N, 3)) * a
    if extra:
        rgb = extra(rgb, a, b)
    return ba.save_tex(name, np.clip(rgb, 0, 1))


def print_star(rgb, a, b, cu=0.5, cv=0.6, r=0.16):
    th = np.arctan2(VV - cv, UU - cu)
    rad = np.hypot(UU - cu, (VV - cv))
    star = r * (0.55 + 0.45 * np.abs(np.cos(2.5 * (th - math.pi / 2))) ** 3)
    m = rad < star
    out = rgb.copy()
    out[m] = b
    return out


def print_leaf(rgb, a, b, cu=0.5, cv=0.6):
    """Folha estilizada (estampa de camiseta)."""
    x, y = (UU - cu) / 0.14, (VV - cv) / 0.2
    leaf = (x * x + (y * 0.9) ** 2 < 1) & (np.abs(x) < 1.0 - 0.25 * (y + 1) ** 2 * 0.3)
    vein = (np.abs(x) < 0.07) & (np.abs(y) < 0.9)
    out = rgb.copy()
    out[leaf] = b
    out[vein & leaf] = a
    return out


def tmat(name, tex, rough=0.9, sheen=0.7, color="#ffffff"):
    m = ba.mat(name, color, rough, tex=tex, sheen=sheen)
    return m


# ====================================================================== utilidades
def planar_uv(ob, z0, z1, w, front_mat_index=None, front_test=None):
    """UV planar frontal (u=x, v=z): estampas e listras ficam retas no peito."""
    me = ob.data
    uvl = me.uv_layers.active.data
    for p in me.polygons:
        c = p.center
        is_front = front_test(c, p.normal) if front_test else True
        if front_mat_index is not None and is_front:
            p.material_index = front_mat_index
        if is_front or front_mat_index is None:
            for li in p.loop_indices:
                co = me.vertices[me.loops[li].vertex_index].co
                uvl[li].uv = (co.x / (2 * w) + 0.5, (co.z - z0) / (z1 - z0))


def finish(ob, thickness=0.006, subdiv=1):
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    if thickness:
        so = ob.modifiers.new("sol", "SOLIDIFY")
        so.thickness = thickness * HT
        so.offset = 0.0
        so.use_rim = True
        bpy.ops.object.modifier_apply(modifier="sol")
    if subdiv:
        sd = ob.modifiers.new("sub", "SUBSURF")
        sd.levels = subdiv
        bpy.ops.object.modifier_apply(modifier="sub")
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


def skirt_cone(name, z_top, z_bot, flare, mat, pleats=0, segs=96, rings=14):
    rx, y0, y1 = ext(z_top)
    cy, ry = (y0 + y1) / 2, (y1 - y0) / 2
    rx, ry = rx * 1.08, ry * 1.12
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    grid = []
    for i in range(rings):
        t = i / (rings - 1)
        z = z_top + (z_bot - z_top) * t
        k = 1 + flare * t ** 1.3
        row = []
        for j in range(segs):
            a = j / segs * math.tau
            pl = 1 + (0.045 * t + 0.01) * math.sin(a * pleats) if pleats else 1
            row.append(bm.verts.new((math.cos(a) * rx * k * pl, cy + math.sin(a) * ry * k * pl, z)))
        grid.append(row)
    for i in range(rings - 1):
        for j in range(segs):
            j2 = (j + 1) % segs
            f = bm.faces.new([grid[i][j], grid[i + 1][j], grid[i + 1][j2], grid[i][j2]])
            for lp, (u, v) in zip(f.loops, [(j / segs, 1 - i / (rings - 1)), (j / segs, 1 - (i + 1) / (rings - 1)), ((j + 1) / segs, 1 - (i + 1) / (rings - 1)), ((j + 1) / segs, 1 - i / (rings - 1))]):
                lp[uvl].uv = (u * 2, v)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    ob.data.materials.append(mat)
    return finish(ob, 0.008, 1)


def prim(fn, *a, **k):
    o = fn(*a, **k)
    return o


EXPORTED = []


def export_piece(pid, slot, name_pt, objs, force=None, extra=None):
    if ONLY and pid not in ONLY:
        for o in objs:
            bpy.data.objects.remove(o)
        return
    path = os.path.join(OUTD, pid + ".glb")
    cl.export_character(objs, M, path, force_part=force or {})
    # remove os pivos exportados (os nomes precisam ficar livres para a proxima peca)
    for o in [o for o in bpy.data.objects if o.name.split(".")[0] in ("Root", "Head", "ArmL", "ArmR", "FootL", "FootR") or o.parent is not None and o.type == "MESH" and o.name != "Body"]:
        try:
            bpy.data.objects.remove(o)
        except ReferenceError:
            pass
    item = {"id": pid, "slot": slot, "name": name_pt, "file": "assets/models/char/" + pid + ".glb"}
    if extra:
        item.update(extra)
    EXPORTED.append(item)
    print("PECA", pid, flush=True)


# ====================================================================== partes de cima
SLEEVE_SHORT = TH + AR + 0.06 * HT
TOP_HEM = ZH - 0.035 * HT
FRONT = lambda c, n: n.y < -0.25 and abs(c.x) < TH * 0.95 and TOP_HEM < c.z < ZN - 0.01 * HT


def tee(pid, name_pt, color, kind="cotton", c2="#ffffff", printer=None, sleeve=SLEEVE_SHORT, hem=TOP_HEM, offset=0.008, collar_color=None):
    base_tex = fabric(pid + "_base", kind, color, c2, seed=hash(pid) % 97)
    mats = [tmat(pid + "_m", base_tex)]
    if printer:
        mats.append(tmat(pid + "_print", fabric(pid + "_print", kind, color, c2, seed=5, extra=printer)))
    o = cl.shell(body, M, pid + "_top", lambda c, n: hem - 0.04 * HT < c.z < ZN + 0.02 * HT and abs(c.x) < sleeve + 0.03 * HT, offset, mats[0],
                 cuts=[cl.cut((0, 0, ZN - 0.004 * HT), UP, "below"), cl.cut((0, 0, hem), UP, "above"),
                       cl.cut((sleeve, 0, 0), (1, 0, 0), "below"), cl.cut((-sleeve, 0, 0), (-1, 0, 0), "below")], thickness=0.005)
    if printer:
        o.data.materials.append(mats[1])
        planar_uv(o, hem, ZN, TH * 1.1, front_mat_index=1, front_test=FRONT)
    elif kind == "stripes":
        planar_uv(o, hem, ZN, TH * 1.1)
    parts = [o]
    rib = tmat(pid + "_rib", fabric(pid + "_rib", "knit", collar_color or color, seed=7))
    parts.append(cl.shell(body, M, pid + "_collar", lambda c, n: ZN - 0.035 * HT < c.z < ZN + 0.01 * HT and abs(c.x) < TH, offset + 0.007, rib,
                          cuts=[cl.cut((0, 0, ZN - 0.003 * HT), UP, "below"), cl.cut((0, 0, ZN - 0.022 * HT), UP, "above")], thickness=0.004))
    for s in (-1, 1):  # barra da manga
        xs = sleeve * s
        parts.append(cl.shell(body, M, pid + "_cuff%d" % (s + 1), lambda c, n, xs=xs: abs(c.x - xs) < 0.03 * HT and c.z > 0.42 * HT and c.z < ZN, offset + 0.006, rib,
                              cuts=[cl.cut((xs, 0, 0), (s, 0, 0), "below"), cl.cut((xs - 0.016 * HT * s, 0, 0), (s, 0, 0), "above")], thickness=0.004))
    return parts


# 1) camiseta azul com estampa de estrela
export_piece("top_tee_estrela", "top", "Camiseta Estrela", tee("top_tee_estrela", "Camiseta Estrela", "#5ab4e8", printer=print_star, c2="#fff6d8", collar_color="#4a9fd0"))
# 2) camiseta listrada
export_piece("top_listrada", "top", "Camiseta Listrada", tee("top_listrada", "Camiseta Listrada", "#ffffff", kind="stripes", c2="#f2735f", collar_color="#f2735f"))
# 3) camiseta verde com folha
export_piece("top_tee_folha", "top", "Camiseta Folha", tee("top_tee_folha", "Camiseta Folha", "#f6efd8", printer=print_leaf, c2="#5bbf6a", collar_color="#5bbf6a"))

# 4) moletom com capuz, bolso canguru e cordoes
HOOD_C = "#f39bb6"
hood_parts = tee("top_moletom", "Moletom", HOOD_C, kind="cotton", sleeve=HAND_X, hem=ZH - 0.05 * HT, offset=0.013, collar_color="#e486a3")
for o in hood_parts:
    if o.name.endswith("_top"):
        o.name = "top_moletom_top"
knit_dark = tmat("moletom_dark", fabric("moletom_dark", "knit", "#e486a3", seed=11))
hood_parts.append(cl.shell(body, M, "moletom_pocket", lambda c, n: n.y < -0.3 and abs(c.x) < TH * 0.75 and ZH - 0.03 * HT < c.z < ZH + 0.09 * HT, 0.02, knit_dark,
                           cuts=[cl.cut((0, 0, ZH + 0.075 * HT), UP, "below"), cl.cut((0, 0, ZH - 0.025 * HT), UP, "above"),
                                 cl.cut((TH * 0.62, 0, 0), (1, 0, 0), "below"), cl.cut((-TH * 0.62, 0, 0), (-1, 0, 0), "below")], thickness=0.004))
nx, ny0, ny1 = ext(ZN - 0.01 * HT, 0.02)
hood = ba.sphere("moletom_hood", (0, ny1 + 0.004 * HT, ZN - 0.01 * HT), (nx * 0.85, 0.045 * HT, 0.06 * HT), tmat("moletom_hoodm", fabric("moletom_hood", "cotton", HOOD_C, seed=12)), 32)
hood_parts.append(hood)
cord = ba.mat("moletom_cord", "#ffffff", 0.7)
for s in (-1, 1):
    hood_parts.append(ba.cyl("moletom_cord%d" % (s + 1), (0.035 * HT * s, ny0 - 0.012 * HT, ZN - 0.05 * HT), 0.0045 * HT, 0.0045 * HT, 0.07 * HT, cord, 8))
    hood_parts.append(ba.sphere("moletom_tip%d" % (s + 1), (0.035 * HT * s, ny0 - 0.012 * HT, ZN - 0.087 * HT), (0.008 * HT,) * 3, cord, 10))
export_piece("top_moletom", "top", "Moletom Rosa", hood_parts, force={"moletom_hood": "Root"})

# 5) vestido: regata + saia evase (peca inteira)
DRESS_C = "#ffd35c"
dress = cl.shell(body, M, "vestido_top", lambda c, n: ZH - 0.01 * HT < c.z < ZN + 0.02 * HT and abs(c.x) < TH * 1.15, 0.008,
                 tmat("vestido_m", fabric("vestido", "cotton", DRESS_C, seed=21)),
                 cuts=[cl.cut((0, 0, ZN - 0.015 * HT), UP, "below"), cl.cut((0, 0, ZH + 0.02 * HT), UP, "above"),
                       cl.cut((TH * 1.02, 0, 0), (1, 0, 0), "below"), cl.cut((-TH * 1.02, 0, 0), (-1, 0, 0), "below")], thickness=0.005)
skirt = skirt_cone("vestido_saia", ZH + 0.035 * HT, 0.2 * HT, 0.55, tmat("vestido_saia_m", fabric("vestido_saia", "pleat", DRESS_C, seed=22)), pleats=18)
bow = ba.sphere("vestido_laco", (0, ext(ZH + 0.03 * HT)[1] - 0.012 * HT, ZH + 0.035 * HT), (0.035 * HT, 0.01 * HT, 0.02 * HT), ba.mat("vestido_laco_m", "#ffffff", 0.6), 20)
export_piece("top_vestido", "top", "Vestido Amarelo", [dress, skirt, bow], force={"vestido_saia": "Root", "vestido_laco": "Root"}, extra={"full": True})

# ====================================================================== partes de baixo
def legwear(pid, z_bottom, tex_kind, color, offset=0.01, cuff=True):
    m = tmat(pid + "_m", fabric(pid, tex_kind, color, seed=hash(pid) % 89))
    parts = [cl.shell(body, M, pid + "_main", lambda c, n: z_bottom - 0.02 * HT < c.z < ZH + 0.06 * HT and abs(c.x) < TH * 1.3, offset, m,
                      cuts=[cl.cut((0, 0, ZH + 0.03 * HT), UP, "below"), cl.cut((0, 0, z_bottom), UP, "above")], thickness=0.005)]
    if cuff:
        parts.append(cl.shell(body, M, pid + "_cuff", lambda c, n: z_bottom - 0.02 * HT < c.z < z_bottom + 0.05 * HT, offset + 0.007, m,
                              cuts=[cl.cut((0, 0, z_bottom + 0.028 * HT), UP, "below"), cl.cut((0, 0, z_bottom - 0.001 * HT), UP, "above")], thickness=0.005))
    waist = tmat(pid + "_waist", fabric(pid + "_w", tex_kind, color, seed=3))
    parts.append(cl.shell(body, M, pid + "_waist", lambda c, n: ZH - 0.01 * HT < c.z < ZH + 0.06 * HT and abs(c.x) < TH * 1.3, offset + 0.006, waist,
                          cuts=[cl.cut((0, 0, ZH + 0.032 * HT), UP, "below"), cl.cut((0, 0, ZH + 0.012 * HT), UP, "above")], thickness=0.004))
    return parts


export_piece("bottom_short_jeans", "bottom", "Short Jeans", legwear("bottom_short_jeans", ZH - 0.11 * HT, "denim", "#4f7fc4"))
export_piece("bottom_calca_bege", "bottom", "Calça de Sarja", legwear("bottom_calca_bege", 0.11 * HT, "cotton", "#d8c39a"))
sk = skirt_cone("bottom_saia", ZH + 0.035 * HT, ZH - 0.13 * HT, 0.45, tmat("saia_m", fabric("saia", "pleat", "#ef7aa0", seed=31)), pleats=16)
export_piece("bottom_saia", "bottom", "Saia Pregueada", [sk], force={"bottom_saia": "Root"})

# jardineira: short jeans + peitilho + alcas + botoes
ov = legwear("bottom_jardineira", ZH - 0.11 * HT, "denim", "#3f6fb5")
dm = tmat("jardineira_m", fabric("jardineira", "denim", "#3f6fb5", seed=41))
ov.append(cl.shell(body, M, "jardineira_bib", lambda c, n: n.y < -0.2 and abs(c.x) < TH * 0.8 and ZH < c.z < ZN - 0.04 * HT, 0.017, dm,
                   cuts=[cl.cut((0, 0, ZN - 0.075 * HT), UP, "below"), cl.cut((0, 0, ZH + 0.02 * HT), UP, "above"),
                         cl.cut((TH * 0.62, 0, 0), (1, 0, 0), "below"), cl.cut((-TH * 0.62, 0, 0), (-1, 0, 0), "below")], thickness=0.005))
SXJ, SWJ = TH * 0.5, 0.02 * HT
for s in (-1, 1):
    xs = SXJ * s
    ov.append(cl.shell(body, M, "jardineira_alca%d" % (s + 1), lambda c, n, xs=xs: abs(c.x - xs) < SWJ + 0.02 * HT and ZH < c.z < ZN + 0.01 * HT and (n.y > -0.2 or c.z > ZN - 0.08 * HT), 0.019, dm,
                       cuts=[cl.cut((xs + SWJ, 0, 0), (1, 0, 0), "below"), cl.cut((xs - SWJ, 0, 0), (1, 0, 0), "above"), cl.cut((0, 0, ZN - 0.008 * HT), UP, "below")], thickness=0.004))
    f = cl.raycast_front(ov, xs, ZN - 0.085 * HT)
    if f:
        ov.append(ba.sphere("jardineira_botao%d" % (s + 1), f[0] + Vector((0, -0.004 * HT, 0)), (0.013 * HT, 0.006 * HT, 0.013 * HT), ba.mat("jard_botao", "#f2c744", 0.3, spec=0.9), 16))
export_piece("bottom_jardineira", "bottom", "Jardineira Jeans", ov)

# ====================================================================== calcados (formas simples e "gordinhas", como no ACNH)
# os calcados seguem o FORMATO DO PE do corpo-base (casca do pe): calcanhar, peito do pe e bico arredondado
FOOT_TOP = max(v.z for v in BV if v.z < 0.12 * HT and abs(v.x) > 0.02 * HT and (v.y < min(w.y for w in BV if w.z < 0.04 * HT) + 0.02 * HT)) if False else 0.075 * HT


def _hull(pts):
    pts = sorted(set(pts))
    if len(pts) < 3:
        return pts

    def cr(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p_ in pts:
        while len(lo) >= 2 and cr(lo[-2], lo[-1], p_) <= 0:
            lo.pop()
        lo.append(p_)
    for p_ in reversed(pts):
        while len(up) >= 2 and cr(up[-2], up[-1], p_) <= 0:
            up.pop()
        up.append(p_)
    return lo[:-1] + up[:-1]


def sole_slab(name, side, mat, height, grow):
    """Sola limpa: contorno da planta do pe (fecho convexo suavizado), perfil com bordas arredondadas."""
    pts = [(round(v.x, 5), round(v.y, 5)) for v in BV if v.z < 0.03 * HT and (v.x > 0) == (side > 0)]
    hull = _hull(pts)
    for _ in range(3):  # Chaikin: contorno arredondado
        nh = []
        for i in range(len(hull)):
            a_, b_ = hull[i], hull[(i + 1) % len(hull)]
            nh += [(a_[0] * 0.75 + b_[0] * 0.25, a_[1] * 0.75 + b_[1] * 0.25), (a_[0] * 0.25 + b_[0] * 0.75, a_[1] * 0.25 + b_[1] * 0.75)]
        hull = nh
    cx = sum(p_[0] for p_ in hull) / len(hull)
    cy = sum(p_[1] for p_ in hull) / len(hull)
    bm = bmesh.new()
    rings = []
    for z, k in ((0.0, -0.35), (0.25, 0.0), (0.75, 0.0), (1.0, -0.45)):
        ring = []
        for x, y in hull:
            dx, dy = x - cx, y - cy
            L = math.hypot(dx, dy) or 1
            g = grow * (1 + k)
            ring.append(bm.verts.new((x + dx / L * g, y + dy / L * g, z * height)))
        rings.append(ring)
    n = len(hull)
    for i in range(3):
        for j in range(n):
            bm.faces.new([rings[i][j], rings[i][(j + 1) % n], rings[i + 1][(j + 1) % n], rings[i + 1][j]])
    bm.faces.new(rings[3])
    bm.faces.new(list(reversed(rings[0])))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.uv_layers.new(name="UVMap")
    o = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(o)
    o.data.materials.append(mat)
    for p_ in me.polygons:
        p_.use_smooth = True
    return o


def shoe_volume(name, top, scale, mat, zscale=1.0, zmin=0.0):
    """Calcado = copia do PROPRIO PE do corpo (ja remodelado: bico + calcanhar), ampliada a partir do centro de cada pe,
    com a boca cortada reta. Assim o formato e identico ao do pe, so que "vestido"."""
    bm = bmesh.new()
    bm.from_mesh(body.data)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.calc_center_median().z > top + 0.03 * HT], context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-6, plane_co=(0, 0, top), plane_no=(0, 0, 1), clear_outer=True)
    bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary], sides=0)
    for side in (-1, 1):
        pts = [v.co for v in bm.verts if (v.co.x > 0) == (side > 0) and v.co.z < 0.03 * HT]
        cx = sum(c.x for c in pts) / len(pts)
        cy = sum(c.y for c in pts) / len(pts)
        for v in bm.verts:
            if (v.co.x > 0) == (side > 0):
                v.co.x = cx + (v.co.x - cx) * scale[0]
                v.co.y = cy + (v.co.y - cy) * scale[1]
                v.co.z = zmin + v.co.z * zscale * (1 - zmin / top)  # zmin: o cabedal apoia em cima da sola
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(o)
    me.materials.append(mat)
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    sd = o.modifiers.new("sub", "SUBSURF")
    sd.levels = 1
    bpy.ops.object.modifier_apply(modifier="sub")
    for p_ in me.polygons:
        p_.use_smooth = True
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.cube_project(cube_size=0.12 * HT)
    bpy.ops.object.mode_set(mode="OBJECT")
    return o


def foot_box(side):
    pts = [v for v in BV if v.z < 0.06 * HT and (v.x > 0) == (side > 0)]
    x0, x1 = min(v.x for v in pts), max(v.x for v in pts)
    y0, y1 = min(v.y for v in pts), max(v.y for v in pts)
    leg = [v for v in BV if 0.085 * HT < v.z < 0.115 * HT and (v.x > 0) == (side > 0)]
    lcy = sum(v.y for v in leg) / len(leg)
    lry = (max(v.y for v in leg) - min(v.y for v in leg)) / 2
    lrx = (max(v.x for v in leg) - min(v.x for v in leg)) / 2
    return (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2, lcy, lry, lrx


def _ss(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def loft(name, cx, heel_y, toe_y, W, hfun, wfun, zbase, mat, t0=0.0, t1=1.0, spring=0.0, grow=0.0, N=30, M=26, pw=0.62):
    """Peca lofteada ao longo do comprimento do pe: secao = meia-superelipse com base plana.
    wfun(t) -> largura relativa (0..1), hfun(t) -> altura; t: 0 = calcanhar, 1 = bico."""
    bm = bmesh.new()
    rings = []
    for i in range(N + 1):
        t = t0 + (t1 - t0) * i / N
        y = heel_y + (toe_y - heel_y) * t
        w = max(1e-5, W * wfun(t) + grow)
        h = max(1e-5, hfun(t) + grow)
        zb = zbase + spring * _ss((t - 0.62) / 0.38) - grow * 0.5
        ring = []
        for j in range(M + 1):
            a = math.pi * j / M
            ring.append(bm.verts.new((cx + w * math.cos(a), y, zb + h * abs(math.sin(a)) ** pw)))
        rings.append(ring)
    for i in range(N):
        for j in range(M):
            bm.faces.new([rings[i][j], rings[i][j + 1], rings[i + 1][j + 1], rings[i + 1][j]])
    for ring in (rings[0], rings[-1]):
        bm.faces.new(ring)
    # base plana
    for i in range(N):
        bm.faces.new([rings[i][0], rings[i + 1][0], rings[i + 1][M], rings[i][M]])
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(o)
    me.materials.append(mat)
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    sd = o.modifiers.new("sub", "SUBSURF")
    sd.levels = 1
    bpy.ops.object.modifier_apply(modifier="sub")
    for p_ in o.data.polygons:
        p_.use_smooth = True
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.cube_project(cube_size=0.12 * HT)
    bpy.ops.object.mode_set(mode="OBJECT")
    return o


def shoes(pid, name_pt, upper, sole="#ffffff", boot=False, lace=None, cap=True):
    """Sapato do ACNH: comprido (~2x a largura), bico redondo levemente erguido, sola grossa de outra cor,
    calcanhar definido e boca alta no tornozelo (a perna sai dela). Feito por loft, nao ampliando o pe."""
    um = tmat(pid + "_u", fabric(pid + "_u", "cotton", upper, seed=51), rough=0.55, sheen=0.3)
    sm = tmat(pid + "_s", fabric(pid + "_s", "cotton", sole, seed=52), rough=0.7, sheen=0.1)
    parts = []
    for s_ in (-1, 1):
        cx, cy, hx, hy, lcy, lry, lrx = foot_box(s_)
        W = max(hx * 1.18, lrx * 1.45)                   # meia-largura do sapato
        heel_y = cy + hy * 1.1                           # calcanhar cobre o calcanhar do pe
        toe_y = cy - hy * 1.18                           # bico logo a frente do dedao
        Hs = (0.13 if boot else 0.12) * HT                # altura do cabedal
        tl = (heel_y - lcy) / (heel_y - toe_y)           # posicao da perna ao longo do sapato
        soleH = 0.026 * HT
        # largura: calcanhar redondo, mais larga na "bola" do pe, bico arredondado
        wfun = lambda t: (max(0.0, 1 - (1 - t / 0.22) ** 2) ** 0.5 if t < 0.22 else 1.0) * (max(0.0, 1 - ((t - 0.74) / 0.26) ** 2) ** 0.5 if t > 0.74 else 1.0) * (0.9 + 0.1 * math.sin(math.pi * min(1, t / 0.6)))
        # altura: alta no tornozelo, desce suave ate o bico
        hfun = lambda t: Hs * (0.5 + 0.5 * _ss(t / max(tl, 0.1))) * (1 - 0.6 * _ss((t - tl) / (1 - tl))) * (max(0.0, 1 - ((t - 0.8) / 0.2) ** 2) ** 0.5 if t > 0.8 else 1.0)
        up = loft(pid + "_up%d" % (s_ + 1), cx, heel_y, toe_y, W, hfun, wfun, soleH * 0.7, um, spring=0.012 * HT)
        parts.append(up)
        # sola grossa (levemente maior), com a ponta erguida
        parts.append(loft(pid + "_sole%d" % (s_ + 1), cx, heel_y, toe_y, W * 1.04, lambda t: soleH, wfun, 0.0, sm, spring=0.012 * HT, grow=0.0, pw=0.35))
        # biqueira de borracha
        # boca do calcado ao redor da perna
        mouth = ba.torus(pid + "_boca%d" % (s_ + 1), (cx, lcy, hfun(tl) * 0.97 + soleH * 0.7), lrx * 1.2, 0.013 * HT, sm if not boot else um, scale=(1.0, lry / max(lrx, 1e-6), 1.0))
        parts.append(mouth)
        if boot:
            parts.append(ba.cyl(pid + "_cano%d" % (s_ + 1), (cx, lcy, hfun(tl) + 0.05 * HT), lrx * 1.22, lrx * 1.28, 0.1 * HT, um, 40, ))
        elif lace:
            lm = ba.mat(pid + "_l", lace, 0.6)
            for i in range(3):
                t = 0.3 + i * 0.07
                y = heel_y + (toe_y - heel_y) * t
                z = soleH * 0.7 + hfun(t) * 0.93
                parts.append(ba.sphere(pid + "_lace%d_%d" % (s_ + 1, i), (cx, y, z), (W * 0.42, 0.007 * HT, 0.006 * HT), lm, 12))
    return parts


export_piece("shoes_tenis", "shoes", "Tênis Verde", shoes("shoes_tenis", "Tênis Verde", "#6cc070", lace="#ffffff"))
export_piece("shoes_botinha", "shoes", "Botinha Marrom", shoes("shoes_botinha", "Botinha Marrom", "#a8754f", sole="#5a3d2b", boot=True))

# ====================================================================== penteados (volumes lisos esculpidos)
rx, ry, rz = HR
CAPC = HC + Vector((0, 0.02 * ry, 0.03 * rz))
CAPR = Vector((rx * 1.07, ry * 1.07, rz * 1.05))
HAIRTEX = fabric("hair_strands", "hair", "#ffffff", seed=61)


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


HAIR_COLORS = {"Castanho": "#7a4a2c", "Preto": "#2b2523", "Loiro": "#f0c35a", "Laranja": "#f08a3c", "Rosa": "#f49ac1", "Azul": "#5d8fe0", "Branco": "#f4f1ea"}


def hair_style(pid, name_pt, builder):
    if ONLY and pid not in ONLY:
        return
    hm = tmat(pid + "_m", HAIRTEX, rough=0.5, sheen=0.6)
    parts, cuts = builder(hm)
    h = sculpt(pid, parts, hm, cuts)
    export_piece(pid, "hair", name_pt, [h], force={pid: "Head"})


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

# ====================================================================== corpo-base (por ultimo: as pecas precisam dele)
if not ONLY or "body" in ONLY:
    b2 = body.copy()
    b2.data = body.data.copy()
    b2.name = "BodyExport"
    bpy.context.collection.objects.link(b2)
    blush = []
    bm_ = ba.mat("blush", "#ff8a8a", 0.9)
    for s_ in (-1, 1):
        f = cl.raycast_front([body], HC.x + 0.6 * rx * s_, HC.z - 0.52 * rz)
        if f:
            yaw = math.atan2(f[1].x, -f[1].y)
            blush.append(ba.sphere("Blush%d" % (s_ + 1), tuple(f[0] + f[1] * 0.002 * HT), (0.17 * rx, 0.012 * ry, 0.1 * rz), bm_, 24, rot=(0, 0, yaw)))
    export_piece("body", "body", "Corpo", [b2] + blush, force={o.name: "Head" for o in blush})

man_path = os.path.join(OUTD, "wardrobe.json")
old = []
if ONLY and os.path.exists(man_path):
    old = [i for i in json.load(open(man_path, encoding="utf-8"))["items"] if i["id"] not in {e["id"] for e in EXPORTED}]
json.dump({"items": old + EXPORTED, "hairColors": HAIR_COLORS}, open(man_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("GUARDA-ROUPA OK", len(EXPORTED), "pecas", flush=True)
