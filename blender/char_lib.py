"""Biblioteca de personagens estilo Animal Crossing (Blender, headless).

Fluxo:
  body, M = load_base()                         # corpo-base chibi (Meshy) em T-pose, medidas em M
  improve_skin(body)                            # pele lisa estilo ACNH
  garment = shell(body, M, "Camisa", filtro, offset, material, cortes=[...])   # roupa = casca do corpo
  hair   = hair_mesh(body, M, material)          # cabelo esculpido (mechas + calota, fundidas)
  export_character([body, garment, hair, ...], M, "assets/models/x.glb")

Tecnica das roupas (pesquisada): duplicar faces do corpo na regiao da peca, afastar da pele
(como Shrinkwrap com offset), cortar bordas retas (bisect), dar espessura (Solidify) e suavizar.
Tecnica do cabelo: mechas = tubos afilados sobre uma calota; tudo fundido por Voxel Remesh e suavizado.
Os bracos sao baixados da T-pose RETOS (dobra apenas na articulacao do ombro).
"""
import bpy, bmesh, os, math, random, importlib.util
import numpy as np
from mathutils import Vector, Matrix
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOTDIR = os.path.dirname(HERE)
_spec = importlib.util.spec_from_file_location("ba", os.path.join(HERE, "build_assets.py"))
ba = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ba)
BASE_OBJ = os.path.join(ROOTDIR, "vendor_ref", "chibi_base", "Meshy_AI_Chibi_Base_Model_Turn_1013010524_texture.obj")
H_FINAL = 2.3


# ====================================================================== corpo-base
def load_base():
    # sem historico de desfazer: em scripts ele so acumula copias da malha e estoura a memoria
    try:
        bpy.context.preferences.edit.undo_steps = 0
        bpy.context.preferences.edit.use_global_undo = False
    except Exception:
        pass
    ba.clear()
    bpy.ops.wm.obj_import(filepath=BASE_OBJ)
    src = [o for o in bpy.context.selected_objects if o.type == "MESH"][0]
    bpy.context.view_layer.objects.active = src
    src.select_set(True)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    me = src.data
    # ilhas da folha de turnaround -> boneco de corpo inteiro mais a esquerda (vista de frente)
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
        info.append((isl, Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))),
                     Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))))
    hmax = max(i[2].z - i[1].z for i in info)
    tall = [t for t in info if (t[2].z - t[1].z) > 0.75 * hmax]
    front = min(tall, key=lambda t: (t[1].x + t[2].x) / 2)
    keep = set()
    for isl, mn, mx in info:
        c = (mn + mx) / 2
        if front[1].x - 0.02 <= c.x <= front[2].x + 0.02 and front[1].z - 0.02 <= c.z <= front[2].z + 0.02:
            keep.update(isl)
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.index not in keep], context="VERTS")
    bm.to_mesh(me)
    bm.free()
    vs = [v.co for v in me.vertices]
    mn = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
    mx = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
    me.transform(Matrix.Translation((-(mn.x + mx.x) / 2, -(mn.y + mx.y) / 2, -mn.z)))
    src.name = "Body"
    reshape_feet(me)
    for p in me.polygons:
        p.use_smooth = True
    return src, measure(src)


def reshape_feet(me):
    """O pe gerado pelo Meshy e uma bolota simetrica. Como na referencia, o pe deve avancar para a frente
    (bico) e ter calcanhar: alonga a metade da frente e recolhe a de tras, so abaixo do tornozelo."""
    vs = me.vertices
    HT = max(v.co.z for v in vs)
    ANK = 0.08 * HT
    for side in (-1, 1):
        leg = [v.co for v in vs if 0.085 * HT < v.co.z < 0.11 * HT and (v.co.x > 0) == (side > 0)]
        cx = sum(c.x for c in leg) / len(leg)
        cy = sum(c.y for c in leg) / len(leg)
        for v in vs:
            c = v.co
            if c.z >= ANK or (c.x > 0) != (side > 0):
                continue
            t = min(1.0, (ANK - c.z) / (ANK * 0.6))   # o peito do pe acompanha (sem formato de cunha)
            t = t * t * (3 - 2 * t)
            dy = c.y - cy
            if dy < 0:   # frente: bico mais longo e um pouco mais largo
                c.y = cy + dy * (1 + 0.14 * t) - 0.006 * HT * t   # bico curto e redondo (pe compacto do ACNH)
                c.x = cx + (c.x - cx) * (1 + 0.06 * t)
            else:        # calcanhar arredondado
                c.y = cy + dy * (1 - 0.08 * t)
    me.update()


def measure(body):
    vs = [v.co.copy() for v in body.data.vertices]
    HT = max(v.z for v in vs)

    def width_at(zf, band=0.02):
        sel = [abs(v.x) for v in vs if abs(v.z - zf * HT) < band * HT]
        return max(sel) if sel else 0.0
    M = {"HT": HT, "Z_NECK": 0.585 * HT, "Z_HIP": 0.37 * HT}
    M["TORSO_HALF"] = max(width_at(0.4), width_at(0.45)) * 1.1
    arm = [v.z for v in vs if abs(v.x) > 0.2 * HT and v.z < M["Z_NECK"]]
    M["ARM_Z"] = (min(arm) + max(arm)) / 2
    M["ARM_R"] = (max(arm) - min(arm)) / 2
    M["ARM_END"] = max(abs(v.x) for v in vs if v.z < M["Z_NECK"])
    # articulacao do ombro: centro de rotacao um raio de braco fora do tronco -> braco desce reto, sem invadir o corpo
    # articulacao no canto SUPERIOR-INTERNO do braco (rente ao tronco): ao girar 90 graus o braco desce reto,
    # encostado ao corpo, e so a curva do ombro sofre transicao
    M["X0"] = M["TORSO_HALF"] + M["ARM_R"] * 0.45
    M["ARM_PZ"] = M["ARM_Z"] + M["ARM_R"] * 0.9
    M["BLEND"] = M["ARM_R"] * 0.45
    M["ARM_ANGLE"] = math.radians(62)  # como no ACNH: bracos retos, abertos ~28 graus do corpo
    head = [v for v in vs if v.z > M["Z_NECK"] + 0.02 * HT and abs(v.x) < width_at(0.7) * 0.82]
    M["HC"] = Vector((0, sum(v.y for v in head) / len(head), (min(v.z for v in head) + max(v.z for v in head)) / 2))
    M["HR"] = Vector((max(abs(v.x) for v in head), (max(v.y for v in head) - min(v.y for v in head)) / 2,
                      (max(v.z for v in head) - min(v.z for v in head)) / 2))
    M["HEAD_TOP"] = max(v.z for v in head)
    M["FRONT_Y"] = min(v.y for v in head)
    print("MEDIDAS", {k: (round(v, 3) if isinstance(v, float) else tuple(round(c, 3) for c in v)) for k, v in M.items()})
    return M


# ====================================================================== pele estilo ACNH
def _box_blur(a, r):
    if r <= 0:
        return a
    k = 2 * r + 1
    p = np.pad(a, ((r, r), (r, r)) + ((0, 0),) * (a.ndim - 2), mode="edge")
    c = np.cumsum(np.cumsum(p, 0), 1)
    c = np.pad(c, ((1, 0), (1, 0)) + ((0, 0),) * (a.ndim - 2))
    return (c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]) / (k * k)


SKIN_BASE = "#e8955c"  # tom da referencia; o jogo multiplica por outros tons usando a mascara


def improve_skin(body, target=SKIN_BASE, keep_shading=0.22, out_name="base_skin_ac.png"):
    """Recolore os pixels de pele da textura para um tom liso e uniforme (como no ACNH),
    preservando olhos, sobrancelhas, nariz, boca e roupa de baixo. Remove as manchas da textura gerada."""
    mat = body.data.materials[0]
    nt = mat.node_tree
    tex = [n for n in nt.nodes if n.type == "TEX_IMAGE"][0]
    img = tex.image
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(h, w, 4)
    rgb = px[..., :3]
    mx, mn = rgb.max(-1), rgb.min(-1)
    sat = (mx - mn) / (mx + 1e-6)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    hue = np.where(mx - mn > 1e-6, (g - b) / (mx - mn + 1e-6) * 60.0, 0)
    skin = (r >= g) & (g >= b) & (sat > 0.2) & (sat < 0.8) & (mx > 0.4) & (hue > 14) & (hue < 42)
    lum = rgb @ np.array([0.3, 0.59, 0.11], dtype=np.float32)
    mean_l = float(lum[skin].mean())
    # variacao suave (remove manchas, mantem um pouco do sombreamento pintado)
    var = _box_blur((lum / mean_l)[..., None], 6)[..., 0]
    tgt = ba.hexrgb(target).astype(np.float32)
    new = tgt[None, None, :] * (1.0 + (var - 1.0) * keep_shading)[..., None]
    m = _box_blur(skin.astype(np.float32)[..., None], 2)[..., 0]
    m = np.clip((m - 0.35) / 0.4, 0, 1)
    out = rgb * (1 - m[..., None]) + new * m[..., None]
    path = os.path.join(ROOTDIR, "assets", "textures", out_name)
    new_img = bpy.data.images.new(out_name, w, h, alpha=False)
    full = np.ones((h, w, 4), dtype=np.float32)
    full[..., :3] = np.clip(out, 0, 1)
    new_img.pixels.foreach_set(full.ravel())
    new_img.filepath_raw = path
    new_img.file_format = "PNG"
    new_img.save()
    tex.image = bpy.data.images.load(path)
    # mascara para o jogo: R = pele (troca de tom), G = iris (troca da cor dos olhos)
    iris = (~skin) & (r >= g) & (g >= b) & (mx > 0.1) & (mx < 0.55) & (sat > 0.35) & (hue > 15) & (hue < 42)
    irm = np.clip((_box_blur(iris.astype(np.float32)[..., None], 1)[..., 0] - 0.2) / 0.5, 0, 1)
    mk = np.zeros((h, w, 4), dtype=np.float32)
    mk[..., 0], mk[..., 1], mk[..., 3] = m, irm, 1
    mpath = os.path.join(ROOTDIR, "assets", "textures", "base_skin_mask.png")
    mi = bpy.data.images.new("base_skin_mask", w, h, alpha=False)
    mi.pixels.foreach_set(mk.ravel())
    mi.filepath_raw = mpath
    mi.file_format = "PNG"
    mi.save()
    print("MASCARA pele/iris ->", mpath, "iris px", int(iris.sum()), flush=True)
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Roughness"].default_value = 0.78
    bsdf.inputs["Metallic"].default_value = 0.0
    for k_ in ("Specular IOR Level", "Specular"):
        if k_ in bsdf.inputs:
            bsdf.inputs[k_].default_value = 0.25
    if "Sheen Weight" in bsdf.inputs:
        bsdf.inputs["Sheen Weight"].default_value = 0.5   # acabamento aveludado (como a referencia)
    mat.use_backface_culling = False
    print("PELE: pixels recoloridos", int(skin.sum()), "->", path)


# ====================================================================== roupas = cascas do corpo
_PROXY = {}


def body_proxy(body, iterations=25):
    """Copia suavizada do corpo (sem o ruido da malha gerada): base limpa para roupas e cabelo."""
    key = (body.name, iterations)
    if key in _PROXY:
        return _PROXY[key]
    bm = bmesh.new()
    bm.from_mesh(body.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    for _ in range(iterations):
        bmesh.ops.smooth_vert(bm, verts=bm.verts, factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    bm.normal_update()
    _PROXY[key] = bm
    return bm


def cut(co, no, keep="below"):
    """Corte reto: plano (co, no). keep='below' mantem o lado negativo da normal."""
    return (Vector(co), Vector(no), keep)


def shell(body, M, name, keep_face, offset, mat, cuts=(), thickness=0.004, subdiv=1, uv_size=0.12, post=None, smooth_iters=8):
    """Roupa a partir da superficie do corpo: faces filtradas -> afastadas ao longo da normal -> cortes retos
    -> espessura (Solidify) -> suavizacao (Subdivision). offset/thickness em fracao da altura (M['HT'])."""
    HT = M["HT"]
    bm = body_proxy(body).copy()
    bm.normal_update()
    nrm = {v.index: v.normal.copy() for v in bm.verts}
    bm.verts.ensure_lookup_table()
    dead = [f for f in bm.faces if not keep_face(f.calc_center_median(), f.normal)]
    bmesh.ops.delete(bm, geom=dead, context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    for v in bm.verts:
        v.co += nrm[v.index] * offset * HT
    for co, no, keep in cuts:
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-6, plane_co=co, plane_no=no,
                               clear_outer=(keep == "below"), clear_inner=(keep == "above"))
    if post:
        post(bm)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    ob.data.materials.append(mat)
    for p in me.polygons:
        p.use_smooth = True
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    # garante que a pele real nunca atravesse a roupa (Shrinkwrap "por fora" contra o corpo verdadeiro)
    sw = ob.modifiers.new("sw", "SHRINKWRAP")
    sw.target = body
    sw.wrap_method = "NEAREST_SURFACEPOINT"
    sw.wrap_mode = "OUTSIDE"
    sw.offset = max(0.002, offset * 0.7) * HT
    bpy.ops.object.modifier_apply(modifier="sw")
    # tecido liso: suaviza (tira o "amassado" herdado da malha gerada) e garante de novo que fica por fora da pele
    if smooth_iters:
        sm = ob.modifiers.new("sm", "SMOOTH")
        sm.factor = 0.6
        sm.iterations = smooth_iters
        bpy.ops.object.modifier_apply(modifier="sm")
        sw = ob.modifiers.new("sw2", "SHRINKWRAP")
        sw.target = body
        sw.wrap_method = "NEAREST_SURFACEPOINT"
        sw.wrap_mode = "OUTSIDE"
        sw.offset = max(0.002, offset * 0.5) * HT
        bpy.ops.object.modifier_apply(modifier="sw2")
    if thickness:
        so = ob.modifiers.new("sol", "SOLIDIFY")
        so.thickness = thickness * HT
        so.offset = 1.0
        so.use_rim = True
        so.use_even_offset = False
        bpy.ops.object.modifier_apply(modifier="sol")
    if subdiv:
        sd = ob.modifiers.new("sub", "SUBSURF")
        sd.levels = subdiv
        sd.render_levels = subdiv
        bpy.ops.object.modifier_apply(modifier="sub")
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.cube_project(cube_size=uv_size * HT)
    bpy.ops.object.mode_set(mode="OBJECT")
    for p in ob.data.polygons:
        p.use_smooth = True
    print("ROUPA", name, "faces", len(ob.data.polygons), flush=True)
    return ob


def raycast_front(objs, x, z, y0=-5.0):
    """Ponto mais a frente (menor y) atingido entre objs no (x,z) dado."""
    bpy.context.view_layer.update()
    best = None
    for o in objs:
        inv = o.matrix_world.inverted()
        hit, loc, n, _ = o.ray_cast(inv @ Vector((x, y0, z)), (inv.to_3x3() @ Vector((0, 1, 0))).normalized())
        if hit:
            w = o.matrix_world @ loc
            if best is None or w.y < best[0].y:
                best = (w, (inv.transposed().to_3x3() @ n).normalized())
    return best


# ====================================================================== cabelo esculpido
def _bez(p0, p1, p2, n):
    return [p0 * (1 - t) ** 2 + p1 * 2 * (1 - t) * t + p2 * t * t for t in (i / (n - 1) for i in range(n))]


def tube(name, pts, radii, mat, segs=10, flat=1.0, side=None):
    bm = bmesh.new()
    rings, n = [], len(pts)
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
        a = side.normalized() if side is not None else Vector((0, 0, 1))
        if abs(t.dot(a)) > 0.95:
            a = Vector((1, 0, 0)) if abs(t.x) < 0.9 else Vector((0, 1, 0))
        u = t.cross(a).normalized()
        v = t.cross(u).normalized()
        if radii[i] <= 1e-6:
            rings.append([bm.verts.new(p)])
            continue
        rings.append([bm.verts.new(p + u * math.cos(k / segs * math.tau) * radii[i] + v * math.sin(k / segs * math.tau) * radii[i] * flat) for k in range(segs)])
    for i in range(n - 1):
        A, B = rings[i], rings[i + 1]
        for k in range(segs):
            if len(B) == 1:
                bm.faces.new([A[k], A[(k + 1) % segs], B[0]])
            else:
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
    o.data.materials.append(mat)
    for p in me.polygons:
        p.use_smooth = True
    return o


def lock(name, root, mid, tip, r0, mat, flat=0.55, side=None, n=14):
    pts = _bez(Vector(root), Vector(mid), Vector(tip), n)
    return tube(name, pts, [r0 * (1 - i / (n - 1)) ** 0.7 for i in range(n)], mat, 10, flat, side)


def hair_mesh(body, M, mat, style="tousled", seed=3, voxel=0.0065, decimate=0.5):
    """Cabelo estilo ACNH: calota sobre o couro cabeludo + mechas grossas, fundidas por Voxel Remesh."""
    HT, HC, HR = M["HT"], M["HC"], M["HR"]
    rx, ry, rz = HR
    random.seed(seed)

    def scalp_keep(c, n):
        lx, ly, lz = (c.x - HC.x) / rx, (c.y - HC.y) / ry, (c.z - HC.z) / rz
        if c.z < M["Z_NECK"] + 0.01 * HT:
            return False
        if abs(lx) > 0.86 and lz < 0.3:      # orelhas ficam de fora
            return False
        if ly < -0.35:                       # frente: so acima da testa
            return lz > 0.38
        if ly < 0.25:                        # laterais
            return lz > 0.1
        return lz > -0.55                    # nuca
    parts = [shell(body, M, "Scalp", scalp_keep, 0.018, mat, thickness=0.03, subdiv=0)]

    def surf(lx, ly, lz, push=1.0):
        d = Vector((lx, ly, lz)).normalized()
        return HC + Vector((d.x * rx, d.y * ry, d.z * rz)) * push, Vector((d.x / rx, d.y / ry, d.z / rz)).normalized()
    k = 0
    # coroa: mechas fofas que varrem para os lados e levantam as pontas
    for i in range(24):
        az = i / 24 * math.tau + random.uniform(-0.12, 0.12)
        el = random.uniform(0.25, 0.85)
        p, d = surf(math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el), 0.98)
        radial = Vector((math.cos(az), math.sin(az), 0))
        L = rx * random.uniform(0.32, 0.48)
        mid = p + radial * L * 0.45 + Vector((0, 0, L * 0.35))
        tip = p + radial * L * 0.95 + Vector((0, 0, L * random.uniform(0.0, 0.3)))
        parts.append(lock("Lock%d" % k, p, mid, tip, rx * random.uniform(0.17, 0.22), mat, 0.55, d)); k += 1
    # topo
    for i in range(6):
        p, d = surf(random.uniform(-0.35, 0.35), random.uniform(-0.2, 0.4), 1.0, 0.95)
        L = rx * 0.35
        parts.append(lock("Top%d" % k, p, p + Vector((p.x * 0.1, 0.05 * rx, L * 0.7)), p + Vector((random.uniform(-0.15, 0.15) * rx, random.uniform(0.05, 0.25) * rx, L)), rx * 0.17, mat, 0.55, Vector((1, 0, 0)))); k += 1
    # franja: mechas grossas caindo sobre a testa ate a sobrancelha
    brow_z = HC.z + 0.22 * rz
    for i, (lx, drop) in enumerate([(-0.78, 0.0), (-0.48, 0.07), (-0.18, 0.02), (0.12, 0.09), (0.42, 0.01), (0.72, 0.05)]):
        root, _ = surf(lx * 0.9, -0.55, 0.8, 1.0)
        fr = raycast_front([body], HC.x + lx * rx * 0.8, brow_z + drop * rz)
        front_y = fr[0].y if fr else HC.y - ry
        tip = Vector((HC.x + lx * rx * 0.85, front_y - 0.035 * HT, brow_z + drop * rz))
        mid = Vector((root.x * 1.05, front_y - 0.07 * HT, (root.z + tip.z) / 2 + 0.05 * rz))
        parts.append(lock("Bang%d" % k, root, mid, tip, rx * 0.2, mat, 0.45, Vector((0, -1, 0.3)))); k += 1
    # laterais (acima das orelhas) e nuca
    for s in (-1, 1):
        for j in range(3):
            root, d = surf(0.85 * s, -0.2 + j * 0.3, 0.45, 1.0)
            tip = root + Vector((0.18 * rx * s, 0.0, -0.32 * rz))
            parts.append(lock("Side%d" % k, root, root + Vector((0.2 * rx * s, 0, -0.08 * rz)), tip, rx * 0.18, mat, 0.5, Vector((s, 0, 0)))); k += 1
    for j in range(5):
        lx = -0.6 + j * 0.3
        root, d = surf(lx, 0.85, -0.05, 1.0)
        parts.append(lock("Nape%d" % k, root, root + Vector((lx * 0.05, 0.12 * ry, -0.12 * rz)), root + Vector((lx * 0.12 * rx, 0.1 * ry, -0.38 * rz)), rx * 0.18, mat, 0.5, Vector((0, 1, 0)))); k += 1
    # funde tudo num volume esculpido
    bpy.ops.object.select_all(action="DESELECT")
    for o in parts:
        o.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    hair = bpy.context.view_layer.objects.active
    hair.name = "Hair"
    # seguranca: nenhum vertice pode escapar muito da cabeca (senao o voxel remesh explode a memoria)
    lim = max(rx, ry, rz) * 2.2
    moved = 0
    for v in hair.data.vertices:
        d = v.co - HC
        if not all(math.isfinite(c) for c in v.co) or d.length > lim:
            v.co = HC + (d.normalized() if d.length > 0 and all(math.isfinite(c) for c in d) else Vector((0, 0, 1))) * lim
            moved += 1
    xs = [v.co for v in hair.data.vertices]
    print("CABELO bbox", [round(min(c[i] for c in xs), 3) for i in range(3)], [round(max(c[i] for c in xs), 3) for i in range(3)], "corrigidos", moved, flush=True)
    rm = hair.modifiers.new("rm", "REMESH")
    rm.mode = "VOXEL"
    rm.voxel_size = voxel * HT
    bpy.ops.object.modifier_apply(modifier="rm")
    sm = hair.modifiers.new("sm", "SMOOTH")
    sm.factor = 0.7
    sm.iterations = 10
    bpy.ops.object.modifier_apply(modifier="sm")
    dc = hair.modifiers.new("dc", "DECIMATE")
    dc.ratio = decimate
    bpy.ops.object.modifier_apply(modifier="dc")
    for p in hair.data.polygons:
        p.use_smooth = True
    # sombreamento suave por vertice: mais escuro perto da cabeca (oclusao), mais claro nas pontas
    ca = hair.data.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
    for i, v in enumerate(hair.data.vertices):
        q = Vector(((v.co.x - HC.x) / rx, (v.co.y - HC.y) / ry, (v.co.z - HC.z) / rz))
        t = max(0.0, min(1.0, (q.length - 1.0) / 0.35))
        kk = 0.78 + 0.22 * t
        ca.data[i].color = (kk, kk, kk, 1.0)
    print("CABELO faces", len(hair.data.polygons), flush=True)
    return hair


# ====================================================================== montagem: bracos retos, partes, exportacao
def _smooth01(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def part_of(c, M):
    x, y, z = c
    if z >= M["Z_NECK"]:
        return "Head"
    if abs(x) > M["X0"] - M["BLEND"] * 0.35 and z > 0.44 * M["HT"]:
        return "ArmL" if x < 0 else "ArmR"
    if z < M["Z_HIP"] - 0.02 * M["HT"]:
        return "FootL" if x < 0 else "FootR"
    return "Root"


ARM_STRETCH = 2.1


def bend_arms(me, M):
    """Baixa os bracos da T-pose: rotacao rigida (braco reto) com transicao curta so na articulacao."""
    HT, X0, BL, ANG, AZ = M["HT"], M["X0"], M["BLEND"], M["ARM_ANGLE"], M["ARM_PZ"]
    for v in me.vertices:
        x, y, z = v.co
        if not (0.42 * HT < z < M["Z_NECK"] + 0.01 * HT) or abs(x) <= X0 - BL:
            continue
        s = 1 if x > 0 else -1
        # alonga o braco (o corpo-base tem bracos muito curtos): estica so o trecho ombro->punho, a mao so desloca
        d = abs(x) - X0
        if d > 0:
            L = M["ARM_END"] - 1.4 * M["ARM_R"] - X0
            d = d * ARM_STRETCH if d <= L else L * ARM_STRETCH + (d - L)
            x = s * (X0 + d)
        a = ANG * _smooth01((abs(x) - (X0 - BL)) / BL) * s
        dx, dz = x - X0 * s, z - AZ
        v.co.x = X0 * s + dx * math.cos(a) + dz * math.sin(a)
        v.co.z = AZ - dx * math.sin(a) + dz * math.cos(a)
    me.update()


def export_character(objs, M, out_path, force_part=None):
    """objs: objetos em T-pose (espaco do corpo-base). force_part: {nome_obj: parte} (ex.: cabelo -> Head)."""
    force_part = force_part or {}
    HT = M["HT"]
    S = H_FINAL / HT
    PIV = {"Head": (0, 0, M["Z_NECK"]), "ArmL": (-M["X0"], 0, M["ARM_PZ"]), "ArmR": (M["X0"], 0, M["ARM_PZ"]),
           "FootL": (-0.06 * HT, 0, M["Z_HIP"]), "FootR": (0.06 * HT, 0, M["Z_HIP"])}

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
    root = pivot("Root", (0, 0, 0))
    pivots = {"Root": root}
    for k, (px, py, pz) in PIV.items():
        pivots[k] = pivot(k, (px * S, py * S, pz * S), root)
    for ob in objs:
        bpy.context.view_layer.update()
        ob.data.transform(ob.matrix_world)
        ob.matrix_world = Matrix.Identity(4)
        me = ob.data
        groups = defaultdict(list)
        for p in me.polygons:
            groups[force_part.get(ob.name) or part_of(p.center, M)].append(p.index)
        bend_arms(me, M)
        for part, idxs in groups.items():
            b = bmesh.new()
            b.from_mesh(me)
            b.faces.ensure_lookup_table()
            keep = set(idxs)
            bmesh.ops.delete(b, geom=[f for f in b.faces if f.index not in keep], context="FACES")
            bmesh.ops.delete(b, geom=[v for v in b.verts if not v.link_faces], context="VERTS")
            m2 = bpy.data.meshes.new(ob.name + "_" + part)
            b.to_mesh(m2)
            b.free()
            for m in me.materials:
                m2.materials.append(m)
            for p in m2.polygons:
                p.use_smooth = True
            m2.transform(Matrix.Scale(S, 4))
            o2 = bpy.data.objects.new(ob.name + "_" + part, m2)
            bpy.context.collection.objects.link(o2)
            att(o2, pivots[part])
        bpy.data.objects.remove(ob)
    bpy.ops.object.select_all(action="DESELECT")
    stack = [root]
    while stack:
        o = stack.pop()
        o.select_set(True)
        stack.extend(o.children)
    kw = dict(filepath=out_path, export_format="GLB", use_selection=True, export_apply=True, export_yup=True, export_image_format="AUTO")
    try:
        bpy.ops.export_scene.gltf(export_vertex_color="ACTIVE", **kw)
    except TypeError:
        bpy.ops.export_scene.gltf(**kw)
    print("OK", out_path)
