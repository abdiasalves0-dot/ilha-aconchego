import bpy, os, math
from mathutils import Vector
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEXD = r"C:\Users\sambalele\Downloads\macchiato-animal-crossing-original-character\textures"
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()
bpy.ops.wm.obj_import(filepath=os.path.join(ROOT, "vendor_ref", "macchiato", "Macchiato.obj"))
o = [o for o in bpy.context.scene.objects if o.type == "MESH"][0]
bpy.context.view_layer.objects.active = o
o.select_set(True)
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
for slot in o.material_slots:
    m = slot.material
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes.get("Principled BSDF")
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = bpy.data.images.load(os.path.join(TEXD, m.name + "_albedo.jpg"))
    nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
    print("MAT", m.name)
sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sc.display.shading.light = "FLAT"
sc.display.shading.color_type = "TEXTURE"
sc.render.resolution_x, sc.render.resolution_y = 700, 700
cam = bpy.data.objects.new("c", bpy.data.cameras.new("c"))
sc.collection.objects.link(cam)
cam.data.type = "ORTHO"
cam.data.ortho_scale = 21
sc.camera = cam
for name, loc, rot in (("front", (0, -40, 8.8), (math.radians(90), 0, 0)), ("side", (40, 0, 8.8), (math.radians(90), 0, math.radians(90)))):
    cam.location = loc
    cam.rotation_euler = rot
    sc.render.filepath = os.path.join(ROOT, "vendor_ref", "prev_" + name + ".png")
    bpy.ops.render.render(write_still=True)
