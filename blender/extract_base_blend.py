"""Extrai o boneco-base (o da direita, x~0) do base.blend em T-pose, sem cabelo/armas, com esqueleto.
Uso: blender -b vendor_ref/base_blend/base.blend -P blender/extract_base_blend.py"""
import bpy, os, math
from mathutils import Vector
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(bpy.data.filepath)).replace("vendor_ref", "").rstrip("\/")) if False else r"C:\Users\sambalele\animalcrossing"
OUT = os.path.join(ROOT, "assets", "models", "base_blend.glb")
KEEP = ["Cube.005", "Circle.003", "Cube.006", "Cube.001", "Circle.004", "Cube.008", "Cube.007", "Plane.003", "Plane.004", "Cube.003"]
arm = bpy.data.objects["Armature"]
arm.data.pose_position = "REST"
bpy.context.scene.frame_set(1)
for o in list(bpy.data.objects):
    if o.type == "MESH" and o.name not in KEEP:
        bpy.data.objects.remove(o)
    elif o.type in ("LIGHT", "CAMERA", "CURVE", "FONT"):
        bpy.data.objects.remove(o)
bpy.context.view_layer.update()
# so o boneco do centro (x~0)
for o in list(bpy.data.objects):
    if o.type == "MESH":
        bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
        cx = sum(v.x for v in bb) / 8
        if abs(cx) > 1.0:
            bpy.data.objects.remove(o)
print("MANTIDOS", [o.name for o in bpy.data.objects if o.type == "MESH"])
bpy.ops.object.select_all(action="SELECT")
bpy.ops.export_scene.gltf(filepath=OUT, export_format="GLB", use_selection=True, export_apply=True, export_skins=True, export_yup=True, export_image_format="AUTO")
print("OK", OUT)
