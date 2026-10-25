# -*- coding: utf-8 -*-
import io
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

AQUI = os.path.dirname(os.path.abspath(__file__))


def pasta_app(aqui):
    for c in (os.path.join(aqui, "..", "app"), os.path.join(aqui, "..")):
        if os.path.exists(os.path.join(c, "radai_watcher.py")):
            return os.path.abspath(c)
    return os.path.abspath(os.path.join(aqui, "..", "app"))


APP = pasta_app(AQUI)
sys.path.insert(0, APP)

import tempfile as _tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _cleanup
import _componentes
_cleanup.adotar_prefixo('radai_ac_nidus')
os.environ["RADAI_CALIB_DIR"] = _tempfile.mkdtemp(prefix="radai_ac_nidus_")


VERBOSO = "-v" in sys.argv
_RES = []


def checar(nome, ok, detalhe=""):
    _RES.append((nome, bool(ok), detalhe))
    if VERBOSO or not ok:
        print("  %s  %s%s" % ("OK   " if ok else "FALHA", nome,
                              ("  [%s]" % (detalhe,)) if detalhe else ""))
    return bool(ok)


def secao(t):
    print(u"\n── %s %s" % (t, u"─" * max(0, 58 - len(t))))


def fonte(nome):
    return io.open(_componentes.fonte("app/" + nome), encoding="utf-8",
                   errors="replace").read()


def sem_prosa(texto):
    import ast
    t = "\n".join(l for l in texto.splitlines()
                  if not l.lstrip().startswith("#")
                  and not l.lstrip().startswith("//"))
    try:
        arv = ast.parse(t)
    except Exception:
        return re.sub(r"<!--.*?-->", " ", t, flags=re.S)
    fora = []
    for no in ast.walk(arv):
        if isinstance(no, (ast.Module, ast.ClassDef, ast.FunctionDef,
                           ast.AsyncFunctionDef)):
            c = no.body[0] if no.body else None
            if (isinstance(c, ast.Expr) and isinstance(c.value, ast.Constant)
                    and isinstance(c.value.value, str)):
                fora.append((c.lineno, getattr(c, "end_lineno", c.lineno)))
    linhas = t.splitlines()
    for a, b in fora:
        for k in range(a - 1, min(b, len(linhas))):
            linhas[k] = ""
    return re.sub(r"<!--.*?-->", " ", "\n".join(linhas), flags=re.S)


def cabeca(nz=96, ny=128, nx=128, esp=1.5, alvo_mm=(18.0, -12.0, 6.0)):
    import numpy as np
    import SimpleITK as sitk
    z, y, x = np.mgrid[0:nz, 0:ny, 0:nx].astype(np.float32)
    cz, cy, cx = nz / 2.0, ny / 2.0, nx / 2.0
    org = (-cx * esp, -cy * esp, -cz * esp)
    r = np.sqrt(((z - cz) / (nz * 0.44)) ** 2 + ((y - cy) / (ny * 0.40)) ** 2
                + ((x - cx) / (nx * 0.38)) ** 2)
    v = np.where(r < 1, 35.0, -1000.0).astype(np.float32)
    v[(r >= 0.93) & (r < 1)] = 900.0
    a = np.array(alvo_mm)
    d = np.sqrt((org[0] + x * esp - a[0]) ** 2 + (org[1] + y * esp - a[1]) ** 2
                + (org[2] + z * esp - a[2]) ** 2)
    alvo = d < 8.0
    v[alvo] = 420.0
    img = sitk.GetImageFromArray(v)
    img.SetSpacing((esp, esp, esp))
    img.SetOrigin(org)
    return img, a, alvo


def circulo(col, lin, raio, n=40):
    import math
    return [(col + raio * math.cos(2 * math.pi * i / n),
             lin + raio * math.sin(2 * math.pi * i / n)) for i in range(n)]


def onde(img, alvo_mm, lao, cra, lado):
    import numpy as np
    import radai_nidus as N
    t = N._transformada(img, lao, cra)
    _ref, diag, passo, passo_fundo = N._grade(img, lado)
    c = t.GetCenter()
    org = (c[0] - diag / 2.0, c[1] - diag / 2.0, c[2] - diag / 2.0)
    p = np.array(t.TransformPoint([float(v) for v in alvo_mm]))
    gx = (p[0] - org[0]) / passo
    gz = (p[2] - org[2]) / passo
    return gx + 0.5, lado - 0.5 - gz


def _eixos_antigos(lao, cra):
    import math
    import SimpleITK as sitk
    t = sitk.Euler3DTransform()
    t.SetRotation(math.radians(cra), 0.0, math.radians(lao))
    m = t.GetMatrix()
    return dict((n, (m[k], -m[6 + k], m[3 + k])) for n, k in
                ((u"L", 0), (u"P", 1), (u"S", 2)))


def _transformada_antiga(img, lao, cra):
    import math
    import SimpleITK as sitk
    t = sitk.Euler3DTransform()
    t.SetCenter(img.TransformContinuousIndexToPhysicalPoint(
        [(s - 1) / 2.0 for s in img.GetSize()]))
    t.SetRotation(math.radians(cra), 0.0, math.radians(lao))
    return t


INCIDENCIAS_ANTIGAS = ((u"AP", 0.0, 0.0), (u"Perfil D", 90.0, 0.0),
                       (u"Perfil E", -90.0, 0.0), (u"Oblíqua ant. D", 45.0, 0.0),
                       (u"Oblíqua ant. E", -45.0, 0.0), (u"Towne", 0.0, -30.0),
                       (u"Caldwell", 0.0, 15.0), (u"Submento-vértex", 0.0, 90.0))


def _tres_pontos(n=81, k=18):
    import math
    import numpy as np
    import SimpleITK as sitk
    c = n // 2
    a = np.full((n, n, n), -1000.0, np.float32)
    dz, dy = int(round(k * math.sin(math.radians(30)))), int(round(k * math.cos(math.radians(30))))
    pts = {u"A": (c + dz, c - dy, c), u"B": (c - dz, c + dy, c),
           u"C": (c, c, c + k)}
    for z, y, x in pts.values():
        a[z - 1:z + 2, y - 1:y + 2, x - 1:x + 2] = 2000.0
    img = sitk.GetImageFromArray(a)
    img.SetSpacing((1.0, 1.0, 1.0))
    img.SetOrigin((-float(c), -float(c), -float(c)))
    return img


def _manchas(plano, lim=1000.0):
    import numpy as np
    from scipy import ndimage
    _r, n = ndimage.label(np.asarray(plano) >= lim)
    return int(n)


def _marcas_na_tela(N, transformada=None):
    import math
    import numpy as np
    import SimpleITK as sitk
    n, c = 81, 40
    esc = {"min": -1000.0, "max": 2000.0, "hu": True}
    pos = {u"E": (1.0, 0.0, 0.0), u"A": (0.0, -1.0, 0.0), u"S": (0.0, 0.0, 1.0)}
    idx = {u"E": (c, c, c + 18), u"A": (c, c - 18, c), u"S": (c + 18, c, c)}
    vols = {}
    for m, (z, y, x) in idx.items():
        a = np.full((n, n, n), -1000, np.float32)
        a[z - 1:z + 2, y - 1:y + 2, x - 1:x + 2] = 2000
        im = sitk.GetImageFromArray(a)
        im.SetOrigin((-c, -c, -c))
        vols[m] = im
    guarda = getattr(N, "_transformada", None)
    linhas = []
    try:
        if transformada is not None:
            N._transformada = transformada
        for nome, lao, cra in tuple(N.INCIDENCIAS) + ((u"LAO 45 + CRA 30", 45.0, 30.0),
                                                     (u"LAO 90 + CRA 30", 90.0, 30.0)):
            for m in (u"E", u"A", u"S"):
                plano, _ = N.projetar(vols[m], lao, cra, "mip", "osso", lado=128,
                                      escala=esc)
                ys, xs = np.nonzero(np.asarray(plano) >= 1000)
                if not len(xs):
                    linhas.append((nome, m, None))
                    continue
                h = (float(xs.mean()) - 64.0, -(float(ys.mean()) - 64.0))
                al, b = math.radians(lao), math.radians(cra)
                r = (math.cos(al), math.sin(al), 0.0)
                u = (-math.sin(al) * math.sin(b), math.cos(al) * math.sin(b), math.cos(b))
                d = (sum(x * y for x, y in zip(r, pos[m])), sum(x * y for x, y in zip(u, pos[m])))
                lh =(0 if abs(h[0]) < 2.5 else (1 if h[0] > 0 else -1),
                      0 if abs(h[1]) < 2.5 else (1 if h[1] > 0 else -1))
                ld = (0 if abs(d[0]) < 0.14 else (1 if d[0] > 0 else -1),
                      0 if abs(d[1]) < 0.14 else (1 if d[1] > 0 else -1))
                linhas.append((nome, m, lh == ld))
    finally:
        if transformada is not None:
            N._transformada = guarda
    return linhas


def teste_a_convencao_e_a_do_arco_em_c():
    secao(u"a convenção dos ângulos é a do arco em C (DICOM): LAO à esquerda, "
          u"Towne CRA 30, Caldwell CAU 15")
    import math
    import radai_nidus as N
    checar(u"a matriz mora numa função só (matriz_da_incidencia)",
           callable(getattr(N, "matriz_da_incidencia", None)))
    if not callable(getattr(N, "matriz_da_incidencia", None)):
        return
    for lao, cra in ((0, 0), (90, 0), (-45, 20), (30, -60), (170, 85)):
        r, v, u = N.matriz_da_incidencia(lao, cra)
        prod = [sum(a * b for a, b in zip(p, q)) for p in (r, v, u) for q in (r, v, u)]
        orto = all(abs(x - (1.0 if i % 4 == 0 else 0.0)) < 1e-12
                   for i, x in enumerate(prod))
        vxu = (v[1] * u[2] - v[2] * u[1], v[2] * u[0] - v[0] * u[2],
               v[0] * u[1] - v[1] * u[0])
        checar(u"LAO %d / CRA %d: ortonormal e sem espelho (v × u = r)" % (lao, cra),
               orto and all(abs(a - b) < 1e-12 for a, b in zip(vxu, r)))
    e = N.eixos_da_incidencia(90.0, 0.0)
    checar(u"LAO 90 põe o detector à esquerda: o eixo L vem para quem olha",
           e[u"L"][2] < -0.99, str(e[u"L"]))
    checar(u"  isca: a convenção de antes põe o L no fundo da tela",
           _eixos_antigos(90.0, 0.0)[u"L"][2] > 0.99)
    e = N.eixos_da_incidencia(90.0, 30.0)
    checar(u"LAO 90 + CRA 30: o detector sobe para a cabeça (S = 0,5)",
           abs(e[u"S"][2] + 0.5) < 1e-6, str(e[u"S"]))
    checar(u"  isca: a de antes deixa o detector na horizontal (S = 0)",
           abs(_eixos_antigos(90.0, 30.0)[u"S"][2]) < 1e-6)
    inc = dict((n, (a, b)) for n, a, b in N.INCIDENCIAS)
    checar(u"as incidências na convenção nova",
           inc == {u"AP": (0.0, 0.0), u"Perfil D": (-90.0, 0.0),
                   u"Perfil E": (90.0, 0.0), u"Oblíqua ant. D": (-45.0, 0.0),
                   u"Oblíqua ant. E": (45.0, 0.0), u"Towne": (0.0, 30.0),
                   u"Caldwell": (0.0, -15.0), u"Submento-vértex": (0.0, 90.0)},
           str(inc))
    img = _tres_pontos()
    esc = {"min": -1000.0, "max": 2000.0, "hu": True}
    tw = N.projetar(img, inc[u"Towne"][0], inc[u"Towne"][1], "mip", "osso",
                    lado=128, escala=esc)[0]
    cw = N.projetar(img, inc[u"Caldwell"][0], inc[u"Caldwell"][1], "mip", "osso",
                    lado=128, escala=esc)[0]
    checar(u"Towne: o anterossuperior e o posteroinferior caem no mesmo ponto",
           _manchas(tw) == 2, u"%d manchas" % _manchas(tw))
    checar(u"  e na Caldwell eles se separam", _manchas(cw) == 3,
           u"%d manchas" % _manchas(cw))
    guarda = N._transformada
    try:
        N._transformada = _transformada_antiga
        tw0 = N.projetar(img, 0.0, -30.0, "mip", "osso", lado=128, escala=esc)[0]
    finally:
        N._transformada = guarda
    checar(u"  isca: a Towne de antes (CRA -30, a outra rotação) não superpõe os dois",
           _manchas(tw0) == 3, u"%d manchas" % _manchas(tw0))
    linhas = _marcas_na_tela(N)
    nao = [(a, b) for a, b, ok in linhas if ok is False]
    checar(u"cada marca (E, A, S) cai na tela onde o arco em C a põe, nas 10 "
           u"incidências (%d linhas)" % len(linhas), not nao and len(linhas) == 30,
           str(nao[:4]))
    guarda_inc = N.INCIDENCIAS
    try:
        N.INCIDENCIAS = INCIDENCIAS_ANTIGAS
        isca = _marcas_na_tela(N, _transformada_antiga)
    finally:
        N.INCIDENCIAS = guarda_inc
    checar(u"  isca: a convenção de antes reprova (%d de 30 linhas NÃO)"
           % sum(1 for x in isca if x[2] is False),
           sum(1 for x in isca if x[2] is False) >= 8)


def teste_o_js_da_convencao_e_o_python():
    secao(u"o JavaScript da convenção é o Python, em 50 ângulos")
    import json
    import random
    import subprocess
    import radai_nidus as N
    js = getattr(N, "JS_CONVENCAO", u"")
    checar(u"a convenção do JS mora no radai_nidus (JS_CONVENCAO)",
           u"function radaiIncidencia(" in js)
    if _sem_node() or not js:
        return
    rnd = random.Random(20261025)
    angulos = [(rnd.uniform(-180, 180), rnd.uniform(-90, 90)) for _ in range(50)]

    def rodar(fonte):
        p = os.path.join(_cleanup.temporaria("radai_ac_nidus_conv_"), "c.js")
        io.open(p, "w", encoding="utf-8").write(
            fonte + u"\nvar A=%s; console.log(JSON.stringify(A.map(function(x){ "
            u"var b=radaiIncidencia(x[0],x[1]); return [b.r,b.v,b.u,b.d] })));"
            % json.dumps(angulos))
        r = subprocess.run([_node(), p], stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, timeout=60)
        return json.loads(r.stdout.decode("utf-8").strip().splitlines()[-1])

    def pior(saida):
        p = 0.0
        for (lao, cra), (r, v, u, d) in zip(angulos, saida):
            mr, mv, mu = N.matriz_da_incidencia(lao, cra)
            for a, b in ((r, mr), (v, mv), (u, mu), (d, [-x for x in mv])):
                p = max(p, max(abs(x - y) for x, y in zip(a, b)))
        return p
    d = pior(rodar(js))
    checar(u"r, v, u e d iguais nos 50 ângulos (erro %.1e)" % d, d < 1e-9)
    isca = js.replace(u"ca*sb, cb]", u"ca*sb, -cb]")
    checar(u"  isca: um sinal trocado no JS é acusado",
           isca != js and pior(rodar(isca)) > 0.1)


def _serie_obliqua(n=(56, 64, 72), esp=(0.8, 0.9, 1.1), giros=(18.0, 11.0)):
    import math
    import numpy as np
    import SimpleITK as sitk
    a = np.full(n, -1000.0, np.float32)
    img = sitk.GetImageFromArray(a)
    img.SetSpacing(tuple(float(e) for e in esp[::-1]))
    gz, gx = (math.radians(g) for g in giros)
    rz = np.array([[math.cos(gz), -math.sin(gz), 0], [math.sin(gz), math.cos(gz), 0],
                   [0, 0, 1]])
    rx = np.array([[1, 0, 0], [0, math.cos(gx), -math.sin(gx)],
                   [0, math.sin(gx), math.cos(gx)]])
    img.SetDirection(tuple(float(x) for x in rz.dot(rx).ravel()))
    img.SetOrigin((-31.0, -27.0, -22.0))
    return img


def teste_a_pegada_da_caixa_numa_serie_obliqua():
    secao(u"a pegada da caixa na projeção, numa série oblíqua (a caixa é do array, "
          u"e não do LPS)")
    import numpy as np
    import SimpleITK as sitk
    import radai_nidus as N
    if not callable(getattr(N, "geometria_da_serie", None)):
        checar(u"radai_nidus.geometria_da_serie existe", False)
        return
    img = _serie_obliqua()
    a = sitk.GetArrayFromImage(img)
    vox = (40, 21, 50)
    a[vox[0] - 1:vox[0] + 2, vox[1] - 1:vox[1] + 2, vox[2] - 1:vox[2] + 2] = 2000.0
    img2 = sitk.GetImageFromArray(a)
    img2.CopyInformation(img)
    serie = N.abrir(img2, "CT")
    g = N.geometria_da_serie(serie)
    P = np.array(g["para_caixa"], dtype=float).reshape(4, 4)
    Q = np.array(g["da_caixa"], dtype=float).reshape(4, 4)
    checar(u"a ida e a volta (LPS -> fração da caixa -> LPS) se desfazem",
           np.allclose(P.dot(Q), np.eye(4), atol=1e-9))
    ponto = np.array(list(img2.TransformIndexToPhysicalPoint(
        (vox[2], vox[1], vox[0]))) + [1.0])
    f = P.dot(ponto)[:3]
    caixa = (f[0] - 0.05, f[0], f[1] - 0.05, f[1], f[2] - 0.05, f[2])
    cx = N.caixa_de_texto(u",".join(u"%.6f" % v for v in caixa))
    sub = serie.img_na_caixa(cx, "mip")
    checar(u"a fração do voxel cai na caixa que o recorte de verdade usa",
           float(sitk.GetArrayViewFromImage(sub).max()) >= 1999.0)
    for lao, cra in ((0.0, 0.0), (-35.0, 20.0), (60.0, -25.0)):
        lado = 256
        plano, _ = N.projetar(img2, lao, cra, "mip", "osso", lado=lado,
                              escala={"min": -1000.0, "max": 2000.0, "hu": True})
        ys, xs = np.nonzero(np.asarray(plano) >= 1000.0)
        alvo = (float(xs.mean()) + 0.5, float(ys.mean()) + 0.5)
        pts = N.pegada_da_caixa(serie, caixa, lao, cra, lado)
        canto = max(pts, key=lambda p: -((p[0] - alvo[0]) ** 2 + (p[1] - alvo[1]) ** 2))
        dist = ((canto[0] - alvo[0]) ** 2 + (canto[1] - alvo[1]) ** 2) ** 0.5
        checar(u"LAO %d / CRA %d: um canto da pegada cai no voxel projetado "
               u"(%.2f px)" % (lao, cra, dist), dist < 1.2, str((canto, alvo)))
    guarda = N.geometria_da_serie
    try:
        def lps_cru(s):
            d = guarda(s)
            P2 = np.eye(4)
            Q2 = np.eye(4)
            d = dict(d, para_caixa=list(P2.ravel()), da_caixa=list(Q2.ravel()))
            return d
        N.geometria_da_serie = lps_cru
        pts = N.pegada_da_caixa(serie, caixa, 0.0, 0.0, 256)
    finally:
        N.geometria_da_serie = guarda
    plano, _ = N.projetar(img2, 0.0, 0.0, "mip", "osso", lado=256,
                          escala={"min": -1000.0, "max": 2000.0, "hu": True})
    ys, xs = np.nonzero(np.asarray(plano) >= 1000.0)
    alvo = (float(xs.mean()) + 0.5, float(ys.mean()) + 0.5)
    dist = min(((p[0] - alvo[0]) ** 2 + (p[1] - alvo[1]) ** 2) ** 0.5 for p in pts)
    checar(u"  isca: a caixa lida como LPS (sem a matriz da série) erra a pegada",
           dist > 3.0, u"%.1f px" % dist)


def _vaso_sintetico(diam_mm=1.5, esp=(0.5, 0.45, 0.45), forma=(80, 96, 96)):
    import numpy as np
    import SimpleITK as sitk
    nz, ny, nx = forma
    z, y, x = np.mgrid[0:nz, 0:ny, 0:nx].astype(np.float32)
    zm, ym, xm = z * esp[0], y * esp[1], x * esp[2]
    c = np.array([nz * esp[0] / 2, ny * esp[1] / 2, nx * esp[2] / 2])
    dirv = np.array([0.8, 0.45, 0.4])
    dirv /= np.linalg.norm(dirv)
    p = np.stack([zm - c[0], ym - c[1], xm - c[2]], -1)
    t = p.dot(dirv)
    dist = np.linalg.norm(p - t[..., None] * dirv, axis=-1)
    v = np.full(forma, 30.0, np.float32)
    v[dist <= diam_mm / 2.0] = 420.0
    v[:, :, :6] = -1000.0
    img = sitk.GetImageFromArray(v)
    img.SetSpacing(tuple(float(e) for e in esp[::-1]))
    return img, dist <= diam_mm / 2.0


def teste_a_malha_da_caixa():
    secao(u"o 3D da caixa: vaso por limiar com passo de no máximo 1 mm, osso só "
          u"da segmentação, teto de 80 mil")
    import numpy as np
    import radai_nidus as N
    import radai_recon3d as R
    if not callable(getattr(N, "malha_da_caixa", None)):
        checar(u"radai_nidus.malha_da_caixa existe", False)
        return
    tetos = dict(N.TETOS_DA_MALHA)
    checar(u"os tetos das três malhas somam o teto do visor (%d)"
           % R.TETO_TRIANGULOS, sum(tetos.values()) <= R.TETO_TRIANGULOS
           and set(tetos) == {u"vaso", u"osso", u"pele"}, str(tetos))
    checar(u"a interseção nunca vira malha (só vaso, osso e pele)",
           tuple(N.QUAIS_DA_MALHA) == (u"vaso", u"osso", u"pele"))
    img, mvaso = _vaso_sintetico()
    serie = N.abrir(img, "CT")
    caixa = (0.1, 0.9, 0.1, 0.9, 0.1, 0.9)
    lps, faces, info = N.malha_da_caixa(serie, caixa, u"vaso")
    checar(u"o vaso de 1,5 mm sai em malha", len(faces) > 50, str(info))
    checar(u"  com passo de no máximo 1 mm", 0 < info.get("passo_mm", 9) <= 1.0,
           str(info))
    if len(lps):
        ext = float(np.linalg.norm(lps.max(axis=0) - lps.min(axis=0)))
        checar(u"  e inteiro, e não em pedaços (%.0f mm de extensão)" % ext,
               ext > 25.0, u"%.1f mm" % ext)
    checar(u"  e sem o osso separado, a malha diz", info.get("motivo")
           == N.OSSO_NAO_SEPARADO, str(info.get("motivo")))
    lps0, f0, i0 = R.malha_de_rotulo(
        np.asarray(mvaso), (0.5, 0.45, 0.45), teto_triangulos=50000)
    checar(u"  isca: com a suavização e o passo do rótulo, o ramo fino some "
           u"(%d triângulos)" % len(f0), len(f0) < len(faces) * 0.5,
           str(i0))
    lo, fo, io_ = N.malha_da_caixa(serie, caixa, u"osso")
    checar(u"sem a segmentação, nenhum osso pela densidade", len(fo) == 0
           and io_.get("motivo") == N.OSSO_NAO_SEPARADO, str(io_))
    import SimpleITK as sitk
    osso = np.zeros(serie.forma_do_array, bool)
    osso[20:30, 30:60, 30:60] = True
    serie.tirar_osso(osso, {u"fonte": u"FULL"})
    lo, fo, io_ = N.malha_da_caixa(serie, caixa, u"osso")
    checar(u"com a segmentação, o osso é a máscara dela", len(fo) > 10
           and not io_.get("motivo"), str(io_))
    lp, fp, ip = N.malha_da_caixa(serie, caixa, u"pele")
    checar(u"na TC a pele sai por -400 HU", len(fp) > 10, str(ip))
    checar(u"  e cada malha respeita o teto dela",
           len(faces) <= tetos[u"vaso"] * 1.15 and len(fo) <= tetos[u"osso"] * 1.15
           and len(fp) <= tetos[u"pele"] * 1.15)
    rm = N.abrir(img, "MR")
    lp, fp, ip = N.malha_da_caixa(rm, caixa, u"pele")
    checar(u"na RM não há pele (o sinal não é HU)", len(fp) == 0, str(ip))
    lv, fv, iv = N.malha_da_caixa(rm, caixa, u"vaso")
    checar(u"  e o vaso sai pelo limiar relativo da série", len(fv) > 50, str(iv))
    try:
        N.malha_da_caixa(serie, None, u"vaso")
        recusou = False
    except N.MalhaRecusada as e:
        recusou = str(e) == N.SEM_CAIXA_PARA_O_3D
    checar(u"sem caixa, o 3D diz que precisa dela (e não monta o volume inteiro)",
           recusou)
    try:
        N.malha_da_caixa(serie, caixa, u"intersecao")
        aceitou = True
    except (KeyError, ValueError):
        aceitou = False
    checar(u"e pedir a malha da interseção é recusado", not aceitou)


def teste_a_geometria_fecha():
    secao(u"a geometria fecha: o alvo cai onde os dois tubos se cruzam")
    import numpy as np
    import radai_nidus as N

    LADO = 128
    img, alvo, mascara = cabeca()
    n_alvo = int(mascara.sum())
    checar(u"o fantoma tem alvo", n_alvo > 100, str(n_alvo))

    tubos = []
    for lao, cra in ((0.0, 0.0), (60.0, 0.0), (0.0, 30.0)):
        col, lin = onde(img, alvo, lao, cra, LADO)
        m = N.tubo(img, circulo(col, lin, 7), lao, cra, lado=LADO)
        pega = int((m & mascara).sum())
        checar(u"o tubo LAO %.0f / CRA %.0f contem o alvo inteiro" % (lao, cra),
               pega == n_alvo, u"%d de %d" % (pega, n_alvo))
        checar(u"e ele nao e o volume inteiro",
               m.sum() < mascara.size * 0.5,
               u"%.1f%%" % (100.0 * m.sum() / mascara.size))
        tubos.append(m)

    inter = N.intersecao(tubos[0], tubos[1])
    pega = int((inter & mascara).sum())
    checar(u"a intersecao contem o alvo inteiro", pega == n_alvo,
           u"%d de %d" % (pega, n_alvo))
    for i, m in enumerate(tubos[:2]):
        parte = 100.0 * inter.sum() / max(1, m.sum())
        checar(u"e e MENOR que o tubo %d (%.0f%%)" % (i + 1, parte),
               parte < 60.0, u"%.1f%%" % parte)

    igual = N.intersecao(tubos[0], tubos[0])
    checar(u"dois tubos do mesmo angulo dao o proprio tubo",
           int(igual.sum()) == int(tubos[0].sum()))

    vazio = N.tubo(img, [(10, 10), (20, 20)], 0, 0, lado=LADO)
    checar(u"poligono de 2 pontos devolve tubo vazio, sem levantar",
           not vazio.any())
    checar(u"e lista vazia tambem",
           not N.tubo(img, [], 0, 0, lado=LADO).any())


def teste_a_projecao_e_o_extremo_do_raio():
    secao(u"MIP e MinIP sao o extremo do raio, e nao a fatia do meio")
    import numpy as np
    import radai_nidus as N
    img, alvo, mascara = cabeca()

    mip, info = N.projetar(img, 0, 0, "mip", lado=96)
    minip, _ = N.projetar(img, 0, 0, "minip", lado=96)
    dentro = (mip > -900) & (minip < 3000)
    checar(u"dentro do volume, o MIP e maior ou igual ao MinIP",
           bool((mip[dentro] >= minip[dentro]).all()),
           u"%d voxels comparados" % int(dentro.sum()))
    checar(u"e o preenchimento nunca vence a projecao",
           float(mip.max()) < 3000.0 and float(minip.min()) > -1500.0,
           u"mip max %.0f · minip min %.0f" % (mip.max(), minip.min()))
    checar(u"o alvo denso aparece no MIP", float(mip.max()) >= 400.0,
           u"%.0f" % float(mip.max()))
    checar(u"e o ar aparece no MinIP", float(minip.min()) <= -900.0,
           u"%.0f" % float(minip.min()))
    checar(u"a projecao e quadrada", mip.shape[0] == mip.shape[1] == 96,
           str(mip.shape))
    checar(u"e a info traz a janela usada",
           info["centro"] and info["largura"], str(info)[:70])

    fina, _ = N.projetar(img, 0, 0, "mip", lado=96, laje_mm=6.0)
    checar(u"a laje fina projeta menos que o volume inteiro",
           float(fina.sum()) < float(mip.sum()))

    reto, _ = N.projetar(img, 0, 0, "mip", lado=96)
    obl, _ = N.projetar(img, 45, 0, "mip", lado=96)
    dentro_reto = int((reto > -900).sum())
    dentro_obl = int((obl > -900).sum())
    checar(u"a obliqua nao perde anatomia (a grade e a diagonal)",
           dentro_obl > dentro_reto * 0.7,
           u"%d contra %d" % (dentro_obl, dentro_reto))


def teste_as_linhas_sao_finas():
    secao(u"as linhas sao finas, e nunca regiao preenchida")
    import numpy as np
    import radai_nidus as N
    img, alvo, mascara = cabeca()
    col, lin = onde(img, alvo, 0, 0, 128)
    m = N.tubo(img, circulo(col, lin, 7), 0, 0, lado=128)
    z = int(np.argwhere(mascara).mean(axis=0)[0])

    segs = N.contorno_do_tubo(m, 0, z)
    checar(u"ha segmentos no corte do alvo", len(segs) > 4, str(len(segs)))
    checar(u"cada um e um par de pontos",
           all(len(s) == 2 and len(s[0]) == 2 for s in segs))
    area = int(m[z].sum())
    checar(u"e sao a FRONTEIRA, e nao a area (%d contra %d)" % (len(segs), area),
           len(segs) < area, u"%d segmentos, %d voxels" % (len(segs), area))

    checar(u"corte sem tubo devolve lista vazia",
           N.contorno_do_tubo(m, 0, 0) == [])
    for eixo in (0, 1, 2):
        try:
            N.contorno_do_tubo(m, eixo, 1)
            checar(u"o eixo %d responde" % eixo, True)
        except Exception as e:
            checar(u"o eixo %d responde" % eixo, False, str(e)[:50])


def teste_a_fronteira_nao_se_cruza():
    secao(u"a fronteira: nao exporta, e nao vira numero")
    import radai_nidus as N

    nomes = [n for n in dir(N)
             if ("volume" in n.lower() or "cm3" in n.lower())
             and n != "SEM_VOLUME"]
    checar(u"o modulo NAO tem funcao de volume", not nomes, ", ".join(nomes))

    codigo = sem_prosa(fonte("radai_nidus.py"))
    corpo = codigo[codigo.index("def ") if "def " in codigo else 0:]
    for proibido in (".sum() *", "volume_de", "def volume", "* espac",
                     "prod(espac", "np.prod"):
        checar(u"o codigo nao calcula `%s`" % proibido, proibido not in corpo)

    tela = sem_prosa(fonte("radai_nidus_screen.py"))
    for proibido in ("cm3", "cm&sup3;", "cm³", "toBlob", "toDataURL",
                     "download", "attachment", "content-disposition",
                     "createObjectURL"):
        checar(u"a tela nao exibe nem exporta `%s`" % proibido,
               proibido.lower() not in tela.lower())
    import radai_nidus as _N
    checar(u"e a tela DIZ que nao e volume de tratamento",
           u"volume de tratamento" in _N.SEM_VOLUME
           and u"radai_nidus.SEM_VOLUME" in fonte("radai_nidus_screen.py"))

    for proibido in ("readpixels", "capturestream", "mediarecorder"):
        checar(u"a tela nao le nem grava o quadro do 3D (`%s`)" % proibido,
               proibido not in tela.lower())
    checar(u"o único canvas é o do 3D da caixa (WebGL)",
           tela.lower().count("<canvas") == 1 and 'id="nd_gl"' in tela)
    contextos = re.findall(r"getContext\(\s*'([^']+)'", tela)
    checar(u"e ele só pede contexto WebGL, nunca o 2D que exporta pixel",
           contextos and set(contextos) <= {u"webgl", u"experimental-webgl"},
           str(contextos))
    checar(u"e o desenho continua em SVG", "<svg" in tela.lower())

    bruto = fonte("radai_nidus_screen.py")
    checar(u"a trava do volume esta declarada", bool(N.SEM_VOLUME))
    import radai_nidus_screen as _S
    checar(u"e a tela a mostra", N.SEM_VOLUME in _S.pagina())
    checar(u"a limitacao clinica esta declarada", bool(N.LIMITACAO_CLINICA))
    checar(u"e ela nomeia o brilho igual",
           u"mesmo brilho" in N.LIMITACAO_CLINICA,
           u"'nao mostra fluxo' e verdadeiro e abstrato; o brilho o leitor "
           u"confere na propria tela")
    checar(u"e diz que nao substitui a angiografia digital",
           u"angiografia digital" in N.LIMITACAO_CLINICA)
    import radai_nidus_screen as S
    pg = S.pagina()
    checar(u"a limitacao da RM esta na tela, e diz que o sinal nao e HU",
           N.LIMITACAO_RM in pg and u"não é HU" in N.LIMITACAO_RM
           and "@LIMITACAO" not in pg)

    import radai_modules
    fs = radai_modules.FERRAMENTAS.get("nidus") or ()
    rotulos = [f[2] for f in fs]
    checar(u"a ferramenta se chama Projecao vascular",
           any(u"Projeção Vascular" == r for r in rotulos), str(rotulos))
    p = radai_modules.pagina("nidus")
    checar(u"e `arteriografia` nao aparece na tela do modulo",
           u"arteriograf" not in p.lower())


def teste_nao_detecta_nada():
    secao(u"nada e aprendido, nada e detectado")
    codigo = sem_prosa(fonte("radai_nidus.py")).lower()
    tela = sem_prosa(fonte("radai_nidus_screen.py")).lower()
    for proibido in ("candidat", "suspeit", "probabilid", "malign", "detect",
                     "score", "torch", "monai", "predict", "model"):
        # GUARDA: o detector do arco em C é o painel de raio X, e não detecção de achado.
        padrao = r"detect(?!or)" if proibido == "detect" else re.escape(proibido)
        checar(u"a lib nao tem `%s`" % proibido, not re.search(padrao, codigo))
        checar(u"a tela nao tem `%s`" % proibido, not re.search(padrao, tela))
    checar(u"  isca: «detectar» ainda é acusado (o detector do arco não abre a porta)",
           re.search(r"detect(?!or)", u"vista do detector · detectar o ninho")
           is not None)

    bruto = fonte("radai_nidus_screen.py")
    checar(u"a imagem viaja por bilhete",
           "?b=' + encodeURIComponent" in bruto or "b='+encodeURIComponent" in bruto)
    checar(u"e nenhuma rota GET recebe caminho",
           not re.search(r'@app\.get\([^)]*\)\s*\n\s*def\s+\w+\([^)]*\bpasta\s*:',
                         bruto))


def teste_a_suite_conhece_o_modulo():
    secao(u"a suite conhece o modulo, nos cinco lugares")
    import radai_menu
    import radai_modules
    import radai_breadcrumb

    checar(u"esta no trilho", "nidus" in radai_menu.MODULOS)
    checar(u"esta na ordem da home", "nidus" in radai_menu.MODULOS_HOME)
    checar(u"esta na arvore da trilha", "nidus" in radai_breadcrumb.ARVORE)
    checar(u"e a ferramenta tambem",
           "nidus_projecao" in radai_breadcrumb.ARVORE)
    checar(u"a trilha da ferramenta tem tres elos",
           len(radai_breadcrumb.trilha("nidus_projecao")) == 3,
           str(radai_breadcrumb.trilha("nidus_projecao")))
    checar(u"tem identidade", "nidus" in radai_modules.MODULOS)
    checar(u"tem cor propria", "nidus" in radai_modules.CORES)
    checar(u"tem ferramentas", bool(radai_modules.FERRAMENTAS.get("nidus")))
    checar(u"tem baloes", bool(radai_modules.AJUDA.get("nidus")))

    ui = fonte("radai_ui.py")
    i = ui.index("TOKENS = u")
    j = ui.index("CASCA = u")
    bloco = ui[i:j]
    claro = bloco[bloco.index('data-tema="claro"'):]
    escuro = bloco[:bloco.index('data-tema="claro"')]
    for ficha in ("--mod-nidus", "--mod-nidus-b"):
        checar(u"`%s` existe no tema escuro" % ficha, ficha + ":" in escuro)
        checar(u"e no tema claro" if ficha == "--mod-nidus"
               else u"`%s` no tema claro" % ficha, ficha + ":" in claro)

    import radai_porta
    linha = radai_porta.cartao("nidus", 3)
    checar(u"o cartão da porta leva para /nidus", 'href="/nidus"' in linha, linha[:80])
    checar(u"modulo desconhecido nao vira cartao",
           radai_porta.cartao("nao_existe", 0) == u"")


def teste_acumular_incidencias():
    import math
    import numpy as np
    import SimpleITK as sitk
    import radai_nidus as N
    secao(u"acumular incidencias: a intersecao aperta e contem o ninho")

    LADO = 96
    vol = np.full((LADO, LADO, LADO), -900.0, dtype=np.float32)
    zz, yy, xx = np.mgrid[0:LADO, 0:LADO, 0:LADO]
    c = LADO / 2.0
    r = np.sqrt((zz - c) ** 2 + (yy - c) ** 2 + (xx - c) ** 2)
    vol[r < 9] = 350.0
    img = sitk.GetImageFromArray(vol)
    img.SetSpacing((1.0, 1.0, 1.0))

    def circulo(lao, cra):
        p, _i = N.projetar(img, lao_rao=lao, cra_cau=cra, modo="mip",
                           janela="angio", lado=LADO)
        a = np.asarray(p, dtype=np.float32)
        lim = a.max() - (a.max() - a.min()) * 0.25
        ys, xs = np.nonzero(a >= lim)
        if not len(xs):
            return []
        cx, cy = float(xs.mean()), float(ys.mean())
        raio = max(6.0, float(max(xs.max() - xs.min(),
                                  ys.max() - ys.min())) / 2 * 1.15)
        return [[cx + raio * math.cos(t), cy + raio * math.sin(t)]
                for t in np.linspace(0, 2 * math.pi, 24, endpoint=False)]

    angulos = [(0, 0), (60, 0), (-60, 0), (0, 45), (0, -45), (35, 30)]
    tubos, tamanhos = [], []
    for lao, cra in angulos:
        pol = circulo(lao, cra)
        if not pol:
            checar(u"a projecao em LAO %d / CRA %d mostra a esfera"
                   % (lao, cra), False, u"nada passou do limiar")
            return
        tubos.append(N.tubo(img, pol, lao, cra, lado=LADO))
        tamanhos.append(int(np.count_nonzero(N.intersecao(tubos))))

    checar(u"as seis incidencias foram retroprojetadas", len(tubos) == 6)
    checar(u"a intersecao SO APERTA a cada incidencia",
           all(tamanhos[i + 1] <= tamanhos[i]
               for i in range(len(tamanhos) - 1)),
           u"%s" % tamanhos)
    ganho = 100.0 * (1 - tamanhos[5] / float(max(1, tamanhos[1])))
    checar(u"e de 2 para 6 ela aperta pelo menos 30%%", ganho >= 30.0,
           u"apertou %.0f%% (%d -> %d)" % (ganho, tamanhos[1], tamanhos[5]))

    inter = N.intersecao(tubos)
    idx = np.array(np.nonzero(inter))
    checar(u"e ela nao ficou vazia", idx.shape[1] > 0)
    if idx.shape[1]:
        cen = idx.mean(axis=1)
        dist = float(np.sqrt(((cen - c) ** 2).sum()))
        checar(u"e o centro dela cai sobre o ninho (< 4 voxels)", dist < 4.0,
               u"centroide=(%.0f,%.0f,%.0f) centro=(%.0f,%.0f,%.0f) dist=%.1f"
               % (cen[0], cen[1], cen[2], c, c, c, dist))
        ext = idx.max(axis=1) - idx.min(axis=1) + 1
        checar(u"e ela e' do tamanho do ninho, nao do volume",
               all(int(e) < LADO / 3 for e in ext), u"extensao %s" % list(ext))

    z = int(np.argmax(inter.sum(axis=(1, 2))))
    segs = N.contorno_do_tubo(inter, 0, z)
    checar(u"o corte mais cheio devolve segmentos", bool(segs),
           u"%d" % len(segs))
    checar(u"e cada um e' um par de pontos",
           all(len(x) == 2 and len(x[0]) == 2 for x in segs[:20]))
    for k in range(len(tubos)):
        if N.contorno_do_tubo(tubos[k], 0, z):
            continue
    checar(u"e cada tubo tem contorno proprio no corte",
           sum(1 for t in tubos if N.contorno_do_tubo(t, 0, z)) >= 4,
           u"so alguns tubos alcancam este corte")

    checar(u"a intersecao nao devolve numero",
           not isinstance(N.intersecao(tubos), (int, float)))
    checar(u"e sem tubo nenhum ela devolve None, e nao o espaco inteiro",
           N.intersecao([]) is None,
           u"intersecao de conjunto vazio seria 'o ninho esta em toda parte'")



_GLOBAIS = frozenset(u"""document window fetch Promise JSON String Number Math
Boolean Array Object setTimeout setInterval clearTimeout console Error Date
RegExp encodeURIComponent decodeURIComponent parseInt parseFloat isNaN
Float32Array Uint16Array Uint32Array Int32Array DataView Infinity""".split())

_PALAVRAS = frozenset(u"""var function return if else for while do in of new
typeof instanceof this null true false undefined break continue try catch
finally throw switch case default delete void class const let""".split())


def _declarados_por_var(t):
    nomes = set()
    for m in re.finditer(r"\bvar\b", t):
        i, prof, esperando = m.end(), 0, True
        while i < len(t):
            c = t[i]
            if c in u"([{":
                prof += 1
            elif c in u")]}":
                if prof == 0:
                    break
                prof -= 1
            elif prof == 0 and c == u";":
                break
            elif prof == 0 and c == u",":
                esperando = True
            elif prof == 0 and c == u"\n" and not esperando:
                anterior = t[:i].rstrip()
                if not anterior.endswith((u",", u"=")):
                    break
            elif esperando and (c.isalpha() or c in u"_$"):
                j = i
                while j < len(t) and (t[j].isalnum() or t[j] in u"_$"):
                    j += 1
                nomes.add(t[i:j])
                esperando, i = False, j
                continue
            elif esperando and not c.isspace():
                esperando = False
            i += 1
    return nomes


def identificadores_soltos(js):
    t = re.sub(r"/\*.*?\*/", " ", js, flags=re.S)
    t = re.sub(r"//[^\n]*", " ", t)
    t = re.sub(r"'(?:\\.|[^'\\])*'", "''", t)
    t = re.sub(r'"(?:\\.|[^"\\])*"', '""', t)
    dec = _declarados_por_var(t)
    dec |= set(re.findall(r"\bfunction\s+([A-Za-z_$][\w$]*)", t))
    for par in re.findall(r"\bfunction\s*[\w$]*\s*\(([^)]*)\)", t):
        dec |= set(p.strip() for p in par.split(",") if p.strip())
    dec |= set(re.findall(r"\bcatch\s*\(\s*([\w$]+)", t))
    fora = set()
    for m in re.finditer(r"(\.\s*)?\b([A-Za-z_$][\w$]*)\b(\s*:)?", t):
        if m.group(1) or m.group(3):
            continue
        n = m.group(2)
        if n not in dec and n not in _GLOBAIS and n not in _PALAVRAS:
            fora.add(n)
    return sorted(fora)


PALCO = u"""
var _FETCHES = [], _ERROS = [], _EL = {}, _CARGA = null, _NINC = 1, _RESP = {};
var _BRILHO = [];

function Elemento(id){
 this.id=id; this.innerHTML=''; this.textContent=''; this.value='';
 this.disabled=false; this.hidden=false;
 this.style={}; this._attrs={}; this._ouvintes={}; this._c=[];
 var eu=this;
 this.classList={
  add:function(k){ if(eu._c.indexOf(k)<0) eu._c.push(k) },
  remove:function(k){ var i=eu._c.indexOf(k); if(i>=0) eu._c.splice(i,1) },
  contains:function(k){ return eu._c.indexOf(k)>=0 },
  toggle:function(k,v){ var tem=eu._c.indexOf(k)>=0;
   if(v===undefined) v=!tem;
   if(v) this.add(k); else this.remove(k) }};
 Object.defineProperty(this,'className',{
  get:function(){ return eu._c.join(' ') },
  set:function(v){ eu._c = String(v||'').split(/\\s+/)
                     .filter(function(x){ return !!x }) }});
}
Elemento.prototype.addEventListener=function(n,f){
 (this._ouvintes[n]=this._ouvintes[n]||[]).push(f) };
Elemento.prototype.getAttribute=function(k){
 return this._attrs[k]===undefined?null:this._attrs[k] };
Elemento.prototype.setAttribute=function(k,v){ this._attrs[k]=v };
Elemento.prototype.removeAttribute=function(k){ delete this._attrs[k];
 if(k==='src') this.src='' };
Elemento.prototype.getBoundingClientRect=function(){
 return {left:0, top:0, width:400, height:400, right:400, bottom:400} };
Elemento.prototype.disparar=function(n,ev){
 (this._ouvintes[n]||[]).forEach(function(f){ f(ev||{}) }) };

var _GRUPOS_BRUTOS = @BOTOES@;
var _GRUPOS = {};
for(var _sel in _GRUPOS_BRUTOS){
 _GRUPOS[_sel] = _GRUPOS_BRUTOS[_sel].map(function(at){
  var e = new Elemento(at.id||'');
  for(var k in at){ e.setAttribute(k, at[k]) }
  e.className = at['class'] || '';
  if(at.id) _EL[at.id] = e;
  return e;
 });
}

var document = {
 getElementById:function(id){ return _EL[id]||(_EL[id]=new Elemento(id)) },
 querySelectorAll:function(sel){ return _GRUPOS[sel]||[] },
 querySelector:function(){ return null },
 addEventListener:function(){}
};
var window = { addEventListener:function(n,f){
 if(n==='DOMContentLoaded') _CARGA=f } };
window.uiVarrerLista = function(o){
 var alvo = document.getElementById(o.alvo);
 alvo.innerHTML = '';
 return fetch('/api/varrer/iniciar', {method:'POST', body:JSON.stringify(
   {uso:o.uso, pasta:o.pasta, dias:o.dias, opcoes:o.opcoes||{}})})
  .then(function(r){ return r.json() }).then(function(d){
   var linhas = d.linhas || [];
   alvo.innerHTML = linhas.map(function(s){ return o.linha(s) }).join('')
     || (o.vazio ? '<p class="ui-vl-vazio">' + o.vazio + '</p>' : '');
   if(o.aoFim) o.aoFim(linhas, d);
  });
};

function _corpo(op){ try{ return JSON.parse((op && op.body) || '{}') }catch(e){ return {} } }
function _padrao(url, op){
 if(url.indexOf('/api/varrer/iniciar')>=0)
  return {v:'V1', fim:true, linhas:[{bilhete:'B1', desc:'angio cranio', cortes:400,
                   espessura_mm:0.5},
                  {bilhete:'B2', desc:'outra serie', cortes:300,
                   espessura_mm:1.0}]};
 if(url.indexOf('/api/nidus/abrir')>=0 || url.indexOf('/api/nidus/forma')>=0)
  return {forma:[400,512,512], espacamento:[0.5,0.45,0.45],
          passos:{'256':1.28,'512':0.64,'768':0.43,'1024':0.32},
          lado_util:768, chave:'K'+(_corpo(op).b||''),
          telas:{'0':[512,512],'1':[400,512],'2':[400,512]},
          osso:{tem:true, fonte:'FULL', estruturas:12}};
 if(url.indexOf('/api/nidus/tubos')>=0)
  return {sessao:'S'+_NINC, incidencias:_NINC, teto:12, cruzam:_NINC>1,
          angulos:[]};
 if(url.indexOf('/api/nidus/linhas')>=0){
  var cam=[];
  for(var k=0;k<_NINC;k++) cam.push({qual:'inc', i:k, lao:k*30, cra:0,
    segmentos:[[[1,1],[2,2]]]});
  if(_NINC>1) cam.push({qual:'inter', i:-1, segmentos:[[[3,3],[4,4]]]});
  return {altura:512, largura:512, camadas:cam, corte:5, n:400,
          incidencias:_NINC};
 }
 if(url.indexOf('/api/nidus/estado')>=0) return {erro:''};
 if(url.indexOf('/api/nidus/eixos')>=0) return {L:[1,0,0], P:[0,0,1], S:[0,-1,0]};
 if(url.indexOf('/api/nidus/segmentar')>=0) return {ok:true, id:'c1', posicao:1};
 if(url.indexOf('/api/fila/estado')>=0)
  return {cartoes:[{id:'c1', estado:'pronto', posicao:0}]};
 if(url.indexOf('/api/nidus/osso')>=0)
  return {osso:{tem:true, fonte:'FULL', estruturas:3}};
 return {};
}
function _resposta(url, op){
 for(var k in _RESP){
  if(url.indexOf(k)>=0)
   return (typeof _RESP[k]==='function') ? _RESP[k](url, op) : _RESP[k];
 }
 return _padrao(url, op);
}
function fetch(url, op){
 _FETCHES.push({url:String(url), op:op||null});
 var d;
 try{ d=_resposta(String(url), op) }catch(e){ return Promise.reject(e) }
 return Promise.resolve({json:function(){ return Promise.resolve(d) }});
}
"""

ABRE = u"""
function _tique(){ return new Promise(function(r){ setTimeout(r,0) }) }
async function _esperar(n){ for(var i=0;i<(n||6);i++){ await _tique() } }
function _tentar(nome,f){ try{ return f() }catch(e){ _ERROS.push(nome+': '+e) } }
function _ligado(b){ return !!(b && (b.classList.contains('on')
  || /(^| )on( |$)/.test(b.className))) }
function _ev(x,y,extra){ var e={clientX:x, clientY:y, button:0, shiftKey:false,
  preventDefault:function(){}, stopPropagation:function(){}};
  for(var k in (extra||{})) e[k]=extra[k]; return e }
function _svg(){ return document.getElementById('nd_svg') }
function _proj(){ return document.getElementById('nd_proj') }
function _carregou(){ var im=_proj(); if(im.onload) im.onload() }
function _falhou_img(){ var im=_proj(); if(im.onerror) im.onerror() }
function _msg(){ return document.getElementById('nd_msg').textContent }
function _urls(de){ return _FETCHES.slice(de||0).map(function(f){ return f.url }) }
function _circulo(cx, cy, R, n){
 var s=_svg();
 s.disparar('mousedown', _ev(cx+R, cy));
 for(var i=1;i<n;i++){ var t=2*Math.PI*i/n;
  s.disparar('mousemove', _ev(cx+R*Math.cos(t), cy+R*Math.sin(t))) }
}
async function _abrir(){
 _tentar('carga', function(){ if(_CARGA) _CARGA() });
 await _esperar();
 if(!ND.b){
  _tentar('listar', function(){ ndListar('X') });
  await _esperar();
  _tentar('escolher', function(){ ndEscolher('B1') });
  await _esperar();
 }
 _carregou();
 await _esperar();
}
function pronto(o){
 o.erros=_ERROS.slice();
 o.urls=_FETCHES.map(function(f){ return f.url });
 console.log('@@'+JSON.stringify(o));
}
(async function(){ try {
"""

FECHA = u"""
 } catch(e){ console.log('@@'+JSON.stringify(
   {explodiu:String(e), erros:_ERROS})) }
})();
"""


def _node():
    import shutil
    return shutil.which("node")


def _botoes_da_pagina():
    import json
    import radai_nidus_screen as S
    html = S.pagina()
    grupos = {}
    for cid in ("nd_incid", "nd_jan"):
        m = re.search(r'id="%s"[^>]*>(.*?)</div>' % cid, html, re.S)
        bs = []
        for tag in re.findall(r"<button\b[^>]*>", m.group(1) if m else u""):
            bs.append(dict(re.findall(r'([\w-]+)="([^"]*)"', tag)))
        grupos["#%s .nd-bt" % cid] = bs
    return json.dumps(grupos)


def _encenar(corpo, ajuste=None):
    import json
    import subprocess
    import radai_nidus_screen as S
    js = S.JS
    if ajuste:
        js = ajuste(js)
    fonte_js = (PALCO.replace("@BOTOES@", _botoes_da_pagina())
                + u"\n" + js + u"\n" + ABRE + corpo + FECHA)
    d = _cleanup.temporaria("radai_ac_nidus_palco_")
    p = os.path.join(d, "palco.js")
    io.open(p, "w", encoding="utf-8").write(fonte_js)
    r = subprocess.run([_node(), p], stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, timeout=120)
    saida = r.stdout.decode("utf-8", "replace")
    for l in saida.splitlines():
        if l.startswith("@@"):
            return json.loads(l[2:])
    raise RuntimeError((r.stderr.decode("utf-8", "replace") or saida
                        or u"o palco não respondeu")[:400])


def _sem_node():
    if _node():
        return False
    checar(u"(sem node — o palco nao rodou)", True,
           u"instale o node para a prova por execucao")
    return True


def teste_o_javascript_nao_le_nome_solto():
    secao(u"o JavaScript da tela nao le nome que ninguem declarou")
    import radai_nidus_screen as S
    soltos = identificadores_soltos(S.JS)
    checar(u"nenhum identificador solto no JS da tela", not soltos,
           u", ".join(soltos))
    isca = S.JS.replace("ndCalcular();", "ndMsg(qual?'a':'b',''); ndCalcular();")
    checar(u"e a checagem sabe reprovar (isca: o `qual` de volta)",
           "qual" in identificadores_soltos(isca))


def teste_a_tela_acorda_e_pede_as_series():
    secao(u"a tela acorda com a escolha da série aberta, e a pasta lista quando pedem")
    import radai_nidus_screen as S
    if _sem_node():
        return
    d = _encenar(u"""
 _tentar('carga', function(){ if(_CARGA) _CARGA() });
 await _esperar();
 var r={escolhendo:ND.escolhendo, guardadas:ND.guardadas.length,
        varreu:_FETCHES.some(function(f){
          return f.url.indexOf('/api/varrer/')>=0 })};
 _tentar('listar', function(){ ndListar('X') });
 await _esperar();
 r.itens=document.getElementById('nd_series').innerHTML;
 r.pedido=_FETCHES.filter(function(f){ return f.url.indexOf('/api/varrer/iniciar')>=0 })
  .map(function(f){ return JSON.parse(f.op.body) });
 _tentar('vazio', function(){ ndListar('   ') });
 await _esperar();
 r.pedidos=_FETCHES.filter(function(f){ return f.url.indexOf('/api/varrer/iniciar')>=0 }).length;
 _tentar('escolher', function(){ ndEscolher('B2') });
 await _esperar();
 r.b=ND.b; r.rotulo=document.getElementById('nd_serie_rot').textContent;
 r.fechou=!ND.escolhendo;
 pronto(r);
""")
    checar(u"a carga da pagina nao levanta", not d["erros"],
           u" | ".join(d["erros"])[:160])
    checar(u"e abre a escolha da série (a tabela do acervo e a pasta)",
           d.get("escolhendo") is True)
    checar(u"  sem varrer pasta nenhuma sozinha", d.get("varreu") is False)
    checar(u"a lista de incidencias nasce vazia", d.get("guardadas") == 0,
           str(d.get("guardadas")))
    checar(u"a pasta pedida vira uma lista de botões, um por série",
           (d.get("itens") or u"").count(u'class="nd-it"') == 2
           and u'data-b="B2"' in (d.get("itens") or u""),
           (d.get("itens") or u"")[:120])
    ped = (d.get("pedido") or [{}])[0]
    checar(u"a lista vem da varredura da casca (C-VARRER), com as modalidades, "
           u"o mínimo de cortes e o filtro de data da tela",
           ped.get("uso") == u"series" and ped.get("pasta") == u"X"
           and ped.get("dias") == u"nd_dias"
           and ped.get("opcoes") == {u"modalidades": list(S.MODALIDADES),
                                     u"min_cortes": S.MIN_CORTES}, str(ped))
    checar(u"  e a pasta em branco não varre nada",
           d.get("pedidos") == 1, str(d.get("pedidos")))
    checar(u"escolher na lista abre a série, fecha a escolha e diz qual é",
           d.get("b") == u"B2" and d.get("fechou") is True
           and u"outra serie" in (d.get("rotulo") or u""), str(d)[:160])

    iscado = _encenar(u"""
 _tentar('carga', function(){ if(_CARGA) _CARGA() });
 await _esperar();
 pronto({escolhendo:!!ND.escolhendo});
""", ajuste=lambda js: js.replace("guardadas:[], sessao:null",
                                  "guardadas:[null,null], sessao:null"))
    checar(u"e com os dois nulos de volta a escolha NAO abre (isca)",
           not iscado.get("escolhendo") and bool(iscado.get("erros")),
           u" | ".join(iscado.get("erros") or [])[:120])


def _falhas_do_popup(p):
    fora = []
    if u'class="ui-guias esq" id="nd_origem"' not in p:
        fora.append(u"as abas não estão à esquerda")
    if u'<div class="ui-ps" id="nd_escolha" data-ui-ps' not in p:
        fora.append(u"a escolha não é o popup da casca")
    lado = p.split(u'id="nd_serie_cx"')[-1].split(u"</div>")[0]
    if (u'id="nd_escolher" data-ui-ps-abre="nd_escolha"' not in lado
            or u">Carregar série</span>" not in lado):
        fora.append(u"falta o cartão «Carregar série» na tela de trabalho")
    return fora


def teste_o_popup_e_o_cartao_carregar_serie():
    secao(u"o popup da casca com as abas à esquerda, e o cartão «Carregar série»")
    import radai_nidus_screen as S
    p = S.pagina()
    f = _falhas_do_popup(p)
    checar(u"abas à esquerda, popup da casca, cartão na tela de trabalho", not f,
           u"; ".join(f))
    isca = p.replace(u'class="ui-guias esq" id="nd_origem"',
                     u'class="ui-guias" id="nd_origem"')
    checar(u"  (isca) as abas centralizadas de antes são acusadas",
           isca != p and bool(_falhas_do_popup(isca)))
    checar(u"o cartão diz a série aberta (o rótulo dele é o `nd_serie_rot`)",
           u'<span class="ui-cartao-rot" id="nd_serie_rot">' in p
           and u"uiCartaoRotulo('nd_escolher'" in S.JS)


def teste_a_tabela_do_acervo_no_lugar_do_seletor():
    secao(u"a tabela do acervo da Suite (C2) no lugar do seletor de série")
    import radai_nidus_screen as S
    p = S.pagina()
    checar(u"o seletor de série saiu", u'id="nd_serie"' not in p
           and u"<select" not in p.split(u'id="nd_serie_cx"')[-1].split(u"</div>")[0])
    checar(u"a escolha tem a tabela do acervo e a aba da pasta",
           u'id="nd_acervo" data-ui-acervo' in p
           and u'data-guia="acervo"' in p and u'data-guia="pasta"' in p
           and u'id="nd_series"' in p)
    checar(u"a tabela é a da casca, com o filtro de modalidade da tela",
           u"window.uiTabelaAcervo('nd_acervo'" in S.JS
           and u"ND_MODALIDADES.indexOf(l.modalidade)" in S.JS)
    checar(u"abrir pela tabela usa só o bilhete da linha, nunca caminho",
           u"bilhete:linha.bilhete" in S.JS and u"linha.pasta" not in S.JS)
    checar(u"«Listar séries» sem pasta treme o campo (C3)",
           u"window.uiTremer(ndEl('nd_pasta'))" in S.JS)


def teste_guardar_dispara_a_retroprojecao():
    secao(u"guardar dispara a retroprojecao (o «vou salvando»)")
    if _sem_node():
        return
    d = _encenar(u"""
 await _abrir();
 _ERROS.length = 0;
 var antes = _FETCHES.length;
 ND.pontos = [[10,10],[60,10],[60,60],[10,60]];
 _tentar('guardar', function(){ ndGuardar() });
 await _esperar();
 var depois = _urls(antes);
 pronto({novas:depois,
         retro:depois.some(function(u){ return u.indexOf('/api/nidus/tubos')>=0 }),
         guardadas:ND.guardadas.length,
         sessao:ND.sessao||null, msg:_msg()});
""")
    checar(u"guardar nao levanta", not d["erros"], u" | ".join(d["erros"])[:160])
    checar(u"a incidencia entra na lista", d.get("guardadas") == 1,
           str(d.get("guardadas")))
    checar(u"e a retroprojecao E PEDIDA no mesmo clique", d.get("retro"),
           str(d.get("novas")))
    checar(u"a sessao volta do servidor", bool(d.get("sessao")),
           str(d.get("sessao")))
    checar(u"e a mensagem fala da incidencia",
           u"incid" in (d.get("msg") or u"").lower(), d.get("msg"))

    d2 = _encenar(u"""
 await _abrir();
 ND.pontos = [[10,10],[60,10],[60,60],[10,60]];
 _tentar('guardar', function(){ ndGuardar() });
 await _esperar();
 _tentar('guardar2', function(){ ndGuardar() });
 await _esperar();
 pronto({guardadas:ND.guardadas.length});
""")
    checar(u"guardar de novo, sem desenhar, nao duplica a incidencia",
           d2.get("guardadas") == 1, str(d2.get("guardadas")))

    iscado = _encenar(u"""
 await _abrir();
 _ERROS.length = 0;
 var antes = _FETCHES.length;
 ND.pontos = [[10,10],[60,10],[60,60],[10,60]];
 _tentar('guardar', function(){ ndGuardar() });
 await _esperar();
 pronto({retro:_urls(antes).some(function(u){
          return u.indexOf('/api/nidus/tubos')>=0 })});
""", ajuste=lambda js: js.replace(
        "ndMsg('incidência '+ND.guardadas.length+' guardada — '",
        "ndMsg('incidência '+(qual?'B':'A')+' guardada — '"))
    checar(u"e com o `qual` de volta a retroprojecao PARA (isca)",
           not iscado.get("retro")
           and any("qual" in e for e in iscado.get("erros") or []),
           u" | ".join(iscado.get("erros") or [])[:120])


def teste_o_lapis_traca_e_afina():
    secao(u"o lapis: arrasto, e o traco e afinado antes de sair")
    if _sem_node():
        return
    d = _encenar(u"""
 await _abrir();
 var N_AM = 240, R = 80, cx = 200, cy = 200, s = _svg();
 function _p(i){
  var t = 2*Math.PI*i/N_AM;
  var j = ((i*2654435761) % 1000)/1000 - 0.5;
  return [cx + (R + j*1.6)*Math.cos(t), cy + (R + j*1.6)*Math.sin(t)];
 }
 var p0 = _p(0);
 s.disparar('mousedown', _ev(p0[0], p0[1]));
 for(var i=1;i<N_AM;i++){ var p=_p(i); s.disparar('mousemove', _ev(p[0],p[1])) }
 var bruto = ND.pontos.slice();
 s.disparar('mouseup', _ev(p0[0], p0[1]));
 pronto({bruto:bruto, fino:ND.pontos.slice(), lado:ND.lado,
         marca:document.getElementById('nd_marca').innerHTML, msg:_msg()});
""")
    checar(u"o arrasto nao levanta", not d["erros"], u" | ".join(d["erros"])[:160])
    bruto, fino = d.get("bruto") or [], d.get("fino") or []
    checar(u"o arrasto captura o traco", len(bruto) > 80, str(len(bruto)))
    checar(u"e o traco e AFINADO ao soltar (%d -> %d)" % (len(bruto), len(fino)),
           3 <= len(fino) < len(bruto) / 2.0,
           u"%d de %d" % (len(fino), len(bruto)))
    checar(u"e sobra vertice para a forma (>= 8)", len(fino) >= 8,
           str(len(fino)))
    checar(u"o traco fica abaixo do teto de vertices", len(fino) <= 160,
           str(len(fino)))
    checar(u"o traco fechado e desenhado em SVG",
           "<path" in (d.get("marca") or u""), (d.get("marca") or u"")[:60])
    try:
        import numpy as np
        import radai_nidus as N
        lado = int(d.get("lado") or 512)
        a = N._mascara_poligono([(p[0], p[1]) for p in bruto], lado)
        b = N._mascara_poligono([(p[0], p[1]) for p in fino], lado)
        dsc = 2.0 * float((a & b).sum()) / max(1.0, float(a.sum() + b.sum()))
        checar(u"e a area do traco sobrevive ao afinamento (DSC %.4f)" % dsc,
               dsc >= 0.99, u"%.4f" % dsc)
    except ImportError:
        checar(u"(sem numpy — a area do traco nao foi medida)", True)


def teste_so_o_lapis():
    secao(u"só o lápis: desenha sem ligar nada, e soltar fecha a área")
    import radai_nidus_screen as S
    pg = S.pagina()
    checar(u"saiu o modo de cliques",
           u'data-f="clique"' not in pg and u"ndClique" not in S.JS
           and u"dblclick" not in S.JS)
    checar(u"saiu o botão «Circular a área»",
           u"nd_bt_desenhar" not in pg and u"Circular a &aacute;rea" not in pg
           and u"ndDesenhar" not in S.JS)
    regra = re.search(r"\.nd-marca\{([^}]*)\}", S.CSS)
    regra = regra.group(1) if regra else u""
    checar(u"o pontilhado é mais fino (1 px) e os pontos mais próximos (2 2)",
           u"stroke-width:1;" in regra and u"stroke-dasharray:2 2" in regra,
           regra)
    if _sem_node():
        return
    corpo = u"""
 await _abrir();
 var r={};
 _circulo(200, 200, 60, 40);
 r.durante=document.getElementById('nd_marca').innerHTML;
 _svg().disparar('mouseup', _ev(260, 200));
 r.depois=document.getElementById('nd_marca').innerHTML;
 r.n=ND.pontos.length;
 _svg().disparar('click', _ev(10,10));
 r.clique_nao_soma=(ND.pontos.length===r.n);
 ND.pontos=[];
 _svg().disparar('mousedown', _ev(100,100,{shiftKey:true}));
 _svg().disparar('mousemove', _ev(150,150,{shiftKey:true}));
 r.shift_nao_desenha=(!ND.tracando && ND.pontos.length===0);
 _svg().disparar('mousedown', _ev(100,100,{button:1}));
 r.meio_nao_desenha=(!ND.tracando && ND.pontos.length===0);
 pronto(r);
"""
    d = _encenar(corpo)
    checar(u"o lápis desenha logo depois de abrir, sem outro botão ligado",
           (d.get("n") or 0) >= 8 and not d.get("erros"),
           u"%s %s" % (d.get("n"), d.get("erros")))
    checar(u"durante o traço a área fica aberta",
           u" Z" not in (d.get("durante") or u""), (d.get("durante") or u"")[-40:])
    checar(u"e soltar fecha do último ponto ao primeiro (o Z)",
           u' Z"' in (d.get("depois") or u""), (d.get("depois") or u"")[-40:])
    checar(u"um clique solto não acrescenta vértice", d.get("clique_nao_soma"))
    checar(u"Shift + arrastar move a imagem, e não desenha",
           d.get("shift_nao_desenha"))
    checar(u"e o botão do meio também não desenha", d.get("meio_nao_desenha"))
    iscado = _encenar(corpo, ajuste=lambda js: js.replace(
        u"if(!ndPodeDesenhar()){", u"if(!ND.desenhando){"))
    checar(u"  isca: o lápis que pede outro botão ligado é acusado",
           (iscado.get("n") or 0) < 3, str(iscado.get("n")))


def teste_os_padroes_de_abertura():
    secao(u"padrões: invertida, todo o volume, MIP e a resolução máxima")
    import radai_nidus as N
    import radai_nidus_screen as S
    pg = S.pagina()
    checar(u"a opção de resolução saiu da tela",
           u'id="nd_res"' not in pg and u"ndResolucao" not in S.JS)
    checar(u"o palco nasce invertido no HTML",
           u'class="nd-palco inv" id="nd_palco"' in pg
           and re.search(r'id="nd_inverter"[^>]*aria-pressed="true"', pg))
    checar(u"o MIP nasce ligado", re.search(r'class="nd-bt on" id="nd_m_mip"', pg))
    checar(u"a resolução da tela é a máxima da lib",
           S.LADO_DA_TELA == N.LADO_ALTA == max(S.LADOS))
    if _sem_node():
        return
    d = _encenar(u"""
 await _abrir();
 pronto({lado:ND.lado, vb:_svg().getAttribute('viewBox'), inv:ND.inverter,
   palco:document.getElementById('nd_palco').className,
   aria:document.getElementById('nd_inverter').getAttribute('aria-pressed'),
   modo:ND.modo, laje:ND.laje, lajev:document.getElementById('nd_lajev').textContent,
   src:_proj().src});
""")
    checar(u"o JS desenha na grade máxima", d.get("lado") == N.LADO_ALTA
           and d.get("vb") == u"0 0 %d %d" % (N.LADO_ALTA, N.LADO_ALTA),
           u"%s %s" % (d.get("lado"), d.get("vb")))
    checar(u"e pede a projeção nela", u"lado=%d" % N.LADO_ALTA in (d.get("src") or u""),
           (d.get("src") or u"")[-90:])
    checar(u"inverter cores ligado ao abrir", d.get("inv") is True
           and u"inv" in (d.get("palco") or u"") and d.get("aria") == u"true",
           u"%s %s" % (d.get("palco"), d.get("aria")))
    checar(u"MIP e todo o volume ao abrir", d.get("modo") == u"mip"
           and d.get("laje") == 0 and d.get("lajev") == u"todo o volume")


def teste_as_barras_de_angulo():
    secao(u"LAO/RAO e CRA/CAU em barra de arrastar")
    import radai_nidus_screen as S
    pg = S.pagina()
    checar(u"a barra do LAO/RAO vai de -180 a 180",
           re.search(r'type="range" id="nd_lao_r" min="-180" max="180"', pg))
    checar(u"a barra do CRA/CAU vai de -90 a 90",
           re.search(r'type="range" id="nd_cra_r" min="-90" max="90"', pg))
    checar(u"e o campo digitado ficou", u'id="nd_lao"' in pg and u'id="nd_cra"' in pg)
    if _sem_node():
        return
    corpo = u"""
 await _abrir();
 var r=document.getElementById('nd_lao_r'), c=document.getElementById('nd_cra_r');
 r.value='-35'; r.disparar('input');
 var prev={rot:document.getElementById('nd_lao_v').textContent,
   txt:document.getElementById('nd_lao').value, lao:ND.lao};
 r.disparar('change');
 _carregou();
 c.value='-20'; c.disparar('change');
 _carregou();
 pronto({prev:prev, lao:ND.lao, cra:ND.cra,
   rl:document.getElementById('nd_lao_v').textContent,
   rc:document.getElementById('nd_cra_v').textContent, src:_proj().src});
"""
    d = _encenar(corpo)
    p = d.get("prev") or {}
    checar(u"arrastar mostra o ângulo (RAO 35°) sem projetar ainda",
           p.get("rot") == u"RAO 35°" and p.get("txt") == u"-35" and p.get("lao") == 0,
           str(p))
    checar(u"soltar a barra gira o gantry", d.get("lao") == -35 and d.get("cra") == -20,
           u"%s %s" % (d.get("lao"), d.get("cra")))
    checar(u"e a projeção é pedida no ângulo novo",
           u"lao=-35&cra=-20" in (d.get("src") or u""), (d.get("src") or u"")[-90:])
    checar(u"negativo diz RAO e CAU", d.get("rl") == u"RAO 35°"
           and d.get("rc") == u"CAU 20°", u"%s %s" % (d.get("rl"), d.get("rc")))
    iscado = _encenar(corpo, ajuste=lambda js: js.replace(
        u"ndPrever(k, +r.value||0)", u"ndMudarAngulo(k, +r.value||0)"))
    checar(u"  isca: barra que projeta a cada passo do arrasto é acusada",
           (iscado.get("prev") or {}).get("lao") != 0)


def teste_a_lista_diz_rao_e_cau():
    secao(u"a lista das guardadas diz RAO e CAU quando o ângulo é negativo")
    if _sem_node():
        return
    corpo = u"""
 await _abrir();
 ndAngulo(-30,-15); _carregou();
 ND.pontos=[[10,10],[60,10],[60,60],[10,60]]; ndGuardar(); await _esperar();
 ndAngulo(30,10); _carregou();
 ND.pontos=[[10,10],[60,10],[60,60],[10,60]]; ndGuardar(); await _esperar();
 pronto({lista:document.getElementById('nd_guardadas').innerHTML});
"""
    d = _encenar(corpo)
    lista = d.get("lista") or u""
    checar(u"a negativa sai como RAO 30° / CAU 15°", u"RAO 30° / CAU 15°" in lista,
           lista[:160])
    checar(u"a positiva sai como LAO 30° / CRA 10°", u"LAO 30° / CRA 10°" in lista)
    checar(u"e nenhum ângulo sai com sinal", u"-30" not in lista and u"-15" not in lista)
    iscado = _encenar(corpo, ajuste=lambda js: js.replace(
        u"(n<0?neg:pos)+' '+Math.abs(n)", u"pos+' '+n"))
    checar(u"  isca: a lista que escreve «LAO -30» é acusada",
           u"RAO 30°" not in (iscado.get("lista") or u""))


def teste_girar_guarda_o_traco():
    secao(u"girar com um traço desenhado guarda o traço antes")
    if _sem_node():
        return
    corpo = u"""
 await _abrir();
 ND.pontos=[[10,10],[60,10],[60,60],[10,60]];
 ndIncidencia(45,0,'x');
 var msg=_msg();
 await _esperar();
 pronto({g:ND.guardadas.map(function(x){ return [x.lao, x.cra, x.pontos.length] }),
   pontos:ND.pontos.length, lao:ND.lao, msg:msg});
"""
    d = _encenar(corpo)
    checar(u"o traço vai para a lista com o ângulo em que foi desenhado",
           d.get("g") == [[0, 0, 4]], str(d.get("g")))
    checar(u"e a incidência nova começa limpa, no ângulo novo",
           d.get("pontos") == 0 and d.get("lao") == 45)
    checar(u"e a tela diz que guardou", u"guardado antes de girar" in (d.get("msg") or u""),
           d.get("msg"))
    iscado = _encenar(corpo, ajuste=lambda js: js.replace(
        u"if(ND.pontos.length>=3){\n  if(ND.guardadas.length>=ND.teto){",
        u"if(false){\n  if(ND.guardadas.length>=ND.teto){"))
    checar(u"  isca: girar que apaga o traço é acusado", iscado.get("g") == [])


def teste_serie_que_nao_abre_trava_a_tela():
    secao(u"série que não abre: a tela trava, e diz por quê")
    if _sem_node():
        return
    corpo = u"""
 _RESP['/api/nidus/abrir']={erro:'A série é uma imagem colorida (3 componentes por pixel) — captura de tela ou reconstrução exportada —, e não os cortes da angioTC ou da RM: escolha a série de cortes.'};
 await _abrir();
 var antes=_FETCHES.length;
 _circulo(200,200,60,30); _svg().disparar('mouseup', _ev(260,200));
 var tracou=ND.pontos.length;
 ND.pontos=[[1,1],[50,1],[50,50]];
 _tentar('guardar', function(){ ndGuardar() });
 _tentar('caixa', function(){ ndCaixaModo(); ndCaixaLimpar() });
 _tentar('girar', function(){ ndIncidencia(45,0,'x') });
 await _esperar();
 pronto({aberta:ND.aberta, tracou:tracou, guardadas:ND.guardadas.length,
   novas:_urls(antes), src:_proj().src||'',
   dis:document.getElementById('nd_bt_guardar').disabled,
   dis_lao:document.getElementById('nd_lao_r').disabled, msg:_msg()});
"""
    d = _encenar(corpo)
    checar(u"a série fica fechada", d.get("aberta") is False)
    checar(u"o lápis não desenha nela", d.get("tracou") == 0, str(d.get("tracou")))
    checar(u"guardar, recortar e girar não chegam ao servidor",
           d.get("guardadas") == 0 and not d.get("novas") and not d.get("src"),
           u"%s %s" % (d.get("novas"), d.get("src")))
    checar(u"os botões ficam apagados", d.get("dis") is True and d.get("dis_lao") is True)
    checar(u"e a mensagem diz o motivo e o que fazer",
           u"colorida" in (d.get("msg") or u"")
           and u"nada pode ser desenhado" in (d.get("msg") or u""), d.get("msg"))
    iscado = _encenar(corpo, ajuste=lambda js: js.replace(
        u"function ndGuardar(auto){\n if(!ND.aberta) return;",
        u"function ndGuardar(auto){\n").replace(
        u"if(!g.length || !ND.b || !ND.aberta) return;",
        u"if(!g.length || !ND.b) return;"))
    checar(u"  isca: guardar sem a trava chega à retroprojeção",
           any(u"/api/nidus/tubos" in u for u in iscado.get("novas") or []))


def teste_o_erro_volta_ao_estado_bom():
    secao(u"erro: a tela volta ao último estado bom, e nada desenhado se perde")
    if _sem_node():
        return
    corpo = u"""
 window.sessionStorage={_d:{}, setItem:function(k,v){ this._d[k]=String(v) },
  getItem:function(k){ return this._d[k]===undefined?null:this._d[k] }};
 await _abrir();
 ND.pontos=[[10,10],[60,10],[60,60],[10,60]]; ndGuardar(); await _esperar();
 var r={};
 _RESP['/api/nidus/estado']={erro:"ValueError: axes don't match array"};
 ndAngulo(60,20);
 _falhou_img(); await _esperar();
 r.a={lao:ND.lao, cra:ND.cra, guardadas:ND.guardadas.length, msg:_msg(), src:_proj().src};
 _carregou(); await _esperar();
 r.a.voltando=ND.voltando;
 var sessao=ND.sessao;
 _RESP['/api/nidus/tubos']={erro:"ValueError: axes don't match array"};
 ND.pontos=[[20,20],[80,20],[80,80]]; ndGuardar(); await _esperar();
 r.b={guardadas:ND.guardadas.length,
   pend:ND.guardadas.filter(function(x){ return x.pendente }).length,
   sessao_igual:ND.sessao===sessao, msg:_msg(),
   cruzar:!document.getElementById('nd_bt_cruzar').hidden};
 var salvo=JSON.parse(window.sessionStorage.getItem(ndChaveSalva())||'null');
 r.c={salvas:salvo?salvo.guardadas.length:-1};
 delete _RESP['/api/nidus/tubos'];
 var antes=_FETCHES.length;
 ndEscolher('B1'); await _esperar(); _carregou(); await _esperar();
 r.d={guardadas:ND.guardadas.length, tubos:_urls(antes).some(function(u){
   return u.indexOf('/api/nidus/tubos')>=0 }), msg:_msg()};
 pronto(r);
"""
    d = _encenar(corpo)
    a, b, c, e = (d.get(k) or {} for k in ("a", "b", "c", "d"))
    checar(u"a projeção que falha devolve a tela ao último ângulo bom",
           a.get("lao") == 0 and a.get("cra") == 0 and u"lao=0&cra=0" in (a.get("src") or u""),
           str(a)[:160])
    checar(u"e avisa, com o motivo", u"voltou ao último estado bom" in (a.get("msg") or u"")
           and u"axes" in (a.get("msg") or u""), a.get("msg"))
    checar(u"e o desenho guardado continua lá", a.get("guardadas") == 1)
    checar(u"quando o estado bom chega, a volta termina", a.get("voltando") is False)
    checar(u"a retroprojeção que falha não perde a incidência nova",
           b.get("guardadas") == 2 and b.get("pend") == 1, str(b))
    checar(u"e as linhas continuam as do último estado bom", b.get("sessao_igual"))
    checar(u"e «Cruzar de novo» aparece, com a mensagem",
           b.get("cruzar") and u"retroprojeção falhou" in (b.get("msg") or u""), b.get("msg"))
    checar(u"o progresso fica salvo depois do erro", c.get("salvas") == 2, str(c))
    checar(u"e volta ao reabrir a série, e é cruzado de novo",
           e.get("guardadas") == 2 and e.get("tubos")
           and u"marcação salva" in (e.get("msg") or u""), str(e))
    iscado = _encenar(corpo, ajuste=lambda js: js.replace(
        u"ndAplicar(ND.bom, false);", u""))
    checar(u"  isca: sem a volta, a tela fica no ângulo que falhou",
           (iscado.get("a") or {}).get("lao") == 60)


def teste_o_brilho_cobre_projecao_e_mpr():
    secao(u"o brilho de processamento na projeção e nos três MPR")
    if _sem_node():
        return
    corpo = u"""
 window.uiCarregando=function(e, liga, txt){ _BRILHO.push([e.id, liga===false?0:1]) };
 await _abrir();
 var antes=_BRILHO.length;
 ndAngulo(30,0);
 var ja=_BRILHO.slice(antes);
 pronto({todos:_BRILHO, ja:ja});
"""
    d = _encenar(corpo)
    ligados = set(x[0] for x in d.get("todos") or [] if x[1] == 1)
    checar(u"a projeção e os três MPR acendem o brilho ao abrir",
           set([u"nd_palco", u"nd_pp0", u"nd_pp1", u"nd_pp2"]) <= ligados,
           sorted(ligados))
    checar(u"e girar acende o da projeção na hora, sem esperar",
           [u"nd_palco", 1] in (d.get("ja") or []), str(d.get("ja")))
    checar(u"e ele se apaga quando a imagem chega",
           [u"nd_palco", 0] in (d.get("todos") or []))
    iscado = _encenar(corpo, ajuste=lambda js: js.replace(
        u"if(brilho) ndCarregando(true, palco,", u"if(false) ndCarregando(true, palco,"))
    ligados_i = set(x[0] for x in iscado.get("todos") or [] if x[1] == 1)
    checar(u"  isca: MPR sem brilho é acusado", u"nd_pp0" not in ligados_i)


def teste_o_osso_na_tela():
    secao(u"o osso: tirado pela segmentação, ou «segmentar primeiro (AUTO)»")
    if _sem_node():
        return
    d = _encenar(u"""
 await _abrir();
 var r={tem:ND.tem_osso, bt:document.getElementById('nd_osso_bt').hidden,
   src1:_proj().src};
 ndOssoAlternar(); r.src2=_proj().src; _carregou();
 _RESP['/api/nidus/abrir']=function(u, op){ var f=_padrao(u, op);
  f.osso={tem:false, motivo:'esta série ainda não tem segmentação do ContourLab: o osso continua na projeção'};
  return f };
 ndEscolher('B2'); await _esperar(); _carregou();
 r.sem={tem:ND.tem_osso, sg:document.getElementById('nd_segmentar').hidden,
   src:_proj().src, txt:document.getElementById('nd_osso_txt').innerHTML};
 ND_FILA_A_CADA_MS=0;
 var antes=_FETCHES.length;
 ndSegmentar(); await _esperar(16);
 r.fila=_urls(antes);
 var seg=_FETCHES.filter(function(f){ return f.url.indexOf('/api/nidus/segmentar')>=0 })[0];
 r.corpo=seg?JSON.parse(seg.op.body):null;
 r.depois={tem:ND.tem_osso, src:_proj().src, msg:_msg()};
 _RESP['/api/nidus/segmentar']={ok:false, indisponivel:true,
  erro:'fila indisponível: a fila da estação não respondeu.'};
 ND.tem_osso=false; ND.fila=null; ndSegmentar(); await _esperar();
 r.indisp=_msg();
 pronto(r);
""")
    checar(u"com a segmentação, o osso sai da projeção ao abrir",
           d.get("tem") is True and d.get("bt") is False
           and u"osso=1" in (d.get("src1") or u""), (d.get("src1") or u"")[-60:])
    checar(u"e o botão põe o osso de volta", u"osso=0" in (d.get("src2") or u""))
    sem = d.get("sem") or {}
    checar(u"sem segmentação, o osso fica, e não se adivinha pela densidade",
           sem.get("tem") is False and u"osso=0" in (sem.get("src") or u""))
    checar(u"e a tela oferece «Segmentar primeiro (AUTO)»", sem.get("sg") is False
           and u"não tem segmentação" in (sem.get("txt") or u""))
    fila = d.get("fila") or []
    ordem = [u for u in fila if u"/api/nidus/segmentar" in u or u"/api/fila/estado" in u
             or u"/api/nidus/osso" in u]
    checar(u"segmentar vai à fila, acompanha o cartão e relê o osso quando termina",
           len(ordem) >= 3 and u"segmentar" in ordem[0] and u"fila/estado" in ordem[1]
           and u"nidus/osso" in ordem[-1], str(ordem))
    checar(u"o pedido leva só o bilhete (o caminho fica no servidor)",
           sorted((d.get("corpo") or {}).keys()) == [u"b", u"rotulo"], str(d.get("corpo")))
    dep = d.get("depois") or {}
    checar(u"e com a segmentação pronta o osso sai sozinho",
           dep.get("tem") is True and u"osso=1" in (dep.get("src") or u""), str(dep)[:120])
    checar(u"fila sem a rota: a tela diz «fila indisponível»",
           u"fila indisponível" in (d.get("indisp") or u""), d.get("indisp"))


def teste_as_incidencias_se_somam_nos_tres_planos():
    secao(u"as incidencias acumuladas aparecem JUNTAS nos tres planos")
    if _sem_node():
        return
    d = _encenar(u"""
 await _abrir();
 var r={};
 for(var k=0;k<5;k++){
  _NINC = k+1;
  ND.lao = k*30;
  ND.pontos = [[10,10],[60,10],[60,60],[10,60]];
  _tentar('guardar'+k, function(){ ndGuardar() });
  await _esperar();
 }
 r.guardadas = ND.guardadas.length;
 r.planos = [0,1,2].map(function(e){
  return document.getElementById('nd_lin'+e).innerHTML });
 r.lista = document.getElementById('nd_guardadas').innerHTML;
 pronto(r);
""")
    checar(u"as cinco incidencias ficam guardadas", d.get("guardadas") == 5,
           str(d.get("guardadas")))
    planos = d.get("planos") or []
    checar(u"os tres planos foram pintados", len(planos) == 3)
    for i, nome in enumerate((u"axial", u"coronal", u"sagital")):
        h = planos[i] if i < len(planos) else u""
        cores = set(re.findall(r"nd-c(\d)", h))
        checar(u"o plano %s traz as cinco incidencias" % nome,
               len(cores) == 5, u"cores: %s" % sorted(cores))
        checar(u"e a soma por cima, no plano %s" % nome, "nd-inter" in h,
               h[:70])
        checar(u"e sao LINHAS, e nunca regiao, no plano %s" % nome,
               "<line" in h and "<polygon" not in h and "fill=" not in h)
    lista = d.get("lista") or u""
    checar(u"a lista ao lado mostra as cinco",
           len(re.findall(r"<li", lista)) == 5,
           u"%d linhas" % len(re.findall(r"<li", lista)))
    checar(u"e cada uma com a cor da sua linha",
           len(set(re.findall(r"nd-c(\d)", lista))) == 5,
           sorted(set(re.findall(r"nd-c(\d)", lista))))


def teste_serie_nova_nao_herda_a_sessao():
    secao(u"serie nova nao herda a sessao da anterior")
    if _sem_node():
        return
    d = _encenar(u"""
 await _abrir();
 ND.pontos = [[10,10],[60,10],[60,60],[10,60]];
 _tentar('guardar', function(){ ndGuardar() });
 await _esperar();
 var antiga = ND.sessao;
 var antes=_FETCHES.length;
 _tentar('trocar', function(){ ndEscolher('B2') });
 await _esperar();
 pronto({antiga:antiga, agora:ND.sessao||null, guardadas:ND.guardadas.length,
         pediu_linhas:_FETCHES.slice(antes).some(function(f){
           return f.url.indexOf('/api/nidus/linhas')>=0 &&
                  f.url.indexOf(encodeURIComponent(antiga))>=0 })});
""")
    checar(u"a primeira serie tinha sessao", bool(d.get("antiga")),
           str(d.get("antiga")))
    checar(u"e a serie nova nao a herda", not d.get("agora"),
           str(d.get("agora")))
    checar(u"a lista de incidencias tambem zera", d.get("guardadas") == 0,
           str(d.get("guardadas")))
    checar(u"e nenhuma linha da serie antiga e pedida",
           not d.get("pediu_linhas"))


def teste_o_passo_do_detector_aparece():
    secao(u"o passo do detector aparece, e vem da lib")
    bruto = fonte("radai_nidus_screen.py")
    checar(u"a rota da forma devolve o passo de cada resolucao",
           '"passos": serie.passos(LADOS)' in bruto)
    checar(u"e os lados oferecidos moram num lugar so",
           len(re.findall(r"\(256,\s*512,\s*768", bruto)) <= 1,
           u"%d copias da lista de lados"
           % len(re.findall(r"\(256,\s*512,\s*768", bruto)))
    if _sem_node():
        return
    d = _encenar(u"""
 await _abrir();
 pronto({passo:document.getElementById('nd_passo').textContent});
""")
    checar(u"o passo da resolução máxima aparece na tela",
           u"0,32" in (d.get("passo") or u""), repr(d.get("passo")))
    checar(u"e pedir acima do que a serie oferece e dito na tela",
           u"interpola" in (d.get("passo") or u"").lower(), repr(d.get("passo")))


def teste_a_tela_diz_a_escala_da_rm():
    secao(u"a tela diz a escala da RM e a modalidade da serie (v8.3)")
    if _sem_node():
        return
    d = _encenar(u"""
 await _abrir();
 var r={tc:document.getElementById('nd_escala').textContent};
 _RESP['/api/varrer/iniciar']={v:'V1', fim:true, linhas:[{bilhete:'B1', modalidade:'CT', desc:'angio', cortes:400,
                    espessura_mm:0.5},
                   {bilhete:'B2', modalidade:'MR', desc:'T1 pos-Gd',
                    cortes:180, espessura_mm:1.0}]};
 _RESP['/api/nidus/abrir']=function(u, op){ var f=_padrao(u, op); f.hu=false; f.modalidade='MR'; return f };
 _tentar('listar', function(){ ndListar('X') });
 await _esperar();
 r.opcoes=document.getElementById('nd_series').innerHTML;
 _tentar('rm', function(){ ndEscolher('B2') });
 await _esperar();
 r.rm=document.getElementById('nd_escala').textContent;
 pronto(r);
""")
    checar(u"sem erro no roteiro", not d.get("erros"), str(d.get("erros")))
    checar(u"na TC a nota de escala fica vazia", (d.get("tc") or u"") == u"",
           repr(d.get("tc")))
    checar(u"na RM a tela diz que nao ha HU e a janela e relativa",
           u"HU" in (d.get("rm") or u"")
           and u"relativa" in (d.get("rm") or u""), repr(d.get("rm")))
    op = d.get("opcoes") or u""
    checar(u"a opcao da lista diz a modalidade", u"MR · " in op
           and u"CT · " in op, op[:120])


ABA_DE_TESTE = u"""
 window.sessionStorage={_d:{}, setItem:function(k,v){ this._d[k]=String(v) },
  getItem:function(k){ return this._d[k]===undefined?null:this._d[k] }};
"""


def teste_serie_nova_volta_aos_padroes():
    secao(u"outra série abre nos padrões; só o estado salvo dela os muda")
    if _sem_node():
        return
    corpo = ABA_DE_TESTE + u"""
 await _abrir();
 ndInverter(); ndModo('minip'); _carregou(); ndJanela('osso'); _carregou();
 var la=document.getElementById('nd_laje'); la.value='40'; la.disparar('change'); _carregou();
 ndAngulo(30,10); _carregou();
 ndOssoAlternar(); _carregou();
 var p0=document.getElementById('nd_pos0'); p0.value='20'; p0.disparar('input');
 var r={mudou:{inv:ND.inverter, modo:ND.modo, laje:ND.laje, jan:ND.jan, lao:ND.lao,
   osso:ND.osso, plano:ND.planos[0]}};
 ndEscolher('B2'); await _esperar(); _carregou(); await _esperar();
 r.nova={inv:ND.inverter, modo:ND.modo, laje:ND.laje, jan:ND.jan, lao:ND.lao, cra:ND.cra,
   osso:ND.osso, plano:ND.planos[0], pos0:document.getElementById('nd_pos0').value,
   palco:document.getElementById('nd_palco').className,
   lajev:document.getElementById('nd_lajev').textContent, src:_proj().src};
 ndEscolher('B1'); await _esperar(); _carregou(); await _esperar();
 r.volta={inv:ND.inverter, modo:ND.modo, laje:ND.laje, jan:ND.jan, lao:ND.lao,
   osso:ND.osso};
 pronto(r);
"""
    d = _encenar(corpo)
    m, n, v = (d.get(k) or {} for k in ("mudou", "nova", "volta"))
    checar(u"na primeira série, tudo foi mudado (inverter, MinIP, laje, janela, "
           u"ângulo, osso, plano)",
           m == {u"inv": False, u"modo": u"minip", u"laje": 40, u"jan": u"osso",
                 u"lao": 30, u"osso": False, u"plano": 0.2} and not d.get("erros"),
           u"%s %s" % (m, d.get("erros")))
    checar(u"a outra série abre invertida, em MIP, com todo o volume",
           n.get("inv") is True and n.get("modo") == u"mip" and n.get("laje") == 0
           and u"inv" in (n.get("palco") or u"")
           and n.get("lajev") == u"todo o volume", str(n)[:200])
    checar(u"  na janela angio, em LAO 0 / CRA 0, com o osso fora",
           n.get("jan") == u"angio" and n.get("lao") == 0 and n.get("cra") == 0
           and n.get("osso") is True, str(n)[:200])
    checar(u"  e os planos do MPR voltam ao meio", n.get("plano") == 0.5
           and n.get("pos0") == u"50", str(n)[:200])
    src = n.get("src") or u""
    checar(u"  e a projeção é pedida assim",
           u"lao=0&cra=0&modo=mip&janela=angio" in src and u"osso=1" in src
           and u"laje=" not in src, src[-140:])
    checar(u"a primeira, reaberta, volta com o estado salvo DELA",
           v == {u"inv": False, u"modo": u"minip", u"laje": 40, u"jan": u"osso",
                 u"lao": 30, u"osso": False}, str(v))
    iscado = _encenar(corpo, ajuste=lambda js: js.replace(
        u" ndPadroes();\n [0,1,2].forEach(function(eixo){ var r=ndEl('nd_pos'+eixo)",
        u" [0,1,2].forEach(function(eixo){ var r=ndEl('nd_pos'+eixo)"))
    checar(u"  isca: sem a volta aos padrões, a outra série herda o inverter desligado",
           (iscado.get("nova") or {}).get("inv") is False, str(iscado.get("nova"))[:120])


def teste_a_marcacao_volta_pela_chave_da_serie():
    secao(u"a marcação volta pela chave da série (não pelo bilhete), e "
          u"«Tentar de novo» devolve o Guardar")
    if _sem_node():
        return
    corpo = ABA_DE_TESTE + u"""
 _RESP['/api/nidus/abrir']=function(u, op){ var f=_padrao(u, op); f.chave='KFIXA'; return f };
 await _abrir();
 ND.pontos=[[10,10],[60,10],[60,60],[10,60]]; ndGuardar(); await _esperar();
 var r={chaves:Object.keys(window.sessionStorage._d)};
 ndAbrirSerie({bilhete:'B9', origem:'pasta', rotulo:'a mesma serie, outro processo'});
 await _esperar(); _carregou(); await _esperar();
 r.outro={b:ND.b, guardadas:ND.guardadas.length, msg:_msg()};
 ndAngulo(60,20); _falhou_img(); await _esperar(); _falhou_img(); await _esperar();
 r.trava={aberta:ND.aberta, guardar:document.getElementById('nd_bt_guardar').disabled,
   retomar:!document.getElementById('nd_bt_retomar').hidden, msg:_msg(),
   salvo_lao:JSON.parse(window.sessionStorage.getItem('radai_nidus_v2_KFIXA')||'{}').lao};
 ndRetomar(); await _esperar(); _carregou(); await _esperar();
 r.volta={aberta:ND.aberta, guardar:document.getElementById('nd_bt_guardar').disabled,
   retomar:!document.getElementById('nd_bt_retomar').hidden, lao:ND.lao,
   guardadas:ND.guardadas.length};
 ND.pontos=[[20,20],[80,20],[80,80]]; ndGuardar(); await _esperar();
 r.depois={guardadas:ND.guardadas.length,
   salvas:JSON.parse(window.sessionStorage.getItem('radai_nidus_v2_KFIXA')||'{"guardadas":[]}').guardadas.length};
 pronto(r);
"""
    d = _encenar(corpo)
    o, t, v, dp = (d.get(k) or {} for k in ("outro", "trava", "volta", "depois"))
    checar(u"o estado salvo mora na chave da série, e não no bilhete",
           d.get("chaves") == [u"radai_nidus_v2_KFIXA"] and not d.get("erros"),
           u"%s %s" % (d.get("chaves"), d.get("erros")))
    checar(u"outro bilhete da mesma série (servidor reiniciado) traz a marcação de volta",
           o.get("b") == u"B9" and o.get("guardadas") == 1
           and u"marcação salva" in (o.get("msg") or u""), str(o))
    checar(u"duas falhas seguidas travam a série, com o Guardar apagado",
           t.get("aberta") is False and t.get("guardar") is True, str(t)[:160])
    checar(u"  e a tela oferece «Tentar de novo», e diz", t.get("retomar") is True
           and u"Tentar de novo" in (t.get("msg") or u""), str(t)[:200])
    checar(u"  e o salvo leva o último ângulo BOM, e não o que falhou",
           t.get("salvo_lao") == 0, str(t.get("salvo_lao")))
    checar(u"«Tentar de novo» reabre a série: o Guardar volta, a marcação também",
           v.get("aberta") is True and v.get("guardar") is False
           and v.get("retomar") is False and v.get("guardadas") == 1
           and v.get("lao") == 0, str(v))
    checar(u"  e guardar depois do erro recuperado funciona e fica salvo",
           dp.get("guardadas") == 2 and dp.get("salvas") == 2, str(dp))
    iscado = _encenar(corpo, ajuste=lambda js: js.replace(
        u"function ndChaveSalva(){ return 'radai_nidus_v2_'+ND.chave }",
        u"function ndChaveSalva(){ return 'radai_nidus_v2_'+ND.b }"))
    checar(u"  isca: a chave pelo bilhete perde a marcação no outro bilhete",
           (iscado.get("outro") or {}).get("guardadas") == 0,
           str(iscado.get("outro"))[:120])
    iscado2 = _encenar(corpo, ajuste=lambda js: js.replace(
        u" ndAbrirSerie(ND.ultima);\n}", u" return;\n}"))
    checar(u"  isca: sem «Tentar de novo», o Guardar fica apagado",
           (iscado2.get("volta") or {}).get("guardar") is True,
           str(iscado2.get("volta"))[:120])


def teste_a_fila_parada_espera_o_iniciar():
    secao(u"«Segmentar primeiro»: a fila parada espera o «Iniciar», e a tela diz")
    if _sem_node():
        return
    corpo = u"""
 _RESP['/api/nidus/abrir']=function(u, op){ var f=_padrao(u, op);
  f.osso={tem:false, motivo:'esta série ainda não tem segmentação do ContourLab: o osso continua na projeção'};
  return f };
 _RESP['/api/nidus/osso']={osso:{tem:false, motivo:'esta série ainda não tem segmentação do ContourLab: o osso continua na projeção'}};
 var EST={rodando:false, estado:'esperando'};
 _RESP['/api/fila/estado']=function(u, op){
  if(EST.cai) throw new Error('rede fora');
  var d={ok:true, cartoes:EST.sumiu?[]:[{id:'c1', estado:EST.estado, posicao:1}]};
  if(EST.rodando!==undefined) d.rodando=EST.rodando;
  EST.pedido=op?op.body:null;
  return d };
 await _abrir();
 ND_FILA_A_CADA_MS=0;
 var r={};
 ndSegmentar(); await _esperar(4);
 r.parada={msg:_msg(), txt:document.getElementById('nd_osso_txt').innerHTML,
   pedido:EST.pedido};
 EST.rodando=true; await _esperar(4);
 r.rodando={msg:_msg()};
 EST.estado='rodando'; await _esperar(4);
 r.dela={msg:_msg()};
 delete EST.rodando; EST.estado='esperando'; await _esperar(4);
 r.sem_campo={msg:_msg(), vigiando:!!ND.fila};
 ND_FILA_TENTATIVAS=ND.fila.tentativas+2; await _esperar(8);
 r.teto={msg:_msg(), vigiando:!!ND.fila};
 EST.cai=true; ndSegmentar(); await _esperar(2);
 r.cai_um={msg:_msg(), vigiando:!!ND.fila};
 EST.cai=false; await _esperar(3);
 r.voltou={vigiando:!!ND.fila, falhas:ND.fila?ND.fila.falhas:-1};
 EST.cai=true; await _esperar(14);
 r.caiu={msg:_msg(), vigiando:!!ND.fila};
 EST.cai=false; EST.sumiu=true; ndSegmentar(); await _esperar(8);
 r.sumiu={msg:_msg(), vigiando:!!ND.fila};
 pronto(r);
"""
    d = _encenar(corpo)
    p = d.get("parada") or {}
    checar(u"com a fila parada, a tela diz que o cartão espera o «Iniciar»",
           u"«Iniciar»" in (p.get("msg") or u"") and u"Iniciar" in (p.get("txt") or u"")
           and not d.get("erros"), u"%s | %s" % (p.get("msg"), d.get("erros")))
    checar(u"  e pergunta só pelo próprio cartão", (p.get("pedido") or u"") == u'{"ids":["c1"]}',
           p.get("pedido"))
    checar(u"com a fila rodando, diz que entra na vez dela",
           u"a fila está rodando" in ((d.get("rodando") or {}).get("msg") or u""),
           (d.get("rodando") or {}).get("msg"))
    checar(u"com o cartão rodando, diz que está rodando",
           u"está rodando" in ((d.get("dela") or {}).get("msg") or u""),
           (d.get("dela") or {}).get("msg"))
    sc = d.get("sem_campo") or {}
    checar(u"sem o campo `rodando`, a tela não inventa a situação (segue acompanhando)",
           sc.get("vigiando") is True and u"Iniciar" not in (sc.get("msg") or u"")
           and u"não responde" not in (sc.get("msg") or u""), str(sc))
    te = d.get("teto") or {}
    checar(u"no teto do acompanhamento, com a fila respondendo, NÃO diz «não responde»",
           te.get("vigiando") is False and u"continua na fila" in (te.get("msg") or u"")
           and u"não responde" not in (te.get("msg") or u""), str(te))
    checar(u"uma falha de rede sozinha não encerra o acompanhamento",
           (d.get("cai_um") or {}).get("vigiando") is True
           and u"não responde" not in ((d.get("cai_um") or {}).get("msg") or u""),
           str(d.get("cai_um")))
    checar(u"  e a resposta seguinte zera a conta das falhas",
           (d.get("voltou") or {}).get("falhas") == 0, str(d.get("voltou")))
    checar(u"falhas seguidas, aí sim: «a fila não responde»",
           (d.get("caiu") or {}).get("vigiando") is False
           and u"a fila não responde" in ((d.get("caiu") or {}).get("msg") or u""),
           str(d.get("caiu")))
    checar(u"o cartão que sai da fila sem osso novo é dito",
           u"saiu da fila" in ((d.get("sumiu") or {}).get("msg") or u""),
           str(d.get("sumiu")))
    iscado = _encenar(corpo, ajuste=lambda js: js.replace(
        u"(d && typeof d.rodando==='boolean') ? d.rodando : null", u"null"))
    checar(u"  isca: sem ler o `rodando`, o «Iniciar» não é dito",
           u"Iniciar" not in ((iscado.get("parada") or {}).get("msg") or u""))


def teste_segmentar_substitui_a_entrega():
    secao(u"série com entrega sem osso: AUTO substitui a entrega, com confirmação")
    if _sem_node():
        return
    corpo = u"""
 _RESP['/api/nidus/abrir']=function(u, op){ var f=_padrao(u, op);
  f.osso={tem:false, motivo:'a entrega desta série não tem osso que sirva para a projeção: o osso continua na projeção', entrega:'OAR_Fast'};
  return f };
 _RESP['/api/nidus/osso']={osso:{tem:false, motivo:'x', entrega:'OAR_Fast'}};
 await _abrir();
 var r={txt:document.getElementById('nd_segmentar_txt').textContent,
   sg:!document.getElementById('nd_segmentar').hidden,
   osso:document.getElementById('nd_osso_txt').innerHTML};
 var antes=_FETCHES.length;
 ndSegmentar(); await _esperar();
 r.sem_painel={novas:_urls(antes), msg:_msg()};
 var pedido=null;
 window.uiConfirmar=function(o){ pedido=o };
 ndSegmentar(); await _esperar();
 r.painel={novas:_urls(antes), titulo:pedido?pedido.titulo:'', html:pedido?pedido.html:'',
   ok:pedido?pedido.ok:''};
 if(pedido) pedido.aoSim(); await _esperar();
 var seg=_FETCHES.filter(function(f){ return f.url.indexOf('/api/nidus/segmentar')>=0 });
 r.corpo=seg.length?JSON.parse(seg[seg.length-1].op.body):null;
 pronto(r);
"""
    d = _encenar(corpo)
    checar(u"o botão diz que segmentar em AUTO substitui a entrega",
           d.get("txt") == u"Segmentar em AUTO (substitui a entrega)" and d.get("sg")
           and not d.get("erros"), u"%s %s" % (d.get("txt"), d.get("erros")))
    checar(u"  e o lado diz qual é a entrega", u"OAR_Fast" in (d.get("osso") or u""),
           d.get("osso"))
    sp = d.get("sem_painel") or {}
    checar(u"sem a confirmação, nada vai para a fila",
           not [u for u in sp.get("novas") or [] if u"/api/nidus/segmentar" in u]
           and u"confirmação" in (sp.get("msg") or u""), str(sp))
    pn = d.get("painel") or {}
    checar(u"a confirmação diz o que vai ser substituído, e espera o sim",
           not [u for u in pn.get("novas") or [] if u"/api/nidus/segmentar" in u]
           and u"Substituir" in (pn.get("titulo") or u"")
           and u"OAR_Fast" in (pn.get("html") or u"")
           and u"substitui a entrega" in (pn.get("html") or u""), str(pn)[:200])
    checar(u"  e o sim manda o pedido com «substituir»",
           (d.get("corpo") or {}).get("substituir") is True, str(d.get("corpo")))

    corpo2 = u"""
 _RESP['/api/nidus/abrir']=function(u, op){ var f=_padrao(u, op);
  f.osso={tem:false, motivo:'esta série ainda não tem segmentação do ContourLab: o osso continua na projeção'};
  return f };
 _RESP['/api/nidus/osso']={osso:{tem:false, motivo:'esta série ainda não tem segmentação do ContourLab: o osso continua na projeção'}};
 await _abrir();
 var r={txt1:document.getElementById('nd_segmentar_txt').textContent};
 ndSegmentar(); await _esperar(10);
 r.depois={msg:_msg(), txt:document.getElementById('nd_segmentar_txt').textContent,
   sg:!document.getElementById('nd_segmentar').hidden};
 window.uiConfirmar=function(o){ r.titulo=o.titulo; o.aoSim() };
 ndSegmentar(); await _esperar(4);
 r.corpos=_FETCHES.filter(function(f){ return f.url.indexOf('/api/nidus/segmentar')>=0 })
  .map(function(f){ return JSON.parse(f.op.body) });
 pronto(r);
"""
    d2 = _encenar(corpo2)
    cs = d2.get("corpos") or []
    checar(u"série sem entrega: o primeiro pedido vai direto, sem «substituir»",
           d2.get("txt1") == u"Segmentar primeiro (AUTO)" and cs[:1]
           and u"substituir" not in cs[0], str(cs)[:160])
    dep = d2.get("depois") or {}
    checar(u"a fila fecha o cartão e o osso não aparece: a tela diz, e não se cala",
           u"a fila fechou o cartão" in (dep.get("msg") or u"") and dep.get("sg") is True
           and dep.get("txt") == u"Segmentar em AUTO (substitui a entrega)", str(dep))
    checar(u"  e o pedido seguinte, confirmado, vai com «substituir»",
           len(cs) == 2 and cs[1].get("substituir") is True and d2.get("titulo"),
           str(cs)[:160])
    iscado = _encenar(corpo, ajuste=lambda js: js.replace(
        u" if(substituir) corpo.substituir=true;\n", u"\n"))
    checar(u"  isca: o pedido sem «substituir» é acusado",
           (iscado.get("corpo") or {}).get("substituir") is not True)


def teste_as_linhas_que_falham_param():
    secao(u"as linhas que falham: uma nova tentativa, e depois o aviso")
    if _sem_node():
        return
    corpo = u"""
 await _abrir();
 _RESP['/api/nidus/linhas']={erro:"ValueError: axes don't match array"};
 var antes=_FETCHES.length;
 ND.pontos=[[10,10],[60,10],[60,60],[10,60]]; ndGuardar(); await _esperar(20);
 var tubos=_urls(antes).filter(function(u){ return u.indexOf('/api/nidus/tubos')>=0 }).length;
 pronto({tubos:tubos, msg:_msg(), sessao:ND.sessao||null,
   cruzar:!document.getElementById('nd_bt_cruzar').hidden,
   linhas:document.getElementById('nd_lin0').innerHTML});
"""
    d = _encenar(corpo)
    checar(u"a sessão é refeita UMA vez (dois pedidos de tubos, e não um laço)",
           d.get("tubos") == 2 and not d.get("erros"),
           u"%s %s" % (d.get("tubos"), d.get("erros")))
    checar(u"  e a segunda falha avisa, com o motivo",
           u"nova tentativa" in (d.get("msg") or u"") and u"axes" in (d.get("msg") or u""),
           d.get("msg"))
    checar(u"  e oferece «Cruzar de novo», sem linhas velhas na tela",
           d.get("cruzar") is True and not d.get("sessao") and d.get("linhas") == u"",
           str(d)[:160])
    iscado = _encenar(corpo, ajuste=lambda js: js.replace(
        u"ND.refeitas<1", u"ND.refeitas<3"))
    checar(u"  isca: mais tentativas caladas são acusadas",
           iscado.get("tubos") != 2, str(iscado.get("tubos")))


def teste_o_acervo_abre_por_post_com_a_origem():
    secao(u"a tela abre por POST, dizendo a origem (o acervo usa o resolvedor da tabela)")
    if _sem_node():
        return
    d = _encenar(u"""
 _tentar('carga', function(){ if(_CARGA) _CARGA() });
 await _esperar();
 ndAbrirDoAcervo({bilhete:'BA', date:'20261014', pid:'X1', modalidade:'CT'});
 await _esperar(); _carregou(); await _esperar();
 _tentar('listar', function(){ ndListar('X') }); await _esperar();
 ndEscolher('B1'); await _esperar(); _carregou(); await _esperar();
 var ab=_FETCHES.filter(function(f){ return f.url.indexOf('/api/nidus/abrir')>=0 })
  .map(function(f){ return {url:f.url, metodo:f.op?f.op.method:'', corpo:JSON.parse(f.op.body)} });
 pronto({abrir:ab, forma:_FETCHES.some(function(f){ return f.url.indexOf('/api/nidus/forma')>=0 }),
   src:_proj().src});
""")
    ab = d.get("abrir") or []
    checar(u"o acervo abre por POST com a origem «acervo» e só o bilhete",
           ab[:1] and ab[0]["metodo"] == u"POST" and ab[0]["url"] == u"/api/nidus/abrir"
           and ab[0]["corpo"] == {u"b": u"BA", u"origem": u"acervo"}
           and not d.get("erros"), str(ab)[:200])
    checar(u"a pasta abre com a origem «pasta»", len(ab) == 2
           and ab[1]["corpo"] == {u"b": u"B1", u"origem": u"pasta"}, str(ab)[:200])
    checar(u"  e a abertura não passa mais pelo GET da forma", d.get("forma") is False)
    src = d.get("src") or u""
    checar(u"a projeção leva o número do pedido e a aba (para cancelar a velha)",
           re.search(r"[?&]n=\d+&t=[a-z0-9]+", src) is not None, src[:120])


def _geometria_obliqua():
    import json
    import radai_nidus as N
    img = _serie_obliqua()
    serie = N.abrir(img, "CT")
    return serie, json.dumps(N.geometria_da_serie(serie))


def teste_a_pegada_do_js_e_a_do_python():
    secao(u"a pegada da caixa no JS é a do Python (série oblíqua)")
    import radai_nidus as N
    if _sem_node():
        return
    serie, geo = _geometria_obliqua()
    caixa = [0.2, 0.55, 0.3, 0.8, 0.15, 0.6]
    casos = [(0, 0), (-35, 20), (60, -25), (170, 85)]
    corpo = (u" await _abrir(); ND.geo=%s; ND.lado=1024;\n"
             u" var cx=%s, frac=ndM4(ND.geo.para_caixa, ndCantos(cx)[7]);\n"
             u" pronto({pts:%s.map(function(a){ return ndPegada(cx, a[0], a[1]) }),"
             u" frac:frac});"
             % (geo, str(caixa), str([list(c) for c in casos])))
    d = _encenar(corpo)
    fr = d.get("frac") or [9, 9, 9]
    checar(u"a matriz do recorte do 3D (LPS -> fração da caixa) leva o canto da caixa "
           u"de volta à fração dele", max(abs(fr[0] - caixa[1]), abs(fr[1] - caixa[3]),
                                         abs(fr[2] - caixa[5])) < 1e-9, str(fr))
    pior = 0.0
    for (lao, cra), pts in zip(casos, d.get("pts") or []):
        py = N.pegada_da_caixa(serie, caixa, lao, cra, 1024)
        for a, b in zip(pts, py):
            pior = max(pior, abs(a[0] - b[0]), abs(a[1] - b[1]))
    checar(u"os oito cantos iguais nas quatro incidências (erro %.1e px)" % pior,
           len(d.get("pts") or []) == 4 and pior < 1e-6 and not d.get("erros"),
           str(d.get("erros"))[:120])
    isca = _encenar(corpo, ajuste=lambda js: js.replace(
        u"ND.lado-0.5-(q[0]*b.u[0]", u"ND.lado-0.5+(q[0]*b.u[0]"))
    p2 = 0.0
    for (lao, cra), pts in zip(casos, isca.get("pts") or []):
        for a, b in zip(pts, N.pegada_da_caixa(serie, caixa, lao, cra, 1024)):
            p2 = max(p2, abs(a[1] - b[1]))
    checar(u"  isca: o alto da tela com o sinal trocado é acusado", p2 > 5.0,
           u"%.1f" % p2)


def teste_o_veu_e_acompanhar_a_caixa():
    secao(u"o véu fora da caixa, a pegada tracejada e «Acompanhar a caixa»")
    if _sem_node():
        return
    _serie, geo = _geometria_obliqua()
    corpo = (u""" await _abrir(); ND.geo=%s; ND.lado=1024;
 ND.caixa=[0.3,0.6,0.35,0.65,0.3,0.6]; ND.caixaOn=true;
 ndPintarPegada(); ndEnquadrar();
 var r={d:document.getElementById('nd_fora').getAttribute('d'),
   peg:document.getElementById('nd_pegada').getAttribute('points'),
   k:ND.zoom.k, seguir:ND.seguir};
 ndZoomPasso(1); r.depoisZoom={seguir:ND.seguir,
   peg:document.getElementById('nd_pegada').getAttribute('points')};
 ndSeguirAlternar(); r.religou={seguir:ND.seguir, k:ND.zoom.k};
 ndZoomAjustar(); r.ajustar={seguir:ND.seguir, k:ND.zoom.k};
 ndCaixaLimpar(); r.limpo={d:document.getElementById('nd_fora').getAttribute('d')};
 pronto(r);""" % geo)
    d = _encenar(corpo)
    checar(u"com caixa, o fora dela fica velado (o véu cobre a tela menos a pegada)",
           (d.get("d") or u"").startswith(u"M0,0H1024V1024H0Z M") and not d.get("erros"),
           str(d.get("erros") or d.get("d"))[:120])
    checar(u"acompanhando, a projeção enquadra a pegada (zoom > 1) e não traceja",
           (d.get("k") or 0) > 1.2 and d.get("peg") == u"" and d.get("seguir") is True,
           str(d)[:160])
    dz = d.get("depoisZoom") or {}
    checar(u"o zoom manual desliga o acompanhar, e a pegada aparece tracejada",
           dz.get("seguir") is False and (dz.get("peg") or u"").count(u",") >= 4, str(dz))
    checar(u"«Acompanhar a caixa» religa e reenquadra",
           (d.get("religou") or {}).get("seguir") is True)
    checar(u"«Ajustar à tela» volta ao inteiro e para de acompanhar",
           (d.get("ajustar") or {}).get("seguir") is False
           and (d.get("ajustar") or {}).get("k") == 1)
    checar(u"sem caixa, nada é velado", (d.get("limpo") or {}).get("d") == u"")
    isca = _encenar(corpo, ajuste=lambda js: js.replace(
        u"function ndSeguirDesligar(){\n if(!ND.seguir) return;",
        u"function ndSeguirDesligar(){\n return;"))
    checar(u"  isca: o zoom que não desliga o acompanhar é acusado",
           (isca.get("depoisZoom") or {}).get("seguir") is True)


def teste_a_previa_durante_o_arraste():
    secao(u"a prévia em baixa resolução durante o arraste; o lápis espera a cheia")
    import radai_nidus_screen as S
    if _sem_node():
        return
    corpo = u""" await _abrir();
 var r=document.getElementById('nd_lao_r');
 r.value='-40'; r.disparar('input');
 var a={src:_proj().src, previa:ND.previa, proj:ND.projetando, lao:ND.lao,
   estado:document.getElementById('nd_estado_t').textContent};
 _circulo(200,200,60,30); _svg().disparar('mouseup', _ev(260,200));
 a.tracou=ND.pontos.length; a.msg=_msg();
 r.disparar('change'); _carregou(); await _esperar();
 var b={src:_proj().src, previa:ND.previa, proj:ND.projetando, lao:ND.lao,
   estado:document.getElementById('nd_estado_t').textContent};
 _circulo(200,200,60,30); _svg().disparar('mouseup', _ev(260,200));
 b.tracou=ND.pontos.length;
 pronto({a:a, b:b});"""
    d = _encenar(corpo)
    a, b = d.get("a") or {}, d.get("b") or {}
    checar(u"arrastando, a projeção vem em %d e diz que é prévia" % S.LADO_DA_PREVIA,
           (u"lado=%d" % S.LADO_DA_PREVIA) in (a.get("src") or u"") and a.get("previa") is True
           and a.get("lao") == 0 and u"prévia" in (a.get("estado") or u"")
           and not d.get("erros"), str(a)[:200])
    checar(u"  e o lápis recusa até a cheia chegar, e diz por quê",
           a.get("tracou") == 0 and u"aguarde a projeção" in (a.get("msg") or u""), str(a))
    checar(u"soltando, a projeção cheia (%d) chega e o lápis volta" % S.LADO_DA_TELA,
           (u"lado=%d" % S.LADO_DA_TELA) in (b.get("src") or u"") and b.get("previa") is False
           and b.get("lao") == -40 and b.get("tracou", 0) >= 8
           and u"cheia" in (b.get("estado") or u""), str(b)[:200])
    isca = _encenar(corpo, ajuste=lambda js: js.replace(
        u"ndUrlDaProjecao(ND.ver.lao, ND.ver.cra, ND_LADO_PREVIA)",
        u"ndUrlDaProjecao(ND.ver.lao, ND.ver.cra, ND.lado)"))
    checar(u"  isca: a prévia pedida na resolução cheia é acusada",
           (u"lado=%d" % S.LADO_DA_PREVIA) not in ((isca.get("a") or {}).get("src") or u""))


def teste_o_mapa_de_incidencias():
    secao(u"o mapa de incidências: encaixa nas oito, Shift tira o encaixe, setas giram")
    import radai_nidus as N
    if _sem_node():
        return
    corpo = u""" await _abrir();
 ND_PAD.W=268; ND_PAD.H=120; ndPintarPad();
 var p=ndPadXY(90,0), r={};
 ndPadPonteiro({clientX:p[0]+4, clientY:p[1]+3, shiftKey:false});
 r.encaixa=[ND.ver.lao, ND.ver.cra, ND.lao];
 ndPadPonteiro({clientX:p[0]+4, clientY:p[1]+3, shiftKey:true});
 r.livre=[ND.ver.lao, ND.ver.cra];
 ndSoltarAngulo(); r.soltou=[ND.lao, ND.cra];
 r.svg=document.getElementById('nd_pad').innerHTML;
 pronto(r);"""
    d = _encenar(corpo)
    perfil_e = dict((n, (a, b)) for n, a, b in N.INCIDENCIAS)[u"Perfil E"]
    checar(u"perto do Perfil E (LAO 90) o mapa encaixa nele, em prévia",
           d.get("encaixa") == [perfil_e[0], perfil_e[1], 0] and not d.get("erros"),
           str(d.get("encaixa")) + str(d.get("erros"))[:80])
    checar(u"  com Shift não encaixa", d.get("livre") not in (None, [90, 0]),
           str(d.get("livre")))
    checar(u"soltar gira de verdade", d.get("soltou") == d.get("livre"),
           str(d.get("soltou")))
    checar(u"o mapa desenha as oito incidências e a atual",
           (d.get("svg") or u"").count(u'class="pre') == 8
           and u'class="atual"' in (d.get("svg") or u""))


def teste_o_arraste_do_3d_e_da_sala():
    secao(u"o arraste: no 3D segue o objeto (direita = RAO, baixo = CRA); na sala move o arco")
    if _sem_node():
        return
    corpo = u""" await _abrir();
 var A={lao:0, cra:0};
 pronto({tres_dir:nd3AnguloDoArrasto(A, 40, 0, false), tres_baixo:nd3AnguloDoArrasto(A, 0, 40, false),
   sala_dir:nd3AnguloDoArrasto(A, 40, 0, true), sala_cima:nd3AnguloDoArrasto(A, 0, -40, true)});"""
    d = _encenar(corpo)
    checar(u"no 3D, para a direita vai para RAO (o que está de frente vai à direita)",
           (d.get("tres_dir") or [0])[0] < 0 and not d.get("erros"), str(d)[:160])
    checar(u"no 3D, para baixo vai para CRA (o alto da cabeça vem para a frente)",
           (d.get("tres_baixo") or [0, 0])[1] > 0)
    checar(u"na sala, para a direita o arco vai para LAO e para cima, para CRA",
           (d.get("sala_dir") or [0])[0] > 0 and (d.get("sala_cima") or [0, 0])[1] > 0)
    isca = _encenar(corpo, ajuste=lambda js: js.replace(
        u"return [A.lao-dx*0.5, A.cra+dy*0.4];", u"return [A.lao+dx*0.5, A.cra+dy*0.4];"))
    checar(u"  isca: o sinal antigo (direita = LAO no 3D) é acusado",
           (isca.get("tres_dir") or [0])[0] > 0)


def teste_a_chave_da_aba_tem_a_versao_da_convencao():
    secao(u"o desenho salvo na convenção de antes não volta na nova (a chave muda)")
    if _sem_node():
        return
    corpo = ABA_DE_TESTE + u"""
 window.sessionStorage.setItem('radai_nidus_KVELHA', JSON.stringify({lao:90, cra:0,
   guardadas:[{lao:90, cra:0, pontos:[[1,1],[50,1],[50,50]]}], pontos:[]}));
 _RESP['/api/nidus/abrir']=function(u, op){ var f=_padrao(u, op); f.chave='KVELHA'; return f };
 await _abrir();
 pronto({guardadas:ND.guardadas.length, lao:ND.lao, chave:ndChaveSalva()});"""
    d = _encenar(corpo)
    checar(u"a marcação da chave velha não é aplicada (outra matriz, outro tubo)",
           d.get("guardadas") == 0 and d.get("lao") == 0 and not d.get("erros"),
           str(d)[:160])
    checar(u"  e a chave nova diz a versão", d.get("chave") == u"radai_nidus_v2_KVELHA",
           str(d.get("chave")))
    isca = _encenar(corpo, ajuste=lambda js: js.replace(
        u"return 'radai_nidus_v2_'+ND.chave", u"return 'radai_nidus_'+ND.chave"))
    checar(u"  isca: com a chave de antes, o desenho velho voltaria",
           isca.get("guardadas") == 1, str(isca.get("guardadas")))


def teste_o_3d_e_a_sala_na_pagina():
    secao(u"o 3D da caixa e a sala: os controles, o canto e o caminho sem WebGL")
    import radai_nidus_screen as S
    p = S.pagina()
    for marca, o_que in (('id="nd_gl"', u"o quadro do 3D"),
                         ('id="nd_detector"', u"«Vista do detector»"),
                         ('id="nd_atraves"', u"«Ver através»"),
                         ('id="nd_sala_padrao"', u"«Sala na vista padrão»"),
                         ('id="nd_pad"', u"o mapa de incidências"),
                         ('id="nd_seguir"', u"«Acompanhar a caixa»"),
                         ('<select id="nd_vista" data-ui-seg', u"o segmentado «3D da caixa | Sala» da casca")):
        checar(u"a tela tem %s" % o_que, marca in p)
    checar(u"o botão de cada incidência leva o ângulo (dado, sem tradução)",
           u'<small translate="no">RAO 90</small>' in p
           and u'<small translate="no">CRA 30</small>' in p)
    checar(u"«Guardar incidência» apagado diz por quê (uiPorQue)",
           u"window.uiPorQue('Guardar incidência'" in S.JS)
    checar(u"a sala é desenhada em código (nenhum modelo de terceiro)",
           u".glb" not in p.lower() and u"gltf" not in p.lower())
    if _sem_node():
        return
    d = _encenar(u""" await _abrir();
 var r={canto:document.getElementById('nd_cant').innerHTML, gl:!!ND3.gl};
 pronto(r);""")
    checar(u"sem WebGL o canto diz, e o resto da tela abre",
           d.get("gl") is False and u"WebGL" in (d.get("canto") or u"")
           and not d.get("erros"), str(d)[:160])


def teste_as_malhas_da_caixa_pela_rota():
    secao(u"o 3D da caixa vem do servidor por bilhete, só vaso, osso e pele")
    import asyncio
    import struct
    import radai_nidus as N
    rotas = _rotas_montadas()
    checar(u"as rotas do 3D estão montadas", "/api/nidus/malhas" in rotas
           and "/api/nidus/malha" in rotas)
    img, _m = _vaso_sintetico()
    lidas, soltar = _com_dubles(img)
    try:
        d = asyncio.run(rotas["/api/nidus/malhas"](_Pedido(
            {"b": u"V1", "caixa": u"0.1,0.9,0.1,0.9,0.1,0.9"})))
        sem = asyncio.run(rotas["/api/nidus/malhas"](_Pedido({"b": u"V1", "caixa": u""})))
    finally:
        soltar()
    quais = [x.get("qual") for x in d.get("malhas") or []]
    checar(u"a resposta traz só vaso, osso e pele", quais == list(N.QUAIS_DA_MALHA)
           and not d.get("erro"), str(d)[:160])
    vaso = [x for x in d.get("malhas") or [] if x.get("qual") == u"vaso"]
    m = vaso[0].get("m") if vaso else u""
    r = rotas["/api/nidus/malha"](m=m)
    corpo = getattr(r, "body", b"") or b""
    ok = len(corpo) > 84 and 84 + 50 * struct.unpack("<I", corpo[80:84])[0] == len(corpo)
    checar(u"a malha do vaso chega em STL pelo bilhete dela", ok,
           u"%d bytes" % len(corpo))
    checar(u"  e o cabeçalho diz que é de visualização, não aprovada",
           b"UNAPPROVED" in corpo[:80])
    checar(u"sem caixa, o servidor recusa com o motivo, sem montar o volume inteiro",
           sem.get("erro") == N.SEM_CAIXA_PARA_O_3D and not sem.get("malhas"))
    r404 = rotas["/api/nidus/malha"](m=u"nao_existe")
    checar(u"bilhete que saiu da memória responde 404 com o motivo",
           getattr(r404, "status_code", 0) == 404)
    fonte_tela = sem_prosa(fonte("radai_nidus_screen.py"))
    checar(u"nenhuma rota leva a interseção ao 3D",
           u"intersecao(" not in fonte_tela.split(u"def _malhas_da_caixa")[-1].split(u"def _tubo_da_incidencia")[0])


TELA = (teste_o_javascript_nao_le_nome_solto,
        teste_a_tela_acorda_e_pede_as_series,
        teste_a_tabela_do_acervo_no_lugar_do_seletor,
        teste_o_popup_e_o_cartao_carregar_serie,
        teste_guardar_dispara_a_retroprojecao,
        teste_o_lapis_traca_e_afina,
        teste_so_o_lapis,
        teste_os_padroes_de_abertura,
        teste_as_barras_de_angulo,
        teste_a_lista_diz_rao_e_cau,
        teste_girar_guarda_o_traco,
        teste_serie_que_nao_abre_trava_a_tela,
        teste_o_erro_volta_ao_estado_bom,
        teste_o_brilho_cobre_projecao_e_mpr,
        teste_o_osso_na_tela,
        teste_as_incidencias_se_somam_nos_tres_planos,
        teste_serie_nova_nao_herda_a_sessao,
        teste_o_passo_do_detector_aparece,
        teste_a_tela_diz_a_escala_da_rm,
        teste_serie_nova_volta_aos_padroes,
        teste_a_marcacao_volta_pela_chave_da_serie,
        teste_a_fila_parada_espera_o_iniciar,
        teste_segmentar_substitui_a_entrega,
        teste_as_linhas_que_falham_param,
        teste_o_acervo_abre_por_post_com_a_origem,
        teste_a_previa_durante_o_arraste,
        teste_o_mapa_de_incidencias,
        teste_o_arraste_do_3d_e_da_sala,
        teste_a_chave_da_aba_tem_a_versao_da_convencao,
        teste_o_3d_e_a_sala_na_pagina)


def _rotas_montadas():
    import radai_nidus_screen as S

    class _App(object):
        def __init__(self):
            self.rotas = {}

        def _reg(self, caminho):
            def dec(f):
                self.rotas[caminho] = f
                return f
            return dec

        def get(self, caminho, **k):
            return self._reg(caminho)

        def post(self, caminho, **k):
            return self._reg(caminho)

    a = _App()
    S.montar(a)
    return a.rotas


def teste_a_rota_da_forma_calcula_o_passo():
    secao(u"a rota da forma calcula o passo, e ele vem da lib")
    import math
    import engine
    import radai_thumbnail
    import radai_nidus as N
    import radai_nidus_screen as S

    f = _rotas_montadas().get("/api/nidus/forma")
    checar(u"a rota da forma esta montada", f is not None)
    if f is None:
        return
    img, _alvo, _m = cabeca()
    guarda = (radai_thumbnail.resolver, engine.load_sitk)
    try:
        radai_thumbnail.resolver = lambda b: (u"fantoma", u"")
        engine.load_sitk = lambda p, u=None: img
        d = f(b="X")
    finally:
        radai_thumbnail.resolver, engine.load_sitk = guarda

    checar(u"a rota responde sem erro", not d.get("erro"), str(d.get("erro")))
    passos = d.get("passos") or {}
    checar(u"ela devolve um passo para cada resolucao oferecida",
           sorted(int(k) for k in passos) == sorted(S.LADOS),
           u"%s contra %s" % (sorted(passos), sorted(S.LADOS)))
    ext = [s * e for s, e in zip(img.GetSize(), img.GetSpacing())]
    diag = math.sqrt(sum(x * x for x in ext))
    for l in S.LADOS:
        v = passos.get(str(l))
        checar(u"o passo de %d bate com a grade da lib" % l,
               v is not None and abs(v - diag / float(l)) < 0.002,
               u"%s contra %.3f" % (v, diag / float(l)))
    checar(u"e ele CAI quando a resolucao sobe",
           all(passos[str(a)] > passos[str(b)]
               for a, b in zip(S.LADOS, S.LADOS[1:])), str(passos))
    checar(u"o lado util e um dos oferecidos", d.get("lado_util") in S.LADOS,
           str(d.get("lado_util")))


def marcada(nz=40, ny=48, nx=56, esp=(1.0, 1.0, 1.0)):
    import numpy as np
    import SimpleITK as sitk
    v = np.full((nz, ny, nx), -1000.0, dtype=np.float32)
    v[4:nz - 4, 4:ny - 4, 4:nx - 4] = 40.0
    v[nz - 12:nz - 6, 6:12, nx - 14:nx - 8] = 800.0
    img = sitk.GetImageFromArray(v)
    img.SetSpacing(tuple(float(e) for e in esp))
    img.SetOrigin((-nx * esp[0] / 2.0, -ny * esp[1] / 2.0, -nz * esp[2] / 2.0))
    return img


def como_sagital(img):
    import SimpleITK as sitk
    nx, ny, nz = img.GetSize()
    sx, sy, sz = img.GetSpacing()
    ox, oy, oz = img.GetOrigin()
    ref = sitk.Image([ny, nz, nx], img.GetPixelID())
    ref.SetSpacing((sy, sz, sx))
    ref.SetDirection((0.0, 0.0, -1.0,
                      1.0, 0.0, 0.0,
                      0.0, -1.0, 0.0))
    ref.SetOrigin((ox + (nx - 1) * sx, oy, oz + (nz - 1) * sz))
    return sitk.Resample(img, ref, sitk.Transform(), sitk.sitkNearestNeighbor,
                         -2000.0)


def _onde_no_corte(plano):
    import numpy as np
    ll, cc = np.nonzero(np.asarray(plano) >= 500)
    if not len(ll):
        return None
    return float(ll.mean()), float(cc.mean())


def teste_os_tres_planos_saem_na_orientacao_do_paciente():
    secao(u"os tres planos saem na orientacao do paciente (v8.3)")
    import numpy as np
    import SimpleITK as sitk
    import radai_nidus as N

    ax = marcada()
    sag = como_sagital(ax)
    checar(u"o fantoma sagital e mesmo sagital (a grade mudou de ordem)",
           sag.GetSize() == (ax.GetSize()[1], ax.GetSize()[2],
                             ax.GetSize()[0]), str(sag.GetSize()))
    e_ax, e_sag = N.eixos_lps(ax), N.eixos_lps(sag)
    v_ax = N.para_lps(sitk.GetArrayViewFromImage(ax), e_ax)
    v_sag = N.para_lps(sitk.GetArrayViewFromImage(sag), e_sag)
    checar(u"a vista S-P-L da serie sagital e o array da axial, byte a byte",
           v_sag.shape == v_ax.shape and bool(np.array_equal(v_sag, v_ax)),
           u"%s contra %s" % (v_sag.shape, v_ax.shape))
    checar(u"e o milimetro de cada eixo vai junto",
           tuple(e_sag[2]) == tuple(e_ax[2]), u"%s contra %s"
           % (e_sag[2], e_ax[2]))

    esperado = {0: (u"axial", u"anterior em cima", u"esquerda a direita",
                    lambda l, c, h, w: l < h / 2.0 and c > w / 2.0),
                1: (u"coronal", u"cranio em cima", u"esquerda a direita",
                    lambda l, c, h, w: l < h / 2.0 and c > w / 2.0),
                2: (u"sagital", u"cranio em cima", u"anterior a esquerda",
                    lambda l, c, h, w: l < h / 2.0 and c < w / 2.0)}
    for nome, v in ((u"axial", v_ax), (u"sagital", v_sag)):
        for eixo in (0, 1, 2):
            rot, a, b, ok = esperado[eixo]
            idx = {0: v.shape[0] - 9, 1: 9, 2: v.shape[2] - 11}[eixo]
            plano = N.corte(v, eixo, idx)
            p = _onde_no_corte(plano)
            checar(u"serie %s, quadro %s: %s e %s" % (nome, rot, a, b),
                   p is not None and ok(p[0], p[1], plano.shape[0],
                                        plano.shape[1]),
                   u"marcador em %s num corte %s" % (p, plano.shape))

    for graus in (17.0, 45.0):
        r = sitk.Euler3DTransform()
        r.SetRotation(np.radians(graus), 0.0, 0.0)
        obl = sitk.Image([8, 8, 8], sitk.sitkInt16)
        obl.SetDirection(r.GetMatrix())
        perm, inv, mm = N.eixos_lps(obl)
        checar(u"a %.0f graus a vista e uma permutacao valida" % graus,
               sorted(perm) == [0, 1, 2], str(perm))


def teste_a_projecao_sai_com_o_cranio_em_cima():
    secao(u"a projecao sai com o cranio em cima (v8.3)")
    import radai_nidus as N
    img = marcada()
    for lao in (0.0, 90.0):
        plano, _info = N.projetar(img, lao, 0.0, "mip", lado=96)
        p = _onde_no_corte(plano)
        checar(u"LAO %.0f: o marcador cranial esta na metade de cima" % lao,
               p is not None and p[0] < plano.shape[0] / 2.0,
               u"linha %s de %d" % (p and round(p[0], 1), plano.shape[0]))
    plano, _info = N.projetar(img, 0.0, 0.0, "mip", lado=96)
    p = _onde_no_corte(plano)
    checar(u"AP: a esquerda do paciente fica a direita da imagem",
           p is not None and p[1] > plano.shape[1] / 2.0,
           u"coluna %s de %d" % (p and round(p[1], 1), plano.shape[1]))


def rm_uint16(nz=36, ny=44, nx=44):
    import numpy as np
    import SimpleITK as sitk
    z, y, x = np.mgrid[0:nz, 0:ny, 0:nx].astype(np.float32)
    r = np.sqrt(((z - nz / 2.0) / (nz * 0.42)) ** 2
                + ((y - ny / 2.0) / (ny * 0.42)) ** 2
                + ((x - nx / 2.0) / (nx * 0.42)) ** 2)
    v = np.where(r < 1.0, 300, 0).astype(np.uint16)
    v[8:28, ny // 2 - 1:ny // 2 + 1, nx // 2 - 1:nx // 2 + 1] = 1100
    img = sitk.GetImageFromArray(v)
    img.SetSpacing((1.0, 1.0, 1.0))
    img.SetOrigin((-nx / 2.0, -ny / 2.0, -nz / 2.0))
    return img


def teste_a_rm_nao_vira_um_quadrado_branco():
    secao(u"a RM sem HU: preenchimento e janela (v8.3)")
    import numpy as np
    import radai_nidus as N
    img = rm_uint16()
    esc = N.escala_de(img, "MR")
    checar(u"RM nao tem HU", esc.get("hu") is False, str(esc.get("hu")))
    checar(u"TC tem, pela modalidade", N.tem_hu("CT") and not N.tem_hu("MR"))
    checar(u"sem modalidade, decide o minimo (ar e -1000; a RM comeca em 0)",
           N.tem_hu(None, -1000.0) and not N.tem_hu(None, 0.0))
    for lao in (0.0, 45.0):
        plano, info = N.projetar(img, lao, 0.0, "mip", lado=64, escala=esc)
        cantos = [int(plano[0, 0]), int(plano[0, -1]), int(plano[-1, 0]),
                  int(plano[-1, -1])]
        checar(u"LAO %.0f: o fora do volume sai com o minimo da serie" % lao,
               cantos == [0, 0, 0, 0], str(cantos))
        checar(u"LAO %.0f: e nada passa do maximo da serie" % lao,
               int(plano.max()) <= 1100, str(int(plano.max())))
        checar(u"LAO %.0f: e o vaso aparece" % lao, int(plano.max()) >= 1000,
               str(int(plano.max())))
    minip, _i = N.projetar(img, 45.0, 0.0, "minip", lado=64, escala=esc)
    checar(u"no MinIP o fora sai com o MAXIMO da serie",
           int(minip[0, 0]) == 1100, str(int(minip[0, 0])))

    c, l = N.janela_de("angio", esc)
    lo = c - l / 2.0
    p = esc["percentis"]
    checar(u"a janela angio da RM comeca no p90 da serie, e nao em HU",
           abs(lo - p[90.0]) < 1e-6 and lo >= 0.0, u"piso %.1f" % lo)
    checar(u"e o piso fica ACIMA da mediana (metade da RM e ar)",
           lo > p[50.0] if 50.0 in p else lo > float(np.median(
               np.asarray(__import__("SimpleITK").GetArrayViewFromImage(img)))),
           u"piso %.1f" % lo)
    checar(u"«osso» numa serie sem HU vira a janela ampla",
           N.janela_de("osso", esc) == N.janela_de("ampla", esc))
    tc = N.escala_de(marcada(), "CT")
    checar(u"na TC a janela continua a de HU",
           N.janela_de("angio", tc) == N.JANELAS["angio"])


def _mascara_de_referencia(poligono, lado):
    import numpy as np
    m = np.zeros((lado, lado), dtype=bool)
    pts = [(float(x), float(y)) for x, y in (poligono or ())]
    if len(pts) < 3:
        return m
    ys, xs = np.mgrid[0:lado, 0:lado]
    ys = ys + 0.5
    xs = xs + 0.5
    dentro = np.zeros((lado, lado), dtype=bool)
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        if y0 == y1:
            continue
        cruza = ((y0 <= ys) & (ys < y1)) | ((y1 <= ys) & (ys < y0))
        with np.errstate(divide="ignore", invalid="ignore"):
            xint = (x1 - x0) * (ys - y0) / (y1 - y0) + x0
        dentro ^= cruza & (xs < xint)
    return dentro


def teste_a_mascara_do_poligono_e_a_mesma_na_caixa():
    secao(u"a mascara do poligono: so a caixa, e a mesma mascara (v8.3)")
    import random
    import numpy as np
    import radai_nidus as N
    casos = [
        [(10.5, 10.5), (20.5, 10.5), (20.5, 20.5), (10.5, 20.5)],
        [(10.0, 10.0), (20.0, 10.0), (20.0, 20.0), (10.0, 20.0)],
        [(-5.0, -5.0), (30.0, 2.0), (12.0, 40.0)],
        [(50.0, 50.0), (70.0, 58.0), (63.9, 63.9), (40.2, 70.0)],
        [(5.0, 5.0), (40.0, 5.0), (40.0, 40.0), (22.0, 12.0), (5.0, 40.0)],
        [(0.0, 0.0), (64.0, 0.0), (64.0, 64.0), (0.0, 64.0)],
        [(30.0, 30.0), (30.2, 30.0), (30.1, 30.3)],
    ]
    rnd = random.Random(8321)
    for _ in range(40):
        n = rnd.randint(3, 14)
        casos.append([(rnd.uniform(-8, 72), rnd.uniform(-8, 72))
                      for _k in range(n)])
    diferentes = 0
    for poli in casos:
        a = N._mascara_poligono(poli, 64)
        b = _mascara_de_referencia(poli, 64)
        if not np.array_equal(a, b):
            diferentes += 1
    checar(u"%d poligonos, a mascara da caixa e a da grade inteira" % len(casos),
           diferentes == 0, u"%d diferentes" % diferentes)


def _tubo_de_referencia(img, poligono, lao, cra, lado):
    import numpy as np
    import SimpleITK as sitk
    import radai_nidus as N
    t = N._transformada(img, lao, cra)
    ref, diag, passo, passo_fundo = N._grade(img, lado)
    c = t.GetCenter()
    ref.SetOrigin((c[0] - diag / 2.0, c[1] - diag / 2.0, c[2] - diag / 2.0))
    plano = N._mascara_poligono(poligono, lado)[::-1]
    volume = np.repeat(plano[:, None, :], int(ref.GetSize()[1]),
                       axis=1).astype(np.uint8)
    m = sitk.GetImageFromArray(volume)
    m.CopyInformation(ref)
    voltou = sitk.Resample(m, img, t, sitk.sitkNearestNeighbor, 0)
    return sitk.GetArrayFromImage(voltou).astype(bool)


def teste_o_tubo_de_duas_camadas_e_o_de_antes():
    secao(u"o tubo de duas camadas e o tubo de antes (v8.3)")
    import numpy as np
    import radai_nidus as N
    img, alvo, _m = cabeca()
    for lao, cra in ((0.0, 0.0), (37.0, 0.0), (0.0, -30.0), (61.0, 22.0)):
        col, lin = onde(img, alvo, lao, cra, 128)
        poli = circulo(col, lin, 11)
        novo = N.tubo(img, poli, lao, cra, lado=128)
        velho = _tubo_de_referencia(img, poli, lao, cra, 128)
        checar(u"LAO %.0f / CRA %.0f: o mesmo tubo" % (lao, cra),
               novo.shape == velho.shape and bool(np.array_equal(novo, velho)),
               u"%d voxels diferentes" % int((novo != velho).sum()))


def teste_o_tubo_em_bits_e_o_mesmo_tubo():
    secao(u"o tubo em bits e o mesmo tubo (v8.3)")
    import numpy as np
    import radai_nidus as N
    rnd = np.random.RandomState(83)
    a = rnd.rand(9, 13, 21) > 0.6
    b = rnd.rand(9, 13, 21) > 0.4
    ca, cb = N.compactar(a), N.compactar(b)
    iguais = all(np.array_equal(N.corte(ca, e, i), N.corte(a, e, i))
                 for e in (0, 1, 2) for i in range(a.shape[e]))
    checar(u"todo corte do tubo em bits e o do tubo denso", iguais)
    ci = N.intersecao(ca, cb)
    di = N.intersecao(a, b)
    checar(u"a intersecao em bits continua em bits",
           isinstance(ci, N.Compacto))
    iguais = all(np.array_equal(N.corte(ci, e, i), N.corte(di, e, i))
                 for e in (0, 1, 2) for i in range(a.shape[e]))
    checar(u"e e a mesma intersecao", iguais)
    iguais = all(N.contorno_do_tubo(ci, e, i) == N.contorno_do_tubo(di, e, i)
                 for e in (0, 1, 2) for i in range(a.shape[e]))
    checar(u"e as linhas finas sao as mesmas", iguais)
    checar(u"e ocupa um oitavo", ca.bits.nbytes <= (a.size + 8 * 9 * 13) // 8,
           u"%d bytes para %d voxels" % (ca.bits.nbytes, a.size))


def teste_o_pixel_da_tela_e_quadrado():
    secao(u"o pixel da tela e quadrado, e as linhas vao na mesma grade (v8.3)")
    import numpy as np
    import radai_nidus as N
    alt, larg, fl, fc = N.grade_da_tela((40, 80), 1.0, 0.5)
    checar(u"1 mm por linha e 0,5 mm por coluna: as linhas dobram",
           (alt, larg) == (80, 80) and fl == 2.0 and fc == 1.0,
           str((alt, larg, fl, fc)))
    a = np.arange(40 * 80, dtype=np.float32).reshape(40, 80)
    t = N.para_a_tela(a, 1.0, 0.5)
    checar(u"e o corte ampliado tem essa forma", t.shape == (80, 80),
           str(t.shape))
    checar(u"por vizinho mais proximo: cada linha aparece duas vezes",
           bool(np.array_equal(t[0], a[0]) and np.array_equal(t[1], a[0])
                and np.array_equal(t[2], a[1])))
    alt, larg, _fl, _fc = N.grade_da_tela((591, 512), 0.625, 0.5)
    checar(u"o teto engrossa os DOIS lados e mantem a proporcao",
           max(alt, larg) <= N.TETO_DA_TELA
           and abs((alt / float(larg)) - (591 * 0.625) / (512 * 0.5)) < 0.01,
           str((alt, larg)))
    segs = N.escalar([((1, 2), (1, 3))], 2.0, 1.0)
    checar(u"as linhas sao multiplicadas pelos mesmos fatores",
           segs == [((1.0, 4.0), (1.0, 6.0))], str(segs))


def _png_wh(dados):
    import struct
    if not dados or dados[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", dados[16:24])


class _Pedido(object):

    def __init__(self, corpo, porta=8777):
        import types
        self._c = corpo
        self.url = types.SimpleNamespace(port=porta)
        self.scope = {"server": ("127.0.0.1", porta)}

    async def json(self):
        return self._c


def _com_dubles(img, pasta=u"", uid=u""):
    import engine
    import radai_thumbnail
    lidas = []

    def _ler(p, u=None):
        lidas.append(p)
        return img
    guarda = (radai_thumbnail.resolver, engine.load_sitk)
    radai_thumbnail.resolver = lambda b: ((pasta or (u"pasta_" + b)),
                                          (uid if pasta else (u"1.2." + b)))
    engine.load_sitk = _ler

    def soltar():
        radai_thumbnail.resolver, engine.load_sitk = guarda
    return lidas, soltar


def teste_a_serie_colorida_e_recusada():
    secao(u"a série colorida ou 4D é recusada com motivo (o «axes don't match array»)")
    import asyncio
    import numpy as np
    import SimpleITK as sitk
    import radai_nidus as N
    img, _a, _m = cabeca(nz=24, ny=32, nx=32)
    a = sitk.GetArrayFromImage(img).astype(np.uint8)
    rgb = sitk.GetImageFromArray(np.stack([a, a, a], -1), isVector=True)
    rgb.CopyInformation(img)
    q = sitk.JoinSeries([img, img])
    try:
        np.transpose(sitk.GetArrayViewFromImage(rgb), N.eixos_lps(rgb)[0])
        cru = u""
    except ValueError as e:
        cru = str(e)
    checar(u"reproduzido: a transposição crua da série colorida dá a mensagem do autor",
           u"axes don't match array" in cru, cru)
    for nome, im, palavra in ((u"colorida", rgb, u"colorida"),
                              (u"4D", q, u"não é 3D")):
        try:
            N.abrir(im, "CT")
            msg = u"(abriu)"
        except N.SerieRecusada as e:
            msg = str(e)
        except Exception as e:
            msg = u"%s: %s" % (type(e).__name__, e)
        checar(u"a série %s é recusada com o motivo, e não com o do numpy" % nome,
               palavra in msg and u"axes" not in msg, msg[:90])
    try:
        um = N.abrir(sitk.Compose(img), "CT")
        ok = um.forma == N.abrir(img, "CT").forma
    except Exception as e:
        ok = False
    checar(u"o pixel vetorial de um componente abre como escalar", ok)
    try:
        N.para_lps(np.zeros((2, 3, 4, 3)), ((0, 1, 2), (False,) * 3, (1, 1, 1)))
        g = u""
    except N.SerieRecusada as e:
        g = str(e)
    checar(u"a guarda da transposição fala a língua da tela", u"não é 3D" in g, g)

    rotas = _rotas_montadas()
    lidas, soltar = _com_dubles(rgb)
    try:
        f = rotas["/api/nidus/forma"](b="RGB")
        checar(u"a rota da forma devolve o motivo",
               u"colorida" in (f.get("erro") or u"")
               and u"axes" not in (f.get("erro") or u""), str(f)[:120])
        r = rotas["/api/nidus/projecao"](b="RGB", lao=0.0, cra=0.0, modo="mip",
                                         janela="angio", lado=256, laje=0.0,
                                         caixa="", osso=0)
        checar(u"a projeção não esconde o erro num 404 calado",
               r.status_code == 422 and u"colorida".encode("utf-8") in r.body,
               str(r.status_code))
        e = rotas["/api/nidus/estado"](b="RGB")
        checar(u"e a tela acha o motivo pela rota do estado",
               u"colorida" in (e.get("erro") or u""))
        t = asyncio.run(rotas["/api/nidus/tubos"](_Pedido(
            {"b": "RGB", "lado": 256,
             "incidencias": [{"lao": 0, "cra": 0,
                              "pontos": [[1, 1], [9, 1], [9, 9]]}]})))
        checar(u"a retroprojeção da série recusada diz o motivo",
               u"colorida" in (t.get("erro") or u""), str(t)[:120])
        checar(u"e a série recusada foi lida do disco uma vez só",
               len(lidas) == 1, u"%d leituras" % len(lidas))
    finally:
        soltar()


def _cilindro(nz=40, ny=64, nx=64):
    import numpy as np
    import SimpleITK as sitk
    z, y, x = np.mgrid[0:nz, 0:ny, 0:nx].astype(np.float32)
    cy, cx = (ny - 1) / 2.0, (nx - 1) / 2.0
    r = np.sqrt((y - cy) ** 2 + (x - cx) ** 2)
    corpo = (z >= 4) & (z < nz - 4)
    v = np.full((nz, ny, nx), -1000.0, dtype=np.float32)
    v[corpo & (r < 30)] = 35.0
    cranio = corpo & (r >= 26) & (r < 30)
    v[cranio] = 1200.0
    vaso = corpo & (np.sqrt((y - cy) ** 2 + (x - (cx + 8)) ** 2) < 2.2)
    v[vaso] = 400.0
    img = sitk.GetImageFromArray(v.astype(np.int16))
    img.SetSpacing((1.0, 1.0, 1.0))
    img.SetOrigin((-cx, -cy, 0.0))
    return img, cranio, vaso, corpo & (r < 26), (cx, cy)


def _rs_full(caminho, rois, img, descricoes=None):
    import pydicom
    from pydicom.dataset import Dataset, FileDataset
    from pydicom.sequence import Sequence
    from pydicom.uid import ExplicitVRLittleEndian, generate_uid
    meta = Dataset()
    meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.481.3"
    meta.MediaStorageSOPInstanceUID = generate_uid()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds = FileDataset(None, {}, file_meta=meta, preamble=bytes(128))
    ds.SOPClassUID = meta.MediaStorageSOPClassUID
    ds.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
    ds.Modality = "RTSTRUCT"
    ds.PatientID = "FANTOMA"
    ds.StructureSetLabel = "RadAI"
    ox, oy, oz = img.GetOrigin()
    sx, sy, sz = img.GetSpacing()
    ssr, rcs = [], []
    for k, (nome, cortes) in enumerate(sorted(rois.items()), start=1):
        it = Dataset()
        it.ROINumber = k
        it.ROIName = nome
        if (descricoes or {}).get(nome):
            it.ROIDescription = descricoes[nome]
        ssr.append(it)
        cs = []
        for z, polis in sorted(cortes.items()):
            for pts in polis:
                c = Dataset()
                c.ContourGeometricType = "CLOSED_PLANAR"
                c.NumberOfContourPoints = len(pts)
                dados = []
                for px, py in pts:
                    dados += [round(ox + px * sx, 3), round(oy + py * sy, 3),
                              round(oz + z * sz, 3)]
                c.ContourData = dados
                cs.append(c)
        rc = Dataset()
        rc.ReferencedROINumber = k
        rc.ROIDisplayColor = [255, 255, 0]
        rc.ContourSequence = Sequence(cs)
        rcs.append(rc)
    ds.StructureSetROISequence = Sequence(ssr)
    ds.ROIContourSequence = Sequence(rcs)
    try:
        ds.save_as(caminho, enforce_file_format=True)
    except TypeError:
        ds.save_as(caminho, write_like_original=False)


def _anel(cx, cy, raio, n=96):
    import math
    return [(cx + raio * math.cos(2 * math.pi * i / n),
             cy + raio * math.sin(2 * math.pi * i / n)) for i in range(n)]


def teste_o_osso_sai_pela_segmentacao():
    secao(u"o osso sai pela segmentação gravada (FULL ou Estudo 3D), e o vaso fica")
    import numpy as np
    import radai_nidus as N
    import radai_nidus_screen as S
    import radai_rotulos
    for nome, esperado in ((u"Skull_ai", True), (u"Vertebrae_C1_ai", True),
                           (u"Bone_Mandible", True), (u"Rib_L_3_ai", True),
                           (u"skull", True), (u"Brain_ai", False),
                           (u"A_Vertebral_L_ai", False),
                           (u"vertebral_artery_left", False),
                           (u"A_Carotid_L_ai", False), (u"SpinalCord_ai", False)):
        checar(u"«%s» %s osso" % (nome, u"é" if esperado else u"não é"),
               S.e_osso(nome) is esperado)

    img, cranio, vaso, interior, (cx, cy) = _cilindro()
    uid = u"1.2.826.0.1.3680043.8.498.20261014"
    forma = cranio.shape

    def medir(pasta, rotulo):
        rotas = _rotas_montadas()
        lidas, soltar = _com_dubles(img, pasta, uid)
        try:
            f = rotas["/api/nidus/forma"](b=rotulo)
            planos = {}
            for o in (1, 0):
                r = rotas["/api/nidus/projecao"](b=rotulo, lao=0.0, cra=0.0,
                                                 modo="mip", janela="osso",
                                                 lado=128, laje=0.0, caixa="",
                                                 osso=o)
                planos[o] = getattr(r, "body", b"")
            return f, planos
        finally:
            soltar()

    def plano_cru(com_osso, mascara):
        s = N.abrir(img, "CT")
        if mascara is not None:
            s.tirar_osso(mascara, {"tem": True})
        p, _i = N.projetar(s.img, 0.0, 0.0, "mip", lado=128, escala=s.escala,
                           amostra=s.base("mip", com_osso))
        return p

    base = _cleanup.temporaria("radai_ac_nidus_osso_")
    mapa = os.path.join(base, "mapa")
    os.makedirs(mapa)
    radai_rotulos.gravar(mapa, uid, {"total": {"skull": cranio,
                                               "brain": interior}}, ref=img)
    f, planos = medir(mapa, u"MAPA")
    o = f.get("osso") or {}
    checar(u"Estudo 3D: o osso é achado pela segmentação da série",
           o.get("tem") is True and o.get("fonte") == u"Estudo 3D", str(o))
    checar(u"e a projeção sem osso é outra imagem", planos[1] != planos[0])

    com = plano_cru(False, None)
    sem = plano_cru(True, cranio)
    checar(u"com o osso, o MIP é o crânio (1200 HU) em toda a cabeça",
           float(np.percentile(com[com > 0], 50)) > 1000.0)
    checar(u"sem o osso, nada passa de 1000 HU (a borda também saiu)",
           float(sem.max()) < 1000.0, u"%.0f" % float(sem.max()))
    checar(u"e o vaso contrastado continua na projeção",
           float(sem.max()) >= 350.0, u"%.0f" % float(sem.max()))
    m_mapa, _im = S.osso_da_segmentacao(N.abrir(img, "CT"), mapa, uid)
    checar(u"e do Estudo 3D sai só o osso: o encéfalo (e o vaso dentro) fica",
           m_mapa is not None and not (m_mapa & interior).any()
           and bool((m_mapa == cranio).all()))

    full = os.path.join(base, "full")
    os.makedirs(full)
    cortes = dict((z, [_anel(cx, cy, 30.0), _anel(cx, cy, 26.0)])
                  for z in range(4, forma[0] - 4))
    vasos = dict((z, [_anel(cx + 8, cy, 2.2, 24)]) for z in range(4, forma[0] - 4))
    _rs_full(os.path.join(full, u"RS_RadAI_FULL_20261014_%s.dcm" % uid[-8:]),
             {u"Skull_ai": cortes, u"A_Vertebral_L_ai": vasos}, img)
    f2, planos2 = medir(full, u"FULL")
    o2 = f2.get("osso") or {}
    checar(u"FULL: o osso é achado no RTSTRUCT da série",
           o2.get("tem") is True and o2.get("fonte") == u"FULL"
           and o2.get("estruturas") == 1, str(o2))
    m, _info = S.osso_da_segmentacao(N.abrir(img, "CT"), full, uid)
    dsc = 2.0 * float((m & cranio).sum()) / max(1.0, float(m.sum() + cranio.sum()))
    checar(u"e a máscara do anel (com o furo) é o crânio do fantoma (DSC %.3f)" % dsc,
           dsc >= 0.9, u"%.3f" % dsc)
    checar(u"e o vaso com nome de osso («A_Vertebral») não entra",
           not (m & vaso).any())

    alheio = os.path.join(base, "alheio")
    os.makedirs(alheio)
    _rs_full(os.path.join(alheio, u"RS_RadAI_FULL_20261014_99999999.dcm"),
             {u"Skull_ai": cortes}, img)
    m3, info3 = S.osso_da_segmentacao(N.abrir(img, "CT"), alheio, uid)
    checar(u"o FULL de outra série da pasta não serve", m3 is None
           and info3.get("tem") is False, str(info3))
    import radai_viewseg as V
    guarda = V._e_desta_serie
    try:
        V._e_desta_serie = lambda n, u: True
        m4, _i4 = S.osso_da_segmentacao(N.abrir(img, "CT"), alheio, uid)
    finally:
        V._e_desta_serie = guarda
    checar(u"  isca: sem a guarda do UID, o FULL alheio seria usado", m4 is not None)

    import radai_sets
    proprio = os.path.join(base, "proprio")
    os.makedirs(proprio)
    _rs_full(os.path.join(proprio, u"RS_RadAI_20261014_%s.dcm" % uid[-8:]),
             {u"CRANIO": cortes}, img,
             descricoes={u"CRANIO": radai_sets.descricao_da_roi(u"Skull_ai")})
    m6, i6 = S.osso_da_segmentacao(N.abrir(img, "CT"), proprio, uid)
    checar(u"STUDY com nome proprio: o osso e achado pelo nome padrao da "
           u"descricao da ROI (CRANIO -> Skull_ai)",
           m6 is not None and i6.get("tem") is True
           and i6.get("estruturas") == 1, str(i6))
    sem_desc = os.path.join(base, "sem_desc")
    os.makedirs(sem_desc)
    _rs_full(os.path.join(sem_desc, u"RS_RadAI_20261014_%s.dcm" % uid[-8:]),
             {u"CRANIO": cortes}, img)
    m7, i7 = S.osso_da_segmentacao(N.abrir(img, "CT"), sem_desc, uid)
    checar(u"  isca: so pelo nome proprio («CRANIO»), o osso nao seria achado",
           m7 is None and not S.e_osso(u"CRANIO"), str(i7))
    tela = fonte("radai_nidus_screen.py")
    checar(u"o osso vem pela C6 (`radai_viewseg.mascaras_da_serie`), sem nome "
           u"interno do ContourLab", u"V.mascaras_da_serie(" in tela
           and not re.search(r"\bV\._", tela) and u"engine._" not in tela)

    vazia = os.path.join(base, "vazia")
    os.makedirs(vazia)
    f5, planos5 = medir(vazia, u"VAZIA")
    o5 = f5.get("osso") or {}
    checar(u"sem segmentação, a tela diz e oferece segmentar",
           o5.get("tem") is False and o5.get("motivo") == S.SEM_SEGMENTACAO, str(o5))
    checar(u"e o osso não é adivinhado pela densidade: a projeção é a mesma",
           planos5[1] == planos5[0] and len(planos5[1]) > 100)


def teste_segmentar_vai_para_a_fila():
    secao(u"«segmentar primeiro (AUTO)» vai à fila única (contrato C1)")
    import ast
    import asyncio
    import inspect
    import textwrap
    import radai_nidus_screen as S
    import radai_queue_state as F
    import radai_thumbnail
    rotas = _rotas_montadas()
    pedidos = []
    guarda = (S.pedir_a_fila, radai_thumbnail.resolver)
    try:
        radai_thumbnail.resolver = lambda b: (u"pasta_X", u"1.2.3")
        S.pedir_a_fila = lambda itens: (
            pedidos.append(itens)
            or {"ok": True, "cartoes": [{"id": "c7", "posicao": 2}]})
        r = asyncio.run(rotas["/api/nidus/segmentar"](
            _Pedido({"b": "X", "rotulo": "CTA cranio"}, porta=8791)))
        item = (pedidos[:1] or [[{}]])[0][0]
        checar(u"o pedido é o do contrato: modo auto, origem nidus",
               item == {"pasta": u"pasta_X", "uid": u"1.2.3", "modo": u"auto",
                        "chaves": {}, "copiar_rs_para": [], "origem": u"nidus",
                        "rotulo": u"CTA cranio"}, str(item))
        checar(u"a tela recebe o cartão", r.get("ok") and r.get("id") == "c7"
               and r.get("posicao") == 2, str(r))
        S.pedir_a_fila = lambda itens: {"ok": False, "indisponivel": True}
        r2 = asyncio.run(rotas["/api/nidus/segmentar"](_Pedido({"b": "X"})))
        checar(u"sem a fila, a resposta diz «fila indisponível»",
               r2.get("ok") is False and r2.get("erro") == S.FILA_INDISPONIVEL
               and u"fila indisponível" in S.FILA_INDISPONIVEL, str(r2))
    finally:
        S.pedir_a_fila, radai_thumbnail.resolver = guarda

    recebidos = []
    guarda_f = F.enfileirar
    try:
        F.enfileirar = lambda corpo, origem=None: (
            recebidos.append(corpo)
            or {"ok": True, "cartoes": [{"id": "c9", "posicao": 1}]})
        r3 = S.pedir_a_fila([{"uid": u"1.2.3"}])
    finally:
        F.enfileirar = guarda_f
    checar(u"o pedido vai a radai_queue_state.enfileirar, no mesmo processo "
           u"(contrato C1)",
           recebidos == [{"itens": [{"uid": u"1.2.3"}]}]
           and r3.get("cartoes") == [{"id": "c9", "posicao": 1}],
           "%s | %s" % (recebidos, r3))
    guarda_m = sys.modules.get("radai_queue_state")
    try:
        sys.modules["radai_queue_state"] = None
        r4 = S.pedir_a_fila([{}])
    finally:
        sys.modules["radai_queue_state"] = guarda_m
    checar(u"sem o módulo da fila, «indisponível»",
           r4.get("indisponivel") is True, str(r4))

    def _fala_por_http(fonte):
        arv = ast.parse(textwrap.dedent(fonte))
        return [getattr(n.func, "attr", None) or getattr(n.func, "id", None)
                for n in ast.walk(arv) if isinstance(n, ast.Call)
                and (getattr(n.func, "attr", None) or getattr(n.func, "id", None))
                in ("urlopen", "Request", "HTTPConnection")]
    checar(u"e não fala HTTP consigo mesmo",
           not _fala_por_http(inspect.getsource(S.pedir_a_fila)),
           str(_fala_por_http(inspect.getsource(S.pedir_a_fila))))
    checar(u"  (isca) o pedido por urlopen é acusado",
           bool(_fala_por_http(u"def f(r):\n    return urllib.request.urlopen(r)\n")))


def teste_a_demo_saiu():
    secao(u"o Nidus não usa mais o módulo da demo (C5)")
    import asyncio
    import radai_dicom
    fonte_tela = fonte("radai_nidus_screen.py")
    checar(u"a tela não importa nem cita o módulo da demo",
           u"radai_demo" not in fonte_tela and u"nd_demo" not in fonte_tela
           and u"_series_da_demo" not in fonte_tela)
    rotas = _rotas_montadas()
    checar(u"a tela não tem lista própria de séries: a pasta é lida pela "
           u"varredura da casca", u"/api/nidus/series" not in rotas
           and u"/api/nidus/series" not in fonte_tela, str(sorted(rotas))[:160])


def _serie_cta(destino, rgb=False):
    from datetime import datetime
    import numpy as np
    import pydicom
    from pydicom.dataset import Dataset, FileDataset
    from pydicom.uid import ExplicitVRLittleEndian, generate_uid
    os.makedirs(destino, exist_ok=True)
    st, se, fr = generate_uid(), generate_uid(), generate_uid()
    nz, ny, nx = (30, 64, 64) if rgb else (48, 80, 80)
    z, y, x = np.mgrid[0:nz, 0:ny, 0:nx].astype(np.float32)
    r = np.sqrt(((z - nz / 2) / (nz * .46)) ** 2 + ((y - ny / 2) / (ny * .42)) ** 2
                + ((x - nx / 2) / (nx * .38)) ** 2)
    v = np.full((nz, ny, nx), -1000, np.int16)
    v[r < 1] = 35
    v[(r >= .9) & (r < 1)] = 1200
    d = np.sqrt((x - nx / 2) ** 2 + (y - ny * .45) ** 2 + (z - nz / 2) ** 2)
    v[d < 5] = 350
    for i in range(nz):
        meta = Dataset()
        meta.MediaStorageSOPClassUID = ("1.2.840.10008.5.1.4.1.1.7" if rgb
                                        else "1.2.840.10008.5.1.4.1.1.2")
        meta.MediaStorageSOPInstanceUID = generate_uid()
        meta.TransferSyntaxUID = ExplicitVRLittleEndian
        ds = FileDataset(None, {}, file_meta=meta, preamble=bytes(128))
        ds.SOPClassUID = meta.MediaStorageSOPClassUID
        ds.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
        ds.Modality = "CT"
        ds.PatientName = "FANTOMA^NIDUS"
        ds.PatientID = "FANTOMA"
        ds.StudyInstanceUID, ds.SeriesInstanceUID = st, se
        ds.FrameOfReferenceUID = fr
        ds.SeriesNumber = 2 if rgb else 1
        ds.InstanceNumber = i + 1
        ds.SeriesDescription = "captura 3D" if rgb else "CTA fantoma"
        ds.StudyDate = ds.SeriesDate = datetime.now().strftime("%Y%m%d")
        ds.ImagePositionPatient = [-nx * 0.75, -ny * 0.75, i * 1.5]
        ds.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
        ds.PatientPosition = "HFS"
        ds.SliceThickness = 1.5
        ds.PixelSpacing = [1.5, 1.5]
        ds.Rows, ds.Columns = ny, nx
        if rgb:
            ds.SamplesPerPixel = 3
            ds.PlanarConfiguration = 0
            ds.PhotometricInterpretation = "RGB"
            ds.BitsAllocated = ds.BitsStored = 8
            ds.HighBit = 7
            ds.PixelRepresentation = 0
            a = np.clip((v[i] + 1000) / 10, 0, 255).astype(np.uint8)
            ds.PixelData = np.stack([a, a, a], -1).tobytes()
        else:
            ds.SamplesPerPixel = 1
            ds.PhotometricInterpretation = "MONOCHROME2"
            ds.BitsAllocated = ds.BitsStored = 16
            ds.HighBit = 15
            ds.PixelRepresentation = 1
            ds.RescaleIntercept = 0
            ds.RescaleSlope = 1
            ds.PixelData = v[i].tobytes()
        nome = ("SC_%04d.dcm" if rgb else "CT_%04d.dcm") % (i + 1)
        try:
            ds.save_as(os.path.join(destino, nome), enforce_file_format=True)
        except TypeError:
            ds.save_as(os.path.join(destino, nome), write_like_original=False)


def _chromium():
    base = os.path.join(os.environ.get("LOCALAPPDATA", ""), "ms-playwright")
    if not os.path.isdir(base):
        return None
    for nome in sorted(os.listdir(base), reverse=True):
        if not nome.startswith("chromium-"):
            continue
        for sub in ("chrome-win64", "chrome-win"):
            exe = os.path.join(base, nome, sub, "chrome.exe")
            if os.path.isfile(exe):
                return exe
    return None


def _servidor():
    import socket
    import threading
    import time
    import uvicorn
    from fastapi import FastAPI
    import radai_nidus_screen as S
    import radai_varrer
    app = FastAPI()
    S.montar(app)
    radai_varrer.montar(app)
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    porta = s.getsockname()[1]
    s.close()
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=porta,
                                       log_level="warning"))
    threading.Thread(target=srv.run, daemon=True).start()
    for _ in range(100):
        if srv.started:
            return srv, porta
        time.sleep(0.1)
    srv.should_exit = True
    return None, porta


def _caixa_de(pg, sel):
    return pg.evaluate("(function(){ var e=document.querySelector(%r);"
                       " if(!e) return null; var r=e.getBoundingClientRect();"
                       " return {x:r.left, y:r.top, w:r.width, h:r.height,"
                       " b:r.bottom, d:r.right} })()" % sel)


def teste_no_navegador():
    secao(u"no navegador: uma tela só, o lápis, e a série colorida que trava")
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        checar(u"(sem Playwright — o navegador não rodou)", True)
        return
    exe = _chromium()
    if not exe:
        checar(u"(sem Chromium — o navegador não rodou)", True)
        return
    base = _cleanup.temporaria("radai_ac_nidus_nav_")
    share = os.path.join(base, "share", "FANTOMA")
    _serie_cta(os.path.join(share, "CTA"))
    _serie_cta(os.path.join(share, "SC3D"), rgb=True)
    srv, porta = _servidor()
    checar(u"o servidor de teste subiu", srv is not None)
    if srv is None:
        return
    erros = []
    try:
        with sync_playwright() as p:
            nav = p.chromium.launch(executable_path=exe, headless=True,
                                    args=["--use-angle=swiftshader",
                                          "--enable-unsafe-swiftshader"])
            for larg, alt in ((1600, 900), (1280, 800)):
                pg = nav.new_page(viewport={"width": larg, "height": alt})
                pg.on("pageerror", lambda e: erros.append(str(e)[:160]))
                pg.goto("http://127.0.0.1:%d/nidus/projecao" % porta)
                pg.wait_for_timeout(500)
                rot = u"%dx%d" % (larg, alt)
                checar(u"[%s] a tela abre com a escolha da série, a tabela do "
                       u"acervo à vista" % rot,
                       pg.is_visible(".ui-modal #nd_acervo"))
                pg.click("#nd_origem-t-pasta")
                pg.click("#nd_listar")
                pg.wait_for_timeout(300)
                checar(u"[%s] «Listar séries» sem pasta não lista nada" % rot,
                       pg.evaluate("document.querySelectorAll('#nd_series .nd-it').length") == 0
                       and pg.evaluate("document.activeElement.id") == u"nd_pasta")
                pg.fill("#nd_pasta", share)
                pg.click("#nd_listar")
                pg.wait_for_function(
                    "document.querySelectorAll('#nd_series .nd-it').length > 1",
                    timeout=60000)
                ops = pg.eval_on_selector_all(
                    "#nd_series .nd-it",
                    "os => os.map(o => [o.getAttribute('data-b'), o.textContent])")
                boa = [b for b, o in ops if u"CTA" in o]
                ruim = [b for b, o in ops if u"captura" in o]
                pg.click('#nd_series .nd-it[data-b="%s"]' % boa[0])
                pg.wait_for_timeout(400)
                checar(u"[%s] escolher fecha a escolha e diz a série no lado" % rot,
                       not pg.is_visible(".ui-modal")
                       and u"CTA" in pg.inner_text("#nd_serie_rot"))
                pg.wait_for_function(
                    "document.getElementById('nd_proj').naturalWidth > 0 && !ND.projetando",
                    timeout=60000)
                pg.wait_for_timeout(2600)
                checar(u"[%s] tudo numa tela, sem rolar" % rot,
                       pg.evaluate("document.documentElement.scrollHeight"
                                   " <= window.innerHeight + 1"),
                       pg.evaluate("[document.documentElement.scrollHeight, window.innerHeight]"))
                cmd, palco, tres, mapa, mpr = (_caixa_de(pg, s) for s in (
                    "#nd_cmd", "#nd_palco", "#nd_palco3d", "#nd_pad",
                    "#nd_mpr .nd-planos"))
                checar(u"[%s] as ferramentas em cima do visor" % rot,
                       cmd and palco and cmd["b"] <= palco["y"] + 1, (cmd, palco))
                checar(u"[%s] o visor é quadrado e grande" % rot,
                       abs(palco["w"] - palco["h"]) <= 1 and palco["h"] >= 300, palco)
                checar(u"[%s] o 3D da caixa e o mapa à direita da projeção, lado a lado" % rot,
                       tres and mapa and tres["x"] >= palco["d"] - 1
                       and mapa["x"] >= tres["d"] - 1 and tres["h"] >= 100
                       and mapa["h"] >= 70, (palco, tres, mapa))
                checar(u"[%s] o MPR em faixa, embaixo do 3D" % rot,
                       mpr and mpr["y"] >= tres["b"] - 1 and mpr["x"] >= palco["d"] - 1
                       and mpr["b"] <= palco["b"] + 60, (tres, mpr))
                pg.mouse.move(palco["x"] + palco["w"] * .6, palco["y"] + palco["h"] * .5)
                pg.mouse.down()
                for k in range(1, 40):
                    import math
                    t = 2 * math.pi * k / 40
                    pg.mouse.move(palco["x"] + palco["w"] * (.5 + .1 * math.cos(t)),
                                  palco["y"] + palco["h"] * (.5 + .1 * math.sin(t)))
                pg.mouse.up()
                checar(u"[%s] o lápis desenha sem ligar nada" % rot,
                       pg.evaluate("ND.pontos.length") >= 8
                       and u" Z" in pg.inner_html("#nd_marca"))
                pg.click("#nd_bt_guardar")
                pg.wait_for_function("ND.sessao && !ND.cruzando", timeout=60000)
                checar(u"[%s] guardar cruza a incidência" % rot,
                       pg.evaluate("document.querySelectorAll('#nd_guardadas li').length") == 1)
                if larg == 1280:
                    pg.screenshot(path=os.path.join(base, "nidus_1280.png"))
                    pg.evaluate(u"() => { ndCaixaModo(); ND.caixa=[0.3,0.7,0.25,0.65,0.3,0.7];"
                                u" ndPintarCaixas(); ndTravas(); ndProjetar(); nd3Malhas();"
                                u" ndPintarPegada(); ndEnquadrar(); }")
                    pg.wait_for_function("ND.aberta && !ND.projetando", timeout=60000)
                    pg.wait_for_timeout(2400)
                    tem_gl = pg.evaluate("!!ND3.gl")
                    tres = _caixa_de(pg, "#nd_palco3d")
                    l0 = pg.evaluate("ND.lao")
                    pg.mouse.move(tres["x"] + tres["w"] * .4, tres["y"] + tres["h"] * .5)
                    pg.mouse.down()
                    pg.mouse.move(tres["x"] + tres["w"] * .4 + 50, tres["y"] + tres["h"] * .5,
                                  steps=5)
                    previa = pg.evaluate("[ND.previa, ND.ver.lao, ND.lao]")
                    pg.mouse.up()
                    pg.wait_for_function("ND.aberta && !ND.projetando", timeout=60000)
                    l1 = pg.evaluate("ND.lao")
                    checar(u"[%s] no 3D da caixa (WebGL), arrastar para a direita vai para "
                           u"RAO, seguindo o objeto, com prévia no caminho" % rot,
                           tem_gl and l1 < l0 and previa[0] is True and previa[1] < 0
                           and previa[2] == l0, (tem_gl, l0, l1, previa))
                    pg.wait_for_timeout(2400)
                    pg.evaluate(u"() => { ND.guardadas.push({lao:0, cra:0, pendente:false,"
                                u" pontos:[[1,1],[50,1],[50,50]]}, {lao:-90, cra:0, pendente:false,"
                                u" pontos:[[1,1],[50,1],[50,50]]}); ndPintarGuardadas();"
                                u" var s=document.getElementById('nd_vista'); s.value='sala';"
                                u" s.dispatchEvent(new Event('change')); }")
                    medidas = []
                    for lao, cra in ((-30, 20), (45, 30), (90, 0), (0, -15)):
                        medidas.append(pg.evaluate(u"""() => { ND.ver={lao:%d, cra:%d}; ND3.pedido=false; nd3Pintar();
 const etq=[...document.querySelectorAll('#nd_etqs .nd-etq')].map(e=>e.getBoundingClientRect());
 const fix=['nd_cant','nd_eixos3d'].map(i=>document.getElementById(i).getBoundingClientRect()).filter(r=>r.width>0);
 const bate=(a,b)=>a.left<b.right&&b.left<a.right&&a.top<b.bottom&&b.top<a.bottom;
 let n=0; for(let i=0;i<etq.length;i++){ for(let j=i+1;j<etq.length;j++) if(bate(etq[i],etq[j])) n++;
  for(const f of fix) if(bate(etq[i],f)) n++; }
 return [n, etq.length, document.getElementById('nd_cant').textContent]; }""" % (lao, cra)))
                    checar(u"[%s] na sala, com duas guardadas, nenhum rótulo cobre outro, a "
                           u"leitura do canto nem os eixos, em quatro incidências" % rot,
                           all(m[0] == 0 and m[1] >= 1 for m in medidas), medidas)
                    checar(u"[%s] e o canto da sala diz que ela é ilustrativa" % rot,
                           all(u"ilustrativa" in m[2] for m in medidas), medidas[0][2])
                    pg.evaluate(u"""() => { window.__rot = nd3Rotular;
 nd3Rotular = function(etqs, PV, w, h){ var alvo=ndEl('nd_etqs'), cv=ND3.canvas,
  W=cv.clientWidth, H=cv.clientHeight, html='';
  (etqs||[]).forEach(function(e){ var p=e.p;
   var x=PV[0]*p[0]+PV[4]*p[1]+PV[8]*p[2]+PV[12], y=PV[1]*p[0]+PV[5]*p[1]+PV[9]*p[2]+PV[13],
    ww=PV[3]*p[0]+PV[7]*p[1]+PV[11]*p[2]+PV[15]; if(ww<=0) return; x/=ww; y/=ww;
   html+='<span class="nd-etq" style="left:'+((x*0.5+0.5)*W).toFixed(0)+'px;top:'
    +((0.5-y*0.5)*H).toFixed(0)+'px">'+e.t+'</span>' });
  alvo.innerHTML=html } }""")
                    isca_s = []
                    for lao, cra in ((-30, 20), (45, 30), (90, 0), (0, -15), (0, 0), (-90, 0)):
                        isca_s.append(pg.evaluate(u"""() => { ND.ver={lao:%d, cra:%d}; ND3.pedido=false; nd3Pintar();
 const etq=[...document.querySelectorAll('#nd_etqs .nd-etq')].map(e=>e.getBoundingClientRect());
 const fix=['nd_cant','nd_eixos3d'].map(i=>document.getElementById(i).getBoundingClientRect()).filter(r=>r.width>0);
 const bate=(a,b)=>a.left<b.right&&b.left<a.right&&a.top<b.bottom&&b.top<a.bottom;
 let n=0; for(let i=0;i<etq.length;i++){ for(let j=i+1;j<etq.length;j++) if(bate(etq[i],etq[j])) n++;
  for(const f of fix) if(bate(etq[i],f)) n++; }
 return n; }""" % (lao, cra)))
                    pg.evaluate(u"() => { nd3Rotular = window.__rot }")
                    checar(u"[%s]   isca: sem o desvio, os rótulos da sala se cobrem" % rot,
                           sum(isca_s) > 0, isca_s)
                    pg.evaluate(u"() => { var s=document.getElementById('nd_vista'); s.value='3d';"
                                u" s.dispatchEvent(new Event('change')); }")
                pg.click("#nd_escolher")
                pg.wait_for_timeout(400)
                pg.click('#nd_series .nd-it[data-b="%s"]' % ruim[0])
                pg.wait_for_function("!ND.abrindo", timeout=60000)
                pg.wait_for_timeout(400)
                msg = pg.inner_text("#nd_msg")
                checar(u"[%s] a série colorida diz por que não abre" % rot,
                       u"colorida" in msg and u"axes" not in msg, msg)
                pg.mouse.move(palco["x"] + 50, palco["y"] + 50)
                pg.mouse.down()
                pg.mouse.move(palco["x"] + 150, palco["y"] + 150)
                pg.mouse.up()
                checar(u"[%s] e nela o lápis e o Guardar ficam travados" % rot,
                       pg.evaluate("ND.pontos.length") == 0
                       and pg.is_disabled("#nd_bt_guardar")
                       and pg.is_disabled("#nd_lao_r"))
                pg.close()
            nav.close()
    finally:
        srv.should_exit = True
    checar(u"nenhum erro de JavaScript", not erros, u"; ".join(erros[:3]))


def teste_as_rotas_leem_a_serie_uma_vez():
    secao(u"as rotas leem a serie uma vez, com o UID, e as linhas casam (v8.3)")
    import asyncio
    import engine
    import radai_thumbnail
    import radai_nidus_screen as S

    rotas = _rotas_montadas()
    base = como_sagital(marcada(esp=(0.5, 0.5, 1.0)))
    lidas = []

    def _ler(pasta, uid=None):
        lidas.append((pasta, uid))
        return base

    guarda = (radai_thumbnail.resolver, engine.load_sitk)
    try:
        radai_thumbnail.resolver = lambda b: (
            (u"pasta_" + b, u"1.2.3." + b) if b else (u"", u""))
        engine.load_sitk = _ler
        forma = rotas["/api/nidus/forma"](b="A")
        rotas["/api/nidus/projecao"](b="A", lao=0.0, cra=0.0, modo="mip",
                                     janela="angio", lado=256, laje=0.0)
        pngs = [rotas["/api/nidus/corte"](b="A", eixo=e, pos=0.5,
                                          janela="angio") for e in (0, 1, 2)]
        checar(u"forma, projecao e tres cortes: UMA leitura da serie",
               len(lidas) == 1, u"%d leituras" % len(lidas))
        checar(u"e o UID foi junto na leitura",
               lidas[:1] == [(u"pasta_A", u"1.2.3.A")], str(lidas[:1]))
        checar(u"a forma e a da vista S-P-L, e nao a do array sagital",
               forma.get("forma") == [40, 48, 56], str(forma.get("forma")))

        pts = [[100.0, 60.0], [160.0, 60.0], [160.0, 120.0], [100.0, 120.0]]
        r = asyncio.run(rotas["/api/nidus/tubos"](_Pedido(
            {"b": "A", "lado": 256,
             "incidencias": [{"lao": 0, "cra": 0, "pontos": pts},
                             {"lao": 90, "cra": 0, "pontos": pts}]})))
        checar(u"a retroprojecao responde sem erro", not r.get("erro"),
               str(r.get("erro")))
        s = r.get("sessao")
        for e in (0, 1, 2):
            png = pngs[e]
            wh = _png_wh(getattr(png, "body", b""))
            li = rotas["/api/nidus/linhas"](s=s, eixo=e, pos=0.5)
            checar(u"eixo %d: as linhas estao na grade do PNG do corte" % e,
                   wh is not None
                   and (li.get("largura"), li.get("altura")) == wh,
                   u"linhas %sx%s, png %s" % (li.get("largura"),
                                             li.get("altura"), wh))
        checar(u"e a retroprojecao nao releu a serie", len(lidas) == 1,
               u"%d leituras" % len(lidas))
        rotas["/api/nidus/forma"](b="B")
        checar(u"a serie B e lida, com o UID dela",
               len(lidas) == 2 and lidas[1] == (u"pasta_B", u"1.2.3.B"),
               str(lidas))
    finally:
        radai_thumbnail.resolver, engine.load_sitk = guarda


def teste_a_rm_entra_no_seletor():
    secao(u"a lista da pasta: TC e RM, pela varredura da casca (C-VARRER)")
    from datetime import datetime
    import make_test_series
    import radai_thumbnail
    import radai_varrer
    import radai_nidus_screen as S
    listar = _funcao_js_nd(S.JS, u"ndListar")
    checar(u"a lista pede TC e RM, com o mínimo de cortes da tela",
           "CT" in S.MODALIDADES and "MR" in S.MODALIDADES
           and u"var ND_MIN_CORTES = %d;" % S.MIN_CORTES in S.JS
           and u"opcoes:{modalidades:ND_MODALIDADES, min_cortes:ND_MIN_CORTES}"
           in listar, listar[:200])
    checar(u"  pela varredura da casca, e não pela do «Rodar agora» nem por "
           u"POST único", u"window.uiVarrerLista({" in listar
           and u"fetch(" not in listar
           and "radai_batch" not in fonte("radai_nidus_screen.py"))
    opcoes = {"modalidades": list(S.MODALIDADES), "min_cortes": S.MIN_CORTES}
    base = _cleanup.temporaria("radai_ac_nidus_varrer_")
    longa = os.path.join(base, "LONGA", "CT")
    uid = make_test_series.escreve_serie(longa, "PAC_LONGA", datetime.now(),
                                         S.MIN_CORTES + 4)
    make_test_series.escreve_serie(os.path.join(base, "CURTA", "CT"),
                                   "PAC_CURTA", datetime.now(), 6)
    d = radai_varrer.iniciar("series", base, dias=0, opcoes=opcoes,
                             em_segundo_plano=False)
    pids = sorted(str(x.get("pid")) for x in d.get("linhas") or ())
    checar(u"a varredura com as opções da tela traz a série longa e deixa de "
           u"fora a de 6 cortes", pids == [u"PAC_LONGA"] and not d.get("erro"),
           u"%s %s" % (pids, d.get("erro")))
    linha = (d.get("linhas") or [{}])[0]
    _p, uid_b = radai_thumbnail.resolver(linha.get("bilhete") or u"")
    checar(u"  e o bilhete da linha abre a série certa", uid_b == uid,
           str(uid_b)[-8:])
    isca = radai_varrer.iniciar("series", base, dias=0,
                                em_segundo_plano=False)
    checar(u"  (isca) sem as opções da tela, a de 6 cortes entraria",
           sorted(str(x.get("pid")) for x in isca.get("linhas") or ())
           == [u"PAC_CURTA", u"PAC_LONGA"])


def _funcao_js_nd(js, nome):
    i = js.find(u"function %s(" % nome)
    if i < 0:
        return u""
    k, prof = js.find(u"{", i), 0
    for j in range(k, len(js)):
        if js[j] == u"{":
            prof += 1
        elif js[j] == u"}":
            prof -= 1
            if prof == 0:
                return js[i:j + 1]
    return u""


class _TravaSolta(object):

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def acquire(self, *a, **k):
        return True

    def release(self):
        pass


def _medir_projecoes(sem_trava=False):
    import threading
    import time
    import radai_nidus as N
    img, _a, _m = cabeca(nz=24, ny=32, nx=32)
    guarda_lock = threading.Lock
    if sem_trava:
        threading.Lock = _TravaSolta
    try:
        rotas = _rotas_montadas()
    finally:
        threading.Lock = guarda_lock
    lidas, soltar = _com_dubles(img)
    guarda_p = N.projetar
    est = {"dentro": 0, "pico": 0, "feitas": []}
    conta = threading.Lock()
    libera, entrou = threading.Event(), threading.Event()

    def _proj(img_, lao, cra, *a, **k):
        with conta:
            est["dentro"] += 1
            est["pico"] = max(est["pico"], est["dentro"])
        entrou.set()
        if lao == 1.0:
            libera.wait(10)
        else:
            time.sleep(0.05)
        with conta:
            est["dentro"] -= 1
            est["feitas"].append(int(lao))
        return guarda_p(img_, lao, cra, *a, **k)

    resp = {}

    def pedir(n):
        resp[n] = rotas["/api/nidus/projecao"](
            b="P", lao=float(n), cra=0.0, modo="mip", janela="angio",
            lado=256, laje=0.0, caixa="", osso=0, n=n, t="aba1")

    N.projetar = _proj
    try:
        rotas["/api/nidus/forma"](b="P")
        ta = threading.Thread(target=pedir, args=(1,))
        ta.start()
        entrou.wait(10)
        tb = threading.Thread(target=pedir, args=(2,))
        tb.start()
        time.sleep(0.25)
        tc = threading.Thread(target=pedir, args=(3,))
        tc.start()
        time.sleep(0.25)
        libera.set()
        for t in (ta, tb, tc):
            t.join(30)
        erro = rotas["/api/nidus/estado"](b="P").get("erro")
    finally:
        N.projetar = guarda_p
        soltar()
    return est, resp, erro


def teste_as_projecoes_vao_uma_por_vez():
    secao(u"a projeção em 1024 vai uma por vez, e a que envelheceu na espera não roda")
    import radai_nidus_screen as S
    est, resp, erro = _medir_projecoes()
    checar(u"nunca duas projeções ao mesmo tempo (pico %d)" % est["pico"],
           est["pico"] == 1, str(est))
    checar(u"a primeira e a mais nova rodam; a do meio, que ficou velha, não",
           sorted(est["feitas"]) == [1, 3], str(est["feitas"]))
    st = dict((n, getattr(r, "status_code", None)) for n, r in resp.items())
    checar(u"  a velha responde 409, e as outras trazem a imagem",
           st == {1: 200, 2: 409, 3: 200}, str(st))
    checar(u"  e a velha não vira erro da série", erro == u"", repr(erro))
    checar(u"a resolução continua a máxima", S.LADO_DA_TELA == max(S.LADOS) == 1024)
    est_i, _r, _e = _medir_projecoes(sem_trava=True)
    checar(u"  isca: sem a trava, duas projeções correm juntas", est_i["pico"] >= 2,
           str(est_i))


def teste_o_acervo_abre_pelo_resolvedor_da_tabela():
    secao(u"abrir pelo acervo passa por radai_tabela_acervo.resolver (C2)")
    import asyncio
    import engine
    import radai_tabela_acervo as TA
    import radai_thumbnail
    import radai_nidus_screen as S
    img, _a, _m = cabeca(nz=24, ny=32, nx=32)
    rotas = _rotas_montadas()
    ch = {"tabela": [], "bilhete": []}
    guarda = (TA.resolver, radai_thumbnail.resolver, engine.load_sitk)
    uid_a = u"1.2.826.0.1.3680043.8.498.1"
    try:
        TA.resolver = lambda b: (ch["tabela"].append(b) or (
            (u"pasta_acervo", uid_a) if b == "NO_ACERVO" else (None, None)))
        radai_thumbnail.resolver = lambda b: (ch["bilhete"].append(b) or (
            u"pasta_" + b, u"1.2.826.0.1.3680043.8.498.2"))
        engine.load_sitk = lambda p, u=None: img
        fora = asyncio.run(rotas["/api/nidus/abrir"](
            _Pedido({"b": "FORA", "origem": "acervo"})))
        dentro = asyncio.run(rotas["/api/nidus/abrir"](
            _Pedido({"b": "NO_ACERVO", "origem": "acervo"})))
        pelo_bilhete = len(ch["bilhete"])
        pasta = asyncio.run(rotas["/api/nidus/abrir"](
            _Pedido({"b": "X", "origem": "pasta"})))
        isca = asyncio.run(rotas["/api/nidus/abrir"](
            _Pedido({"b": "FORA", "origem": "pasta"})))
    finally:
        TA.resolver, radai_thumbnail.resolver, engine.load_sitk = guarda
    checar(u"o bilhete que não está no acervo é recusado, com o motivo",
           fora.get("erro") == S.FORA_DO_ACERVO and not fora.get("forma"), str(fora)[:120])
    checar(u"o do acervo abre pela tabela", bool(dentro.get("forma"))
           and ch["tabela"] == ["FORA", "NO_ACERVO"], str(ch))
    checar(u"  sem consultar o resolvedor genérico de bilhete", pelo_bilhete == 0,
           str(ch["bilhete"]))
    checar(u"a origem «pasta» continua pelo bilhete", bool(pasta.get("forma"))
           and ch["bilhete"][:1] == ["X"], str(ch["bilhete"]))
    checar(u"  isca: a mesma série fora do acervo abriria pela pasta",
           bool(isca.get("forma")))
    checar(u"a chave da série sai da impressão do UID, sem o UID e sem a pasta",
           dentro.get("chave") == S.chave_da_serie(u"pasta_acervo", uid_a)
           and uid_a not in dentro.get("chave") and u"pasta" not in dentro.get("chave")
           and re.match(r"^[0-9a-f]{24}$", dentro.get("chave") or u""),
           dentro.get("chave"))


def teste_a_chave_da_serie_nao_depende_do_bilhete():
    secao(u"a chave do estado salvo é a mesma para dois bilhetes da mesma série")
    import engine
    import radai_thumbnail
    import radai_nidus_screen as S
    img, _a, _m = cabeca(nz=24, ny=32, nx=32)
    chaves = []
    guarda = (radai_thumbnail.resolver, engine.load_sitk)
    try:
        engine.load_sitk = lambda p, u=None: img
        for b, uid in ((u"B_PROC1", u"1.2.3.4.5"), (u"B_PROC2", u"1.2.3.4.5"),
                       (u"B_OUTRA", u"1.2.3.4.6")):
            radai_thumbnail.resolver = (lambda u: lambda bb: (u"C:\\fantoma\\CT", u))(uid)
            chaves.append(_rotas_montadas()["/api/nidus/forma"](b=b).get("chave"))
    finally:
        radai_thumbnail.resolver, engine.load_sitk = guarda
    checar(u"a mesma série em dois processos (dois bilhetes): a mesma chave",
           chaves[0] and chaves[0] == chaves[1], str(chaves))
    checar(u"outra série: outra chave", chaves[2] and chaves[2] != chaves[0], str(chaves))
    checar(u"sem UID, a chave sai da pasta, sem mostrá-la",
           S.chave_da_serie(u"C:\\fantoma\\CT", u"") != S.chave_da_serie(u"C:\\outra", u"")
           and u"fantoma" not in S.chave_da_serie(u"C:\\fantoma\\CT", u""))


def teste_o_osso_sai_tambem_pelo_oar_e_pelo_oar_fast():
    secao(u"o osso sai também pela entrega (OAR, OAR_Fast); sem osso nela, a tela diz qual é")
    import radai_nidus_screen as S
    img, cranio, _vaso, _interior, (cx, cy) = _cilindro()
    uid = u"1.2.826.0.1.3680043.8.498.20261015"
    forma = cranio.shape
    base = _cleanup.temporaria("radai_ac_nidus_fast_")
    cortes = dict((z, [_anel(cx, cy, 30.0), _anel(cx, cy, 26.0)])
                  for z in range(4, forma[0] - 4))
    miolo = dict((z, [_anel(cx, cy, 24.0)]) for z in range(4, forma[0] - 4))

    def pasta_com(nome, arquivos):
        p = os.path.join(base, nome)
        os.makedirs(p)
        for arq, rois in arquivos:
            _rs_full(os.path.join(p, arq % uid[-8:]), rois, img)
        return p

    def osso(p):
        lidas, soltar = _com_dubles(img, p, uid)
        try:
            return _rotas_montadas()["/api/nidus/forma"](b=u"F").get("osso") or {}
        finally:
            soltar()
    fast = pasta_com(u"fast", [(u"RS_RadAI_FAST_20261015_%s.dcm",
                                {u"Skull_ai": cortes, u"Brain_ai": miolo})])
    oar = pasta_com(u"oar", [(u"RS_RadAI_20261015_%s.dcm",
                              {u"Skull_ai": cortes, u"Brain_ai": miolo})])
    sem = pasta_com(u"sem", [(u"RS_RadAI_FAST_20261015_%s.dcm",
                              {u"Brain_ai": miolo})])
    duas = pasta_com(u"duas", [(u"RS_RadAI_FAST_20261015_%s.dcm", {u"Skull_ai": cortes}),
                               (u"RS_RadAI_FULL_20261015_%s.dcm", {u"Skull_ai": cortes})])
    o_fast, o_oar, o_sem, o_duas = osso(fast), osso(oar), osso(sem), osso(duas)
    import radai_sets
    na_tela = radai_sets.NOME_NA_TELA
    checar(u"série só em FAST: o osso sai pela entrega do FAST (%s)" % na_tela["fast"],
           o_fast.get("tem") is True and o_fast.get("fonte") == na_tela["fast"]
           and o_fast.get("estruturas") == 1, str(o_fast))
    checar(u"série com a entrega (sem FULL): o osso sai por ela (%s)" % na_tela["oar"],
           o_oar.get("tem") is True and o_oar.get("fonte") == na_tela["oar"],
           str(o_oar))
    checar(u"com o FULL ao lado da entrega do FAST, vale o FULL",
           o_duas.get("fonte") == na_tela["full"], str(o_duas))
    checar(u"entrega sem osso: a tela diz qual é a entrega, para oferecer substituí-la",
           o_sem.get("tem") is False and o_sem.get("entrega") == na_tela["fast"]
           and o_sem.get("motivo") == S.SEM_OSSO_NA_ENTREGA, str(o_sem))
    guarda = S.ORDEM_DO_OSSO
    try:
        S.ORDEM_DO_OSSO = (((u"full",), True),)
        o_isca = osso(fast)
    finally:
        S.ORDEM_DO_OSSO = guarda
    checar(u"  isca: só com o FULL, a série em FAST fica sem tirar o osso",
           o_isca.get("tem") is False, str(o_isca))


PENDENTE_SUBSTITUIR_NA_FILA = False


def teste_o_pedido_leva_substituir():
    secao(u"«substituir» confirmado vai no pedido à fila (e a fila o guarda)")
    import asyncio
    import radai_nidus_screen as S
    import radai_queue_state as F
    import radai_thumbnail
    rotas = _rotas_montadas()
    pedidos = []
    guarda = (S.pedir_a_fila, radai_thumbnail.resolver)
    try:
        radai_thumbnail.resolver = lambda b: (u"pasta_X", u"1.2.3")
        S.pedir_a_fila = lambda itens: (
            pedidos.append(itens) or {"ok": True, "cartoes": [{"id": "c7", "posicao": 1}]})
        for corpo in ({"b": "X", "substituir": True}, {"b": "X", "substituir": "sim"},
                      {"b": "X"}):
            asyncio.run(rotas["/api/nidus/segmentar"](_Pedido(corpo)))
    finally:
        S.pedir_a_fila, radai_thumbnail.resolver = guarda
    itens = [p[0] for p in pedidos]
    checar(u"confirmado (true): o item leva «substituir»",
           len(itens) == 3 and itens[0].get("substituir") is True, str(itens[:1]))
    checar(u"  qualquer outro valor não substitui nada",
           len(itens) == 3 and "substituir" not in itens[1] and "substituir" not in itens[2],
           str(itens[1:]))
    pasta = _cleanup.temporaria("radai_ac_nidus_fila_")
    r = F.enfileirar({"itens": [{"pasta": pasta, "uid": u"1.2.826.0.1.3680043.8.498.77",
                                 "modo": "auto", "origem": "nidus",
                                 "substituir": True}]})
    cid = ((r.get("cartoes") or [{}])[0] or {}).get("id")
    carga = (F.cartao(cid) or {}).get("carga") or {}
    if cid:
        F.tirar(cid)
    guardou = carga.get("substituir") is True
    if PENDENTE_SUBSTITUIR_NA_FILA:
        print(u"  pendente (FILA): radai_queue_state.enfileirar ainda descarta "
              u"«substituir»; o lote pula a série com marcador de pronta")
        checar(u"  (pendente da FILA) a fila ainda descarta «substituir»: quando "
               u"guardar, esta checagem reprova e a lista de pendentes muda",
               r.get("ok") and not guardou, str(carga)[:120])
    else:
        checar(u"a fila guarda «substituir» no cartão (o lote refaz a série pronta)",
               r.get("ok") and guardou, str(carga)[:120])


def main():
    print(u"=" * 68)
    print(u"  test_nidus — a projecao vascular e a fronteira")
    print(u"=" * 68)
    if not _node():
        print(u"  sem node nesta maquina — o palco da tela nao roda; a analise"
              u" de escopo roda")
    try:
        import numpy
        import SimpleITK
    except Exception as e:
        print(u"  runtime sem numpy/SimpleITK (%s) — so as checagens de fonte"
              % type(e).__name__)
        for t in (teste_a_fronteira_nao_se_cruza, teste_nao_detecta_nada,
                  teste_a_suite_conhece_o_modulo) + TELA:
            try:
                t()
            except Exception as e:
                checar(u"%s (excecao)" % t.__name__, False, str(e)[:60])
        return _fechar()

    for t in (teste_a_convencao_e_a_do_arco_em_c,
              teste_o_js_da_convencao_e_o_python,
              teste_a_geometria_fecha,
              teste_a_projecao_e_o_extremo_do_raio,
              teste_as_linhas_sao_finas,
              teste_a_fronteira_nao_se_cruza,
              teste_nao_detecta_nada,
              teste_a_suite_conhece_o_modulo,
              teste_acumular_incidencias,
              teste_a_rota_da_forma_calcula_o_passo,
              teste_os_tres_planos_saem_na_orientacao_do_paciente,
              teste_a_projecao_sai_com_o_cranio_em_cima,
              teste_a_rm_nao_vira_um_quadrado_branco,
              teste_a_mascara_do_poligono_e_a_mesma_na_caixa,
              teste_o_tubo_de_duas_camadas_e_o_de_antes,
              teste_o_tubo_em_bits_e_o_mesmo_tubo,
              teste_o_pixel_da_tela_e_quadrado,
              teste_as_rotas_leem_a_serie_uma_vez,
              teste_a_rm_entra_no_seletor,
              teste_a_serie_colorida_e_recusada,
              teste_o_osso_sai_pela_segmentacao,
              teste_segmentar_vai_para_a_fila,
              teste_a_demo_saiu,
              teste_as_projecoes_vao_uma_por_vez,
              teste_o_acervo_abre_pelo_resolvedor_da_tabela,
              teste_a_chave_da_serie_nao_depende_do_bilhete,
              teste_o_osso_sai_tambem_pelo_oar_e_pelo_oar_fast,
              teste_o_pedido_leva_substituir,
              teste_a_pegada_da_caixa_numa_serie_obliqua,
              teste_a_malha_da_caixa,
              teste_as_malhas_da_caixa_pela_rota,
              teste_a_pegada_do_js_e_a_do_python,
              teste_o_veu_e_acompanhar_a_caixa) + TELA + (teste_no_navegador,):
        try:
            t()
        except Exception as e:
            import traceback
            checar(u"%s (excecao inesperada)" % t.__name__, False,
                   u"%s: %s" % (type(e).__name__, e))
            traceback.print_exc()
    return _fechar()


def _fechar():
    falhas = [(n, d) for n, ok, d in _RES if not ok]
    print(u"\n" + u"=" * 68)
    if falhas:
        print(u"FALHOU: %d de %d checagens" % (len(falhas), len(_RES)))
        for n, d in falhas:
            print(u"  - %s%s" % (n, ("  [%s]" % (d,)) if d else ""))
    else:
        print(u"OK: %d checagens, todas passaram" % len(_RES))
    print(u"=" * 68)
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
