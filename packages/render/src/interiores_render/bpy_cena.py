"""Script do Blender: lê ``cena.json`` e gera os renders e o ``.glb``.

Roda **dentro do Blender** (Python embutido): só stdlib + ``bpy``. Nenhuma regra
de negócio aqui (CLAUDE.md §2.4): a geometria já vem pronta do orquestrador.

Uso: ``blender --background --factory-startup --python bpy_cena.py -- cena.json pasta``
"""

import json
import math
import sys
from pathlib import Path

import bpy  # type: ignore[import-not-found]
from mathutils import Vector  # type: ignore[import-not-found]

MM = 0.001


def _cor(hexa):
    h = hexa.lstrip("#")
    srgb = [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    # hexadecimal está em sRGB; o Blender trabalha em linear
    return [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb] + [1.0]


def limpar():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)


def _tom(cor, fator):
    """Mesma cor, mais clara (fator > 1) ou mais escura (< 1), em linear."""
    return [min(c * fator, 1.0) for c in cor[:3]] + [1.0]


def _textura(mat, bsdf, d):
    """Textura procedural a partir da cor (a variação continua valendo):
    madeira, porcelanato, tecido ou pintura. Coordenadas do objeto, em metros."""
    nt, nos, links = mat.node_tree, mat.node_tree.nodes, mat.node_tree.links
    cor = _cor(d["cor"])
    coord = nos.new("ShaderNodeTexCoord").outputs["Object"]
    tipo = d["textura"]
    if tipo == "madeira":
        tabua = nos.new("ShaderNodeTexBrick")  # tábuas com tons alternados
        tabua.offset, tabua.offset_frequency = 0.5, 1
        tabua.inputs["Color1"].default_value = _tom(cor, 1.04)
        tabua.inputs["Color2"].default_value = _tom(cor, 0.92)
        tabua.inputs["Mortar"].default_value = _tom(cor, 0.55)
        tabua.inputs["Scale"].default_value = 1.0
        tabua.inputs["Mortar Size"].default_value = 0.0015 if d.get("tabuas", True) else 0.0
        tabua.inputs["Brick Width"].default_value = 1.2
        tabua.inputs["Row Height"].default_value = 0.19
        links.new(coord, tabua.inputs["Vector"])
        veio = nos.new("ShaderNodeTexWave")  # veios ao longo da tábua
        veio.wave_type, veio.bands_direction = "BANDS", "Y"
        veio.inputs["Scale"].default_value = 45.0
        veio.inputs["Distortion"].default_value = 1.5
        veio.inputs["Detail"].default_value = 2.0
        links.new(coord, veio.inputs["Vector"])
        mistura = nos.new("ShaderNodeMixRGB")
        mistura.blend_type = "MULTIPLY"
        mistura.inputs["Fac"].default_value = 0.12
        links.new(tabua.outputs["Color"], mistura.inputs["Color1"])
        links.new(veio.outputs["Color"], mistura.inputs["Color2"])
        links.new(mistura.outputs["Color"], bsdf.inputs["Base Color"])
        relevo = nos.new("ShaderNodeBump")
        relevo.inputs["Strength"].default_value = 0.05
        links.new(veio.outputs["Fac"], relevo.inputs["Height"])
        links.new(relevo.outputs["Normal"], bsdf.inputs["Normal"])
    elif tipo == "porcelanato":
        placa = nos.new("ShaderNodeTexBrick")  # placas 60×60, rejunte fino
        placa.offset = 0.0
        variacao = nos.new("ShaderNodeTexNoise")
        variacao.inputs["Scale"].default_value = 3.0
        links.new(coord, variacao.inputs["Vector"])
        placa.inputs["Color1"].default_value = _tom(cor, 1.03)
        placa.inputs["Color2"].default_value = _tom(cor, 0.95)
        placa.inputs["Mortar"].default_value = _tom(cor, 0.7)
        placa.inputs["Scale"].default_value = 1.0
        placa.inputs["Mortar Size"].default_value = 0.002
        placa.inputs["Brick Width"].default_value = 0.6
        placa.inputs["Row Height"].default_value = 0.6
        links.new(coord, placa.inputs["Vector"])
        mistura = nos.new("ShaderNodeMixRGB")
        mistura.blend_type = "OVERLAY"
        mistura.inputs["Fac"].default_value = 0.08
        links.new(placa.outputs["Color"], mistura.inputs["Color1"])
        links.new(variacao.outputs["Color"], mistura.inputs["Color2"])
        links.new(mistura.outputs["Color"], bsdf.inputs["Base Color"])
        relevo = nos.new("ShaderNodeBump")
        relevo.inputs["Strength"].default_value = 0.3
        relevo.invert = True
        links.new(placa.outputs["Fac"], relevo.inputs["Height"])
        links.new(relevo.outputs["Normal"], bsdf.inputs["Normal"])
        bsdf.inputs["Roughness"].default_value = 0.22
    elif tipo in ("tecido", "pintura"):
        grao = nos.new("ShaderNodeTexNoise")  # trama (tecido) ou rolo de tinta (pintura)
        grao.inputs["Scale"].default_value = 900.0 if tipo == "tecido" else 120.0
        grao.inputs["Detail"].default_value = 2.0
        links.new(coord, grao.inputs["Vector"])
        relevo = nos.new("ShaderNodeBump")
        relevo.inputs["Strength"].default_value = 0.25 if tipo == "tecido" else 0.04
        links.new(grao.outputs["Fac"], relevo.inputs["Height"])
        links.new(relevo.outputs["Normal"], bsdf.inputs["Normal"])
        if tipo == "tecido":
            bsdf.inputs["Sheen Weight"].default_value = 0.4  # brilho aveludado do tecido
    del nt


def materiais(defs):
    criados = {}
    for nome, d in defs.items():
        mat = bpy.data.materials.new(nome)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Base Color"].default_value = _cor(d["cor"])
        bsdf.inputs["Roughness"].default_value = d.get("rugosidade", 0.6)
        if d.get("textura"):
            _textura(mat, bsdf, d)
        if d.get("emissao"):  # luminária acesa
            bsdf.inputs["Emission Color"].default_value = _cor(d["cor"])
            bsdf.inputs["Emission Strength"].default_value = d["emissao"]
        if d.get("metal"):
            bsdf.inputs["Metallic"].default_value = 1.0
        if d.get("vidro"):
            bsdf.inputs["Transmission Weight"].default_value = 1.0
            bsdf.inputs["Roughness"].default_value = 0.02
            bsdf.inputs["IOR"].default_value = 1.45
        criados[nome] = mat
    return criados


def cor_lisa(mats):
    """Para o .glb: a textura procedural (madeira, tecido...) não sai no glTF e o material
    ficaria branco; depois dos PNG, a cor base volta a ser a cor lisa da variação."""
    for mat in mats.values():
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf is None:
            continue
        for entrada in ("Base Color", "Normal"):
            for ligacao in list(bsdf.inputs[entrada].links):
                mat.node_tree.links.remove(ligacao)


def _objeto(nome, verts, faces, material):
    malha = bpy.data.meshes.new(nome)
    malha.from_pydata(verts, [], faces)
    malha.validate()
    malha.update()
    obj = bpy.data.objects.new(nome, malha)
    obj.data.materials.append(material)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def prisma(p, mats):
    pts = p["contorno"]
    n = len(pts)
    z0, z1 = p["z0"] * MM, p["z1"] * MM
    verts = [(x * MM, y * MM, z0) for x, y in pts] + [(x * MM, y * MM, z1) for x, y in pts]
    faces = [list(range(n - 1, -1, -1)), list(range(n, 2 * n))]
    faces += [[i, (i + 1) % n, n + (i + 1) % n, n + i] for i in range(n)]
    return _objeto(p["nome"], verts, faces, mats[p["material"]])


def caixa(c, mats):
    sx, sy, sz = (v * MM / 2 for v in c["tamanho"])
    verts = [(x, y, z) for z in (-sz, sz) for y in (-sy, sy) for x in (-sx, sx)]
    faces = [[0, 2, 3, 1], [4, 5, 7, 6], [0, 1, 5, 4], [2, 6, 7, 3], [0, 4, 6, 2], [1, 3, 7, 5]]
    obj = _objeto(c["nome"], verts, faces, mats[c["material"]])
    obj.location = [v * MM for v in c["centro"]]
    obj.rotation_euler = (0, 0, math.radians(c["rotacao"]))
    if c.get("chanfro"):  # quinas arredondadas: o que mais tira o "aspecto de caixa"
        mod = obj.modifiers.new("chanfro", "BEVEL")
        mod.width = min(c["chanfro"] * MM, min(sx, sy, sz) * 0.9)
        mod.segments = 3
        mod.limit_method = "ANGLE"
        for poli in obj.data.polygons:
            poli.use_smooth = True
        obj.modifiers.new("normais", "WEIGHTED_NORMAL")
    return obj


def camera(d):
    cam = bpy.data.cameras.new(d["nome"])
    obj = bpy.data.objects.new(d["nome"], cam)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = [v * MM for v in d["posicao"]]
    direcao = Vector([v * MM for v in d["alvo"]]) - obj.location
    obj.rotation_euler = direcao.to_track_quat("-Z", "Y").to_euler()
    if d["tipo"] == "ortografica":
        cam.type = "ORTHO"
        cam.ortho_scale = d["escala"] * MM
    else:
        cam.lens = d.get("lente", 18)
    cam.clip_start = 0.05
    cam.clip_end = 200
    return obj


def luzes(defs):
    for i, d in enumerate(defs):
        if d["tipo"] == "area":
            luz = bpy.data.lights.new(f"luz-{i}", "AREA")
            luz.shape = "RECTANGLE"
            luz.size, luz.size_y = (v * MM for v in d["tamanho"])
            luz.energy = d["energia"]
            obj = bpy.data.objects.new(luz.name, luz)
            obj.location = [v * MM for v in d["posicao"]]
        else:
            luz = bpy.data.lights.new(f"luz-{i}", "SUN")
            luz.energy = d["energia"]
            obj = bpy.data.objects.new(luz.name, luz)
            obj.rotation_euler = Vector(d["direcao"]).to_track_quat("-Z", "Y").to_euler()
        bpy.context.scene.collection.objects.link(obj)
    mundo = bpy.data.worlds.new("mundo")
    mundo.use_nodes = True
    fundo = mundo.node_tree.nodes["Background"]
    fundo.inputs["Color"].default_value = (0.8, 0.85, 0.9, 1)
    fundo.inputs["Strength"].default_value = 0.2
    bpy.context.scene.world = mundo


def faixa_aviso(cam, saida, aviso, objetos):
    """Faixa vermelha com o aviso no rodapé do quadro, presa à câmera (CLAUDE.md §5.1).

    Fica a 6 cm da lente, no tamanho exato do quadro; só aparece no render desta
    câmera e não vai para o .glb.
    """
    dados = cam.data
    proporcao = saida["altura"] / saida["largura"]
    dist = 0.06  # logo depois do clip_start (0,05): nada da cena fica na frente
    largura = dados.ortho_scale if dados.type == "ORTHO" else dist * dados.sensor_width / dados.lens
    altura = largura * proporcao
    faixa_h = altura * 0.07
    y = -altura / 2 + faixa_h / 2

    def emissivo(nome, cor):
        mat = bpy.data.materials.new(nome)
        mat.use_nodes = True
        nos = mat.node_tree.nodes
        nos.clear()
        saida_no = nos.new("ShaderNodeOutputMaterial")
        emissao = nos.new("ShaderNodeEmission")
        emissao.inputs["Color"].default_value = cor
        emissao.inputs["Strength"].default_value = 1.0
        mat.node_tree.links.new(emissao.outputs["Emission"], saida_no.inputs["Surface"])
        return mat

    w2, h2 = largura / 2, faixa_h / 2
    fundo = _objeto(
        f"aviso-fundo-{cam.name}",
        [(-w2, -h2, 0), (w2, -h2, 0), (w2, h2, 0), (-w2, h2, 0)],
        [[0, 1, 2, 3]],
        emissivo("aviso-fundo", (0.55, 0, 0, 1)),
    )
    fundo.parent = cam
    fundo.location = (0, y, -dist)
    curva = bpy.data.curves.new(f"aviso-texto-{cam.name}", "FONT")
    curva.body = aviso
    curva.align_x = "CENTER"
    curva.align_y = "CENTER"
    curva.size = faixa_h * 0.55
    texto = bpy.data.objects.new(curva.name, curva)
    texto.data.materials.append(emissivo("aviso-texto", (1, 1, 1, 1)))
    bpy.context.scene.collection.objects.link(texto)
    texto.parent = cam
    texto.location = (0, y, -dist + 0.0005)
    objetos.append((fundo, []))
    objetos.append((texto, []))
    return [fundo, texto]


def configurar_render(saida):
    cena = bpy.context.scene
    cena.render.engine = "CYCLES"
    cena.cycles.device = "CPU"
    cena.cycles.samples = saida["amostras"]
    cena.cycles.use_denoising = True
    cena.render.resolution_x = saida["largura"]
    cena.render.resolution_y = saida["altura"]
    cena.render.resolution_percentage = 100
    cena.render.image_settings.file_format = "PNG"
    # Standard: a cor do hexadecimal sai como foi escolhida (AgX dessaturava os claros)
    cena.view_settings.view_transform = "Standard"


def main():
    args = sys.argv[sys.argv.index("--") + 1 :]
    cena_json, pasta = Path(args[0]), Path(args[1])
    cena = json.loads(cena_json.read_text(encoding="utf-8"))
    limpar()
    mats = materiais(cena["materiais"])
    objetos = [(prisma(p, mats), p.get("oculto_em", [])) for p in cena["prismas"]]
    objetos += [(caixa(c, mats), c.get("oculto_em", [])) for c in cena["caixas"]]
    for obj, oculto_em in objetos:
        if oculto_em:  # vai para o .glb (extras): o visor 3D esconde o teto na vista de cima
            obj["oculto_em"] = ",".join(oculto_em)
    for (obj, _), c in zip(objetos, cena["prismas"] + cena["caixas"], strict=True):
        for chave, valor in c.get("extras", {}).items():  # móvel e parte: o visor pinta
            obj[chave] = valor
    cameras = [camera(c) for c in cena["cameras"]]
    luzes(cena["luzes"])
    configurar_render(cena["saida"])
    avisos = {}
    if cena.get("aviso"):
        for cam in cameras:
            avisos[cam.name] = faixa_aviso(cam, cena["saida"], cena["aviso"], objetos)

    for i, cam in enumerate(cameras, 1):
        # o orquestrador lê esta linha para a barra de progresso ("imagem 1 de 2")
        print(f"PROGRESSO imagem {i} {len(cameras)} {cam.name}", flush=True)  # noqa: T201
        bpy.context.scene.camera = cam
        for obj, oculto_em in objetos:
            obj.hide_render = cam.name in oculto_em
        for dono, faixa in avisos.items():
            for obj in faixa:
                obj.hide_render = dono != cam.name
        bpy.context.scene.render.filepath = str(pasta / f"render-{cam.name}.png")
        bpy.ops.render.render(write_still=True)

    for faixa in avisos.values():  # o aviso é do PNG, não do modelo 3D
        for obj in faixa:
            bpy.data.objects.remove(obj, do_unlink=True)
    for obj in bpy.context.scene.objects:
        obj.hide_render = False
    cor_lisa(mats)
    bpy.ops.export_scene.gltf(
        filepath=str(pasta / f"{cena.get('modelo') or cena['comodo']}.glb"),
        export_format="GLB",
        export_cameras=False,
        export_lights=False,
        export_apply=True,  # leva o chanfro (modificador) para o .glb
        export_extras=True,  # leva ``oculto_em`` (teto, luminárias) para o visor 3D
    )


if __name__ == "__main__":
    main()
