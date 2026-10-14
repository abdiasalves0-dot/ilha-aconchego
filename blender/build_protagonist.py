"""Protagonista: corpo-base chibi + roupa + cabelo (estilo ACNH). Exporta assets/models/player.glb
Uso: blender -b -P build_protagonist.py
"""
import bpy, bmesh, os, sys, math
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import char_lib as cl
ba = cl.ba

body, M = cl.load_base()
cl.improve_skin(body)
HT, ZN, ZH, TH, X0, AR = M["HT"], M["Z_NECK"], M["Z_HIP"], M["TORSO_HALF"], M["X0"], M["ARM_R"]

# ------------------------------------------------------------------ materiais
SHIRT = ba.tmat("pr_shirt", "plaster", "#f6f3ee", seed=91, rough=0.9, sheen=0.8)
VEST = ba.tmat("pr_vest", "plaster", "#28231f", seed=92, rough=0.8, sheen=0.5)
SUSP = ba.mat("pr_susp", "#e8b52b", 0.55, sheen=0.4)
PANTS = ba.tmat("pr_pants", "tartan", "#2b2421", "#7d5c3c", seed=93, rough=0.9, sheen=0.6)
SHOE = ba.mat("pr_shoe", "#2a1c17", 0.22, spec=1.0)
TIE = ba.mat("pr_tie", "#c81f2a", 0.5, sheen=0.5)
METAL = ba.mat("pr_metal", "#8f8372", 0.3, spec=1.0)
HAIR = ba.mat("pr_hair", "#f3f0e9", 0.55, sheen=0.7)
HORN = ba.mat("pr_horn", "#d9a42c", 0.28, spec=0.9)
BTN = ba.mat("pr_btn", "#14110f", 0.3)

UP, DOWN = (0, 0, 1), (0, 0, -1)
SLEEVE_END = X0 + 0.085 * HT          # manga curta ate o meio do braco (em T-pose o braco esta no eixo X)
HEM = ZH - 0.01 * HT                  # barra da camisa (aparece abaixo do colete)
VEST_BOTTOM = ZH + 0.025 * HT
CUFF_Z = 0.1 * HT                     # barra da calca

# ------------------------------------------------------------------ camisa branca (manga curta dobrada) + gola
shirt = cl.shell(body, M, "Shirt", lambda c, n: HEM - 0.03 * HT < c.z < ZN + 0.02 * HT and abs(c.x) < SLEEVE_END + 0.03 * HT,
                 0.006, SHIRT, cuts=[cl.cut((0, 0, ZN - 0.004 * HT), UP, "below"), cl.cut((0, 0, HEM), UP, "above"),
                                     cl.cut((SLEEVE_END, 0, 0), (1, 0, 0), "below"), cl.cut((-SLEEVE_END, 0, 0), (-1, 0, 0), "below")])
cuffs = cl.shell(body, M, "ShirtCuffs", lambda c, n: abs(c.x) > SLEEVE_END - 0.045 * HT and abs(c.x) < SLEEVE_END + 0.03 * HT and c.z > 0.44 * HT and c.z < ZN,
                 0.014, SHIRT, cuts=[cl.cut((SLEEVE_END, 0, 0), (1, 0, 0), "below"), cl.cut((-SLEEVE_END, 0, 0), (-1, 0, 0), "below"),
                                     cl.cut((SLEEVE_END - 0.035 * HT, 0, 0), (1, 0, 0), "above") if False else cl.cut((0, 0, 0), (0, 0, 1), "above")],
                 post=lambda bm: bmesh.ops.delete(bm, geom=[f for f in bm.faces if abs(f.calc_center_median().x) < SLEEVE_END - 0.035 * HT], context="FACES"))
collar = cl.shell(body, M, "Collar", lambda c, n: ZN - 0.05 * HT < c.z < ZN + 0.01 * HT and abs(c.x) < TH,
                  0.016, SHIRT, cuts=[cl.cut((0, 0, ZN - 0.002 * HT), UP, "below"), cl.cut((0, 0, ZN - 0.03 * HT), UP, "above")])

# ------------------------------------------------------------------ colete preto com decote em V
VK, VB = 0.62, ZH + 0.12 * HT          # inclinacao e fundo do V


def vest_post(bm):
    for sx in (1, -1):
        bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-6, plane_co=(0, 0, VB), plane_no=(sx, 0, -VK))
    dead = []
    for f in bm.faces:
        c = f.calc_center_median()
        if c.y < M["HC"].y and c.z > VB and abs(c.x) < (c.z - VB) * VK:
            dead.append(f)
    bmesh.ops.delete(bm, geom=dead, context="FACES")


vest = cl.shell(body, M, "Vest", lambda c, n: VEST_BOTTOM - 0.03 * HT < c.z < ZN and abs(c.x) < TH * 1.25,
                0.012, VEST, cuts=[cl.cut((0, 0, ZN - 0.03 * HT), UP, "below"), cl.cut((0, 0, VEST_BOTTOM), UP, "above"),
                                   cl.cut((TH * 1.08, 0, 0), (1, 0, 0), "below"), cl.cut((-TH * 1.08, 0, 0), (-1, 0, 0), "below")],
                post=vest_post)

# ------------------------------------------------------------------ suspensorios (faixas sobre o colete, frente e costas)
SX, SW = TH * 0.55, 0.018 * HT
straps = []
for s in (-1, 1):
    xs = SX * s
    straps.append(cl.shell(body, M, "Strap%d" % (s + 1), lambda c, n, xs=xs: abs(c.x - xs) < SW + 0.02 * HT and ZH - 0.02 * HT < c.z < ZN + 0.01 * HT,
                           0.019, SUSP, thickness=0.003,
                           cuts=[cl.cut((xs + SW, 0, 0), (1, 0, 0), "below"), cl.cut((xs - SW, 0, 0), (1, 0, 0), "above"),
                                 cl.cut((0, 0, ZH - 0.005 * HT), UP, "above"), cl.cut((0, 0, ZN - 0.012 * HT), UP, "below")]))

# ------------------------------------------------------------------ calca xadrez com barra dobrada + mocassins
pants = cl.shell(body, M, "Pants", lambda c, n: CUFF_Z - 0.02 * HT < c.z < ZH + 0.06 * HT and abs(c.x) < TH * 1.3,
                 0.009, PANTS, cuts=[cl.cut((0, 0, ZH + 0.035 * HT), UP, "below"), cl.cut((0, 0, CUFF_Z), UP, "above")])
pcuff = cl.shell(body, M, "PantsCuff", lambda c, n: CUFF_Z - 0.02 * HT < c.z < CUFF_Z + 0.05 * HT,
                 0.017, PANTS, cuts=[cl.cut((0, 0, CUFF_Z + 0.03 * HT), UP, "below"), cl.cut((0, 0, CUFF_Z - 0.002 * HT), UP, "above")])
shoes = cl.shell(body, M, "Shoes", lambda c, n: c.z < 0.085 * HT, 0.013, SHOE, thickness=0.008,
                 cuts=[cl.cut((0, 0, 0.07 * HT), UP, "below")])

# ------------------------------------------------------------------ gravata, botoes e fivelas
extras = []
fr = cl.raycast_front([shirt], 0.0, ZN - 0.03 * HT)
ty = fr[0].y if fr else M["FRONT_Y"]
extras.append(ba.sphere("TieKnot", (0, ty - 0.008 * HT, ZN - 0.03 * HT), (0.022 * HT, 0.016 * HT, 0.02 * HT), TIE, 20))
tie = ba.cone("Tie", (0, ty - 0.004 * HT, ZN - 0.105 * HT), 0.032 * HT, 0.13 * HT, TIE, 4)
tie.rotation_euler = (math.radians(180), 0, math.radians(45))
tie.scale = (1, 0.22, 1)
extras.append(tie)
for i in range(2):
    z = VB - 0.012 * HT - i * 0.04 * HT
    f = cl.raycast_front([vest], 0.0, z)
    if f:
        extras.append(ba.sphere("Btn", f[0] + Vector((0, -0.004 * HT, 0)), (0.009 * HT, 0.005 * HT, 0.009 * HT), BTN, 12))
for s in (-1, 1):
    for z in (ZN - 0.075 * HT, ZH + 0.03 * HT):
        f = cl.raycast_front(straps, SX * s, z)
        if f:
            extras.append(ba.box("Buckle", tuple(f[0] + Vector((0, -0.004 * HT, 0))), (0.03 * HT, 0.006 * HT, 0.022 * HT), METAL, 0.002 * HT, 0.05))

# ------------------------------------------------------------------ cabelo esculpido + chifres
hair = cl.hair_mesh(body, M, HAIR)
HC, HR = M["HC"], M["HR"]
horns = []
for s in (-1, 1):
    d = Vector((0.5 * s, -0.55, 0.67)).normalized()
    root = HC + Vector((d.x * HR.x, d.y * HR.y, d.z * HR.z)) * 1.12
    horns.append(cl.lock("Horn%d" % (s + 1), root, root + Vector((0.16 * HR.x * s, -0.05 * HR.y, 0.22 * HR.z)),
                         root + Vector((0.06 * HR.x * s, -0.1 * HR.y, 0.45 * HR.z)), 0.13 * HR.x, HORN, flat=1.0, side=Vector((0, 1, 0)), n=16))

objs = [body, shirt, cuffs, collar, vest, pants, pcuff, shoes, hair] + straps + extras + horns
force = {o.name: "Head" for o in [hair] + horns}
cl.export_character(objs, M, os.path.join(cl.ROOTDIR, "assets", "models", "player.glb"), force_part=force)
