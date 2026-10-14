# -*- coding: utf-8 -*-
import math

SEM_VOLUME = (
    u"A interseção é uma construção geométrica a partir do desenho do "
    u"usuário — não é um volume de tratamento, e este módulo não calcula "
    u"nem exibe o volume dela em cm³."
)

LIMITACAO_CLINICA = (
    u"Reconstrução por projeção a partir de angiotomografia. Não substitui "
    u"angiografia digital e não mostra dinâmica de fluxo — na angioTC a veia "
    u"de drenagem e a artéria nutridora têm o mesmo brilho, e é por isso que "
    u"a definição de nidus por uma difere da definição pela outra."
)

LIMITACAO_RM = (
    u"Na RM com gadolínio vale o mesmo: a imagem é estática e artéria e veia "
    u"realçam as duas. E o sinal da RM não é HU — as janelas são relativas "
    u"ao sinal da própria série, e o brilho de uma série não se compara com "
    u"o de outra."
)

INCIDENCIAS = (
    (u"AP", 0.0, 0.0),
    (u"Perfil D", 90.0, 0.0),
    (u"Perfil E", -90.0, 0.0),
    (u"Oblíqua ant. D", 45.0, 0.0),
    (u"Oblíqua ant. E", -45.0, 0.0),
    (u"Towne", 0.0, -30.0),
    (u"Caldwell", 0.0, 15.0),
    (u"Submento-vértex", 0.0, 90.0),
)

JANELAS = {
    "angio": (300.0, 700.0),
    "vaso_fino": (200.0, 400.0),
    "osso": (400.0, 1800.0),
    "parenquima": (40.0, 80.0),
}

JANELAS_RELATIVAS = {
    "angio": (90.0, 99.9),
    "vaso_fino": (99.0, 99.95),
    "parenquima": (1.0, 99.0),
    "ampla": (0.0, 99.99),
}
_PERCENTIS = tuple(sorted(set(p for par in JANELAS_RELATIVAS.values()
                              for p in par)))


def estatistica(img):
    import numpy as np
    import SimpleITK as sitk
    a = sitk.GetArrayViewFromImage(img)[::2, ::3, ::3]
    v = np.percentile(np.asarray(a, dtype=np.float32), _PERCENTIS)
    return dict(zip(_PERCENTIS, (float(x) for x in v)))


def tem_hu(modalidade=None, minimo=None):
    if modalidade:
        return str(modalidade).strip().upper() == "CT"
    return minimo is None or float(minimo) < -500.0


def escala_de(img, modalidade=None):
    import SimpleITK as sitk
    f = sitk.MinimumMaximumImageFilter()
    f.Execute(img)
    lo, hi = float(f.GetMinimum()), float(f.GetMaximum())
    e = {"hu": tem_hu(modalidade, lo), "min": lo, "max": hi}
    if not e["hu"]:
        e["percentis"] = estatistica(img)
    return e


def janela_de(nome, escala=None):
    if not escala or escala.get("hu", True) or not escala.get("percentis"):
        return JANELAS.get(nome, JANELAS["angio"])
    p = escala["percentis"]
    par = JANELAS_RELATIVAS.get(
        "ampla" if nome == "osso" else nome, JANELAS_RELATIVAS["angio"])
    lo, hi = float(p[par[0]]), float(p[par[1]])
    if hi <= lo:
        hi = lo + 1.0
    return ((lo + hi) / 2.0, hi - lo)

LADO_PADRAO = 512

LADO_ALTA = 1024

FUNDO_MAXIMO = 384


class SerieRecusada(ValueError):
    pass


RECUSA_COR = (
    u"A série é uma imagem colorida (%d componentes por pixel) — captura de "
    u"tela ou reconstrução exportada —, e não os cortes da angioTC ou da RM: "
    u"escolha a série de cortes.")

RECUSA_DIMENSAO = (
    u"O volume desta série não é 3D (dimensão %d): ela não é uma pilha de "
    u"cortes, e não dá projeção. Escolha a série de cortes.")

RECUSA_POUCOS_CORTES = (
    u"A série tem %d corte(s): não há volume para projetar.")


def conferir_serie(img):
    import SimpleITK as sitk
    comp = int(img.GetNumberOfComponentsPerPixel())
    if comp != 1:
        raise SerieRecusada(RECUSA_COR % comp)
    if u"vector" in str(img.GetPixelIDTypeAsString()).lower():
        img = sitk.VectorIndexSelectionCast(img, 0)
    dim = int(img.GetDimension())
    if dim != 3:
        raise SerieRecusada(RECUSA_DIMENSAO % dim)
    if min(int(s) for s in img.GetSize()) < 2:
        raise SerieRecusada(RECUSA_POUCOS_CORTES % min(img.GetSize()))
    return img

def lado_para_o_exame(img, teto=LADO_ALTA):
    import math as _m
    try:
        ext = [s * e for s, e in zip(img.GetSize(), img.GetSpacing())]
        diag = _m.sqrt(sum(x * x for x in ext))
        fino = min(float(e) for e in img.GetSpacing())
        ideal = int(round(diag / max(fino, 1e-6)))
        for cand in (256, 512, 768, LADO_ALTA):
            if cand >= ideal:
                return cand
        return teto
    except Exception:
        return LADO_PADRAO


def _euler(img, lao_rao, cra_cau):
    import SimpleITK as sitk
    t = sitk.Euler3DTransform()
    t.SetCenter(img.TransformContinuousIndexToPhysicalPoint(
        [(s - 1) / 2.0 for s in img.GetSize()]))
    t.SetRotation(math.radians(cra_cau), 0.0, math.radians(lao_rao))
    return t


def eixos_da_incidencia(lao_rao=0.0, cra_cau=0.0):
    import SimpleITK as sitk
    t = sitk.Euler3DTransform()
    t.SetRotation(math.radians(cra_cau), 0.0, math.radians(lao_rao))
    m = t.GetMatrix()
    fora = {}
    for nome, k in ((u"L", 0), (u"P", 1), (u"S", 2)):
        # GUARDA: mesma rotação de `_euler`; coluna = x, profundidade = y, linha = -z (crânio em cima).
        vx, vy, vz = m[k], m[3 + k], m[6 + k]
        fora[nome] = (round(vx, 4), round(-vz, 4), round(vy, 4))
    return fora


def caixa_de_texto(texto):
    try:
        v = [min(1.0, max(0.0, float(x))) for x in str(texto or u"").split(u",")]
    except (TypeError, ValueError):
        return None
    if len(v) != 6:
        return None
    pares = [tuple(sorted(v[i:i + 2])) for i in (0, 2, 4)]
    if any(b - a <= 0.0 for a, b in pares):
        return None
    if all(a <= 0.0 and b >= 1.0 for a, b in pares):
        return None
    return tuple(round(x, 4) for par in pares for x in par)


def _medidas_da_grade(img, lado, fundo=None):
    extensao = [s * e for s, e in zip(img.GetSize(), img.GetSpacing())]
    diag = math.sqrt(sum(x * x for x in extensao))
    passo = diag / float(lado)
    fundo = int(fundo or min(lado, FUNDO_MAXIMO))
    passo_fundo = diag / float(fundo)
    return diag, passo, passo_fundo, fundo


def _grade(img, lado, fundo=None):
    import SimpleITK as sitk
    diag, passo, passo_fundo, fundo = _medidas_da_grade(img, lado, fundo)
    ref = sitk.Image([lado, fundo, lado], sitk.sitkFloat32)
    ref.SetSpacing((passo, passo_fundo, passo))
    return ref, diag, passo, passo_fundo


def projetar(img, lao_rao=0.0, cra_cau=0.0, modo="mip", janela="angio",
             lado=LADO_PADRAO, laje_mm=None, fundo=None, escala=None,
             amostra=None):
    import numpy as np
    import SimpleITK as sitk

    if escala is None:
        escala = escala_de(img)
    t = _euler(img, lao_rao, cra_cau)
    ref, diag, passo, passo_fundo = _grade(img, lado, fundo)
    c = t.GetCenter()
    ref.SetOrigin((c[0] - diag / 2.0, c[1] - diag / 2.0, c[2] - diag / 2.0))
    fora = float(escala["min"] if modo == "mip" else escala["max"])
    r = sitk.Resample(img if amostra is None else amostra, ref, t.GetInverse(),
                      sitk.sitkLinear, fora)
    a = sitk.GetArrayViewFromImage(r)

    if laje_mm:
        espessura = max(1, int(round(float(laje_mm) / passo_fundo)))
        meio = a.shape[1] // 2
        i0 = max(0, meio - espessura // 2)
        a = a[:, i0:i0 + espessura, :]
    plano = a.max(axis=1) if modo == "mip" else a.min(axis=1)
    plano = np.ascontiguousarray(plano[::-1])

    centro, largura = janela_de(janela, escala)
    return plano, {"lao_rao": lao_rao, "cra_cau": cra_cau, "modo": modo,
                   "janela": janela, "centro": centro, "largura": largura,
                   "passo_mm": passo, "lado": lado,
                   "passo_fundo_mm": passo_fundo,
                   "fundo": int(ref.GetSize()[1]),
                   "hu": bool(escala.get("hu", True))}


def tubo(img, poligono, lao_rao=0.0, cra_cau=0.0, lado=LADO_PADRAO,
         fundo=None):
    import numpy as np
    import SimpleITK as sitk

    t = _euler(img, lao_rao, cra_cau)
    diag, passo, _pf, _f = _medidas_da_grade(img, lado)
    c = t.GetCenter()

    plano = _mascara_poligono(poligono, lado)[::-1]
    extrudado = np.ascontiguousarray(np.broadcast_to(
        plano.astype(np.uint8)[:, None, :], (lado, 2, lado)))
    m = sitk.GetImageFromArray(extrudado)
    m.SetSpacing((passo, diag, passo))
    m.SetOrigin((c[0] - diag / 2.0, c[1] - diag / 2.0, c[2] - diag / 2.0))

    voltou = sitk.Resample(m, img, t, sitk.sitkNearestNeighbor, 0)
    return sitk.GetArrayFromImage(voltou).view(np.bool_)


def _mascara_poligono(poligono, lado, largura=None):
    import numpy as np
    alt, larg = int(lado), int(lado if largura is None else largura)
    m = np.zeros((alt, larg), dtype=bool)
    pts = [(float(x), float(y)) for x, y in (poligono or ())]
    if len(pts) < 3:
        return m
    xs_p = [p[0] for p in pts]
    ys_p = [p[1] for p in pts]
    c0 = max(0, int(math.floor(min(xs_p) - 0.5)))
    c1 = min(larg, int(math.ceil(max(xs_p) - 0.5)) + 1)
    l0 = max(0, int(math.floor(min(ys_p) - 0.5)))
    l1 = min(alt, int(math.ceil(max(ys_p) - 0.5)) + 1)
    if c1 <= c0 or l1 <= l0:
        return m
    p = np.asarray(pts, dtype=np.float64)
    ax, ay = p[:, 0], p[:, 1]
    bx, by = np.roll(ax, -1), np.roll(ay, -1)
    ok = ay != by
    ax, ay, bx, by = ax[ok], ay[ok], bx[ok], by[ok]
    xs = np.arange(c0, c1, dtype=np.float64) + 0.5
    yc = np.arange(l0, l1, dtype=np.float64)[:, None] + 0.5
    cruza = (ay[None, :] > yc) != (by[None, :] > yc)
    linha, aresta = np.nonzero(cruza)
    if not linha.size:
        return m
    yy = yc[linha, 0]
    # GUARDA: mesma conta de antes; o pixel conta a aresta que cruza à direita do centro dele.
    xint = ((bx[aresta] - ax[aresta]) * (yy - ay[aresta])
            / (by[aresta] - ay[aresta]) + ax[aresta])
    k = np.searchsorted(xs, xint, side="left")
    h = np.zeros((l1 - l0, c1 - c0 + 1), dtype=np.int32)
    np.add.at(h, (linha, k), 1)
    direita = h[:, ::-1].cumsum(axis=1)[:, ::-1][:, 1:]
    m[l0:l1, c0:c1] = (direita % 2) == 1
    return m


OSSO_DILATACAO_VOXELS = 1


def dilatar(m, voltas=1):
    import numpy as np
    m = np.asarray(m, dtype=bool)
    for _ in range(int(voltas)):
        d = m.copy()
        d[1:] |= m[:-1]
        d[:-1] |= m[1:]
        d[:, 1:] |= m[:, :-1]
        d[:, :-1] |= m[:, 1:]
        d[:, :, 1:] |= m[:, :, :-1]
        d[:, :, :-1] |= m[:, :, 1:]
        m = d
    return m


def mascara_dos_cortes(cortes, forma, destino=None):
    import numpy as np
    forma = tuple(int(s) for s in forma)
    m = np.zeros(forma, dtype=bool) if destino is None else destino
    for z, polis in (cortes or {}).items():
        z = int(z)
        if not 0 <= z < forma[0]:
            continue
        plano = np.zeros(forma[1:], dtype=bool)
        for p in polis or ():
            # GUARDA: paridade entre os contornos do corte; o furo (por XOR ou por fenda) fica furo.
            plano ^= _mascara_poligono([(float(x), float(y)) for x, y in p],
                                       forma[1], forma[2])
        m[z] |= plano
    return m


def sem_osso(img, osso, valor):
    import numpy as np
    import SimpleITK as sitk
    a = sitk.GetArrayFromImage(img)
    m = dilatar(osso, OSSO_DILATACAO_VOXELS)
    if m.shape != a.shape:
        raise ValueError(u"a máscara do osso não tem a forma desta série")
    a[m] = np.asarray(valor).astype(a.dtype)
    out = sitk.GetImageFromArray(a)
    out.CopyInformation(img)
    return out


def eixos_lps(img):
    import itertools as _it
    d = [float(x) for x in img.GetDirection()]
    col = [(d[0 + n], d[3 + n], d[6 + n]) for n in range(3)]
    melhor, alvo = None, -1.0
    for p in _it.permutations(range(3)):
        s = sum(abs(col[p[f]][f]) for f in range(3))
        if s > alvo:
            melhor, alvo = p, s
    esp = img.GetSpacing()
    perm, inverter, mm = [], [], []
    for a in range(3):
        f = 2 - a
        n = melhor[f]
        perm.append(2 - n)
        inverter.append(col[n][f] < 0)
        mm.append(float(esp[n]))
    return tuple(perm), tuple(inverter), tuple(mm)


def para_lps(a, eixos):
    import numpy as np
    perm, inverter = eixos[0], eixos[1]
    if np.ndim(a) != len(perm):
        raise SerieRecusada(RECUSA_DIMENSAO % np.ndim(a))
    v = np.transpose(a, perm)
    fatia = tuple(slice(None, None, -1) if inv else slice(None)
                  for inv in inverter)
    return v[fatia]


def corte(v, eixo, indice):
    if isinstance(v, Compacto):
        f = v.fatia(eixo, indice)
        return f if eixo == 0 else f[::-1]
    if eixo == 0:
        return v[indice, :, :]
    if eixo == 1:
        return v[::-1, indice, :]
    return v[::-1, :, indice]


def mm_do_corte(mm_zyx, eixo):
    z, y, x = (float(e) for e in mm_zyx)
    return {0: (y, x), 1: (z, x), 2: (z, y)}[int(eixo)]


from radai_recon3d import (TETO_DA_TELA, grade_da_tela,
                           para_a_tela)


def escalar(segmentos, fator_lin, fator_col):
    return [((round(c0 * fator_col, 2), round(l0 * fator_lin, 2)),
             (round(c1 * fator_col, 2), round(l1 * fator_lin, 2)))
            for (c0, l0), (c1, l1) in segmentos]


class Compacto(object):

    __slots__ = ("bits", "shape")

    def __init__(self, bits, shape):
        self.bits = bits
        self.shape = tuple(int(s) for s in shape)

    def fatia(self, eixo, indice):
        import numpy as np
        nx = self.shape[2]
        if eixo == 0:
            return np.unpackbits(self.bits[indice], axis=-1,
                                 count=nx).astype(bool)
        if eixo == 1:
            return np.unpackbits(self.bits[:, indice, :], axis=-1,
                                 count=nx).astype(bool)
        byte, bit = divmod(int(indice), 8)
        return ((self.bits[:, :, byte] >> (7 - bit)) & 1).astype(bool)

    def any(self):
        return bool(self.bits.any())


def compactar(m):
    import numpy as np
    a = np.ascontiguousarray(np.asarray(m, dtype=bool))
    return Compacto(np.packbits(a, axis=-1), a.shape)


def intersecao(*tubos):
    import numpy as np
    if len(tubos) == 1 and isinstance(tubos[0], (list, tuple)):
        tubos = tuple(tubos[0])
    tubos = [t for t in tubos if t is not None]
    if not tubos:
        return None
    if all(isinstance(t, Compacto) for t in tubos):
        b = tubos[0].bits.copy()
        for t in tubos[1:]:
            np.bitwise_and(b, t.bits, out=b)
        return Compacto(b, tubos[0].shape)
    r = np.asarray(tubos[0], dtype=bool)
    for t in tubos[1:]:
        r = np.logical_and(r, np.asarray(t, dtype=bool))
    return r


def contorno_do_tubo(mascara, eixo, indice):
    import numpy as np
    plano = np.asarray(corte(mascara, eixo, indice), dtype=bool)
    if not plano.any():
        return []
    segs = []
    alt, larg = plano.shape
    for l in range(alt):
        linha = plano[l]
        muda = np.flatnonzero(np.diff(linha.astype(np.int8)))
        for c in muda:
            segs.append(((int(c) + 1, l), (int(c) + 1, l + 1)))
    for c in range(larg):
        col = plano[:, c]
        muda = np.flatnonzero(np.diff(col.astype(np.int8)))
        for l in muda:
            segs.append(((c, int(l) + 1), (c + 1, int(l) + 1)))
    return segs


class Serie(object):

    def __init__(self, img, modalidade=None):
        import SimpleITK as sitk
        img = conferir_serie(img)
        self.img = img
        self.modalidade = str(modalidade or u"")
        self.eixos = eixos_lps(img)
        self.v = para_lps(sitk.GetArrayViewFromImage(img), self.eixos)
        self.mm = self.eixos[2]
        self.escala = escala_de(img, modalidade)
        self.lado_util = lado_para_o_exame(img)
        self._recorte = (None, None)
        self.osso = None
        self._sem_osso = None

    @property
    def forma_do_array(self):
        return tuple(int(s) for s in reversed(self.img.GetSize()))

    def tirar_osso(self, mascara, info=None):
        import numpy as np
        m = np.asarray(mascara, dtype=bool)
        if m.shape != self.forma_do_array:
            raise ValueError(u"a máscara do osso não tem a forma desta série")
        self._recorte = (None, None)
        if not m.any():
            self.osso, self._sem_osso = None, None
            return False
        self._sem_osso = sem_osso(self.img, m, self.escala["min"])
        self.osso = dict(info or {}, voxels=int(m.sum()))
        return True

    def base(self, modo="mip", osso=False):
        # GUARDA: o osso só sai no MIP; no MinIP o valor que o apaga viraria buraco escuro.
        if osso and modo == "mip" and self._sem_osso is not None:
            return self._sem_osso
        return self.img

    def img_na_caixa(self, caixa, modo="mip", osso=False):
        import SimpleITK as sitk
        base = self.base(modo, osso)
        if caixa is None:
            return base
        chave = (tuple(caixa), base is not self.img)
        if self._recorte[0] == chave:
            return self._recorte[1]
        self._recorte = (None, None)
        perm, inverter = self.eixos[0], self.eixos[1]
        tam = list(self.img.GetSize())
        ini, ext = [0, 0, 0], list(tam)
        for eixo in range(3):
            # GUARDA: eixo da vista -> eixo do array (`perm`) -> dimensão do sitk (2 - eixo do array).
            dim = 2 - perm[eixo]
            n = tam[dim]
            i0 = max(0, int(math.floor(caixa[2 * eixo] * n)))
            i1 = min(n, int(math.ceil(caixa[2 * eixo + 1] * n)))
            if inverter[eixo]:
                i0, i1 = n - i1, n - i0
            ini[dim], ext[dim] = i0, max(1, i1 - i0)
        out = sitk.RegionOfInterest(base, ext, ini)
        self._recorte = (chave, out)
        return out

    @property
    def forma(self):
        return tuple(int(s) for s in self.v.shape)

    def passos(self, lados):
        return {str(l): round(float(_medidas_da_grade(self.img, l)[1]), 3)
                for l in lados}

    def tubo(self, poligono, lao_rao, cra_cau, lado):
        return compactar(para_lps(
            tubo(self.img, poligono, lao_rao, cra_cau, lado=lado),
            self.eixos))


def abrir(img, modalidade=None):
    return Serie(img, modalidade)
