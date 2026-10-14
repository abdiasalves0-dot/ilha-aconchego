import bpy
from mathutils import Vector
print("INFO objetos", len(bpy.data.objects), "malhas", len(bpy.data.meshes), "materiais", len(bpy.data.materials), "imagens", len(bpy.data.images), "armaduras", len(bpy.data.armatures), "acoes", len(bpy.data.actions))
for o in bpy.data.objects:
    d = o.dimensions
    extra = ""
    if o.type == "MESH":
        me = o.data
        extra = "verts=%d faces=%d uv=%s mats=%s mods=%s shapekeys=%s vgroups=%d" % (len(me.vertices), len(me.polygons), [u.name for u in me.uv_layers], [m.name if m else None for m in me.materials], [m.type for m in o.modifiers], [k.name for k in me.shape_keys.key_blocks] if me.shape_keys else None, len(o.vertex_groups))
    print("INFO OBJ", o.name, o.type, "parent=", o.parent.name if o.parent else None, "loc", tuple(round(c, 3) for c in o.location), "dim", tuple(round(c, 3) for c in d), extra)
for a in bpy.data.armatures:
    print("INFO ARM", a.name, "ossos", len(a.bones), [b.name for b in a.bones][:80])
for m in bpy.data.materials:
    tex = []
    if m.use_nodes:
        tex = [n.image.name for n in m.node_tree.nodes if n.type == "TEX_IMAGE" and n.image]
    print("INFO MAT", m.name, tex)
for i in bpy.data.images:
    print("INFO IMG", i.name, tuple(i.size), i.filepath, "packed" if i.packed_file else "")
for a in bpy.data.actions:
    print("INFO ACT", a.name, [int(a.frame_range[0]), int(a.frame_range[1])])
