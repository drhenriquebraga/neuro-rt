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
                              ("  [%s]" % detalhe) if detalhe else ""))
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
    t = N._euler(img, lao, cra)
    _ref, diag, passo, passo_fundo = N._grade(img, lado)
    c = t.GetCenter()
    org = (c[0] - diag / 2.0, c[1] - diag / 2.0, c[2] - diag / 2.0)
    p = np.array(t.TransformPoint([float(v) for v in alvo_mm]))
    gx = (p[0] - org[0]) / passo
    gz = (p[2] - org[2]) / passo
    return gx + 0.5, lado - 0.5 - gz


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

    checar(u"a tela nao usa canvas", "<canvas" not in tela.lower())
    checar(u"nem getContext", "getcontext" not in tela.lower())
    checar(u"e desenha em SVG", "<svg" in tela.lower())

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
        checar(u"a lib nao tem `%s`" % proibido, proibido not in codigo)
        checar(u"a tela nao tem `%s`" % proibido, proibido not in tela)

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
RegExp encodeURIComponent decodeURIComponent parseInt parseFloat isNaN""".split())

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
var _FETCHES = [], _ERROS = [], _EL = {}, _CARGA = null, _NINC = 1;

function Elemento(id){
 this.id=id; this.innerHTML=''; this.textContent=''; this.value='';
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
Elemento.prototype.removeAttribute=function(k){ delete this._attrs[k] };
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
  e.className = at['class'] || '';   // e isso ja acende o `on` do gabarito
  if(at.id) _EL[at.id] = e;
  return e;
 });
}

var document = {
 getElementById:function(id){ return _EL[id]||(_EL[id]=new Elemento(id)) },
 querySelectorAll:function(sel){ return _GRUPOS[sel]||[] },
 addEventListener:function(){}
};
var window = { addEventListener:function(n,f){
 if(n==='DOMContentLoaded') _CARGA=f } };

function _resposta(url){
 if(url.indexOf('/api/nidus/series')>=0)
  return {series:[{bilhete:'B1', desc:'angio cranio', cortes:400,
                   espessura_mm:0.5},
                  {bilhete:'B2', desc:'outra serie', cortes:300,
                   espessura_mm:1.0}]};
 if(url.indexOf('/api/nidus/forma')>=0)
  return {forma:[400,512,512], espacamento:[0.5,0.45,0.45],
          passos:{'256':1.28,'512':0.64,'768':0.43,'1024':0.32},
          lado_util:768};
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
 return {};
}
function fetch(url, op){
 _FETCHES.push({url:String(url), op:op||null});
 var d=_resposta(String(url));
 return Promise.resolve({json:function(){ return Promise.resolve(d) }});
}
"""

ABRE = u"""
function _tique(){ return new Promise(function(r){ setTimeout(r,0) }) }
async function _esperar(n){ for(var i=0;i<(n||6);i++){ await _tique() } }
function _tentar(nome,f){ try{ return f() }catch(e){ _ERROS.push(nome+': '+e) } }
function _ligado(b){ return !!(b && (b.classList.contains('on')
  || /(^| )on( |$)/.test(b.className))) }
function _ev(x,y){ return {clientX:x, clientY:y, preventDefault:function(){},
                           stopPropagation:function(){}} }
function _svg(){ return document.getElementById('nd_svg') }
async function _abrir(){
 _tentar('carga', function(){ if(_CARGA) _CARGA() });
 await _esperar();
 if(!ND.b){
  document.getElementById('nd_serie').value='0';
  _tentar('escolher', function(){ ndEscolher() });
  await _esperar();
 }
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
    for cid in ("nd_res", "nd_incid", "nd_ferr", "nd_jan"):
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
    secao(u"a tela acorda, e a lista de series e pedida")
    if not _node():
        checar(u"(sem node — o palco nao rodou)", True,
               u"instale o node para a prova por execucao")
        return
    d = _encenar(u"""
 _tentar('carga', function(){ if(_CARGA) _CARGA() });
 await _esperar();
 pronto({pediu:_FETCHES.some(function(f){
          return f.url.indexOf('/api/nidus/series')>=0 }),
         guardadas:ND.guardadas.length,
         opcoes:document.getElementById('nd_serie').innerHTML.length});
""")
    checar(u"a carga da pagina nao levanta", not d["erros"],
           u" | ".join(d["erros"])[:160])
    checar(u"e a lista de series e pedida", d.get("pediu"), str(d.get("urls")))
    checar(u"a lista de incidencias nasce vazia", d.get("guardadas") == 0,
           str(d.get("guardadas")))
    checar(u"e o seletor de serie foi preenchido", (d.get("opcoes") or 0) > 20)

    iscado = _encenar(u"""
 _tentar('carga', function(){ if(_CARGA) _CARGA() });
 await _esperar();
 pronto({pediu:_FETCHES.some(function(f){
          return f.url.indexOf('/api/nidus/series')>=0 })});
""", ajuste=lambda js: js.replace("guardadas:[], sessao:null",
                                  "guardadas:[null,null], sessao:null"))
    checar(u"e com os dois nulos de volta a lista NAO e pedida (isca)",
           not iscado.get("pediu") and bool(iscado.get("erros")),
           u" | ".join(iscado.get("erros") or [])[:120])


def teste_guardar_dispara_a_retroprojecao():
    secao(u"guardar dispara a retroprojecao (o «vou salvando»)")
    if not _node():
        checar(u"(sem node — o palco nao rodou)", True)
        return
    d = _encenar(u"""
 await _abrir();
 _ERROS.length = 0;
 var antes = _FETCHES.length;
 _tentar('desenhar', function(){ ndDesenhar() });
 ND.pontos = [[10,10],[60,10],[60,60],[10,60]];
 _tentar('guardar', function(){ ndGuardar() });
 await _esperar();
 var depois = _FETCHES.slice(antes).map(function(f){ return f.url });
 pronto({novas:depois,
         retro:depois.some(function(u){ return u.indexOf('/api/nidus/tubos')>=0 }),
         guardadas:ND.guardadas.length,
         sessao:ND.sessao||null,
         msg:document.getElementById('nd_msg').textContent});
""")
    checar(u"guardar nao levanta", not d["erros"], u" | ".join(d["erros"])[:160])
    checar(u"a incidencia entra na lista", d.get("guardadas") == 1,
           str(d.get("guardadas")))
    checar(u"e a retroprojecao E PEDIDA no mesmo clique", d.get("retro"),
           str(d.get("novas")))
    checar(u"a sessao volta do servidor", bool(d.get("sessao")),
           str(d.get("sessao")))
    checar(u"e a mensagem fala da incidencia guardada",
           u"incid" in (d.get("msg") or u"").lower(), d.get("msg"))

    d2 = _encenar(u"""
 await _abrir();
 _tentar('desenhar', function(){ ndDesenhar() });
 ND.pontos = [[10,10],[60,10],[60,60],[10,60]];
 _tentar('guardar', function(){ ndGuardar() });
 await _esperar();
 _tentar('guardar2', function(){ ndGuardar() });
 await _esperar();
 pronto({guardadas:ND.guardadas.length,
         msg:document.getElementById('nd_msg').textContent});
""")
    checar(u"guardar de novo, sem desenhar, nao duplica a incidencia",
           d2.get("guardadas") == 1, str(d2.get("guardadas")))

    iscado = _encenar(u"""
 await _abrir();
 _ERROS.length = 0;
 var antes = _FETCHES.length;
 _tentar('desenhar', function(){ ndDesenhar() });
 ND.pontos = [[10,10],[60,10],[60,60],[10,60]];
 _tentar('guardar', function(){ ndGuardar() });
 await _esperar();
 pronto({retro:_FETCHES.slice(antes).some(function(u){
          return u.url.indexOf('/api/nidus/tubos')>=0 })});
""", ajuste=lambda js: js.replace(
        "ndMsg('incidência '+ND.guardadas.length+' guardada — LAO '",
        "ndMsg('incidência '+(qual?'B':'A')+' guardada — LAO '"))
    checar(u"e com o `qual` de volta a retroprojecao PARA (isca)",
           not iscado.get("retro")
           and any("qual" in e for e in iscado.get("erros") or []),
           u" | ".join(iscado.get("erros") or [])[:120])


def teste_o_lapis_traca_e_afina():
    secao(u"o lapis: arrasto, e o traco e afinado antes de sair")
    if not _node():
        checar(u"(sem node — o palco nao rodou)", True)
        return
    d = _encenar(u"""
 await _abrir();
 _tentar('ferramenta', function(){ ndFerramenta('lapis') });
 _tentar('desenhar', function(){ ndDesenhar() });
 var N_AM = 240, R = 80, cx = 200, cy = 200, s = _svg();
 function _p(i){
  var t = 2*Math.PI*i/N_AM;
  var j = ((i*2654435761) % 1000)/1000 - 0.5;   // tremor reprodutivel
  return [cx + (R + j*1.6)*Math.cos(t), cy + (R + j*1.6)*Math.sin(t)];
 }
 var p0 = _p(0);
 s.disparar('mousedown', _ev(p0[0], p0[1]));
 for(var i=1;i<N_AM;i++){ var p=_p(i); s.disparar('mousemove', _ev(p[0],p[1])) }
 var bruto = ND.pontos.slice();
 s.disparar('mouseup', _ev(p0[0], p0[1]));
 pronto({bruto:bruto, fino:ND.pontos.slice(), lado:ND.lado,
         marca:document.getElementById('nd_marca').innerHTML,
         msg:document.getElementById('nd_msg').textContent});
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


def teste_os_dois_modos_convivem():
    secao(u"os dois modos convivem, e a tela diz qual esta valendo")
    if not _node():
        checar(u"(sem node — o palco nao rodou)", True)
        return
    d = _encenar(u"""
 await _abrir();
 _tentar('desenhar', function(){ ndDesenhar() });
 var s=_svg(), r={};
 r.inicial = ND.ferramenta;
 s.disparar('click', _ev(100,100)); s.disparar('click', _ev(160,100));
 s.disparar('click', _ev(160,160));
 r.por_clique = ND.pontos.length;
 s.disparar('mousedown', _ev(50,50)); s.disparar('mousemove', _ev(60,60));
 s.disparar('mouseup', _ev(60,60));
 r.clique_ignora_arrasto = ND.pontos.length;
 _tentar('lapis', function(){ ndFerramenta('lapis') });
 r.depois = ND.ferramenta;
 var bts = document.querySelectorAll('#nd_ferr .nd-bt');
 r.botoes = bts.map(function(b){ return [b.getAttribute('data-f'), _ligado(b)] });
 s.disparar('mousedown', _ev(100,100));
 for(var i=0;i<30;i++) s.disparar('mousemove', _ev(100+i*2, 100+i));
 r.por_arrasto = ND.pontos.length;
 s.disparar('mouseup', _ev(160,130));
 var n = ND.pontos.length;
 s.disparar('click', _ev(10,10));
 r.lapis_ignora_clique = (ND.pontos.length === n);
 pronto(r);
""")
    checar(u"o modo de fabrica e o de cliques", d.get("inicial") == "clique",
           str(d.get("inicial")))
    checar(u"tres cliques marcam tres vertices", d.get("por_clique") == 3,
           str(d.get("por_clique")))
    checar(u"e o arrasto nao desenha no modo de cliques",
           d.get("clique_ignora_arrasto") == 3,
           str(d.get("clique_ignora_arrasto")))
    checar(u"o lapis assume", d.get("depois") == "lapis", str(d.get("depois")))
    checar(u"e o arrasto desenha nele", (d.get("por_arrasto") or 0) >= 8,
           str(d.get("por_arrasto")))
    checar(u"e o clique nao acrescenta vertice no lapis",
           d.get("lapis_ignora_clique"))
    bts = d.get("botoes") or []
    checar(u"a barra de ferramenta tem os dois botoes", len(bts) == 2, str(bts))
    acesos = [b[0] for b in bts if b[1]]
    checar(u"e so o corrente esta aceso", acesos == ["lapis"], str(bts))


def teste_a_grade_do_desenho_acompanha_a_resolucao():
    secao(u"a grade do desenho acompanha a resolucao escolhida")
    if not _node():
        checar(u"(sem node — o palco nao rodou)", True)
        return
    d = _encenar(u"""
 await _abrir();
 var r={inicial:ND.lado, vb0:_svg().getAttribute('viewBox')};
 var bts=document.querySelectorAll('#nd_res .nd-bt');
 r.aceso_no_html = bts.filter(function(b){ return _ligado(b) })
                      .map(function(b){ return b.getAttribute('data-r') });
 _tentar('res', function(){ ndResolucao(1024) });
 r.depois=ND.lado; r.vb1=_svg().getAttribute('viewBox');
 r.aceso = bts.filter(function(b){ return _ligado(b) })
              .map(function(b){ return b.getAttribute('data-r') });
 pronto(r);
""")
    checar(u"o `lado` de fabrica e o do botao aceso no HTML",
           [str(d.get("inicial"))] == (d.get("aceso_no_html") or []),
           u"JS %s · HTML %s" % (d.get("inicial"), d.get("aceso_no_html")))
    checar(u"o viewBox nasce do `lado`",
           (d.get("vb0") or u"") == u"0 0 %s %s" % (d.get("inicial"),
                                                    d.get("inicial")),
           str(d.get("vb0")))
    checar(u"e ele acompanha a troca de resolucao",
           d.get("vb1") == u"0 0 1024 1024", str(d.get("vb1")))
    checar(u"e o botao aceso acompanha", d.get("aceso") == ["1024"],
           str(d.get("aceso")))


def teste_as_incidencias_se_somam_nos_tres_planos():
    secao(u"as incidencias acumuladas aparecem JUNTAS nos tres planos")
    if not _node():
        checar(u"(sem node — o palco nao rodou)", True)
        return
    d = _encenar(u"""
 await _abrir();
 _tentar('desenhar', function(){ ndDesenhar() });
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
    if not _node():
        checar(u"(sem node — o palco nao rodou)", True)
        return
    d = _encenar(u"""
 await _abrir();
 _tentar('desenhar', function(){ ndDesenhar() });
 ND.pontos = [[10,10],[60,10],[60,60],[10,60]];
 _tentar('guardar', function(){ ndGuardar() });
 await _esperar();
 var antiga = ND.sessao;
 document.getElementById('nd_serie').value='1';
 var antes=_FETCHES.length;
 _tentar('trocar', function(){ ndEscolher() });
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
    import radai_nidus_screen as S
    bruto = fonte("radai_nidus_screen.py")
    checar(u"a rota da forma devolve o passo de cada resolucao",
           '"passos": serie.passos(LADOS)' in bruto)
    checar(u"e os lados oferecidos moram num lugar so",
           len(re.findall(r"\(256,\s*512,\s*768", bruto)) <= 1,
           u"%d copias da lista de lados"
           % len(re.findall(r"\(256,\s*512,\s*768", bruto)))
    if not _node():
        checar(u"(sem node — o palco nao rodou)", True)
        return
    d = _encenar(u"""
 await _abrir();
 var r={normal:document.getElementById('nd_passo').textContent};
 _tentar('alta', function(){ ndResolucao(1024) });
 r.alta=document.getElementById('nd_passo').textContent;
 _tentar('rapida', function(){ ndResolucao(256) });
 r.rapida=document.getElementById('nd_passo').textContent;
 pronto(r);
""")
    for k, esperado in (("normal", u"0,64"), ("alta", u"0,32"),
                        ("rapida", u"1,28")):
        checar(u"o passo em «%s» aparece na tela" % k,
               esperado in (d.get(k) or u""), repr(d.get(k)))
    checar(u"e pedir acima do que a serie oferece e dito na tela",
           u"interpola" in (d.get("alta") or u"").lower(), repr(d.get("alta")))
    checar(u"e o que cabe na serie nao leva aviso nenhum",
           u"interpola" not in (d.get("normal") or u"").lower(),
           repr(d.get("normal")))


def teste_a_tela_diz_a_escala_da_rm():
    secao(u"a tela diz a escala da RM e a modalidade da serie (v8.3)")
    if not _node():
        checar(u"(sem node — o palco nao rodou)", True)
        return
    d = _encenar(u"""
 await _abrir();
 var r={tc:document.getElementById('nd_escala').textContent};
 var _velha=_resposta;
 _resposta=function(url){
  if(url.indexOf('/api/nidus/series')>=0)
   return {series:[{bilhete:'B1', modalidade:'CT', desc:'angio', cortes:400,
                    espessura_mm:0.5},
                   {bilhete:'B2', modalidade:'MR', desc:'T1 pos-Gd',
                    cortes:180, espessura_mm:1.0}]};
  if(url.indexOf('/api/nidus/forma')>=0){
   var f=_velha(url); f.hu=false; f.modalidade='MR'; return f }
  return _velha(url) };
 _tentar('listar', function(){ ndListar('X') });
 await _esperar();
 r.opcoes=document.getElementById('nd_serie').innerHTML;
 document.getElementById('nd_serie').value='1';
 _tentar('rm', function(){ ndEscolher() });
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


TELA = (teste_o_javascript_nao_le_nome_solto,
        teste_a_tela_acorda_e_pede_as_series,
        teste_guardar_dispara_a_retroprojecao,
        teste_o_lapis_traca_e_afina,
        teste_os_dois_modos_convivem,
        teste_a_grade_do_desenho_acompanha_a_resolucao,
        teste_as_incidencias_se_somam_nos_tres_planos,
        teste_serie_nova_nao_herda_a_sessao,
        teste_o_passo_do_detector_aparece,
        teste_a_tela_diz_a_escala_da_rm)


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
    t = N._euler(img, lao, cra)
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

    def __init__(self, corpo):
        self._c = corpo

    async def json(self):
        return self._c


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
    secao(u"a RM entra no seletor (v8.3)")
    import asyncio
    import radai_batch
    import radai_nidus_screen as S
    rotas = _rotas_montadas()
    pedidos = []

    def _varrer(pasta, **k):
        pedidos.append(k)
        return []

    guarda = radai_batch.varrer
    try:
        radai_batch.varrer = _varrer
        asyncio.run(rotas["/api/nidus/series"](_Pedido({"pasta": u"X"})))
    finally:
        radai_batch.varrer = guarda
    mods = tuple((pedidos[:1] or [{}])[0].get("modalidades") or ())
    checar(u"a lista pede TC e RM", "CT" in mods and "MR" in mods, str(mods))


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

    for t in (teste_a_geometria_fecha,
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
              teste_a_rm_entra_no_seletor) + TELA:
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
            print(u"  - %s%s" % (n, ("  [%s]" % d) if d else ""))
    else:
        print(u"OK: %d checagens, todas passaram" % len(_RES))
    print(u"=" * 68)
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
