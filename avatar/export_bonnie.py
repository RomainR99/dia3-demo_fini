#avatar
"""Exporte asset/Bonnie2.blend en GLB avec des clés de bouche.

Le .blend n'a ni armature ni shape keys. Ce script en crée six, nommées
comme les blendshapes ARKit qu'Audio2Face renvoie, puis écrit
avatar/view/bonnie.glb pour l'affichage dans le navigateur.

    /Applications/Blender.app/Contents/MacOS/Blender --background \
        asset/Bonnie2.blend --python avatar/export_bonnie.py
"""

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


def _lisse(valeur):
    #avatar
    valeur = min(1.0, max(0.0, valeur))
    return valeur * valeur * (3.0 - 2.0 * valeur)


def _zone_bouche(world, center):
    #avatar
    # La face regarde vers -Y. Z est le haut. Le poids s'estompe jusqu'aux joues.
    dx = world.x - center.x
    devant = center.y - world.y
    bas = center.z - world.z
    if devant < -0.0012:
        return 0.0, 0.0, 0.0
    face = _lisse((devant + 0.0012) / 0.0022)
    cote = 1.0 - _lisse((abs(dx) - 0.0013) / 0.0020)
    if face <= 0.0 or cote <= 0.0:
        return 0.0, 0.0, 0.0
    machoire = 0.0
    if bas > 0.0:
        ouvert = _lisse(min(1.0, bas / 0.00055))
        menton = 1.0 - _lisse(max(0.0, (bas - 0.0020) / 0.0022))
        machoire = ouvert * menton * cote * face
    levre = _lisse(1.0 - min(1.0, abs(bas) / 0.00075)) * cote * face
    return machoire, levre, dx


def _bouche(head_name, teeth_name):
    #avatar
    # Toute la mâchoire descend ensemble. Un anneau de lèvres seul déchirait le visage.
    head = bpy.data.objects[head_name]
    teeth = bpy.data.objects[teeth_name]
    samples = _points(teeth, step=8)
    center = sum(samples, Vector()) / len(samples)
    keys = _cles(head)
    inverse = head.matrix_world.inverted()
    touched = 0
    for index, vertex in enumerate(head.data.vertices):
        world = head.matrix_world @ vertex.co
        machoire, levre, dx = _zone_bouche(world, center)
        if machoire <= 0.02 and levre <= 0.02:
            continue
        # Après l'export, +Y du monde devient le bas de l'écran. Z avançait vers la caméra.
        keys["JawOpen"].data[index].co = inverse @ (
            world + Vector((0.0, 0.00062 * machoire, 0.0))
        )
        if levre > 0.02 and machoire > 0.0:
            keys["MouthClose"].data[index].co = inverse @ (
                world + Vector((0.0, -0.00028 * levre, 0.0))
            )
        signe = 1.0 if dx >= 0.0 else -1.0
        keys["MouthFunnel"].data[index].co = inverse @ (
            world + Vector((signe * 0.00016 * levre, 0.0, 0.0))
        )
        keys["MouthPucker"].data[index].co = inverse @ (
            world + Vector((-signe * 0.00012 * levre, 0.0, 0.0))
        )
        coin = _lisse(max(0.0, (abs(dx) - 0.00045) / 0.0011)) * levre
        if coin > 0.02:
            side = "MouthSmileLeft" if dx < 0.0 else "MouthSmileRight"
            keys[side].data[index].co = inverse @ (
                world + Vector((signe * 0.00008 * coin, -0.0002 * coin, 0.0))
            )
        touched += 1
    print(f"{head_name}: {touched} sommets de mâchoire")

    #avatar
    tooth_keys = _cles(teeth)
    dropped = 0
    inverse = teeth.matrix_world.inverted()
    for index, vertex in enumerate(teeth.data.vertices):
        world = teeth.matrix_world @ vertex.co
        bas = center.z - world.z
        if bas <= 0.00005:
            continue
        poids = _lisse(min(1.0, bas / 0.00035))
        tooth_keys["JawOpen"].data[index].co = inverse @ (
            world + Vector((0.0, 0.0005 * poids, 0.0))
        )
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
