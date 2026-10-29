#avatar
"""Exporte asset/Bonnie1.blend en GLB avec des clés de bouche.

Le .blend n'a ni armature ni shape keys. Ce script en crée six, nommées
comme les blendshapes ARKit qu'Audio2Face renvoie, puis écrit
avatar/view/bonnie.glb pour l'affichage dans le navigateur.

    /Applications/Blender.app/Contents/MacOS/Blender --background \
        asset/Bonnie1.blend --python avatar/export_bonnie.py
"""

import math
import os

import bpy
from mathutils import Vector

#avatar
DESTINATION = os.path.join(os.path.dirname(__file__), "view", "bonnie.glb")
# Les .001 sont des copies superposées. La tête basse se confond avec bonnie_head.
GARDES = (
    "bonnie_head",
    "eyes",
    "hair",
    "teeth",
    "polySurface1_Pupil_0.001",
    "polySurface1_Pupil_0.002",
    "polySurface2_Eye_0",
)
CLES = (
    "JawOpen",
    "MouthClose",
    "MouthFunnel",
    "MouthPucker",
    "MouthSmileLeft",
    "MouthSmileRight",
)


def _points(obj, step=1):
    #avatar
    world = obj.matrix_world
    vertices = obj.data.vertices
    return [world @ vertices[index].co for index in range(0, len(vertices), step)]


def _cles(obj):
    #avatar
    if obj.data.shape_keys is None:
        obj.shape_key_add(name="Basis", from_mix=False)
    blocks = obj.data.shape_keys.key_blocks
    created = {}
    for name in CLES:
        created[name] = blocks.get(name) or obj.shape_key_add(name=name, from_mix=False)
        created[name].value = 0.0
    return created


def _bouche(head_name, teeth_name):
    #avatar
    # Les lèvres sont les sommets de la tête les plus proches des dents.
    head = bpy.data.objects[head_name]
    teeth = bpy.data.objects[teeth_name]
    samples = _points(teeth, step=8)
    center = sum(samples, Vector()) / len(samples)
    keys = _cles(head)
    inverse = head.matrix_world.inverted()
    touched = 0
    for index, vertex in enumerate(head.data.vertices):
        world = head.matrix_world @ vertex.co
        nearest = min(samples, key=lambda point: (point - world).length)
        distance = (nearest - world).length
        # Devant les dents seulement : la face regarde vers -Y.
        if distance > 0.00055 or world.y > nearest.y + 0.00015:
            continue
        falloff = 1.0 - distance / 0.00055
        lower = world.z < nearest.z
        offset = Vector((0.0, 0.0, 0.0))
        if lower:
            offset = Vector((0.0, -0.00015, -0.0016 * falloff))
            keys["MouthClose"].data[index].co = inverse @ (world + Vector((0.0, 0.00005, 0.00045 * falloff)))
        else:
            offset = Vector((0.0, -0.00005, 0.00035 * falloff))
        keys["JawOpen"].data[index].co = inverse @ (world + offset)
        away = Vector((world.x - center.x, 0.0, world.z - center.z))
        if away.length > 1e-8:
            away.normalize()
        keys["MouthFunnel"].data[index].co = inverse @ (
            world + (away * 0.00055 + Vector((0.0, -0.00035, 0.0))) * falloff
        )
        keys["MouthPucker"].data[index].co = inverse @ (
            world + (-away * 0.0004 + Vector((0.0, 0.00015, 0.0))) * falloff
        )
        smile = Vector((0.0, 0.0, 0.0009 * falloff))
        side = "MouthSmileLeft" if world.x < center.x else "MouthSmileRight"
        keys[side].data[index].co = inverse @ (world + smile)
        touched += 1
    print(f"{head_name}: {touched} sommets de lèvres")

    #avatar
    # La mâchoire ouverte descend aussi les dents du bas.
    tooth_keys = _cles(teeth)
    dropped = 0
    inverse = teeth.matrix_world.inverted()
    for index, vertex in enumerate(teeth.data.vertices):
        world = teeth.matrix_world @ vertex.co
        if world.z >= center.z:
            continue
        tooth_keys["JawOpen"].data[index].co = inverse @ (world + Vector((0.0, 0.0, -0.0011)))
        dropped += 1
    print(f"{teeth_name}: {dropped} sommets de dents du bas")


def _teinte_materiau(nom):
    #avatar
    materiau = bpy.data.materials[nom]
    for noeud in materiau.node_tree.nodes:
        if noeud.type == "BSDF_PRINCIPLED":
            return tuple(noeud.inputs["Base Color"].default_value[:3])
    return (1.0, 1.0, 1.0)


def _brancher_couleurs():
    #avatar
    # Les teintes sont sur skin.001, hair.001 et eyes.001.
    # Les maillages exportés ont un gris neutre, et Col est presque blanc.
    teintes = {
        "bonnie_head": _teinte_materiau("skin.001"),
        "hair": _teinte_materiau("hair.001"),
        "eyes": _teinte_materiau("eyes.001"),
    }
    for nom, teinte in teintes.items():
        obj = bpy.data.objects.get(nom)
        if obj is None or not obj.data.color_attributes:
            continue
        calque = obj.data.color_attributes.get("Col") or obj.data.color_attributes[0]
        total = 0.0
        for item in calque.data:
            total += (item.color[0] + item.color[1] + item.color[2]) / 3.0
        moyenne = total / max(len(calque.data), 1)
        for item in calque.data:
            for canal in range(3):
                # Un Col très sombre avale la teinte. On la pose telle quelle.
                if moyenne < 0.35:
                    item.color[canal] = teinte[canal]
                else:
                    item.color[canal] = item.color[canal] * teinte[canal]
        for material in obj.data.materials:
            if material is None or material.node_tree is None:
                continue
            noeuds = material.node_tree.nodes
            shader = next((noeud for noeud in noeuds if noeud.type == "BSDF_PRINCIPLED"), None)
            if shader is None or shader.inputs["Base Color"].is_linked:
                continue
            couleur = shader.inputs["Base Color"].default_value
            couleur[0] = couleur[1] = couleur[2] = 1.0
            attribut = noeuds.new("ShaderNodeVertexColor")
            attribut.layer_name = calque.name
            material.node_tree.links.new(attribut.outputs["Color"], shader.inputs["Base Color"])


def exporter():
    #avatar
    os.makedirs(os.path.dirname(DESTINATION), exist_ok=True)
    _brancher_couleurs()
    _bouche("bonnie_head", "teeth")
    for obj in bpy.data.objects:
        obj.select_set(False)
    for name in GARDES:
        target = bpy.data.objects.get(name)
        if target is not None:
            target.select_set(True)
    bpy.context.view_layer.objects.active = bpy.data.objects["bonnie_head"]
    bpy.ops.export_scene.gltf(
        filepath=DESTINATION,
        export_format="GLB",
        use_selection=True,
        export_morph=True,
        export_animations=False,
    )
    print("GLB", DESTINATION, os.path.getsize(DESTINATION))


if __name__ == "__main__":
    exporter()
