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


def _cloche(valeur, centre, rayon):
    #avatar
    ecart = abs(valeur - centre) / rayon
    if ecart >= 1.0:
        return 0.0
    return _lisse(1.0 - ecart)


def _zone_bouche(world, center):
    #avatar
    # La face regarde vers -Y. Z est le haut. L'ouverture est un ovale au centre des lèvres.
    dx = world.x - center.x
    devant = center.y - world.y
    bas = center.z - world.z
    if devant < -0.0006:
        return 0.0, 0.0, 0.0, 0.0
    face = _lisse((devant + 0.0006) / 0.0016)
    ovale = 1.0 - _lisse((abs(dx) - 0.00025) / 0.00105)
    if face <= 0.0:
        return 0.0, 0.0, 0.0, dx
    masque = face * ovale
    levre_bas = _cloche(bas, 0.0012, 0.00085) * masque
    levre_haut = _cloche(bas, -0.00055, 0.0007) * masque
    menton = 0.0
    if 0.0015 < bas < 0.0048:
        suit = _lisse(min(1.0, (bas - 0.0015) / 0.0008))
        cou = 1.0 - _lisse(max(0.0, (bas - 0.0031) / 0.0014))
        large = 1.0 - _lisse((abs(dx) - 0.00055) / 0.00115)
        menton = suit * cou * face * large
    return levre_bas, levre_haut, menton, dx


def _bouche(head_name, teeth_name):
    #avatar
    # Les lèvres s'écartent au centre. Le menton suit, moins fort, pour ne pas tomber d'un bloc.
    head = bpy.data.objects[head_name]
    teeth = bpy.data.objects[teeth_name]
    samples = _points(teeth, step=8)
    center = sum(samples, Vector()) / len(samples)
    keys = _cles(head)
    inverse = head.matrix_world.inverted()
    touched = 0
    for index, vertex in enumerate(head.data.vertices):
        world = head.matrix_world @ vertex.co
        levre_bas, levre_haut, menton, dx = _zone_bouche(world, center)
        devant = center.y - world.y
        face = _lisse((devant + 0.0006) / 0.0016) if devant > -0.0006 else 0.0
        joue = face * _lisse(max(0.0, (abs(dx) - 0.00045) / 0.00055))
        joue *= 1.0 - _lisse(min(1.0, abs(center.z - world.z) / 0.00115))
        joue *= 1.0 - _lisse(max(0.0, (abs(dx) - 0.00145) / 0.00055))
        if levre_bas <= 0.02 and levre_haut <= 0.02 and menton <= 0.02 and joue <= 0.02:
            continue
        # Après l'export, +Y du monde devient le bas de l'écran. Z avançait vers la caméra.
        descente = 0.0021 * levre_bas + 0.00042 * menton - 0.00095 * levre_haut
        keys["JawOpen"].data[index].co = inverse @ (world + Vector((0.0, descente, 0.0)))
        ferme = -0.00048 * levre_bas + 0.00028 * levre_haut
        if abs(ferme) > 0.00002:
            keys["MouthClose"].data[index].co = inverse @ (world + Vector((0.0, ferme, 0.0)))
        signe = 1.0 if dx >= 0.0 else -1.0
        bord = _lisse(max(0.0, (abs(dx) - 0.00035) / 0.0007)) * (levre_bas + levre_haut)
        if bord > 0.02:
            keys["MouthFunnel"].data[index].co = inverse @ (
                world + Vector((-signe * 0.00022 * bord, 0.00018 * levre_bas - 0.0001 * levre_haut, 0.0))
            )
            keys["MouthPucker"].data[index].co = inverse @ (
                world + Vector((-signe * 0.0003 * bord, -0.00022 * levre_bas + 0.0001 * levre_haut, 0.0))
            )
        if joue > 0.02:
            side = "MouthSmileLeft" if dx < 0.0 else "MouthSmileRight"
            keys[side].data[index].co = inverse @ (
                world + Vector((signe * 0.00016 * joue, -0.0004 * joue, 0.0))
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
            world + Vector((0.0, 0.0017 * poids, 0.0))
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
