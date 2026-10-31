# -*- coding: utf-8 -*-
import hashlib
import itertools
import json
import os

import radai_menu
import radai_nidus
import radai_recon3d_gl
import radai_web

LADOS = (256, 512, 768, radai_nidus.LADO_ALTA)

LADO_DA_TELA = radai_nidus.LADO_ALTA

LADO_DA_PREVIA = LADOS[0]

MODALIDADES = ("CT", "MR")
MIN_CORTES = 20

SEM_SEGMENTACAO = (
    u"esta série ainda não tem segmentação do ContourLab: o osso continua "
    u"na projeção")

SEM_UID = (
    u"sem o UID da série não dá para achar a segmentação dela: o osso "
    u"continua na projeção")

SEM_OSSO_NA_ENTREGA = (
    u"a entrega desta série não tem osso que sirva para a projeção: o osso "
    u"continua na projeção")

FILA_INDISPONIVEL = (
    u"fila indisponível: a fila da estação não respondeu. Mande a série pelo "
    u"«Rodar agora» e escolha-a de novo quando terminar.")

FORA_DO_ACERVO = (
    u"esta série não está mais no acervo: recarregue a lista e escolha-a de "
    u"novo")

PROJECAO_VELHA = u"pedido de projeção substituído por um mais novo"

ORDEM_DO_OSSO = (((u"full", u"oar"), True), ((u"fast",), False))


def chave_da_serie(pasta, uid):
    uid = str(uid or u"").strip()
    base = (u"uid:" + uid) if uid else (
        u"pasta:" + os.path.normcase(os.path.abspath(str(pasta or u""))))
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:24]

CSS = u"""
.nd-wrap{--nd-c0:#7FD1D6;--nd-c1:#B886F0;--nd-c2:#6FD08C;--nd-c3:#F0846F;--nd-c4:#D8C24F;
 --nd-i0:#7FD1D6;--nd-i1:#B886F0;--nd-i2:#6FD08C;--nd-i3:#F0846F;--nd-i4:#D8C24F;
 --nd-caixa:#E39B4F;--nd-pad-fundo:var(--panel-2);--nd-pad-grade:var(--line);
 --nd-pad-forte:var(--line-strong);
 max-width:1760px;margin:0 auto;padding:0 16px 0;display:flex;flex-direction:column;
 gap:6px;min-width:0}
:root[data-tema="claro"] .nd-wrap{--nd-c0:#176A6F;--nd-c1:#6E3FB0;--nd-c2:#1F7A3E;
 --nd-c3:#B4432F;--nd-c4:#7A6A0C}
.nd-cabeca{display:flex;align-items:center;gap:14px;min-height:46px;margin:10px 0 0;min-width:0}
.nd-cabeca .ui-fn{display:flex;align-items:center;gap:14px;margin:0;min-width:0;flex:1 1 auto}
.nd-cabeca .ui-fn-tit{flex:none}
.nd-cabeca .ui-fn-frase{margin:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
 font-size:13.5px;min-width:0}
.nd-serie{margin-left:auto;display:flex;align-items:center;gap:8px;flex:none;max-width:44%}
.nd-serie .ui-cartao{padding:6px 10px 6px 8px;min-height:0;gap:10px;max-width:100%}
.nd-serie .ui-cartao-ic{width:30px;height:30px}
.nd-ferramentas{display:flex;flex-direction:column;gap:5px;margin:0;padding:6px 12px;
 background:var(--panel);border:1px solid var(--line);border-radius:var(--r-2xl,12px)}
.nd-linha{display:flex;flex-wrap:nowrap;gap:5px 18px;align-items:center;min-width:0}
.nd-ferramentas .nd-grupo{display:flex;align-items:center;gap:6px;flex:none;padding:0;border:0}
.nd-grupo > .t{font:400 10px/1 var(--font-mono,monospace);letter-spacing:.14em;
 text-transform:uppercase;color:var(--text-dim);white-space:nowrap}
.nd-grupo .g{display:flex;gap:4px;align-items:center}
.nd-grupo .sub{font-size:11px;color:var(--text-dim);line-height:1.45;white-space:nowrap}
.nd-ferramentas .nd-osso{min-width:0;flex:1 1 auto}
.nd-osso .nd-bt{flex:none}
.nd-osso .sub{overflow:hidden;text-overflow:ellipsis;min-width:0}
.nd-osso .sub b{font-weight:500;color:var(--text)}
.nd-laje input[type=range]{width:96px}
.nd-lapis{display:inline-flex;align-items:center;gap:5px;font-size:11px;color:var(--accent)}
.nd-lapis .ui-ic{position:static;width:1em;height:1em}
#nd_msg{min-height:18px;font-size:12px;line-height:18px;margin:0;color:var(--text-muted);
 white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#nd_msg.erro{color:var(--perigo,#E96A5C)}
#nd_msg.ok{color:var(--success,#5BC57F)}
.nd-wrap input[type=range]{accent-color:var(--mod-nidus);cursor:pointer}

.nd-trabalho{display:flex;gap:12px;min-height:0;align-items:stretch}
.nd-cx{border:1px solid var(--line);border-radius:var(--r-xl,10px);background:var(--panel);
 padding:9px;box-sizing:border-box}
.nd-rot{font:400 10px/1 var(--font-mono,monospace);letter-spacing:.11em;
 text-transform:uppercase;color:var(--text-dim);display:flex;align-items:center;gap:10px;
 height:20px;white-space:nowrap;min-width:0}
.nd-rot b{font-weight:400;color:var(--text-muted)}
.nd-rot .dir{margin-left:auto;display:flex;align-items:center;gap:6px}
.nd-leitura{font:600 13px/1 var(--font-mono,monospace) !important;color:var(--text) !important;
 letter-spacing:.02em;text-transform:none}
.nd-estado{display:inline-flex;align-items:center;gap:6px;font:400 10px/1 var(--font-mono,monospace);
 letter-spacing:.08em;color:var(--text-dim);text-transform:uppercase}
.nd-estado i{width:7px;height:7px;border-radius:50%;background:var(--success);display:block}
.nd-estado.previa{color:var(--aviso)}
.nd-estado.previa i{background:var(--aviso);animation:nd-pulso 1s ease-in-out infinite}
@keyframes nd-pulso{50%{opacity:.35}}

.nd-colA{display:grid;grid-template-columns:var(--nd-q,480px) 44px;
 grid-template-rows:20px var(--nd-q,480px) 40px;gap:6px;padding:9px 9px 6px;flex:none}
.nd-colA > .nd-rot{grid-column:1 / 3}
.nd-palco{position:relative;background:var(--img-fundo,#000);border-radius:var(--r-lg,8px);
 overflow:hidden;display:flex;align-items:center;justify-content:center}
.nd-colA .nd-palco{width:var(--nd-q,480px);height:var(--nd-q,480px)}
.nd-palco img{width:100%;height:100%;object-fit:contain;display:block;
 image-rendering:pixelated;user-select:none}
.nd-palco svg{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}
.nd-palco.desenhavel{cursor:crosshair}
.nd-palco.desenhavel #nd_svg{pointer-events:auto}
.nd-palco.esperando #nd_svg{cursor:progress}
.nd-palco.arrastando{cursor:grabbing}
.nd-zoom{position:absolute;inset:0;transform-origin:0 0;will-change:transform}
.nd-palco.inv{background:#fff}
.nd-palco.inv .nd-zoom img{filter:invert(1)}
.nd-fora{fill:rgba(110,124,148,.24);fill-rule:evenodd;stroke:none;pointer-events:none}
.nd-pegada{fill:none;stroke:var(--nd-caixa);stroke-width:1.2;stroke-dasharray:6 4;
 vector-effect:non-scaling-stroke;opacity:.9;pointer-events:none}
.nd-ferr-palco{position:absolute;top:8px;right:8px;z-index:3;display:flex;gap:4px}
.nd-ferr-palco .nd-bt{background:rgba(6,13,26,.74);border-color:rgba(230,237,247,.16);
 color:var(--img-texto,#e6edf7)}
.nd-ferr-palco .nd-bt:hover{color:var(--img-texto,#e6edf7);border-color:rgba(230,237,247,.4)}
.nd-ferr-palco .nd-bt[aria-pressed="true"]{border-color:var(--nd-caixa);color:#f3c99b;
 background:rgba(40,24,8,.8)}
.nd-bt.nd-ic{width:30px;padding:0;display:inline-flex;align-items:center;
 justify-content:center;font-size:15px}
.nd-zoomv{position:absolute;left:8px;bottom:8px;z-index:3;
 font:400 10px/1 var(--font-mono,monospace);color:var(--img-texto,#e6edf7);
 background:rgba(0,0,0,.72);padding:4px 6px;border-radius:4px;pointer-events:none}
.nd-zoomv.previa{color:#f6c37a}
.nd-bt .ui-ic{position:static;inset:auto;width:1em;height:1em;pointer-events:none}
.nd-palco .nd-eixos{position:absolute;inset:auto 6px 6px auto;width:84px;height:84px;
 z-index:3;pointer-events:none}
.nd-eixos line{stroke:#8fa6c8;stroke-width:1.5;stroke-linecap:round}
.nd-eixos text{fill:#dce6f5;font:600 11px var(--font-mono,monospace);
 text-anchor:middle;dominant-baseline:central}
.nd-palco.inv .nd-eixos line{stroke:#46607f}
.nd-palco.inv .nd-eixos text{fill:#1b2a40}

.nd-barra-v{display:flex;flex-direction:column;align-items:center;gap:4px;height:var(--nd-q,480px)}
.nd-barra-v .rotulo{font:400 11px/1.1 var(--font-mono,monospace);color:var(--text-muted);
 letter-spacing:.04em}
.nd-barra-v .trilho{position:relative;flex:1 1 0;min-height:0;width:44px}
.nd-barra-v input[type=range]{position:absolute;top:0;bottom:0;left:10px;
 writing-mode:vertical-lr;direction:rtl;width:24px;height:100%;margin:0}
.nd-ang{width:44px;height:26px;box-sizing:border-box;padding:0 5px;text-align:right;
 border-radius:var(--r-md,6px);border:1px solid var(--line-strong);background:var(--panel-2);
 color:var(--text);font:12px var(--font-mono,monospace)}
.nd-ang:focus{outline:0;border-color:var(--accent)}
.nd-barra-h{display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:8px;
 grid-column:1 / 3}
.nd-barra-h .lado{font:400 11px/1 var(--font-mono,monospace);color:var(--text-muted);
 letter-spacing:.04em;white-space:nowrap}
.nd-barra-h .trilho{position:relative;height:40px;display:flex;flex-direction:column;
 justify-content:center}
.nd-barra-h input[type=range]{width:100%;margin:0}
.nd-barra-h .escala{position:relative;height:12px;margin-top:2px}
.nd-barra-h .escala span{position:absolute;transform:translateX(-50%);
 font:400 10px/1 var(--font-mono,monospace);color:var(--text-dim);white-space:nowrap}
.nd-barra-h .fim{display:flex;align-items:center;gap:6px}

.nd-colB{flex:1 1 auto;min-width:0;display:flex;flex-direction:column;gap:10px}
.nd-cima{flex:1 1 auto;min-height:0;display:flex;gap:10px}
.nd-3d{flex:1 1 auto;min-width:0;display:flex;flex-direction:column;gap:6px}
.nd-palco3d{position:relative;flex:1 1 auto;min-height:110px;background:var(--img-fundo,#000);
 border-radius:var(--r-lg,8px);overflow:hidden}
.nd-palco3d canvas{position:absolute;inset:0;width:100%;height:100%;display:block;
 cursor:grab;touch-action:none}
.nd-palco3d canvas:active{cursor:grabbing}
.nd-palco3d .nd-eixos{position:absolute;right:6px;bottom:6px;width:70px;height:70px;
 z-index:3;pointer-events:none}
.nd-palco3d .nd-eixos text{font-size:10px}
.nd-etq{position:absolute;z-index:2;font:400 10px/1 var(--font-mono,monospace);
 color:var(--img-texto-fraco,#a3b1c6);background:rgba(0,0,0,.6);padding:3px 5px;
 border-radius:4px;pointer-events:none;transform:translate(-50%,-50%);white-space:nowrap}
.nd-etq.forte{color:#f6c37a}
.nd-cant{position:absolute;left:8px;top:8px;z-index:3;font:400 10px/1.35 var(--font-mono,monospace);
 color:var(--img-texto-fraco,#a3b1c6);background:rgba(0,0,0,.6);padding:4px 6px;
 border-radius:4px;pointer-events:none;max-width:calc(100% - 96px)}
.nd-cant:empty{display:none}
.nd-cant b{color:var(--img-texto,#e6edf7);font-weight:600}
.nd-dica{position:absolute;left:8px;bottom:8px;z-index:3;font:400 10px/1.35 var(--font-mono,monospace);
 color:var(--img-texto-fraco,#a3b1c6);background:rgba(0,0,0,.6);padding:3px 6px;
 border-radius:4px;pointer-events:none;max-width:calc(100% - 96px)}
.nd-dica:empty{display:none}
.nd-ctl3d{display:flex;align-items:center;gap:6px;min-height:28px}
.nd-ctl3d .dica{margin-left:auto;font-size:11px;color:var(--text-dim);white-space:nowrap;
 overflow:hidden;text-overflow:ellipsis;min-width:0}
.nd-ctl3d[hidden]{display:none}
.nd-3d .ui-seg{padding:2px}
.nd-3d .ui-seg-ind{top:2px;bottom:2px}
.nd-3d .ui-seg>button{padding:3px 10px;font-size:11.5px;letter-spacing:0}

.nd-inc{flex:none;width:286px;display:flex;flex-direction:column;gap:7px;min-height:0}
.nd-pad{position:relative;flex:1 1 0;min-height:64px;border-radius:var(--r-lg,8px);
 background:var(--nd-pad-fundo);border:1px solid var(--line);outline:none;touch-action:none;
 cursor:crosshair}
.nd-pad:focus-visible{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent)}
.nd-pad svg{position:absolute;inset:0;display:block;width:100%;height:100%}
.nd-pad .gr{stroke:var(--nd-pad-grade);stroke-width:1}
.nd-pad .gr.f{stroke:var(--nd-pad-forte)}
.nd-pad text{font:400 10px var(--font-mono,monospace);fill:var(--text-dim)}
.nd-pad .pre{fill:var(--panel);stroke:var(--text-dim);stroke-width:1.2}
.nd-pad .pre.on{stroke:var(--accent);fill:var(--accent-fraco)}
.nd-pad .pre.quente{stroke:var(--text);stroke-width:1.8}
.nd-pad .cruz{stroke:var(--mod-nidus);stroke-width:1;opacity:.45}
.nd-pad .atual{fill:var(--mod-nidus);stroke:var(--panel);stroke-width:2}
.nd-pad .gd{fill:none;stroke-width:1.8;stroke:currentColor}
.nd-pad .gd-n{font:600 8.5px var(--font-mono,monospace);text-anchor:middle;
 dominant-baseline:central;fill:currentColor}
.nd-pad .nd-c0{color:var(--nd-c0)}
.nd-pad .nd-c1{color:var(--nd-c1)}
.nd-pad .nd-c2{color:var(--nd-c2)}
.nd-pad .nd-c3{color:var(--nd-c3)}
.nd-pad .nd-c4{color:var(--nd-c4)}
.nd-guardadas{flex:0 1 auto;min-height:24px;max-height:64px;overflow:auto}
.nd-lista{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:4px}
.nd-lista li{display:inline-flex;align-items:center;gap:6px;height:24px;padding:0 4px 0 8px;
 border-radius:var(--r-pill,999px);border:1px solid var(--line);background:var(--panel-2);
 font:400 10.5px/1 var(--font-mono,monospace)}
.nd-lista li i{width:8px;height:8px;border-radius:50%;flex:none;font-style:normal;
 background:currentColor;display:block}
.nd-lista li b{color:var(--text);font-weight:500}
.nd-lista li.pend{border-style:dashed}
.nd-lista li.nd-c0{color:var(--nd-c0)}
.nd-lista li.nd-c1{color:var(--nd-c1)}
.nd-lista li.nd-c2{color:var(--nd-c2)}
.nd-lista li.nd-c3{color:var(--nd-c3)}
.nd-lista li.nd-c4{color:var(--nd-c4)}
.nd-x{background:none;border:0;color:var(--text-dim);cursor:pointer;width:18px;height:18px;
 border-radius:50%;display:inline-flex;align-items:center;justify-content:center;padding:0;
 font-size:13px;line-height:1}
.nd-x:hover{color:var(--perigo,#E96A5C);background:var(--panel)}
.nd-x:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
.nd-vazio{font-size:11px;color:var(--text-dim);line-height:1.4}
.nd-teto{font-size:10.5px;color:var(--aviso,#E8A33D);margin:2px 0 0}
.nd-acoes{display:flex;gap:6px;margin-top:auto}
.nd-acoes .nd-bt{flex:1 1 auto;justify-content:center}
.nd-guardar{display:inline-flex;align-items:center;gap:6px}
.nd-guardar:not(:disabled):not([aria-disabled="true"]){border-color:var(--mod-nidus);color:var(--mod-nidus)}
.nd-guardar[aria-disabled="true"]{opacity:.5;cursor:help}

.nd-mpr{flex:none;display:flex;flex-direction:column;gap:6px}
.nd-planos{display:flex;gap:8px;align-items:flex-start}
.nd-mpr .p{position:relative;display:flex;flex-direction:column;gap:3px;width:var(--nd-p,168px);flex:none}
.nd-mpr .nd-palco{width:var(--nd-p,168px);height:var(--nd-p,168px)}
.nd-mpr .p > span{position:absolute;left:5px;top:4px;z-index:4;
 font:400 10px var(--font-mono,monospace);color:var(--img-texto,#e6edf7);
 background:rgba(0,0,0,.72);padding:1px 5px;border-radius:4px;pointer-events:none}
.nd-mpr .p input[type=range]{width:100%;margin:0}
.nd-cx-svg{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}
.nd-cx-svg.on{pointer-events:auto;cursor:crosshair}
.nd-caixa{fill:rgba(227,155,79,.07);stroke:var(--nd-caixa);stroke-width:1.5;
 stroke-dasharray:6 4;vector-effect:non-scaling-stroke}
.nd-cx-svg.on .nd-caixa{stroke-dasharray:none}
.nd-alca{fill:var(--nd-caixa)}
.nd-legenda{flex:1 1 auto;min-width:0;display:flex;flex-direction:column;gap:6px;
 padding:2px 0 0 4px;font-size:11px;line-height:1.35;color:var(--text-muted)}
.nd-legenda .t{font:400 10px/1 var(--font-mono,monospace);letter-spacing:.12em;
 text-transform:uppercase;color:var(--text-dim);margin-top:4px}
.nd-legenda .l{display:flex;align-items:center;gap:7px}
.nd-legenda .l i{flex:none;width:16px;height:0;border-top:2px solid currentColor}
.nd-legenda .l span{color:var(--text-muted)}
.nd-legenda .l.nd-c0{color:var(--nd-c0)}
.nd-legenda .l.nd-c1{color:var(--nd-c1)}
.nd-legenda .l.nd-c2{color:var(--nd-c2)}
.nd-legenda .l.nd-c3{color:var(--nd-c3)}
.nd-legenda .l.nd-c4{color:var(--nd-c4)}
.nd-legenda .l.cx{color:var(--mod-nidus)}
.nd-legenda .l.inter{color:var(--accent)}
.nd-legenda .l.inter i{border-top-width:3px}
.nd-rodape{display:flex;gap:10px;font-size:11px;line-height:1.4;color:var(--text-dim);
 white-space:nowrap;overflow:hidden;min-width:0}
.nd-rodape span{overflow:hidden;text-overflow:ellipsis;min-width:0}
.nd-rodape span:empty{display:none}

.nd-tubo{fill:none;stroke-width:1.1;vector-effect:non-scaling-stroke;opacity:.85}
.nd-tubo.nd-c0{stroke:var(--nd-i0)}
.nd-tubo.nd-c1{stroke:var(--nd-i1)}
.nd-tubo.nd-c2{stroke:var(--nd-i2)}
.nd-tubo.nd-c3{stroke:var(--nd-i3)}
.nd-tubo.nd-c4{stroke:var(--nd-i4)}
.nd-inter{fill:none;stroke:var(--accent,#4DA3FF);stroke-width:2;
 vector-effect:non-scaling-stroke}
.nd-marca{fill:none;stroke:var(--nd-caixa);stroke-width:1;
 stroke-dasharray:2 2;stroke-linecap:round;vector-effect:non-scaling-stroke}

.nd-bt{display:inline-flex;align-items:center;gap:6px;font-size:11.5px;padding:3px 9px;
 border-radius:var(--r-md,7px);cursor:pointer;border:1px solid var(--line);
 background:var(--panel);color:var(--text-muted);min-height:28px;white-space:nowrap}
.nd-bt:hover{border-color:var(--line-strong);color:var(--text)}
.nd-bt.on,.nd-bt[aria-pressed="true"]{border-color:var(--accent);color:var(--accent)}
.nd-bt:disabled,.ui-bt:disabled{opacity:.45;cursor:not-allowed}
.nd-bt:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.nd-bt[hidden]{display:none}
.nd-bt.pre{flex-direction:column;align-items:flex-start;gap:1px;line-height:1.15}
.nd-bt.pre small{font:400 10px/1 var(--font-mono,monospace);color:var(--text-dim);letter-spacing:.02em}
.nd-bt.pre.on small{color:inherit;opacity:.85}
.nd-escolha{display:flex;flex-direction:column;gap:10px;min-width:0}
.nd-escolha .nd-pasta{display:flex;gap:6px;align-items:center;flex-wrap:wrap;
 margin:0 0 8px}
.nd-pasta-campo{display:flex;gap:6px;align-items:stretch;flex:1 1 260px;min-width:0}
.nd-filtro{margin:0}
.nd-escolha input[type=text]{flex:1 1 auto;min-width:0;height:30px;
 box-sizing:border-box;padding:0 8px;border-radius:var(--r-md,6px);
 border:1px solid var(--line-strong);background:var(--panel-2);color:var(--text);
 font:12px var(--font-mono,monospace)}
.nd-escolha input[type=text]:focus{outline:0;border-color:var(--accent)}
.nd-series{display:flex;flex-direction:column;gap:5px;max-height:46vh;overflow:auto}
.nd-series .sub{font-size:11.5px;color:var(--text-dim);margin:2px 0}
.nd-it{display:block;width:100%;text-align:left;padding:7px 10px;font-size:12px;
 border-radius:var(--r-md,6px);border:1px solid var(--line);
 background:var(--panel-2);color:var(--text);cursor:pointer}
.nd-it:hover{border-color:var(--mod-nidus,#E39B4F)}
.nd-it:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.nd-wrap > .ui-alerta{margin:4px 0 0;padding:8px 0 10px}
@media (max-width:1100px){
 .nd-trabalho{flex-direction:column}
 .nd-cima{flex-direction:column}
 .nd-inc{width:auto}
 .nd-linha{flex-wrap:wrap}
}
/* Consensus/MPR layout adds no motion and preserves all existing animations. */
.nd-consenso{display:flex;align-items:center;flex-wrap:wrap;gap:8px;margin:8px 0}
.nd-consenso small{flex-basis:100%;color:var(--text-muted)}
.nd-consenso input[type=range]{flex:1 1 180px;min-width:100px}
.nd-mpr-title{display:flex;align-items:center;justify-content:space-between;gap:6px}
.nd-consenso-linha{stroke:var(--success,#6fd08c);stroke-width:2;vector-effect:non-scaling-stroke}
.nd-legenda .l.consenso{color:var(--success,#6fd08c)}
.nd-consenso-vazio{flex-basis:100%;color:var(--text-muted);font-size:12px}
.nd-consenso [hidden],#nd_layout_original[hidden],#nd_estado[hidden]{display:none}
.nd-colB{overflow-y:auto;scrollbar-gutter:stable}
.nd-colB > .nd-cima{flex:1 0 210px;min-height:210px}
@media(max-width:1100px){.nd-colB > .nd-cima{flex:0 0 auto}}
.nd-edit-trace{fill:none;stroke:var(--accent,#7fd1d6);stroke-width:2;vector-effect:non-scaling-stroke}
.nd-palco .nd-edit-surface{pointer-events:none}
.nd-palco.nd-editavel .nd-edit-surface{pointer-events:auto;cursor:crosshair}
#nd_mpr_main{grid-column:1 / 3;grid-row:2;min-width:0;height:var(--nd-q,480px)}
#nd_mpr_main > .p{height:100%;display:flex;flex-direction:column;gap:6px}
#nd_mpr_main .nd-palco{width:100%;flex:1 1 auto;height:auto;min-height:0}
#nd_mpr_main input[type=range]{width:100%}
.nd-colA.nd-mpr-principal{grid-template-rows:20px var(--nd-q,480px)}
.nd-colA.nd-mpr-principal > #nd_palco,.nd-colA.nd-mpr-principal > .nd-barra-v,
.nd-colA.nd-mpr-principal > .nd-barra-h{display:none}
@media (prefers-reduced-motion:reduce){.nd-estado.previa i{animation:none}}
"""

JS_TELA = u"""
var ND_PADROES = {lao:0, cra:0, modo:'mip', jan:'angio', laje:0, inverter:true,
                  osso:true};
var ND = {b:'', chave:'', desc:'', porB:{}, lado:@LADO@, tem_osso:false,
          ossoInfo:null, tracando:false, pontos:[], guardadas:[], sessao:null,
          planos:{0:0.5,1:0.5,2:0.5}, forma:null,
          passos:null, lado_util:0, teto:12,
          zoom:{k:1, x:0, y:0},
          caixa:null, caixaOn:false, telas:null, abrindo:false,
          aberta:false, motivo:'', projetando:false, cruzando:false,
          recruzar:false, voltando:false, refeitas:0, recuperavel:false,
          bom:null, historico:[], fila:null, restaurou:false, ultima:null,
          substituirOsso:false, seqProj:0,
          tabela:null, escolhendo:false,
          geo:null, ver:{lao:0, cra:0}, seguir:true, previa:false,
          previaNoAr:false, previaDepois:false, hu:true};
ND.temperatura=50; ND.consensoEditavel=false; ND.consensoBusy=false;
ND.consIndices={}; ND.consSeq={}; ND.principal=null; ND.consOperacao='add';
ndPadroes();
var ND_MODALIDADES = @MODALIDADES@;
var ND_MIN_CORTES = @MIN_CORTES@;
var ND_INCIDENCIAS = @INCIDENCIAS_JS@;
var ND_LADO_PREVIA = @LADO_PREVIA@;
var ND_ABA = Math.random().toString(36).slice(2, 10);

var ND_EPS = 0.5, ND_TETO_VERTICES = 120, ND_PASSO_MIN = 0.6;
var ND_TETO_HISTORICO = 60, ND_FILA_A_CADA_MS = 15000, ND_FILA_TENTATIVAS = 960;
var ND_FILA_FALHAS = 4, ND_CORES = 5;
var ND_TRAVAVEIS = ['nd_lao','nd_cra','nd_lao_r','nd_cra_r','nd_m_mip','nd_m_minip',
 'nd_inverter','nd_osso_bt','nd_segmentar','nd_laje','nd_caixa_bt','nd_caixa_limpar',
 'nd_bt_guardar','nd_bt_cruzar'];
var ND_IMG_CORES = [[127,209,214],[184,134,240],[111,208,140],[240,132,111],[216,194,79]];

function ndEl(i){ return document.getElementById(i) }
function ndEsc(t){ return String(t==null?'':t).replace(/&/g,'&amp;')
 .replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;') }
function ndMsg(t,c){ var e=ndEl('nd_msg'); if(!e) return;
 if(window.uiTexto) window.uiTexto(e, t); else e.textContent=t;
 e.className=c||'' }
function ndMsg2(motivo, fixa, c){
 var e=ndEl('nd_msg'); if(!e) return;
 e.className=c||'';
 if(!window.uiTexto || !e.children){ e.textContent=motivo+' — '+fixa; return }
 e.innerHTML='<span></span> — <span data-radai-frase></span>';
 e.children[0].textContent=motivo;
 window.uiTexto(e.children[1], fixa);
}
function ndTexto(e, t){ if(!e) return; if(window.uiTexto) window.uiTexto(e, t); else e.textContent=t }

function ndAng(v, pos, neg){
 var n=Math.round(+v||0);
 return (n<0?neg:pos)+' '+Math.abs(n)+'°';
}
function ndRotulo(g){ return ndAng(g.lao,'LAO','RAO')+' / '+ndAng(g.cra,'CRA','CAU') }
function ndCopia(o){ return JSON.parse(JSON.stringify(o)) }

function ndFoto(){
 return ndCopia({lao:ND.lao, cra:ND.cra, modo:ND.modo, jan:ND.jan, laje:ND.laje,
  inverter:ND.inverter, osso:ND.osso, caixa:ND.caixa, guardadas:ND.guardadas,
  pontos:ND.pontos, sessao:ND.sessao, temperatura:ND.temperatura, planos:ND.planos});
}
function ndPadroes(){
 for(var k in ND_PADROES) ND[k]=ND_PADROES[k];
 ND.planos={0:0.5,1:0.5,2:0.5};
 ND.ver={lao:ND.lao, cra:ND.cra};
}
// GUARDA: a chave é a impressão do UID que o servidor manda; o v2 é a convenção do arco em C (o salvo na convenção velha não volta).
function ndChaveSalva(){ return 'radai_nidus_v2_'+ND.chave }
function ndRegistrar(acao){
 if(!ND.chave) return;
 var f=ndFoto();
 ND.historico.push({acao:acao, foto:f});
 while(ND.historico.length>ND_TETO_HISTORICO) ND.historico.shift();
 // Este snapshot fica na aba; preparar/editar/exportar salva a sugestão privada explicitamente.
 try{ var s=window.sessionStorage; if(s) s.setItem(ndChaveSalva(), JSON.stringify(f)) }
 catch(e){}
}
function ndSalvo(){
 if(!ND.chave) return null;
 try{
  var s=window.sessionStorage, t=s?s.getItem(ndChaveSalva()):null;
  return t?JSON.parse(t):null;
 }catch(e){ return null }
}
function ndMarcarBom(){ ND.bom=ndFoto() }
function ndAplicar(f, comDesenho){
 if(!f) return;
 ['lao','cra','modo','jan','laje','inverter','osso'].forEach(function(k){
  if(f[k]!==undefined && f[k]!==null) ND[k]=f[k] });
 if(Number.isFinite(f.temperatura) && f.temperatura>=0 && f.temperatura<=100) ND.temperatura=f.temperatura;
 if(f.planos) [0,1,2].forEach(function(axis){var p=f.planos[axis];if(Number.isFinite(p) && p>=0 && p<=1) ND.planos[axis]=p});
 ND.caixa=f.caixa?f.caixa.slice():null;
 if(comDesenho){
  ND.guardadas=(f.guardadas||[]).filter(Boolean).map(function(g){
   g.pendente=true; return g });
  ND.pontos=(f.pontos||[]).slice();
 }
}

function ndPodeDesenhar(){ return !!(ND.aberta && !ND.projetando) }
function ndTravas(){
 var aberta=!!ND.aberta;
 ND_TRAVAVEIS.forEach(function(i){ var e=ndEl(i); if(e) e.disabled=!aberta });
 ['#nd_incid .nd-bt','#nd_jan .nd-bt'].forEach(function(sel){
  var bs=document.querySelectorAll(sel);
  for(var i=0;i<bs.length;i++) bs[i].disabled=!aberta;
 });
 var g=ndEl('nd_bt_guardar');
 if(g) g.disabled=!(aberta && !ND.projetando);
 ndAtualizarGuardar();
 var c=ndEl('nd_bt_cruzar');
 if(c){
  c.hidden=!ND.guardadas.some(function(x){ return x && x.pendente });
  c.disabled=!aberta || ND.cruzando;
 }
 var rt=ndEl('nd_bt_retomar');
 if(rt) rt.hidden=!(ND.recuperavel && ND.ultima && !aberta && !ND.abrindo);
 var p=ndEl('nd_palco');
 if(p){ p.classList.toggle('desenhavel', ndPodeDesenhar());
  p.classList.toggle('esperando', !!(aberta && ND.projetando)) }
 var sg=ndEl('nd_seguir');
 if(sg){ var tem=!!(aberta && ND.caixa && !ndCaixaCheia(ND.caixa));
  sg.disabled=!tem; sg.setAttribute('aria-pressed', ND.seguir?'true':'false') }
}
function ndAtualizarGuardar(){
 var g=ndEl('nd_bt_guardar'); if(!g || !g.setAttribute) return;
 var falta=!(ND.pontos && ND.pontos.length>=3);
 g.setAttribute('aria-disabled', falta?'true':'false');
 if(falta) g.setAttribute('title', 'circule o ninho antes de guardar (3 pontos, no mínimo)');
 else if(g.removeAttribute) g.removeAttribute('title');
}
function ndBloquear(motivo, recuperavel){
 ND.aberta=false; ND.motivo=motivo||''; ND.tracando=false;
 ND.recuperavel=!!recuperavel;
 ndTravas();
}
function ndRetomar(){
 if(!ND.ultima || ND.aberta || ND.abrindo) return;
 ndAbrirSerie(ND.ultima);
}

function ndFrases(alvo, frases){
 alvo.innerHTML=(frases||[]).map(function(t){
  return '<p class="sub" data-radai-frase>'+ndEsc(t)+'</p>' }).join('');
 if(window.radaiRetraduzir) window.radaiRetraduzir();
}
function ndRotuloDaLista(s){
 var molde=(s.espessura_mm!=null)?'%s · %s cortes · %s mm':'%s · %s cortes';
 var vs=[ndEsc(s.desc||s.curto||'série'), s.cortes, s.espessura_mm];
 return (s.modalidade?(ndEsc(s.modalidade)+' · '):'')
   +molde.replace(/%s/g,function(){ return vs.shift() });
}
function ndListar(pasta){
 var alvo=ndEl('nd_series');
 pasta=(pasta||'').trim();
 if(!pasta){ if(window.uiTremer) window.uiTremer(ndEl('nd_pasta')); return }
 ND.porB={};
 if(!window.uiVarrerLista){ ndFrases(alvo, ['não consegui listar esta pasta']); return }
 window.uiVarrerLista({alvo:'nd_series', estado:'nd_busca', uso:'series',
  chave:'nidus', pasta:pasta, dias:'nd_dias',
  opcoes:{modalidades:ND_MODALIDADES, min_cortes:ND_MIN_CORTES},
  vazio:'Nenhuma série nesta pasta.',
  linha:function(s){
   ND.porB[s.bilhete]=s;
   return '<button type="button" class="nd-it" role="option" data-b="'
     +ndEsc(s.bilhete)+'">'+ndRotuloDaLista(s)+'</button>';
  }});
}

function ndTabela(){
 if(!ND.tabela && window.uiTabelaAcervo && ndEl('nd_acervo')){
  ND.tabela=window.uiTabelaAcervo('nd_acervo', {
   aoAbrir:function(linha){ ndAbrirDoAcervo(linha) },
   filtro:function(l){ return !l.modalidade || ND_MODALIDADES.indexOf(l.modalidade)>=0 }});
 }
}
function ndPopup(){
 if(!window.uiPopupSerie) return null;
 return window.uiPopupSerie('nd_escolha', {
  aoAbrir:function(){ ND.escolhendo=true; ndTabela() },
  aoFechar:function(){ ND.escolhendo=false }});
}
function ndAbrirEscolha(){
 var casa=ndEl('nd_escolha_casa');
 if(!ndEl('nd_escolha')) return;
 ND.escolhendo=true;
 ndTabela();
 var p=ndPopup();
 if(p){ p.abrir(ndEl('nd_escolher')); return }
 if(casa) casa.hidden=false;
}
function ndFecharEscolha(){
 ND.escolhendo=false;
 var p=ndPopup();
 if(p){ p.fechar(); return }
 var casa=ndEl('nd_escolha_casa'); if(casa) casa.hidden=true;
}
function ndAbrirDoAcervo(linha){
 if(!linha || !linha.bilhete) return;
 var d=String(linha.date||''), data=(d.length>=8)?(d.slice(6,8)+'/'+d.slice(4,6)+'/'+d.slice(0,4)):d;
 ndAbrirSerie({bilhete:linha.bilhete, modalidade:linha.modalidade||'',
  origem:'acervo',
  rotulo:[data, linha.pid, linha.modalidade].filter(function(x){ return x }).join(' · ')});
}
function ndEscolher(b){
 var s=ND.porB[b]; if(!s) return;
 ndAbrirSerie({bilhete:s.bilhete, modalidade:s.modalidade||'', desc:s.desc||'',
  origem:'pasta', rotulo:ndRotuloDaLista(s)});
}
function ndRotuloDaSerie(t){
 if(window.uiCartaoRotulo && ndEl('nd_escolher')){ window.uiCartaoRotulo('nd_escolher', t||''); return }
 var e=ndEl('nd_serie_rot'); if(!e) return;
 e.textContent=t||'';
 if(e.setAttribute) e.setAttribute('translate','no');
}

function ndAbrirSerie(s){
 if(!s || !s.bilhete) return;
 ndFecharEscolha();
 if(ND.tabela && s.origem!=='acervo') ND.tabela.marcar(null);
 ndRotuloDaSerie(s.rotulo);
 ND.ultima=s; ND.chave='';
 ND.b=s.bilhete; ND.desc=s.desc||''; ND.guardadas=[]; ND.pontos=[]; ND.forma=null;
 ND.sessao=null; ND.tracando=false; ND.passos=null; ND.lado_util=0;
 ND.caixa=null; ND.caixaOn=false; ND.telas=null; ND.abrindo=true;
 ND.aberta=false; ND.motivo=''; ND.projetando=false; ND.cruzando=false;
 ND.recruzar=false; ND.voltando=false; ND.refeitas=0; ND.recuperavel=false;
 ND.bom=null; ND.historico=[]; ND.fila=null; ND.tem_osso=false; ND.ossoInfo=null;
 ND.restaurou=false; ND.substituirOsso=false;
 ND.geo=null; ND.seguir=true; ND.previa=false; ND.previaNoAr=false; ND.previaDepois=false;
 // GUARDA: série nova abre nos padrões; só o estado salvo DELA os muda (depois do abrir).
 ndPadroes();
 [0,1,2].forEach(function(eixo){ var r=ndEl('nd_pos'+eixo); if(r) r.value='50' });
 nd3Esquecer();
 ndSincronizar();
 ndTravas(); ndModalidade(s.modalidade); ndZoomRepor(); ndPintarCaixas();
 ndPintarMarca(); ndPintarPegada();
 // GUARDA: a imagem da série anterior sai já; sob o carregamento ela pareceria a nova.
 ['nd_proj','nd_pl0','nd_pl1','nd_pl2'].forEach(function(i){
  var im=ndEl(i); if(im && im.removeAttribute) im.removeAttribute('src') });
 ndCarregando(true);
 [0,1,2].forEach(function(eixo){ ndLinhas(eixo) });
 ndPasso(); ndEscala(null); ndOsso(null);
 ndMsg('abrindo a série…','');
 var b=ND.b;
 fetch('/api/nidus/abrir',{method:'POST',
   headers:{'Content-Type':'application/json'},
   body:JSON.stringify({b:b, origem:s.origem||''})})
  .then(function(r){return r.json()}).then(function(d){
   if(b!==ND.b) return;
   ND.abrindo=false;
   if(!d || d.erro || !d.forma){
    ndCarregando(false);
    ndBloquear((d && d.erro) ? String(d.erro) : 'a série não pôde ser lida.');
    ndMsg2(ND.motivo, 'nesta série nada pode ser desenhado: escolha outra na lista.', 'erro');
    ndPintarGuardadas();
    return;
   }
   ND.chave=String(d.chave||'');
   ND.forma=d.forma; ND.telas=d.telas||null; ND.geo=d.geometria||null;
   ND.hu=(d.hu!==false);
   if(d.modalidade) ndModalidade(d.modalidade);
   ND.passos=d.passos||null; ND.lado_util=d.lado_util||0;
   ndPasso(); ndEscala(d);
   ND.aberta=true;
   var salvo=ndSalvo();
   if(salvo) ndAplicar(salvo, true);
   ND.restaurou=!!ND.guardadas.length;
   ndSincronizar(); ndOsso(d.osso||null); ndTravas();
   if(ND.restaurou)
    ndMsg('a marcação salva desta série voltou: as incidências estão na lista','ok');
   else ndMsg('série aberta — escolha a incidência e circule a área','');
   ndPintarMarca(); ndPintarCaixas(); ndPintarPegada();
   ndProjetar(); ndPintarPlanos(true); ndPintarGuardadas();
   nd3Malhas();
   if(ND.guardadas.length) ndCalcular();
  })
  .catch(function(e){ if(b!==ND.b) return;
   ND.abrindo=false; ndCarregando(false);
   ndBloquear('não consegui abrir: '+e, true); ndMsg(ND.motivo,'erro') });
 ndPintarGuardadas();
}

function ndModalidade(m){
 var e=ndEl('nd_mod'); if(e) e.textContent=m?String(m):'';
}

function ndCarregando(liga, alvo, txt){
 var e=alvo||ndEl('nd_palco');
 if(!e || !window.uiCarregando) return;
 if(!liga){ window.uiCarregando(e, false); return }
 window.uiCarregando(e, true, txt || (ND.abrindo?'abrindo a série…':'projetando…'));
}

function ndUrlDaProjecao(lao, cra, lado){
 return '/api/nidus/projecao?b='+encodeURIComponent(ND.b)
   +'&n='+ND.seqProj+'&t='+ND_ABA
   +'&lao='+lao+'&cra='+cra+'&modo='+ND.modo+'&janela='+ND.jan
   +'&lado='+lado+(ND.laje?('&laje='+ND.laje):'')
   +'&osso='+((ND.osso && ND.tem_osso)?1:0)
   +((ND.caixa && !ndCaixaCheia(ND.caixa))?('&caixa='+ND.caixa.map(function(v){ return v.toFixed(4) }).join(',')):'');
}
function ndProjetar(previa){
 if(!ND.b || !ND.aberta) return;
 var img=ndEl('nd_proj'), b=ND.b;
 ND.projetando=true; ND.tracando=false;
 if(previa){
  ND.previa=true; ND.previaNoAr=true;
  img.onerror=function(){ if(b!==ND.b) return; ND.previaNoAr=false };
  img.onload=function(){ if(b!==ND.b) return; ND.previaNoAr=false;
   if(ND.previaDepois){ ND.previaDepois=false; ndProjetar(true) } };
  ND.seqProj++;
  img.src=ndUrlDaProjecao(ND.ver.lao, ND.ver.cra, ND_LADO_PREVIA);
  ndEstado(); ndTravas();
  return;
 }
 ND.previa=false; ND.previaNoAr=false; ND.previaDepois=false;
 ndTravas();
 img.onerror=function(){ if(b!==ND.b) return;
  img.removeAttribute('src'); ND.projetando=false;
  ndCarregando(false); ndTravas(); ndEstado(); ndFalhou('proj') };
 img.onload=function(){ if(b!==ND.b) return;
  ND.projetando=false; ND.voltando=false;
  ndCarregando(false); ndMarcarBom(); ndTravas(); ndEstado() };
 ndCarregando(true);
 ND.seqProj++;
 img.src=ndUrlDaProjecao(ND.lao, ND.cra, ND.lado);
 ndEstado();
 ndPedirEixos(ND.lao, ND.cra);
}
function ndEstado(){
 var e=ndEl('nd_estado'), t=ndEl('nd_estado_t'), z=ndEl('nd_zoomv');
 var previa=!!(ND.previa && ND.projetando);
 if(e) e.classList.toggle('previa', previa);
 if(t) ndTexto(t, previa?'prévia · baixa resolução':'projeção cheia');
 if(z) z.classList.toggle('previa', previa);
 ndZoomAplicar();
}

function ndFalhou(tipo){
 var b=ND.b;
 var fixa=(tipo==='proj')?'a projeção não veio do servidor':'o corte não veio do servidor';
 fetch('/api/nidus/estado?b='+encodeURIComponent(b))
  .then(function(r){return r.json()}).then(function(d){
   if(b!==ND.b) return;
   var m=(d && d.erro) ? String(d.erro) : fixa;
   if(tipo==='proj') ndVoltarAoBom(m);
   else ndMsg2(m, 'a marcação continua salva.', 'erro');
  }).catch(function(){ if(b===ND.b && tipo==='proj') ndVoltarAoBom(fixa) });
}

function ndVoltarAoBom(motivo){
 if(ND.voltando || !ND.bom){
  ND.voltando=false;
  // GUARDA: o salvo leva os parâmetros bons; reabrir no ângulo que falhou falharia de novo.
  if(ND.bom){ var g0=ND.guardadas, p0=ND.pontos;
   ndAplicar(ND.bom, false); ND.guardadas=g0; ND.pontos=p0; ndSincronizar() }
  ndRegistrar('erro');
  ndBloquear(motivo, true);
  ndMsg2(motivo, 'a série parou de responder: «Tentar de novo» reabre a série, e a marcação continua salva.', 'erro');
  return;
 }
 ND.voltando=true;
 var g=ND.guardadas, p=ND.pontos;
 ndAplicar(ND.bom, false);
 ND.guardadas=g; ND.pontos=p;
 ndSincronizar(); ndPintarCaixas(); ndPintarMarca(); ndRegistrar('voltar');
 ndMsg2(motivo, 'a tela voltou ao último estado bom, e nada do que foi desenhado se perdeu.', 'erro');
 ndProjetar();
}

// GUARDA: os eixos saem de radaiIncidencia, a mesma matriz de radai_nidus.matriz_da_incidencia (a bateria compara as duas).
function ndEixosDe(lao, cra){
 var b=radaiIncidencia(lao, cra), d={};
 [['L',0],['P',1],['S',2]].forEach(function(p){ var k=p[1];
  d[p[0]]=[b.r[k], -b.u[k], b.v[k]] });
 return d;
}
function ndPedirEixos(lao, cra){ ndEixos(ndEixosDe(lao, cra)) }

function ndEixosSvg(g, d){
 if(!g) return;
 if(!d || !d.L){ g.innerHTML=''; return }
 var lg='';
 try{ lg=String(document.documentElement.getAttribute('lang')||'').toLowerCase() }
 catch(e){}
 var pt=(!lg || lg.indexOf('pt')===0);
 var letras={L:[pt?'E':'L', pt?'D':'R'], P:['P','A'], S:['S','I']};
 var R=27, c=42, h='';
 ['L','P','S'].forEach(function(k){
  var v=d[k];
  [[1,letras[k][0]],[-1,letras[k][1]]].forEach(function(par){
   var s=par[0], frente=(s*v[2])<=0.0001, a=frente?0.95:0.32;
   h+='<line x1="'+c+'" y1="'+c+'" x2="'+(c+s*v[0]*R).toFixed(1)
     +'" y2="'+(c+s*v[1]*R).toFixed(1)+'" opacity="'+a+'"/>'
     +'<text x="'+(c+s*v[0]*R*1.3).toFixed(1)+'" y="'+(c+s*v[1]*R*1.3).toFixed(1)
     +'" opacity="'+a+'">'+par[1]+'</text>';
  });
 });
 g.innerHTML=h;
}
function ndEixos(d){ ndEixosSvg(ndEl('nd_eixos'), d) }

// GUARDA: o desenho e a imagem estão no MESMO contêiner escalado; `ndPonto` lê o retângulo já escalado.
function ndZoomAplicar(){
 var w=ndEl('nd_zoom'), z=ND.zoom; if(!w) return;
 w.style.transform='translate('+z.x.toFixed(1)+'px,'+z.y.toFixed(1)+'px) scale('+z.k.toFixed(3)+')';
 var v=ndEl('nd_zoomv'); if(!v) return;
 var pct=Math.round(z.k*100)+'%', previa=!!(ND.previa && ND.projetando);
 if(v.getAttribute && v.getAttribute('data-nd')===(previa?'p':'')+pct) return;
 if(v.setAttribute) v.setAttribute('data-nd', (previa?'p':'')+pct);
 if(!previa){ v.textContent=pct; return }
 v.innerHTML='<span data-radai-frase>prévia</span> · '+pct;
 if(window.radaiRetraduzir) window.radaiRetraduzir();
}
function ndZoomPrender(){
 var p=ndEl('nd_palco'), z=ND.zoom; if(!p) return;
 var r=p.getBoundingClientRect(), W=r.width, H=r.height;
 z.k=Math.max(1, Math.min(8, z.k));
 z.x=Math.min(0, Math.max(W-W*z.k, z.x));
 z.y=Math.min(0, Math.max(H-H*z.k, z.y));
}
function ndZoomEm(k, cx, cy){
 var z=ND.zoom;
 k=Math.max(1, Math.min(8, k));
 var px=(cx-z.x)/z.k, py=(cy-z.y)/z.k;
 z.x=cx-px*k; z.y=cy-py*k; z.k=k;
 ndZoomPrender(); ndZoomAplicar();
}
function ndSeguirDesligar(){
 if(!ND.seguir) return;
 ND.seguir=false; ndTravas(); ndPintarPegada();
}
function ndZoomPasso(s){
 var p=ndEl('nd_palco'); if(!p) return;
 ndSeguirDesligar();
 var r=p.getBoundingClientRect();
 ndZoomEm(ND.zoom.k*(s>0?1.25:0.8), r.width/2, r.height/2);
}
function ndZoomRepor(){
 ND.zoom={k:1, x:0, y:0}; ndZoomAplicar();
}
function ndZoomAjustar(){
 ndSeguirDesligar(); ndZoomRepor();
}
function ndSeguirAlternar(){
 ND.seguir=!ND.seguir;
 ndTravas(); ndPintarPegada();
 if(ND.seguir) ndEnquadrar();
}
function ndRoda(ev){
 if(!ND.b) return;
 if(ev.preventDefault) ev.preventDefault();
 ndSeguirDesligar();
 var p=ndEl('nd_palco'), r=p.getBoundingClientRect();
 ndZoomEm(ND.zoom.k*(ev.deltaY<0?1.15:1/1.15), ev.clientX-r.left, ev.clientY-r.top);
}
var ND_ARRASTO=null;
function ndQuerMover(ev){ return !!(ev && (ev.button===1 || ev.shiftKey)) }
function ndPegar(ev){
 if(!ndQuerMover(ev) || ND.zoom.k<=1.001) return;
 if(ev.preventDefault) ev.preventDefault();
 ndSeguirDesligar();
 ND_ARRASTO={x:ev.clientX, y:ev.clientY, zx:ND.zoom.x, zy:ND.zoom.y};
 ndEl('nd_palco').classList.add('arrastando');
}
function ndMoverPalco(ev){
 if(!ND_ARRASTO) return;
 ND.zoom.x=ND_ARRASTO.zx+(ev.clientX-ND_ARRASTO.x);
 ND.zoom.y=ND_ARRASTO.zy+(ev.clientY-ND_ARRASTO.y);
 ndZoomPrender(); ndZoomAplicar();
}
function ndLargar(){
 if(!ND_ARRASTO) return;
 ND_ARRASTO=null; ndEl('nd_palco').classList.remove('arrastando');
}

function ndM4(M, p){
 return [M[0]*p[0]+M[1]*p[1]+M[2]*p[2]+M[3], M[4]*p[0]+M[5]*p[1]+M[6]*p[2]+M[7],
         M[8]*p[0]+M[9]*p[1]+M[10]*p[2]+M[11]];
}
function ndCantos(c){
 var Q=ND.geo.da_caixa, fora=[];
 for(var i=0;i<8;i++) fora.push(ndM4(Q, [c[i&1?1:0], c[i&2?3:2], c[i&4?5:4]]));
 return fora;
}
// GUARDA: a caixa é fração dos eixos do array; os cantos vão ao LPS pela matriz da série, e a grade é a de radai_nidus.projetar (centro da série, lado = diagonal).
function ndNaTela(P, b){
 var g=ND.geo, q=[P[0]-g.centro[0], P[1]-g.centro[1], P[2]-g.centro[2]], passo=g.diag/ND.lado;
 return [(q[0]*b.r[0]+q[1]*b.r[1]+q[2]*b.r[2]+g.diag/2)/passo+0.5,
         ND.lado-0.5-(q[0]*b.u[0]+q[1]*b.u[1]+q[2]*b.u[2]+g.diag/2)/passo];
}
function ndPegada(caixa, lao, cra){
 var b=radaiIncidencia(lao, cra);
 return ndCantos(caixa).map(function(P){ return ndNaTela(P, b) });
}
function ndCasco(P){
 P=P.slice().sort(function(a,b){ return a[0]-b[0] || a[1]-b[1] });
 function cr(o,a,b){ return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0]) }
 var lo=[], up=[], i;
 for(i=0;i<P.length;i++){ while(lo.length>=2 && cr(lo[lo.length-2],lo[lo.length-1],P[i])<=0) lo.pop(); lo.push(P[i]) }
 for(i=P.length-1;i>=0;i--){ while(up.length>=2 && cr(up[up.length-2],up[up.length-1],P[i])<=0) up.pop(); up.push(P[i]) }
 up.pop(); lo.pop(); return lo.concat(up);
}
function ndPintarPegada(){
 var f=ndEl('nd_fora'), pg=ndEl('nd_pegada'); if(!f || !pg) return;
 var c=ND.caixa;
 if(!ND.geo || !c || ndCaixaCheia(c)){ f.setAttribute('d',''); pg.setAttribute('points',''); return }
 var hs=ndCasco(ndPegada(c, ND.ver.lao, ND.ver.cra)).map(function(p){
  return p[0].toFixed(1)+','+p[1].toFixed(1) });
 var L=ND.lado;
 // GUARDA: fora da caixa fica velado nos dois modos; sem o véu o recortado se confunde com o ar.
 f.setAttribute('d', 'M0,0H'+L+'V'+L+'H0Z M'+hs.join(' L')+'Z');
 pg.setAttribute('points', ND.seguir?'':hs.join(' '));
}
function ndEnquadrar(){
 if(!ND.seguir || !ND.geo || !ND.caixa || ndCaixaCheia(ND.caixa)) return;
 var p=ndEl('nd_palco'); if(!p || !p.getBoundingClientRect) return;
 var r=p.getBoundingClientRect(), W=r.width, H=r.height; if(!W || !H) return;
 var pts=ndPegada(ND.caixa, ND.ver.lao, ND.ver.cra), x0=1e9, x1=-1e9, y0=1e9, y1=-1e9;
 pts.forEach(function(q){ x0=Math.min(x0,q[0]); x1=Math.max(x1,q[0]); y0=Math.min(y0,q[1]); y1=Math.max(y1,q[1]) });
 var L=ND.lado, meia=Math.max(x1-x0, y1-y0)/2*1.08;
 var k=Math.max(1, Math.min(8, L/(2*Math.max(meia, 1))));
 ND.zoom.k=k; ND.zoom.x=W/2-(x0+x1)/2/L*W*k; ND.zoom.y=H/2-(y0+y1)/2/L*H*k;
 ndZoomPrender(); ndZoomAplicar();
}

function ndLeitura(lao, cra){
 var l=ndEl('nd_lao_v'), c=ndEl('nd_cra_v');
 if(l) l.textContent=ndAng(lao, 'LAO', 'RAO');
 if(c) c.textContent=ndAng(cra, 'CRA', 'CAU');
}
function ndSincronizar(){
 ND.ver={lao:ND.lao, cra:ND.cra};
 [['lao','LAO','RAO'],['cra','CRA','CAU']].forEach(function(a){
  var v=ND[a[0]], t=ndEl('nd_'+a[0]), r=ndEl('nd_'+a[0]+'_r');
  if(t) t.value=String(v);
  if(r) r.value=String(v);
 });
 ndLeitura(ND.lao, ND.cra);
 var bs=document.querySelectorAll('#nd_incid .nd-bt');
 for(var i=0;i<bs.length;i++){
  var on=+bs[i].getAttribute('data-lao')===ND.lao && +bs[i].getAttribute('data-cra')===ND.cra;
  bs[i].classList.toggle('on', on);
  bs[i].setAttribute('aria-pressed', on?'true':'false');
 }
 ['mip','minip'].forEach(function(k){
  var b=ndEl('nd_m_'+k); if(b) b.classList.toggle('on', k===ND.modo) });
 var js=document.querySelectorAll('#nd_jan .nd-bt');
 for(var j=0;j<js.length;j++)
  js[j].classList.toggle('on', js[j].getAttribute('data-j')===ND.jan);
 var p=ndEl('nd_palco'), iv=ndEl('nd_inverter');
 if(p) p.classList.toggle('inv', !!ND.inverter);
 if(iv){ iv.classList.toggle('on', !!ND.inverter);
  iv.setAttribute('aria-pressed', ND.inverter?'true':'false') }
 var la=ndEl('nd_laje'), lv=ndEl('nd_lajev');
 if(la) la.value=String(ND.laje);
 if(lv){ var tl=ND.laje?(ND.laje+' mm'):'todo o volume';
  if(window.uiTexto) window.uiTexto(lv, tl); else lv.textContent=tl }
 var cb=ndEl('nd_caixa_bt');
 if(cb){ cb.classList.toggle('on', !!ND.caixaOn);
  cb.setAttribute('aria-pressed', ND.caixaOn?'true':'false') }
 ndPintarOsso();
 ndPedirEixos(ND.lao, ND.cra);
 ndPintarPad(); nd3Pedir();
}

function ndInverter(){
 ND.inverter=!ND.inverter;
 ndSincronizar(); ndRegistrar('inverter');
}

// GUARDA: `ND.caixa` = [s0,s1,p0,p1,l0,l1] em fração da vista S-P-L, a ordem de `radai_nidus.caixa_de_texto`.
function ndCaixaModo(){
 if(!ND.aberta) return;
 ND.caixaOn=!ND.caixaOn;
 if(ND.caixaOn && !ND.caixa) ND.caixa=[0,1,0,1,0,1];
 ndSincronizar();
 if(ND.caixaOn) ndMsg('arraste as bordas da caixa nos três planos: a projeção mostra só o que fica dentro dela','');
 ndPintarCaixas(); ndRegistrar('recorte'); ndTravas();
}
function ndCaixaLimpar(){
 if(!ND.aberta) return;
 ND.caixa=null; ND.caixaOn=false;
 ndSincronizar(); ndPintarCaixas(); ndRegistrar('recorte'); ndProjetar();
 ndPintarPegada(); ndZoomRepor(); ndTravas(); nd3Malhas(); ndPintarLegenda();
}
function ndCaixaCheia(c){
 return !c || (c[0]<=0 && c[1]>=1 && c[2]<=0 && c[3]>=1 && c[4]<=0 && c[5]>=1);
}
function ndCaixaNoCorte(eixo){
 var c=ND.caixa;
 if(eixo===0) return [c[4], c[2], c[5], c[3]];
 if(eixo===1) return [c[4], 1-c[1], c[5], 1-c[0]];
 return [c[2], 1-c[1], c[3], 1-c[0]];
}
function ndCaixaDoCorte(eixo, r){
 var c=ND.caixa, x0=Math.min(r[0],r[2]), x1=Math.max(r[0],r[2]);
 var y0=Math.min(r[1],r[3]), y1=Math.max(r[1],r[3]);
 function p(v){ return Math.max(0, Math.min(1, v)) }
 if(eixo===0){ c[4]=p(x0); c[5]=p(x1); c[2]=p(y0); c[3]=p(y1) }
 else if(eixo===1){ c[4]=p(x0); c[5]=p(x1); c[0]=p(1-y1); c[1]=p(1-y0) }
 else { c[2]=p(x0); c[3]=p(x1); c[0]=p(1-y1); c[1]=p(1-y0) }
 [0,2,4].forEach(function(i){ if(c[i+1]-c[i]<0.02){ c[i+1]=Math.min(1,c[i]+0.02); c[i]=c[i+1]-0.02 } });
}
function ndPintarCaixas(){
 [0,1,2].forEach(function(eixo){
  var svg=ndEl('nd_cx'+eixo); if(!svg) return;
  var t=ND.telas ? ND.telas[String(eixo)] : null;
  svg.classList.toggle('on', !!(ND.caixaOn && t && ND.aberta));
  if(!t || !ND.caixa || (ndCaixaCheia(ND.caixa) && !ND.caixaOn)){ svg.innerHTML=''; return }
  var H=t[0], W=t[1], r=ndCaixaNoCorte(eixo);
  svg.setAttribute('viewBox','0 0 '+W+' '+H);
  var x0=r[0]*W, y0=r[1]*H, x1=r[2]*W, y1=r[3]*H, s=Math.max(W,H)/60, h='';
  h+='<rect class="nd-caixa" x="'+x0.toFixed(1)+'" y="'+y0.toFixed(1)+'" width="'
    +(x1-x0).toFixed(1)+'" height="'+(y1-y0).toFixed(1)+'"/>';
  if(ND.caixaOn) [[x0,y0],[x1,y0],[x0,y1],[x1,y1]].forEach(function(q){
   h+='<rect class="nd-alca" x="'+(q[0]-s/2).toFixed(1)+'" y="'+(q[1]-s/2).toFixed(1)
     +'" width="'+s.toFixed(1)+'" height="'+s.toFixed(1)+'"/>';
  });
  svg.innerHTML=h;
 });
}
function ndPontoNoCorte(svg, ev, eixo){
 var t=ND.telas[String(eixo)], H=t[0], W=t[1];
 var r=svg.getBoundingClientRect(), k=Math.min(r.width/W, r.height/H);
 var ox=r.left+(r.width-W*k)/2, oy=r.top+(r.height-H*k)/2;
 return [(ev.clientX-ox)/(W*k), (ev.clientY-oy)/(H*k)];
}
var ND_CX=null;
function ndCaixaPegar(eixo, ev){
 if(!ND.caixaOn || !ND.telas || !ND.caixa || !ND.aberta) return;
 var svg=ndEl('nd_cx'+eixo), p=ndPontoNoCorte(svg, ev, eixo), r=ndCaixaNoCorte(eixo);
 var tol=0.035, dx=p[0]>r[0]-tol && p[0]<r[2]+tol, dy=p[1]>r[1]-tol && p[1]<r[3]+tol;
 var h={a0:Math.abs(p[0]-r[0])<tol && dy, a1:Math.abs(p[0]-r[2])<tol && dy,
        b0:Math.abs(p[1]-r[1])<tol && dx, b1:Math.abs(p[1]-r[3])<tol && dx};
 if(!(h.a0||h.a1||h.b0||h.b1)){
  if(p[0]>r[0] && p[0]<r[2] && p[1]>r[1] && p[1]<r[3]) h={mover:true};
  else return;
 }
 if(ev.preventDefault) ev.preventDefault();
 ND_CX={eixo:eixo, h:h, p0:p, r0:r.slice()};
}
function ndCaixaCursor(eixo, ev){
 var svg=ndEl('nd_cx'+eixo); if(!svg || !svg.style) return;
 if(ND_CX || !ND.caixaOn || !ND.telas || !ND.caixa){ return }
 var p=ndPontoNoCorte(svg, ev, eixo), r=ndCaixaNoCorte(eixo), t=0.035;
 var nx=Math.abs(p[0]-r[0])<t || Math.abs(p[0]-r[2])<t, ny=Math.abs(p[1]-r[1])<t || Math.abs(p[1]-r[3])<t;
 svg.style.cursor = (nx && ny) ? 'nwse-resize' : nx ? 'ew-resize' : ny ? 'ns-resize'
  : (p[0]>r[0] && p[0]<r[2] && p[1]>r[1] && p[1]<r[3]) ? 'move' : 'crosshair';
}
function ndCaixaMover(ev){
 if(!ND_CX) return;
 var svg=ndEl('nd_cx'+ND_CX.eixo), p=ndPontoNoCorte(svg, ev, ND_CX.eixo);
 var dx=p[0]-ND_CX.p0[0], dy=p[1]-ND_CX.p0[1], r=ND_CX.r0.slice(), h=ND_CX.h;
 if(h.mover){
  dx=Math.max(-r[0], Math.min(1-r[2], dx)); dy=Math.max(-r[1], Math.min(1-r[3], dy));
  r[0]+=dx; r[2]+=dx; r[1]+=dy; r[3]+=dy;
 } else { if(h.a0) r[0]+=dx; if(h.a1) r[2]+=dx; if(h.b0) r[1]+=dy; if(h.b1) r[3]+=dy }
 ndCaixaDoCorte(ND_CX.eixo, r);
 ndPintarCaixas(); ndPintarPegada(); ndEnquadrar(); nd3Pedir();
}
function ndCaixaSoltar(){
 if(!ND_CX) return;
 ND_CX=null;
 ndRegistrar('recorte');
 ndTravas(); ndProjetar(); nd3Malhas();
}

function ndIncidencia(lao,cra,nome){ ndAngulo(lao, cra) }

function ndAngulo(lao, cra){
 if(!ND.aberta) return;
 lao=Math.max(-180, Math.min(180, Math.round(+lao||0)));
 cra=Math.max(-90, Math.min(90, Math.round(+cra||0)));
 if(lao===ND.lao && cra===ND.cra){
  ndSincronizar(); if(ND.previa && ND.projetando) ndProjetar(); return }
 var guardou=false;
 if(ND.pontos.length>=3){
  if(ND.guardadas.length>=ND.teto){
   ndSincronizar();
   ndMsg('guarde ou apague o traço antes de girar: a lista já tem o máximo de incidências','erro');
   return;
  }
  ndGuardar(true); guardou=true;
 } else { ND.pontos=[]; ndPintarMarca() }
 ND.lao=lao; ND.cra=cra;
 ndSincronizar(); ndRegistrar('girar'); ndProjetar(); ndPintarPegada(); ndEnquadrar();
 if(guardou) ndMsg('o traço da incidência anterior foi guardado antes de girar','ok');
}
function ndPreverAng(lao, cra){
 if(!ND.aberta) return;
 lao=Math.round(+lao||0); cra=Math.round(+cra||0);
 lao=((lao+180)%360+360)%360-180; if(lao===-180 && ND.ver.lao>0) lao=180;
 cra=Math.max(-90, Math.min(90, cra));
 if(lao===ND.ver.lao && cra===ND.ver.cra) return;
 ND.ver={lao:lao, cra:cra};
 var t=ndEl('nd_lao'), c=ndEl('nd_cra');
 if(t && document.activeElement!==t) t.value=String(lao);
 if(c && document.activeElement!==c) c.value=String(cra);
 var rl=ndEl('nd_lao_r'), rc=ndEl('nd_cra_r');
 if(rl && document.activeElement!==rl) rl.value=String(lao);
 if(rc && document.activeElement!==rc) rc.value=String(cra);
 ndLeitura(lao, cra);
 ndPedirEixos(lao, cra);
 ndPintarPegada(); ndEnquadrar(); ndPintarPad(); nd3Pedir();
 ndPedirPrevia();
}
// GUARDA: uma prévia no ar por vez; a que chega com o ângulo já mudado pede a seguinte.
function ndPedirPrevia(){
 if(!ND.b || !ND.aberta) return;
 if(ND.previaNoAr){ ND.previaDepois=true; return }
 ndProjetar(true);
}
function ndPrever(k, v){
 ndPreverAng(k==='lao'?v:ND.ver.lao, k==='cra'?v:ND.ver.cra);
}
function ndMudarAngulo(k, v){
 ndAngulo(k==='lao'?v:ND.ver.lao, k==='cra'?v:ND.ver.cra);
}
function ndSoltarAngulo(){
 if(ND.ver.lao!==ND.lao || ND.ver.cra!==ND.cra) ndAngulo(ND.ver.lao, ND.ver.cra);
 else if(ND.previa && ND.projetando) ndProjetar();
}

function ndGradeDoDesenho(){
 var svg=ndEl('nd_svg'); if(!svg) return;
 svg.setAttribute('viewBox','0 0 '+ND.lado+' '+ND.lado);
}

function ndPonto(ev){
 var svg=ndEl('nd_svg'), r=svg.getBoundingClientRect();
 return [(ev.clientX-r.left)/r.width*ND.lado,
         (ev.clientY-r.top)/r.height*ND.lado];
}

function ndPressionar(ev){
 if(ndQuerMover(ev)) return;
 if(!ndPodeDesenhar()){
  if(ND.aberta) ndMsg('aguarde a projeção desta incidência chegar para desenhar sobre ela','erro');
  else if(ND.motivo) ndMsg2(ND.motivo, 'nesta série nada pode ser desenhado: escolha outra na lista.', 'erro');
  return;
 }
 if(ev.preventDefault) ev.preventDefault();
 ND.tracando=true; ND.pontos=[ndPonto(ev)]; ndPintarMarca();
}

function ndArrastar(ev){
 if(!ND.tracando) return;
 var p=ndPonto(ev), u=ND.pontos[ND.pontos.length-1];
 var dx=p[0]-u[0], dy=p[1]-u[1];
 if(dx*dx+dy*dy < ND_PASSO_MIN*ND_PASSO_MIN) return;
 ND.pontos.push(p); ndPintarMarca();
}

function ndSoltar(){
 if(!ND.tracando) return;
 ND.tracando=false;
 if(ND.pontos.length<3){
  ndMsg('o traço foi curto demais — arraste contornando o ninho','erro');
  ND.pontos=[]; ndPintarMarca(); ndAtualizarGuardar(); return;
 }
 var bruto=ND.pontos.length;
 ND.pontos=ndAfinar(ND.pontos);
 ndPintarMarca(); ndRegistrar('desenhar'); ndAtualizarGuardar();
 ndMsg('traço fechado: '+bruto+' pontos afinados para '+ND.pontos.length
   +' vértices — Guardar guarda esta incidência, ou trace de novo por cima',
   '');
}

function ndSimplificar(pts, eps){
 if(pts.length<3) return pts.slice();
 var fica=new Array(pts.length), pilha=[[0,pts.length-1]];
 fica[0]=fica[pts.length-1]=true;
 while(pilha.length){
  var par=pilha.pop(), a=par[0], b=par[1];
  if(b<=a+1) continue;
  var ax=pts[a][0], ay=pts[a][1];
  var dx=pts[b][0]-ax, dy=pts[b][1]-ay;
  var den=Math.sqrt(dx*dx+dy*dy), pior=-1, longe=-1;
  for(var i=a+1;i<b;i++){
   var ux=pts[i][0]-ax, uy=pts[i][1]-ay;
   var d = (den<1e-9) ? Math.sqrt(ux*ux+uy*uy)
                      : Math.abs(dy*ux - dx*uy)/den;
   if(d>pior){ pior=d; longe=i }
  }
  if(pior>eps && longe>a){
   fica[longe]=true; pilha.push([a,longe]); pilha.push([longe,b]);
  }
 }
 var out=[];
 for(var k=0;k<pts.length;k++) if(fica[k]) out.push(pts[k]);
 return out;
}

function ndAfinar(pts){
 var eps=ND_EPS, out=ndSimplificar(pts,eps), voltas=0;
 while(out.length>ND_TETO_VERTICES && voltas<12){
  eps*=1.6; out=ndSimplificar(pts,eps); voltas++;
 }
 return out;
}

function ndPintarMarca(){
 var g=ndEl('nd_marca'); if(!g) return;
 var r=ND.lado/256;
 if(ND.pontos.length<2){ g.innerHTML=ND.pontos.length
   ? '<circle cx="'+ND.pontos[0][0]+'" cy="'+ND.pontos[0][1]
     +'" r="'+r+'" class="nd-marca"/>' : ''; return }
 var d=ND.pontos.map(function(p,i){ return (i?'L':'M')+p[0]+' '+p[1] }).join(' ');
 // GUARDA: soltar fecha a área do último ponto ao primeiro (o Z); durante o traço ela fica aberta.
 g.innerHTML='<path d="'+d+(ND.tracando?'':' Z')+'" class="nd-marca"/>';
}

function ndPasso(){
 var e=ndEl('nd_passo'); if(!e) return;
 var mm = ND.passos ? ND.passos[String(ND.lado)] : null;
 if(mm==null){ e.textContent=''; return }
 var molde = (ND.lado_util && ND.lado>ND.lado_util)
  ? '%s mm por pixel da projeção — acima do que esta série oferece: o que aparece a mais é interpolação, e não o paciente'
  : '%s mm por pixel da projeção';
 var t = molde.replace('%s', (+mm).toFixed(2).replace('.',','));
 if(window.uiTexto) window.uiTexto(e, t); else e.textContent=t;
 if(e.setAttribute) e.setAttribute('title', t);
}

function ndEscala(d){
 var e=ndEl('nd_escala'); if(!e) return;
 var t = (d && d.hu===false)
  ? 'sinal da RM, sem HU: as janelas são relativas ao sinal desta série'
  : '';
 if(window.uiTexto) window.uiTexto(e, t); else e.textContent=t;
}

function ndOsso(d){
 ND.ossoInfo=d||null;
 ND.tem_osso=!!(d && d.tem);
 ndPintarOsso();
}
function ndPedeSubstituir(){
 var d=ND.ossoInfo;
 return !!((d && !d.tem && d.entrega) || ND.substituirOsso);
}
function ndPintarOsso(){
 var d=ND.ossoInfo, t=ndEl('nd_osso_txt'), bt=ndEl('nd_osso_bt'), sg=ndEl('nd_segmentar');
 if(bt){
  bt.hidden=!ND.tem_osso;
  bt.classList.toggle('on', !!(ND.tem_osso && ND.osso));
  bt.setAttribute('aria-pressed', (ND.tem_osso && ND.osso)?'true':'false');
 }
 if(sg){
  sg.hidden=!(d && !d.tem && ND.aberta && !ND.fila);
  var st=ndEl('nd_segmentar_txt'), ts=ndPedeSubstituir()
   ? 'Segmentar em AUTO (substitui a entrega)' : 'Segmentar primeiro (AUTO)';
  if(st){ if(window.uiTexto) window.uiTexto(st, ts); else st.textContent=ts }
 }
 if(!t) return;
 if(ND.fila && ND.fila.frase){
  t.innerHTML='<span data-radai-frase>'+ndEsc(ND.fila.frase)+'</span>';
 } else if(!d){ t.innerHTML=''; return }
 else if(d.tem){
  t.innerHTML='<span data-radai-frase>'+(ND.osso
    ? 'o osso sai da projeção (MIP) pela segmentação do ContourLab'
    : 'o osso está à mostra: a segmentação do ContourLab foi achada, e está desligada')
   +'</span> <b>'+ndEsc(d.fonte||'')+' · '+(+d.estruturas||0)+'</b>';
 } else {
  t.innerHTML='<span data-radai-frase>'+ndEsc(d.motivo||'esta série ainda não tem segmentação do ContourLab: o osso continua na projeção')+'</span>'
   +(d.entrega?(' <b translate="no">'+ndEsc(d.entrega)+'</b>'):'');
 }
 if(t.setAttribute) t.setAttribute('title', String(t.textContent||''));
 if(window.radaiRetraduzir) window.radaiRetraduzir();
}
function ndOssoAlternar(){
 if(!ND.aberta || !ND.tem_osso) return;
 ND.osso=!ND.osso;
 ndPintarOsso(); ndRegistrar('osso'); ndProjetar();
}
function ndSegmentar(){
 if(!ND.b || !ND.aberta) return;
 if(!ndPedeSubstituir()){ ndPedirSegmentacao(false); return }
 var entrega=String((ND.ossoInfo && ND.ossoInfo.entrega) || '');
 var h='<p data-radai-frase>'+ndEsc(entrega
   ? 'Esta série já tem uma entrega do ContourLab, e ela não tem osso que sirva para a projeção.'
   : 'A fila deu esta série como pronta, e nenhuma segmentação com osso apareceu ao lado dela.')
  +'</p>'+(entrega?('<p><b translate="no">'+ndEsc(entrega)+'</b></p>'):'')
  +'<p data-radai-frase>Segmentar em AUTO grava o FULL e substitui a entrega desta série. A entrega nova também é sugestão, e passa pela revisão médica.</p>';
 // GUARDA: substituir apaga a entrega que existe; sem a confirmação, nada vai para a fila.
 if(!window.uiConfirmar){
  ndMsg('a confirmação não abriu: nada foi para a fila','erro'); return }
 window.uiConfirmar({titulo:'Substituir a entrega desta série?', html:h,
  ok:'Segmentar em AUTO e substituir',
  aoSim:function(){ ndPedirSegmentacao(true) }});
}
function ndPedirSegmentacao(substituir){
 var b=ND.b, sg=ndEl('nd_segmentar');
 if(sg) sg.disabled=true;
 var corpo={b:b, rotulo:ND.desc||''};
 if(substituir) corpo.substituir=true;
 fetch('/api/nidus/segmentar',{method:'POST',
   headers:{'Content-Type':'application/json'},
   body:JSON.stringify(corpo)})
  .then(function(r){return r.json()}).then(function(d){
   if(b!==ND.b) return;
   if(sg) sg.disabled=false;
   if(!d || !d.ok){
    ndMsg((d && d.erro) ? String(d.erro) : 'fila indisponível','erro'); return }
   ND.fila={id:d.id, tentativas:0, falhas:0, frase:''};
   ND.substituirOsso=false;
   ndPintarOsso();
   ndMsg('na fila: quando a segmentação AUTO do ContourLab terminar, o osso sai da projeção','ok');
   if(window.radaiFilaAbrir){ try{ window.radaiFilaAbrir() }catch(e){} }
   ndFilaVigiar(0);
  }).catch(function(){ if(sg) sg.disabled=false; ndMsg('fila indisponível','erro') });
}
function ndFilaSituacao(estado, rodando){
 var f=ND.fila; if(!f) return;
 var t='';
 if(estado==='rodando')
  t='a segmentação AUTO desta série está rodando: quando terminar, o osso sai da projeção';
 else if(rodando===false)
  t='a fila está parada: o cartão espera alguém clicar em «Iniciar» na barra da fila, e só então a segmentação AUTO começa';
 else if(rodando===true)
  t='na fila, e a fila está rodando: a segmentação AUTO desta série começa na vez dela';
 // GUARDA: sem o campo `rodando` a situação da fila é desconhecida, e a tela não a inventa.
 if(!t || t===f.frase) return;
 f.frase=t;
 ndMsg(t, (estado!=='rodando' && rodando===false) ? '' : 'ok');
 ndPintarOsso();
}
function ndFilaVigiar(espera){
 var b=ND.b;
 if(!ND.fila) return;
 setTimeout(function(){
  if(b!==ND.b || !ND.fila) return;
  var id=ND.fila.id;
  fetch('/api/fila/estado',{method:'POST',
    headers:{'Content-Type':'application/json'}, body:JSON.stringify({ids:[id]})})
   .then(function(r){return r.json()}).then(function(d){
    if(b!==ND.b || !ND.fila) return;
    ND.fila.falhas=0;
    var cs=(d && d.cartoes) ? d.cartoes : (Array.isArray(d) ? d : []);
    var c=cs.filter(function(x){ return x && x.id===id })[0];
    if(!c){ ND.fila=null; ndOssoRecarregar('saiu'); return }
    if(c.estado==='pronto' || c.estado==='parcial'){
     ND.fila=null; ndOssoRecarregar('pronto'); return }
    if(c.estado==='falhou' || c.estado==='cancelado'){
     ND.fila=null; ndPintarOsso();
     ndMsg2(String(c.mensagem||c.estado), 'a segmentação não terminou: o osso continua na projeção.', 'erro');
     return }
    ndFilaSituacao(c.estado, (d && typeof d.rodando==='boolean') ? d.rodando : null);
    ND.fila.tentativas++;
    if(ND.fila.tentativas>ND_FILA_TENTATIVAS){ ND.fila=null; ndPintarOsso();
     ndMsg('o cartão continua na fila, e esta tela parou de acompanhá-lo: quando a segmentação terminar, escolha a série de novo','');
     return }
    ndFilaVigiar();
   }).catch(function(){ if(b!==ND.b || !ND.fila) return;
    ND.fila.falhas++;
    // GUARDA: a fila só é dada como muda depois de falhas SEGUIDAS; o cartão que responde esperando respondeu.
    if(ND.fila.falhas>=ND_FILA_FALHAS){ ND.fila=null; ndPintarOsso();
     ndMsg('a fila não responde: quando a segmentação terminar, escolha a série de novo','erro');
     return }
    ndFilaVigiar() });
 }, (espera==null) ? ND_FILA_A_CADA_MS : espera);
}
function ndOssoRecarregar(porque){
 var b=ND.b;
 fetch('/api/nidus/osso',{method:'POST', headers:{'Content-Type':'application/json'},
   body:JSON.stringify({b:b})})
  .then(function(r){return r.json()}).then(function(d){
   if(b!==ND.b) return;
   if(!d || !d.osso){ ndPintarOsso();
    ndMsg2((d && d.erro) ? String(d.erro) : 'sem resposta', 'não consegui reler a segmentação: escolha a série de novo.', 'erro');
    return }
   ndOsso(d.osso);
   if(ND.tem_osso){ ND.osso=true; ndPintarOsso(); ndRegistrar('osso'); ndProjetar();
    nd3Esquecer(); nd3Malhas();
    ndMsg('a segmentação terminou: o osso saiu da projeção','ok'); return }
   if(porque==='pronto') ND.substituirOsso=true;
   ndPintarOsso();
   ndMsg(porque==='saiu'
    ? 'o cartão saiu da fila, e nenhuma segmentação com osso apareceu ao lado da série: o osso continua na projeção'
    : 'a fila fechou o cartão, e nenhuma segmentação com osso apareceu ao lado da série: o osso continua na projeção',
    'erro');
  }).catch(function(){ if(b===ND.b) ndPintarOsso() });
}

function ndGuardar(auto){
 if(!ND.aberta) return;
 if(!ND.pontos || ND.pontos.length < 3){
  if(!auto){
   ndMsg('circule o ninho antes de guardar (3 pontos, no mínimo)','erro');
   if(window.uiPorQue) window.uiPorQue('Guardar incidência',
    '<span data-radai-frase>circule o ninho antes de guardar (3 pontos, no mínimo)</span>');
  }
  return;
 }
 if(ND.guardadas.length>=ND.teto){
  ndMsg(ND.teto+' é o máximo — cada incidência é um volume na memória.','erro');
  return;
 }
 ND.tracando=false;
 ND.guardadas.push({lao:ND.lao, cra:ND.cra, pontos:ND.pontos.slice(),
   caixa:ND.caixa?ND.caixa.slice():null, jan:ND.jan, modo:ND.modo,
   laje:ND.laje, osso:ND.osso, pendente:true});
 ND.pontos=[]; ndPintarMarca();
 ndPintarGuardadas(); ndRegistrar('guardar');
 ndMsg('incidência '+ND.guardadas.length+' guardada — '+ndRotulo(ND),'ok');
 ndCalcular();
}

function ndLimparGuardadas(){
 ND.guardadas=[]; ND.pontos=[]; ND.sessao=null;
 ndPintarMarca(); ndPintarGuardadas(); ndRegistrar('limpar');
 [0,1,2].forEach(function(eixo){ ndLinhas(eixo) });
 ndTravas(); ndMsg('marcação limpa','');
}

function ndTirar(i){
 ND.guardadas.splice(i,1);
 ndPintarGuardadas(); ndRegistrar('tirar');
 if(ND.guardadas.length){ ndCalcular(); }
 else { ND.sessao=null; [0,1,2].forEach(function(eixo){ ndLinhas(eixo) });
  ndTravas(); ndMsg('marcação limpa',''); }
}

// GUARDA: o âmbar do Nidus é só da caixa e do traço; as guardadas usam a paleta sem ele.
function ndCor(i){ return 'nd-c'+(i%ND_CORES); }
function ndNomeDaIncidencia(g){
 for(var i=0;i<ND_INCIDENCIAS.length;i++)
  if(ND_INCIDENCIAS[i][1]===g.lao && ND_INCIDENCIAS[i][2]===g.cra) return ND_INCIDENCIAS[i][0];
 return '';
}

function ndPintarGuardadas(){
 ndConsControles();
 var e=ndEl('nd_guardadas'); if(!e) return;
 if(!ND.guardadas.length){
  e.innerHTML='<span class="nd-vazio" data-radai-frase>'
   +'nenhuma incidência guardada — gire o gantry, circule o ninho, e guarde'
   +'</span>';
  var lp0=ndEl('nd_bt_limpar'); if(lp0) lp0.hidden=true;
  ndTravas(); ndPintarLegenda(); ndPintarPad(); nd3Pedir();
  return;
 }
 var h='<ol class="nd-lista">';
 ND.guardadas.forEach(function(g,i){
  var nome=ndNomeDaIncidencia(g);
  h+='<li class="'+ndCor(i)+(g.pendente?' pend':'')+'" title="'+ndEsc(nome||ndRotulo(g))
    +' · '+g.pontos.length+'"><i></i>'
    +'<b translate="no">'+(i+1)+' · '+ndRotulo(g)+'</b>'
    +'<button type="button" class="nd-x" title="tirar esta incidência"'
    +' aria-label="tirar esta incidência" onclick="ndTirar('+i+')">&times;</button>'
    +'</li>';
 });
 h+='</ol>';
 if(ND.teto && ND.guardadas.length >= ND.teto){
  h+='<div class="nd-teto">'+ND.teto+' é o máximo — cada incidência é '
    +'um volume na memória.</div>';
 }
 e.innerHTML=h;
 var lp=ndEl('nd_bt_limpar'); if(lp) lp.hidden=false;
 ndTravas(); ndPintarLegenda(); ndPintarPad(); nd3Pedir();
 if(window.radaiRetraduzir) window.radaiRetraduzir();
}

function ndPintarLegenda(){
 var e=ndEl('nd_legenda'); if(!e) return;
 var h='<span class="t" data-radai-frase>no MPR</span>'
  +'<span class="l cx"><i></i><span data-radai-frase>caixa de recorte</span></span>'
  +'<span class="t" data-radai-frase>tubos</span>';
 if(!ND.guardadas.length){
  h+='<span data-radai-frase>aparecem aqui quando uma incidência é guardada</span>';
 } else {
  ND.guardadas.forEach(function(g,i){
   h+='<span class="l '+ndCor(i)+'"><i></i><span translate="no">'+(i+1)+' · '+ndRotulo(g)+'</span></span>' });
  if(ND.guardadas.length>=2)
   h+='<span class="l inter"><i></i><span data-radai-frase>onde se cruzam</span></span>';
  if(ND.sessao) h+='<span class="l consenso"><i></i><span data-radai-frase>sugestão geométrica</span></span>';
 }
 e.innerHTML=h;
 if(window.radaiRetraduzir) window.radaiRetraduzir();
}

function ndCalcular(refazer){
 var g=ND.guardadas.filter(Boolean);
 if(!g.length || !ND.b || !ND.aberta) return;
 if(refazer!==true) ND.refeitas=0;
 if(ND.cruzando){ ND.recruzar=true; return }
 ND.cruzando=true; ND.recruzar=false; ndTravas();
 var b=ND.b;
 ndMsg('retroprojetando…','');
 fetch('/api/nidus/tubos',{method:'POST',
   headers:{'Content-Type':'application/json'},
   body:JSON.stringify({b:b, lado:ND.lado, incidencias:g.map(function(x){
    return {lao:x.lao, cra:x.cra, pontos:x.pontos} })})})
  .then(function(r){return r.json()}).then(function(d){
   if(b!==ND.b) return;
   ND.cruzando=false;
   if(!d || d.erro){ ndFalhaDaRetro((d && d.erro) ? String(d.erro) : 'sem resposta'); return }
   ND.sessao=d.sessao; ND.teto=d.teto||12;
   ND.consensoEditavel=false; ND.consIndices={}; ndConsControles();
   g.forEach(function(x){ x.pendente=false });
   ndMarcarBom(); ndRegistrar('cruzar');
   var n=d.incidencias||g.length;
   if(ND.restaurou){
    ND.restaurou=false;
    ndMsg('a marcação salva desta série voltou: as incidências estão na lista','ok');
   } else if(n<2){
    ndMsg('1 incidência guardada — gire o gantry e marque outra para '
      +'começar a cruzar','');
   } else {
    ndMsg(n+' incidências cruzadas — a linha grossa é onde TODAS se '
      +'encontram; cada linha fina é uma delas','ok');
   }
   ndPintarGuardadas();
   [0,1,2].forEach(function(eixo){ ndLinhas(eixo) });
   if(ND.recruzar) ndCalcular();
  }).catch(function(e){ if(b!==ND.b) return;
   ND.cruzando=false; ndFalhaDaRetro(String(e)) });
}

function ndFalhaDaRetro(motivo){
 ND.recruzar=false;
 ndPintarGuardadas(); ndRegistrar('falhou');
 ndMsg2(motivo, 'a retroprojeção falhou: as linhas continuam as do último estado bom, e as incidências desenhadas estão salvas — «Cruzar de novo» tenta outra vez.', 'erro');
}

function ndLinhasFalharam(motivo){
 ND.sessao=null;
 ND.guardadas.forEach(function(x){ if(x) x.pendente=true });
 [0,1,2].forEach(function(eixo){ var g=ndEl('nd_lin'+eixo); if(g) g.innerHTML='' });
 ndPintarGuardadas(); ndRegistrar('falhou');
 ndMsg2(motivo, 'as linhas da marcação não vieram do servidor, nem depois de uma nova tentativa: as incidências desenhadas estão salvas — «Cruzar de novo» tenta outra vez.', 'erro');
}

var ND_T_CORTE={};
function ndCorte(eixo, brilho){
 var img=ndEl('nd_pl'+eixo), palco=ndEl('nd_pp'+eixo);
 if(!img || !ND.b || !ND.aberta) return;
 if(ND_T_CORTE[eixo]){ clearTimeout(ND_T_CORTE[eixo]); ND_T_CORTE[eixo]=null }
 var b=ND.b;
 function fim(){ if(ND_T_CORTE[eixo]){ clearTimeout(ND_T_CORTE[eixo]); ND_T_CORTE[eixo]=null }
  ndCarregando(false, palco) }
 if(brilho) ndCarregando(true, palco, ND.abrindo?'abrindo a série…':'carregando o corte…');
 else ND_T_CORTE[eixo]=setTimeout(function(){
  ndCarregando(true, palco, 'carregando o corte…') }, 250);
 img.onerror=function(){ if(b!==ND.b) return; img.removeAttribute('src'); fim(); ndFalhou('corte') };
 img.onload=function(){ fim() };
 img.src='/api/nidus/corte?b='+encodeURIComponent(ND.b)
   +'&eixo='+eixo+'&pos='+ND.planos[eixo]+'&janela='+ND.jan;
 ndLinhas(eixo);
}

function ndPintarPlanos(brilho){
 if(!ND.b || !ND.aberta) return;
 [0,1,2].forEach(function(eixo){ ndCorte(eixo, brilho) });
 ndPintarCaixas();
}

function ndLinhas(eixo){
 var g=ndEl('nd_lin'+eixo); if(!g) return;
 if(!ND.sessao){ g.innerHTML=''; return }
 var s=ND.sessao;
 ND.consSeq[eixo]=(ND.consSeq[eixo]||0)+1; var seq=ND.consSeq[eixo], pos=ND.planos[eixo];
 fetch('/api/nidus/linhas?s='+encodeURIComponent(s)
   +'&eixo='+eixo+'&pos='+pos+'&temperatura='+ND.temperatura+'&editado='+(ND.consensoEditavel?'true':'false'))
  .then(function(r){return r.json()}).then(function(d){
   if(s!==ND.sessao || seq!==ND.consSeq[eixo] || pos!==ND.planos[eixo]) return;
   if(!d || d.erro){
    if(ND.cruzando) return;
    // GUARDA: a sessão que falha é refeita das incidências salvas UMA vez por ato; a segunda falha avisa e para.
    if(ND.guardadas.length && ND.refeitas<1){
     ND.refeitas++; ND.sessao=null; ndCalcular(true); return }
    ndLinhasFalharam((d && d.erro) ? String(d.erro) : 'sem resposta');
    return;
   }
   g.setAttribute('viewBox','0 0 '+d.largura+' '+d.altura);
   ND.consIndices[eixo]=d.indice;
   ndConsVazio(d.consenso_vazio===true);
   var ed=ndEl('nd_ed'+eixo); if(ed) ed.setAttribute('viewBox','0 0 '+d.largura+' '+d.altura);
   var h='';
   (d.camadas||[]).forEach(function(cam){
    var cls = cam.qual==='consenso' ? 'nd-consenso-linha' : cam.qual==='inter' ? 'nd-inter' : ('nd-tubo '+ndCor(cam.i||0));
    (cam.segmentos||[]).forEach(function(sg){
     h+='<line x1="'+sg[0][0]+'" y1="'+sg[0][1]+'" x2="'+sg[1][0]
       +'" y2="'+sg[1][1]+'" class="'+cls+'"/>';
    });
   });
   g.innerHTML=h;
  }).catch(function(){ g.innerHTML='' });
}

function ndJanela(j){
 if(!ND.aberta) return;
 ND.jan=j;
 ndSincronizar(); ndRegistrar('janela');
 ndProjetar(); ndPintarPlanos(true);
}
function ndModo(m){
 if(!ND.aberta) return;
 ND.modo=m;
 ndSincronizar(); ndRegistrar('modo'); ndProjetar();
}
function ndOutra(){
 var p=(ndEl('nd_pasta').value||'').trim();
 if(!p){ if(window.uiTremer) window.uiTremer(ndEl('nd_pasta')); return }
 ndListar(p);
}

function ndProcurar(){
 if(!window.uiExplorador) return;
 window.uiExplorador({inicial:(ndEl('nd_pasta').value||'').trim(),
  origem:ndEl('nd_procurar'),
  aoUsar:function(c){ ndEl('nd_pasta').value=c||''; ndOutra() }});
}

var ND_PAD={W:0, H:0, m:14, quente:null, arrasto:false, t:null};
function ndPadXY(lao, cra){ var m=ND_PAD.m;
 return [m+(lao+180)/360*(ND_PAD.W-2*m), m+(90-cra)/180*(ND_PAD.H-2*m-10)] }
function ndPadAng(x, y){ var m=ND_PAD.m;
 return [(x-m)/(ND_PAD.W-2*m)*360-180, 90-(y-m)/(ND_PAD.H-2*m-10)*180] }
function ndPintarPad(){
 var el=ndEl('nd_pad'); if(!el || !ND_PAD.W) return;
 var W=ND_PAD.W, H=ND_PAD.H, h='<svg viewBox="0 0 '+W+' '+H+'" aria-hidden="true">', a, b;
 for(a=-180;a<=180;a+=45){ var p=ndPadXY(a,0);
  h+='<line class="gr'+(a%90===0?' f':'')+'" x1="'+p[0]+'" y1="'+ndPadXY(0,90)[1]+'" x2="'+p[0]+'" y2="'+ndPadXY(0,-90)[1]+'"/>' }
 for(b=-90;b<=90;b+=30){ var q=ndPadXY(-180,b);
  h+='<line class="gr'+(b===0?' f':'')+'" x1="'+q[0]+'" y1="'+q[1]+'" x2="'+ndPadXY(180,b)[0]+'" y2="'+q[1]+'"/>' }
 var yb=H-4;
 [[-90,'RAO 90'],[0,'AP'],[90,'LAO 90']].forEach(function(t){
  h+='<text x="'+ndPadXY(t[0],0)[0]+'" y="'+yb+'" text-anchor="middle">'+t[1]+'</text>' });
 h+='<text x="'+(ND_PAD.m+2)+'" y="'+(ndPadXY(0,90)[1]+8)+'">CRA</text><text x="'+(ND_PAD.m+2)+'" y="'+(ndPadXY(0,-90)[1]-3)+'">CAU</text>';
 var c=ndPadXY(ND.ver.lao, ND.ver.cra);
 h+='<line class="cruz" x1="'+c[0]+'" y1="'+ndPadXY(0,90)[1]+'" x2="'+c[0]+'" y2="'+ndPadXY(0,-90)[1]+'"/>'
   +'<line class="cruz" x1="'+ndPadXY(-180,0)[0]+'" y1="'+c[1]+'" x2="'+ndPadXY(180,0)[0]+'" y2="'+c[1]+'"/>';
 ND_INCIDENCIAS.forEach(function(t){ var p=ndPadXY(t[1],t[2]);
  var on=t[1]===ND.ver.lao && t[2]===ND.ver.cra, qq=ND_PAD.quente && ND_PAD.quente[0]===t[1] && ND_PAD.quente[1]===t[2];
  h+='<circle class="pre'+(on?' on':'')+(qq?' quente':'')+'" cx="'+p[0]+'" cy="'+p[1]+'" r="3.6"/>' });
 ND.guardadas.forEach(function(g,i){ var p=ndPadXY(g.lao,g.cra);
  h+='<g class="'+ndCor(i)+'"><circle class="gd" cx="'+p[0]+'" cy="'+p[1]+'" r="7"/>'
    +'<text class="gd-n" x="'+p[0]+'" y="'+(p[1]-12)+'">'+(i+1)+'</text></g>' });
 h+='<circle class="atual" cx="'+c[0]+'" cy="'+c[1]+'" r="4.5"/></svg>';
 el.innerHTML=h;
}
function ndPadAjustar(){
 var el=ndEl('nd_pad'); if(!el || !el.getBoundingClientRect) return;
 var r=el.getBoundingClientRect();
 ND_PAD.W=Math.round(r.width)||268; ND_PAD.H=Math.round(r.height)||120;
 ndPintarPad();
}
function ndPadPonteiro(ev){
 var el=ndEl('nd_pad'), rc=el.getBoundingClientRect(), x=ev.clientX-rc.left, y=ev.clientY-rc.top;
 var a=ndPadAng(x, y);
 if(!ev.shiftKey){ var mais=null, dm=7;
  ND_INCIDENCIAS.forEach(function(t){ var p=ndPadXY(t[1],t[2]), dd=Math.sqrt((p[0]-x)*(p[0]-x)+(p[1]-y)*(p[1]-y));
   if(dd<dm){ dm=dd; mais=t } });
  if(mais) a=[mais[1], mais[2]] }
 ndPreverAng(a[0], a[1]);
}
function ndLigarPad(){
 var el=ndEl('nd_pad'); if(!el) return;
 el.addEventListener('pointerdown', function(ev){ if(ev.button!==0 || !ND.aberta) return;
  try{ el.setPointerCapture(ev.pointerId) }catch(e){}
  ND_PAD.arrasto=true; ndPadPonteiro(ev) });
 el.addEventListener('pointermove', function(ev){ if(ND_PAD.arrasto) ndPadPonteiro(ev) });
 el.addEventListener('pointerup', function(){ if(ND_PAD.arrasto){ ND_PAD.arrasto=false; ndSoltarAngulo() } });
 el.addEventListener('keydown', function(ev){ var p=ev.shiftKey?10:1, dl=0, dc=0;
  if(ev.key==='ArrowLeft') dl=-p; else if(ev.key==='ArrowRight') dl=p;
  else if(ev.key==='ArrowUp') dc=p; else if(ev.key==='ArrowDown') dc=-p; else return;
  if(ev.preventDefault) ev.preventDefault();
  ndPreverAng(ND.ver.lao+dl, ND.ver.cra+dc);
  clearTimeout(ND_PAD.t); ND_PAD.t=setTimeout(ndSoltarAngulo, 220) });
}

var ND3 = {gl:null, prog:null, loc:{}, u32:null, canvas:null, motivo:'', objs:{},
           aux:{}, sala:{}, caixaMalha:null, info:{}, pedido:false, n:0,
           detector:true, atraves:false, emSala:false, livre:{a:-40, b:22},
           cam:{yaw:120, pitch:16, dist:3050}, arr:null, motivoMalha:''};
var ND3_COR = {vaso:[229,130,111], osso:[233,223,201], pele:[196,154,132],
 arame:[227,155,79], placa:[169,195,230], sala:[92,109,134], mesa:[58,71,92],
 arco:[201,211,225], piso:[29,42,61], feixe:[246,231,200]};

function nd3Construtor(){ return {p:[], n:[], i:[]} }
function nd3V(C, p, n){ C.p.push(p[0],p[1],p[2]); C.n.push(n[0],n[1],n[2]); return C.p.length/3-1 }
function nd3T(C, a, b, c){ C.i.push(a,b,c) }
function nd3Subir(C, linhas, cor){
 var m=r3gMalhaDe(C.p, C.n, C.i, linhas);
 return r3gSubirEm(ND3, m, cor||[200,200,200]);
}
function nd3Norm(a){ var l=Math.sqrt(a[0]*a[0]+a[1]*a[1]+a[2]*a[2])||1; return [a[0]/l,a[1]/l,a[2]/l] }
function nd3Cruz(a,b){ return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]] }
function nd3Soma(a,b){ return [a[0]+b[0],a[1]+b[1],a[2]+b[2]] }
function nd3Menos(a,b){ return [a[0]-b[0],a[1]-b[1],a[2]-b[2]] }
function nd3Vezes(a,s){ return [a[0]*s,a[1]*s,a[2]*s] }
function nd3Pe(a,b){ return a[0]*b[0]+a[1]*b[1]+a[2]*b[2] }
function nd3Elipsoide(C, c, r, nu, nv){
 var ids=[], i, j;
 for(j=0;j<=nv;j++){ var ct=1-2*j/nv, st=Math.sqrt(Math.max(0,1-ct*ct)), linha=[];
  for(i=0;i<=nu;i++){ var ph=i/nu*2*Math.PI, e=[st*Math.cos(ph), st*Math.sin(ph), ct];
   linha.push(nd3V(C, [c[0]+r[0]*e[0], c[1]+r[1]*e[1], c[2]+r[2]*e[2]], nd3Norm([e[0]/r[0],e[1]/r[1],e[2]/r[2]]))) }
  ids.push(linha) }
 for(j=0;j<nv;j++) for(i=0;i<nu;i++){ var a=ids[j][i], b=ids[j][i+1], c2=ids[j+1][i], d=ids[j+1][i+1];
  nd3T(C,a,c2,b); nd3T(C,b,c2,d) }
}
function nd3Cilindro(C, c, rx, ry, z0, z1, n, tampas){
 var a0=[], a1=[], i, k;
 for(i=0;i<=n;i++){ var ph=i/n*2*Math.PI, e=[Math.cos(ph),Math.sin(ph)], nn=nd3Norm([e[0]/rx,e[1]/ry,0]);
  a0.push(nd3V(C,[c[0]+rx*e[0], c[1]+ry*e[1], z0], nn)); a1.push(nd3V(C,[c[0]+rx*e[0], c[1]+ry*e[1], z1], nn)) }
 for(k=0;k<n;k++){ nd3T(C,a0[k],a0[k+1],a1[k]); nd3T(C,a0[k+1],a1[k+1],a1[k]) }
 if(tampas){ [[z0,-1],[z1,1]].forEach(function(t){ var cc=nd3V(C,[c[0],c[1],t[0]],[0,0,t[1]]), aro=[];
  for(var q=0;q<=n;q++){ var ph=q/n*2*Math.PI; aro.push(nd3V(C,[c[0]+rx*Math.cos(ph), c[1]+ry*Math.sin(ph), t[0]],[0,0,t[1]])) }
  for(var w=0;w<n;w++) nd3T(C,cc,aro[w],aro[w+1]) }) }
}
function nd3Bloco(C, c, h){
 var fs=[[[1,0,0],[0,1,0],[0,0,1]],[[-1,0,0],[0,0,1],[0,1,0]],[[0,1,0],[0,0,1],[1,0,0]],
         [[0,-1,0],[1,0,0],[0,0,1]],[[0,0,1],[1,0,0],[0,1,0]],[[0,0,-1],[0,1,0],[1,0,0]]];
 fs.forEach(function(F){ var n=F[0], a=F[1], b=F[2], ids=[];
  [[-1,-1],[1,-1],[1,1],[-1,1]].forEach(function(s){
   ids.push(nd3V(C, [c[0]+(n[0]+a[0]*s[0]+b[0]*s[1])*h[0], c[1]+(n[1]+a[1]*s[0]+b[1]*s[1])*h[1],
                     c[2]+(n[2]+a[2]*s[0]+b[2]*s[1])*h[2]], n)) });
  nd3T(C,ids[0],ids[1],ids[2]); nd3T(C,ids[0],ids[2],ids[3]) });
}
function nd3MontarAux(){
 var A=ND3.aux, n=[0,0,1], C=nd3Construtor();
 var a=nd3V(C,[-1,-1,0],n), b=nd3V(C,[1,-1,0],n), c=nd3V(C,[1,1,0],n), d=nd3V(C,[-1,1,0],n);
 nd3T(C,a,b,c); nd3T(C,a,c,d); A.placa=nd3Subir(C, false);
 var L=nd3Construtor(); [[-1,-1,0],[1,-1,0],[1,1,0],[-1,1,0]].forEach(function(p){ nd3V(L,p,n) });
 L.i=[0,1,1,2,2,3,3,0]; A.contorno=nd3Subir(L, true);
 var W=nd3Construtor(); for(var i=0;i<8;i++) nd3V(W,[i&1?1:0, i&2?1:0, i&4?1:0],n);
 W.i=[0,1,2,3,4,5,6,7, 0,2,1,3,4,6,5,7, 0,4,1,5,2,6,3,7]; A.arame=nd3Subir(W, true);
 var S=nd3Construtor(); nd3V(S,[0,0,0],n); nd3V(S,[0,0,1],n); S.i=[0,1]; A.segmento=nd3Subir(S, true);
}
function nd3MontarSala(){
 var S=ND3.sala, n=[0,-1,0], k=0, x, z;
 var G=nd3Construtor();
 for(x=-2200;x<=2200;x+=250){ nd3V(G,[x,1050,-2700],n); nd3V(G,[x,1050,1900],n); G.i.push(k,k+1); k+=2 }
 for(z=-2700;z<=1900;z+=250){ nd3V(G,[-2200,1050,z],n); nd3V(G,[2200,1050,z],n); G.i.push(k,k+1); k+=2 }
 S.piso=nd3Subir(G, true);
 var M=nd3Construtor(); nd3Bloco(M,[0,129,-950],[260,25,1250]); nd3Bloco(M,[0,600,-1500],[150,446,250]);
 nd3Bloco(M,[0,1035,-1500],[330,15,420]); S.mesa=nd3Subir(M, false);
 var P=nd3Construtor();
 nd3Elipsoide(P,[0,4,18],[76,96,86],40,24); nd3Cilindro(P,[0,10],50,48,-120,-30,24,false);
 nd3Elipsoide(P,[0,10,-400],[190,105,300],40,24); nd3Elipsoide(P,[0,15,-760],[170,96,140],40,24);
 [-1,1].forEach(function(s){ nd3Cilindro(P,[s*92,30],66,60,-1680,-840,20,true);
  nd3Elipsoide(P,[s*92,30,-1690],[60,55,60],16,10); nd3Cilindro(P,[s*232,20],46,44,-740,-160,16,true) });
 S.paciente=nd3Subir(P, false);
 var A=nd3Construtor(), Rc=760, sec=[[-45,-70],[45,-70],[45,70],[-45,70]], segs=48, aneis=[], i, f;
 for(i=0;i<=segs;i++){ var ph=i/segs*Math.PI, e1=[Math.cos(ph),0,Math.sin(ph)], anel=[];
  sec.forEach(function(s){ anel.push(nd3Soma(nd3Vezes(e1,Rc+s[0]),[0,s[1],0])) }); aneis.push(anel) }
 for(i=0;i<segs;i++) for(f=0;f<4;f++){ var p0=aneis[i][f], p1=aneis[i][(f+1)%4], q0=aneis[i+1][f], q1=aneis[i+1][(f+1)%4];
  var nn=nd3Norm(nd3Cruz(nd3Menos(p1,p0),nd3Menos(q0,p0)));
  var ia=nd3V(A,p0,nn), ib=nd3V(A,p1,nn), ic=nd3V(A,q0,nn), id=nd3V(A,q1,nn); nd3T(A,ia,ib,ic); nd3T(A,ib,id,ic) }
 S.arco=nd3Subir(A, false);
 var D=nd3Construtor(); nd3Bloco(D,[470,0,0],[34,160,160]); nd3Bloco(D,[(470+34+Rc)/2,0,0],[(Rc-470-34)/2,46,62]);
 S.detector=nd3Subir(D, false);
 var DF=nd3Construtor(); nd3Bloco(DF,[470,0,0],[30,150,150]); S.detectorF=nd3Subir(DF, false);
 var U=nd3Construtor(); nd3Bloco(U,[-640,0,0],[64,80,90]); nd3Bloco(U,[-(Rc+640+64)/2,0,0],[(Rc-640-64)/2,46,62]);
 S.tubo=nd3Subir(U, false);
 var B=nd3Construtor(); nd3Bloco(B,[-60,0,0],[516,78,78]); S.feixe=nd3Subir(B, false);
 var R=nd3Construtor(); nd3Bloco(R,[0,0,Rc],[80,110,70]); S.carro=nd3Subir(R, false);
 var Cl=nd3Construtor(); nd3Cilindro(Cl,[0,0],72,72,Rc+60,Rc+330,24,true);
 nd3Bloco(Cl,[0,525,Rc+330],[110,525,110]); nd3Bloco(Cl,[0,1035,Rc+330],[380,15,380]);
 S.coluna=nd3Subir(Cl, false);
}
function nd3Iniciar(){
 var c=ndEl('nd_gl');
 if(!c || !c.getContext){ ND3.motivo='o navegador não criou um contexto WebGL'; nd3Canto(); return }
 var gl=null, op={antialias:true, alpha:false, depth:true, premultipliedAlpha:false};
 try{ gl=c.getContext('webgl', op) || c.getContext('experimental-webgl', op) }catch(e){ gl=null }
 if(!gl){ ND3.motivo='o navegador não criou um contexto WebGL'; nd3Canto(); return }
 var m=r3gPrograma(ND3, gl);
 if(m){ ND3.gl=null; ND3.motivo=m; nd3Canto(); return }
 ND3.canvas=c;
 try{ nd3MontarAux(); nd3MontarSala() }catch(e){ ND3.gl=null; ND3.motivo=String(e && e.message || e); nd3Canto(); return }
 nd3Ligar(c);
 c.addEventListener('webglcontextlost', function(ev){ if(ev.preventDefault) ev.preventDefault();
  ND3.gl=null; ND3.motivo='o contexto WebGL foi perdido (o driver de vídeo reiniciou)'; nd3Canto() });
 nd3Pedir();
}
function nd3Pedir(){
 if(ND3.pedido) return;
 if(!ND3.gl){ nd3Canto(); return }
 ND3.pedido=true;
 (window.requestAnimationFrame || setTimeout)(nd3Pintar);
}
function nd3Esquecer(){
 ['vaso','osso','pele'].forEach(function(q){ if(ND3.objs[q]) r3gSoltarObj(ND3, ND3.objs[q]); delete ND3.objs[q] });
 ND3.caixaMalha=null; ND3.info={}; ND3.motivoMalha=''; ND3.n++;
}
function nd3CaixaDentro(a, b){
 return !!(a && b && a[0]>=b[0] && a[1]<=b[1] && a[2]>=b[2] && a[3]<=b[3] && a[4]>=b[4] && a[5]<=b[5]);
}
// GUARDA: arrastar a caixa não refaz malha (o sombreador recorta); refaz ao soltar só se a caixa nova sair da que fez a malha.
function nd3Malhas(){
 if(!ND.b || !ND.aberta || !ND3.gl) { nd3Pedir(); return }
 var c=ND.caixa;
 if(!c || ndCaixaCheia(c)){ nd3Esquecer(); ND3.motivoMalha=''; nd3Pedir(); return }
 if(ND3.caixaMalha && nd3CaixaDentro(c, ND3.caixaMalha)){ nd3Pedir(); return }
 var meu=++ND3.n, b=ND.b, alvo=c.slice();
 ND3.motivoMalha='montando…'; nd3Canto();
 fetch('/api/nidus/malhas',{method:'POST', headers:{'Content-Type':'application/json'},
   body:JSON.stringify({b:b, t:ND_ABA, n:meu, caixa:alvo.map(function(v){ return v.toFixed(4) }).join(',')})})
  .then(function(r){ return r.json() }).then(function(d){
   if(meu!==ND3.n || b!==ND.b) return;
   ['vaso','osso','pele'].forEach(function(q){ if(ND3.objs[q]) r3gSoltarObj(ND3, ND3.objs[q]); delete ND3.objs[q] });
   ND3.info={}; ND3.motivoMalha=(d && d.erro) ? String(d.erro) : '';
   ND3.caixaMalha=(d && !d.erro) ? alvo : null;
   var lista=(d && d.malhas) || [];
   lista.forEach(function(x){ ND3.info[x.qual]=x });
   nd3Canto(); nd3Pedir();
   lista.forEach(function(x){
    if(!x.m || !x.triangulos) return;
    fetch('/api/nidus/malha?m='+encodeURIComponent(x.m)).then(function(r){
     if(!r.ok) throw new Error('HTTP '+r.status); return r.arrayBuffer() })
     .then(function(buf){ if(meu!==ND3.n) return;
      var o=r3gSubirEm(ND3, r3gLerStl(buf), ND3_COR[x.qual]); if(o) ND3.objs[x.qual]=o; nd3Pedir() })
     .catch(function(){ if(meu!==ND3.n) return; ND3.info[x.qual]={qual:x.qual, triangulos:0, motivo:'a malha não veio do servidor'}; nd3Canto() });
   });
  }).catch(function(){ if(meu!==ND3.n) return; ND3.motivoMalha='o 3D não veio do servidor'; nd3Canto() });
}
function nd3Caixa(){
 if(!ND.geo || !ND.caixa || ndCaixaCheia(ND.caixa)) return null;
 var c=ND.caixa, Q=ND.geo.da_caixa;
 var lo=[c[0],c[2],c[4]], hi=[c[1],c[3],c[5]];
 var cantos=ndCantos(c), centro=ndM4(Q, [(lo[0]+hi[0])/2, (lo[1]+hi[1])/2, (lo[2]+hi[2])/2]);
 var e=[0,1,2].map(function(a){ return [Q[a], Q[4+a], Q[8+a]] });
 var d=[0,1,2].map(function(a){ return nd3Vezes(e[a], hi[a]-lo[a]) });
 var diag=nd3Soma(nd3Soma(d[0], d[1]), d[2]);
 var raio=Math.sqrt(nd3Pe(diag, diag))/2;
 var o=ndM4(Q, lo);
 var Mcaixa=r3gM4base(d[0], d[1], d[2], o);
 var mm=[Math.sqrt(nd3Pe(d[2],d[2])), Math.sqrt(nd3Pe(d[1],d[1])), Math.sqrt(nd3Pe(d[0],d[0]))];
 return {centro:centro, raio:Math.max(raio, 5), cantos:cantos, lo:lo, hi:hi, M:Mcaixa,
         para:r3gColunas(ND.geo.para_caixa), mm:mm};
}
function nd3Canto(){
 var e=ndEl('nd_cant'); if(!e) return;
 var h='';
 if(!ND3.gl){
  h='<b data-radai-frase>sem WebGL</b><br><span data-radai-frase>'+ndEsc(ND3.motivo||'o navegador não criou um contexto WebGL')+'</span>';
 } else if(ND3.emSala){
  h='<b data-radai-frase>Sala</b> · <span translate="no">'+ndAng(ND.ver.lao,'LAO','RAO')+' · '+ndAng(ND.ver.cra,'CRA','CAU')
   +'</span><br><span data-radai-frase>ilustrativa: projeção paralela, sem colisão</span>';
 } else {
  var cx=nd3Caixa();
  if(!ND.aberta) h='';
  else if(!cx) h='<span data-radai-frase>ligue a caixa de recorte e aperte-a em volta do ninho para ver o 3D do que fica dentro dela</span>';
  else {
   h='<b data-radai-frase>'+(ND3.detector?'Vista do detector':'Vista livre')+'</b> · <span translate="no">'
    +ndAng(ND.ver.lao,'LAO','RAO')+' · '+ndAng(ND.ver.cra,'CRA','CAU')+'</span>'
    +'<br><span translate="no">'+cx.mm.map(function(v){ return Math.round(v) }).join(' × ')+' mm</span>';
   var mot=[];
   if(ND3.motivoMalha) mot.push(ND3.motivoMalha);
   ['vaso','osso','pele'].forEach(function(q){ var x=ND3.info[q];
    if(x && x.motivo && mot.indexOf(x.motivo)<0) mot.push(x.motivo) });
   mot.slice(0,2).forEach(function(m){ h+='<br><span data-radai-frase>'+ndEsc(m)+'</span>' });
  }
 }
 e.innerHTML=h;
 var d=ndEl('nd_dica3d');
 if(d) ndTexto(d, (!ND3.gl || ND3.emSala || !ND.aberta || !nd3Caixa()) ? ''
  : (ND3.detector ? 'arrastar gira a incidência' : 'arrastar gira só o 3D'));
 if(window.radaiRetraduzir) window.radaiRetraduzir();
}
function nd3Pintar(){
 ND3.pedido=false;
 var gl=ND3.gl, c=ND3.canvas; if(!gl || !c) return;
 r3gAjustar(c);
 var w=c.width, h=c.height, L=ND3.loc;
 gl.viewport(0, 0, w, h); gl.clearColor(0, 0, 0, 1);
 gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
 gl.useProgram(ND3.prog);
 gl.enableVertexAttribArray(L.aPos); gl.enableVertexAttribArray(L.aNrm);
 gl.enable(gl.DEPTH_TEST); gl.depthFunc(gl.LEQUAL); gl.depthMask(true);
 gl.disable(gl.BLEND); gl.disable(gl.CULL_FACE);
 if(ND3.emSala) nd3PintarSala(w, h); else nd3PintarCaixa(w, h);
}
function nd3Desenhar(o, MVP, N9, alfa, liso){
 if(!o) return;
 r3gCamera(ND3, MVP, N9); r3gLiso(ND3, !!liso);
 if(alfa>=0.995){ ND3.gl.disable(ND3.gl.BLEND); r3gUmEm(ND3, o, 1) }
 else { r3gTranslucidoEm(ND3, o, alfa) }
}
function nd3PintarCaixa(w, h){
 var gl=ND3.gl, cx=nd3Caixa(), etqs=[];
 if(!cx){ ndEixosSvg(ndEl('nd_eixos3d'), null); nd3Rotular([], null, w, h); nd3Canto(); return }
 var b=ND3.detector ? radaiIncidencia(ND.ver.lao, ND.ver.cra) : radaiIncidencia(ND3.livre.a, ND3.livre.b);
 var M9=[b.r[0],b.r[1],b.r[2], b.u[0],b.u[1],b.u[2], b.d[0],b.d[1],b.d[2]];
 var asp=w/h, meia=cx.raio*1.7;
 if(ND3.detector){ var xs=cx.cantos.map(function(p){ return nd3Pe(p, b.r) }), ys=cx.cantos.map(function(p){ return nd3Pe(p, b.u) });
  meia=Math.max(Math.max.apply(null,xs)-Math.min.apply(null,xs), Math.max.apply(null,ys)-Math.min.apply(null,ys))/2*1.08 }
 meia=Math.max(meia, 6);
 var VP=r3gOrto(M9, cx.centro, 1/(meia*Math.max(1,asp)), 1/(meia*Math.max(1,1/asp)), 0, 0, 1/(cx.raio*4));
 var N9=r3gNrmDe(M9);
 r3gCorte(ND3, cx.para, cx.lo, cx.hi);
 nd3Desenhar(ND3.objs.vaso, VP, N9, 1, false);
 nd3Desenhar(ND3.objs.osso, VP, N9, ND3.atraves?0.1:0.5, false);
 nd3Desenhar(ND3.objs.pele, VP, N9, ND3.atraves?0.03:0.14, false);
 r3gCorte(ND3, null);
 gl.disable(gl.DEPTH_TEST); gl.enable(gl.BLEND); gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
 r3gCamera(ND3, r3gM4mul(VP, cx.M), N9); r3gLiso(ND3, true); r3gUmEm(ND3, ND3.aux.arame, 0.85);
 if(!ND3.detector){
  var placa=function(g, cor, alfa, nome){
   var bb=radaiIncidencia(g.lao, g.cra), dist=cx.raio*1.25, s=cx.raio*0.42;
   var c=nd3Soma(cx.centro, nd3Vezes(bb.d, dist)), Mp=r3gM4base(nd3Vezes(bb.r,s), nd3Vezes(bb.u,s), bb.d, c);
   ND3.aux.placa.cor=cor; ND3.aux.contorno.cor=cor; ND3.aux.segmento.cor=cor;
   r3gCamera(ND3, r3gM4mul(VP, Mp), N9); r3gUmEm(ND3, ND3.aux.placa, alfa*0.28); r3gUmEm(ND3, ND3.aux.contorno, alfa);
   var ini=nd3Soma(cx.centro, nd3Vezes(bb.d, -dist));
   r3gCamera(ND3, r3gM4mul(VP, r3gM4base([0,0,0],[0,0,0], nd3Menos(c, ini), ini)), N9);
   r3gUmEm(ND3, ND3.aux.segmento, alfa*0.55);
   if(nome) etqs.push({p:nd3Soma(c, nd3Vezes(bb.u, s*1.25)), t:nome, forte:alfa>0.9});
  };
  ND.guardadas.forEach(function(g, i){ placa(g, ND_IMG_CORES[i%ND_CORES], 0.8, String(i+1)) });
  placa({lao:ND.ver.lao, cra:ND.ver.cra}, ND3_COR.placa, 1, 'detector');
 }
 gl.enable(gl.DEPTH_TEST); gl.disable(gl.BLEND);
 nd3Canto();
 nd3Rotular(etqs, VP, w, h);
 ndEixosSvg(ndEl('nd_eixos3d'), {L:[b.r[0], -b.u[0], b.v[0]], P:[b.r[1], -b.u[1], b.v[1]], S:[b.r[2], -b.u[2], b.v[2]]});
}
function nd3Pose(lao, cra){
 var a=lao*Math.PI/180, b=cra*Math.PI/180, e1=[Math.sin(a),-Math.cos(a),0], nn=[Math.cos(a),Math.sin(a),0], e2=[0,0,1];
 var X=nd3Soma(nd3Vezes(e1,Math.cos(b)), nd3Vezes(e2,Math.sin(b))), Z=nd3Soma(nd3Vezes(e1,-Math.sin(b)), nd3Vezes(e2,Math.cos(b)));
 return {M:r3gM4base(X,nn,Z,[0,0,0]), Mc:r3gM4base(e1,nn,e2,[0,0,0])};
}
function nd3PintarSala(w, h){
 var gl=ND3.gl, S=ND3.sala, cam=ND3.cam, alvo=[0,80,260], up=[0,-1,0];
 var yaw=cam.yaw*Math.PI/180, pit=cam.pitch*Math.PI/180;
 var dir=[Math.cos(pit)*Math.sin(yaw), -Math.sin(pit), Math.cos(pit)*Math.cos(yaw)], olho=nd3Soma(alvo, nd3Vezes(dir, cam.dist));
 var f=nd3Norm(nd3Menos(alvo, olho)), r=nd3Norm(nd3Cruz(f, up)), u=nd3Cruz(r, f);
 var V=r3gVista(r, u, f, olho), P=r3gPersp(34*Math.PI/180, w/h, 100, 12000), PV=r3gM4mul(P, V);
 var I=r3gM4base([1,0,0],[0,1,0],[0,0,1],[0,0,0]);
 function um(o, M, cor, alfa, liso){ if(!o) return; if(cor) o.cor=cor;
  nd3Desenhar(o, r3gM4mul(PV, M), r3gNrmV(r3gM4mul(V, M)), alfa, liso) }
 r3gCorte(ND3, null);
 um(S.piso, I, ND3_COR.piso, 1, true); um(S.mesa, I, ND3_COR.mesa, 1, false);
 um(S.paciente, I, ND3_COR.sala, 1, false);
 var pose=nd3Pose(ND.ver.lao, ND.ver.cra);
 um(S.coluna, I, ND3_COR.mesa, 1, false); um(S.carro, pose.Mc, ND3_COR.arco, 1, false);
 um(S.arco, pose.M, ND3_COR.arco, 1, false); um(S.detector, pose.M, ND3_COR.placa, 1, false);
 um(S.tubo, pose.M, ND3_COR.arco, 1, false);
 var cx=nd3Caixa();
 if(cx){ var g0=ND.geo.centro, Mt=r3gM4base([1,0,0],[0,1,0],[0,0,1],[-g0[0],-g0[1],-g0[2]]);
  gl.disable(gl.DEPTH_TEST); gl.enable(gl.BLEND); gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
  ND3.aux.arame.cor=ND3_COR.arame; r3gCamera(ND3, r3gM4mul(PV, r3gM4mul(Mt, cx.M)), r3gNrmV(V)); r3gLiso(ND3, true);
  r3gUmEm(ND3, ND3.aux.arame, 0.95);
  gl.enable(gl.DEPTH_TEST); gl.disable(gl.BLEND) }
 ND.guardadas.forEach(function(g, i){ var pg=nd3Pose(g.lao, g.cra); um(S.detectorF, pg.M, ND_IMG_CORES[i%ND_CORES], 0.5, false) });
 um(S.feixe, pose.M, ND3_COR.feixe, 0.10, false);
 var b=radaiIncidencia(ND.ver.lao, ND.ver.cra), etqs=[{p:nd3Vezes(b.d,470+230), t:'detector', forte:true},
  {p:nd3Vezes(b.d,-640-150), t:'tubo'}];
 ND.guardadas.forEach(function(g, i){ var bg=radaiIncidencia(g.lao, g.cra); etqs.push({p:nd3Vezes(bg.d,470+60), t:String(i+1)}) });
 nd3Canto();
 nd3Rotular(etqs, PV, w, h);
 ndEixosSvg(ndEl('nd_eixos3d'), {L:[r[0], -u[0], f[0]], P:[r[1], -u[1], f[1]], S:[r[2], -u[2], f[2]]});
}
// GUARDA: rótulo da cena nunca cobre a leitura do canto, os eixos, a dica nem outro rótulo; o fraco que não acha lugar sai.
function nd3Rotular(etqs, PV, w, h){
 var alvo=ndEl('nd_etqs'), palco=ndEl('nd_palco3d'); if(!alvo || !palco) return;
 var cv=ND3.canvas, W=cv?cv.clientWidth:0, H=cv?cv.clientHeight:0, html='';
 (etqs||[]).forEach(function(e){ if(!PV) return; var p=e.p;
  var x=PV[0]*p[0]+PV[4]*p[1]+PV[8]*p[2]+PV[12], y=PV[1]*p[0]+PV[5]*p[1]+PV[9]*p[2]+PV[13], ww=PV[3]*p[0]+PV[7]*p[1]+PV[11]*p[2]+PV[15];
  if(ww<=0) return; x/=ww; y/=ww; if(x<-1.1 || x>1.1 || y<-1.1 || y>1.1) return;
  html+='<span class="nd-etq'+(e.forte?' forte':'')+'" style="left:'+((x*0.5+0.5)*W).toFixed(0)+'px;top:'+((0.5-y*0.5)*H).toFixed(0)
   +'px"'+(/^[0-9]+$/.test(e.t)?' translate="no"':' data-radai-frase')+'>'+e.t+'</span>' });
 alvo.innerHTML=html;
 if(!alvo.children || !palco.getBoundingClientRect) return;
 var pr=palco.getBoundingClientRect(), ocupado=[];
 ['nd_cant','nd_eixos3d','nd_dica3d'].forEach(function(id){ var el=ndEl(id); if(!el || !el.getBoundingClientRect) return;
  var r=el.getBoundingClientRect(); if(r.width>0 && r.height>0) ocupado.push(r) });
 function bate(r){ return ocupado.some(function(o){ return r.left<o.right && o.left<r.right && r.top<o.bottom && o.top<r.bottom }) }
 var lista=[].slice.call(alvo.children).sort(function(a,b){ return b.classList.contains('forte')-a.classList.contains('forte') });
 lista.forEach(function(s){ var y0=parseFloat(s.style.top), passo=s.offsetHeight+2, r=null;
  for(var k=0;k<7;k++){ s.style.top=(y0+(k%2?1:-1)*Math.ceil(k/2)*passo)+'px'; r=s.getBoundingClientRect();
   if(r.top>=pr.top && r.bottom<=pr.bottom && !bate(r)) break; r=null }
  if(r){ ocupado.push(r); return }
  if(s.classList.contains('forte')){ s.style.top=y0+'px'; ocupado.push(s.getBoundingClientRect()) }
  else if(s.parentNode) s.parentNode.removeChild(s) });
}
// GUARDA: no 3D o arraste segue o objeto, como o n3Girar das Reconstruções (direita = RAO, para baixo = CRA); na sala ele move o arco, como o mapa (direita = LAO, para cima = CRA).
function nd3AnguloDoArrasto(A, dx, dy, sala){
 if(sala) return [A.lao+dx*0.45, A.cra-dy*0.35];
 return [A.lao-dx*0.5, A.cra+dy*0.4];
}
function nd3Ligar(c){
 c.addEventListener('pointerdown', function(ev){ if(ev.button!==0 || !ND.aberta) return;
  try{ c.setPointerCapture(ev.pointerId) }catch(e){}
  ND3.arr={x:ev.clientX, y:ev.clientY, lao:ND.ver.lao, cra:ND.ver.cra, a:ND3.livre.a, b:ND3.livre.b,
   yaw:ND3.cam.yaw, pit:ND3.cam.pitch, orbita:!!ev.shiftKey, girou:false} });
 c.addEventListener('pointermove', function(ev){ var A=ND3.arr; if(!A) return;
  var dx=ev.clientX-A.x, dy=ev.clientY-A.y;
  var ang;
  if(ND3.emSala){
   if(A.orbita){ ND3.cam.yaw=A.yaw-dx*0.35; ND3.cam.pitch=Math.max(4, Math.min(80, A.pit+dy*0.25)); nd3Pedir() }
   else { A.girou=true; ang=nd3AnguloDoArrasto(A, dx, dy, true); ndPreverAng(ang[0], ang[1]) }
  } else if(ND3.detector){ A.girou=true; ang=nd3AnguloDoArrasto(A, dx, dy, false); ndPreverAng(ang[0], ang[1]) }
  else { ND3.livre.a=A.a-dx*0.5; ND3.livre.b=Math.max(-89, Math.min(89, A.b+dy*0.4)); nd3Pedir() } });
 function solta(){ var A=ND3.arr; ND3.arr=null; if(A && A.girou) ndSoltarAngulo() }
 c.addEventListener('pointerup', solta);
 c.addEventListener('pointercancel', solta);
 c.addEventListener('wheel', function(ev){ if(!ND3.emSala) return; if(ev.preventDefault) ev.preventDefault();
  ND3.cam.dist=Math.max(1600, Math.min(6500, ND3.cam.dist*(ev.deltaY<0?0.9:1.1))); nd3Pedir() }, {passive:false});
}
function nd3Vista(valor){
 ND3.emSala=(valor==='sala');
 var a=ndEl('nd_ctl_3d'), s=ndEl('nd_ctl_sala'), t=ndEl('nd_3d_t');
 if(a) a.hidden=ND3.emSala; if(s) s.hidden=!ND3.emSala;
 if(t) ndTexto(t, ND3.emSala?'Sala':'3D da caixa');
 nd3Canto(); nd3Pedir();
}
function nd3Detector(){
 ND3.detector=!ND3.detector;
 if(!ND3.detector) ND3.livre={a:ND.ver.lao-40, b:Math.max(-80, Math.min(80, ND.ver.cra+22))};
 var b=ndEl('nd_detector'); if(b) b.setAttribute('aria-pressed', ND3.detector?'true':'false');
 nd3Canto(); nd3Pedir();
}
function nd3Atraves(){
 ND3.atraves=!ND3.atraves;
 var b=ndEl('nd_atraves'); if(b) b.setAttribute('aria-pressed', ND3.atraves?'true':'false');
 nd3Pedir();
}
function nd3SalaPadrao(){ ND3.cam={yaw:120, pitch:16, dist:3050}; nd3Pedir() }

function ndMaximizar(eixo){
 if(eixo!==null && (!ND.sessao || ND.cruzando || ND.consensoBusy)) return;
 var host=ndEl('nd_mpr_main'), box=ndEl('nd_proj_cx'); if(!host || !box) return;
 if(ND.principal!==null){
  var old=ndEl('nd_pane'+ND.principal), home=ndEl('nd_home'+ND.principal);
  if(old && home) home.parentNode.insertBefore(old, home);
 }
 ND.principal=eixo;
 if(eixo!==null){ var pane=ndEl('nd_pane'+eixo); if(pane) host.appendChild(pane) }
 host.hidden=eixo===null; box.classList.toggle('nd-mpr-principal', eixo!==null);
 var title=ndEl('nd_principal_t'); if(title) ndTexto(title, eixo===null?'projeção':['axial','coronal','sagital'][eixo]);
 var rotation=ndEl('nd_rot_proj'); if(rotation) rotation.hidden=eixo!==null;
 var state=ndEl('nd_estado'); if(state) state.hidden=eixo!==null;
 var back=ndEl('nd_layout_original'); if(back) back.hidden=eixo===null;
 ndAjustarTela(); nd3Pedir();
}
function ndConsControles(){
 var ready=!!ND.sessao && !ND.cruzando && !ND.consensoBusy;
 ['nd_cons_editar','nd_cons_exportar'].forEach(function(id){ var e=ndEl(id); if(e) e.disabled=!ready });
 [0,1,2].forEach(function(axis){
  var b=ndEl('nd_max'+axis); if(b) b.disabled=!ready;
  var pane=ndEl('nd_pp'+axis); if(pane) pane.classList.toggle('nd-editavel', !!(ready && ND.consensoEditavel));
 });
 var slider=ndEl('nd_temperatura'); if(slider) slider.disabled=!ready || ND.consensoEditavel;
 var temperature=ndEl('nd_temperatura_v'); if(temperature) temperature.textContent=String(ND.temperatura);
 ['nd_cons_add','nd_cons_remove','nd_cons_undo','nd_cons_temperatura'].forEach(function(id){
  var button=ndEl(id); if(button){ button.hidden=!ND.consensoEditavel; button.disabled=!ready } });
 var add=ndEl('nd_cons_add'), remove=ndEl('nd_cons_remove');
 if(add) add.setAttribute('aria-pressed', ND.consOperacao==='add'?'true':'false');
 if(remove) remove.setAttribute('aria-pressed', ND.consOperacao==='remove'?'true':'false');
 var exp=ndEl('nd_cons_exportar'); if(exp) ndTexto(exp, ND.consensoEditavel?'Exportar contorno editado':'Exportar sugestão');
 if(!ND.sessao && ND.principal!==null) ndMaximizar(null);
}
function ndTemperatura(value){
 if(ND.consensoEditavel || ND.consensoBusy) return;
 ND.temperatura=Math.max(0,Math.min(100,+value||0)); ndConsControles();
 ndConsVazio(false);ndRegistrar('temperatura');
 clearTimeout(ND.consTimer); ND.consTimer=setTimeout(function(){[0,1,2].forEach(ndLinhas)},150);
}
function ndConsVazio(empty){var e=ndEl('nd_cons_vazio');if(e)e.hidden=!empty}
async function ndConsPost(path, payload){
 var response=await fetch('/neuro/api/status',{cache:'no-store'});
 if(!response.ok) throw Error('A sessão da suíte não está disponível.');
 var status=await response.json();
 var result=await fetch('/api/nidus/consenso'+path,{method:'POST',
  headers:{'Content-Type':'application/json','X-Neuro-Token':status.token},body:JSON.stringify(payload)});
 var data=await result.json();
 if(!result.ok) throw Error(data.detail||'Não foi possível concluir o consenso.');
 return data;
}
async function ndEditarConsenso(){
 if(!ND.sessao || ND.consensoBusy) return;
 var session=ND.sessao; ND.consensoBusy=true; ndConsControles();
 ndMsg('preparando o contorno na fila da suíte…','');
 try{
  var candidate=await ndConsPost('',{s:session,temperatura:ND.temperatura});
  if(session!==ND.sessao) return;
  ND.consensoEditavel=true;
  ndConsVazio(candidate.empty===true);
  ndMsg('sugestão pronta para editar: desenhe no axial, coronal ou sagital; o contorno continua não aprovado','ok');
  [0,1,2].forEach(ndLinhas);
 }catch(error){if(session===ND.sessao) ndMsg(String(error.message||error),'erro')}
 finally{ND.consensoBusy=false;ndConsControles()}
}
function ndConsOperacao(operation){ND.consOperacao=operation;ndConsControles()}
function ndVoltarTemperatura(){
 if(ND.consensoBusy) return;
 ND.consensoEditavel=false;ndConsControles();[0,1,2].forEach(ndLinhas);
 ndMsg('o contorno editado foi conservado; preparar outra sugestão cria uma nova revisão','');
}
async function ndConsDesfazer(){
 if(!ND.consensoEditavel || ND.consensoBusy) return;
 ND.consensoBusy=true;ndConsControles();
 try{await ndConsPost('/desfazer',{s:ND.sessao});[0,1,2].forEach(ndLinhas)}
 catch(error){ndMsg(String(error.message||error),'erro')}
 finally{ND.consensoBusy=false;ndConsControles()}
}
async function ndExportarConsenso(){
 if(!ND.sessao || ND.consensoBusy) return;
 var session=ND.sessao;ND.consensoBusy=true;ndConsControles();ndMsg('gravando RTSTRUCT na fila da suíte…','');
 try{
  var data=await ndConsPost('/exportar',{s:session,temperatura:ND.temperatura,editado:!!ND.consensoEditavel});
  if(session!==ND.sessao) return;
  var link=document.createElement('a');link.href=data.url;link.download='RS_Nidus_Sugestao.dcm';
  document.body.appendChild(link);link.click();link.remove();
  ndMsg('RTSTRUCT de sugestão não aprovada conferido na referência original','ok');
 }catch(error){if(session===ND.sessao)ndMsg(String(error.message||error),'erro')}
 finally{ND.consensoBusy=false;ndConsControles()}
}
function ndEditPoint(svg,event){
 var point=svg.createSVGPoint();point.x=event.clientX;point.y=event.clientY;
 point=point.matrixTransform(svg.getScreenCTM().inverse());var vb=svg.viewBox.baseVal;
 return [Math.max(0,Math.min(1,point.x/vb.width)),Math.max(0,Math.min(1,point.y/vb.height))];
}
function ndEditPaint(trace){
 var svg=ndEl('nd_ed'+trace.axis), vb=svg.viewBox.baseVal;
 var points=trace.points.map(function(p){return (p[0]*vb.width)+','+(p[1]*vb.height)}).join(' ');
 svg.innerHTML='<rect width="100%" height="100%" fill="transparent"/><polyline class="nd-edit-trace" points="'+points+'"/>';
}
function ndEditStart(axis,event){
 if(!ND.consensoEditavel || ND.consensoBusy || event.button!==0 || !ND.forma) return;
 var index=Math.round(ND.planos[axis]*(ND.forma[axis]-1));
 if(ND.consIndices[axis]!==index) return;
 var svg=ndEl('nd_ed'+axis);event.preventDefault();
 if(svg.setPointerCapture)svg.setPointerCapture(event.pointerId);
 ND.consTrace={axis:axis,index:index,points:[ndEditPoint(svg,event)],session:ND.sessao};ndEditPaint(ND.consTrace);
}
function ndEditMove(axis,event){
 var trace=ND.consTrace;if(!trace || trace.axis!==axis || trace.points.length>=120)return;
 var point=ndEditPoint(ndEl('nd_ed'+axis),event),last=trace.points[trace.points.length-1];
 if(Math.hypot(point[0]-last[0],point[1]-last[1])>.005){trace.points.push(point);ndEditPaint(trace)}
}
async function ndEditEnd(axis,event){
 var trace=ND.consTrace;if(!trace || trace.axis!==axis)return;ND.consTrace=null;
 var svg=ndEl('nd_ed'+axis);svg.innerHTML='<rect width="100%" height="100%" fill="transparent"/>';
 if(trace.points.length<3 || trace.session!==ND.sessao)return;
 ND.consensoBusy=true;ndConsControles();
 try{await ndConsPost('/editar',{s:trace.session,eixo:axis,indice:trace.index,pontos:trace.points,operacao:ND.consOperacao});
  if(trace.session===ND.sessao)[0,1,2].forEach(ndLinhas)}
 catch(error){ndMsg(String(error.message||error),'erro')}
 finally{ND.consensoBusy=false;ndConsControles()}
}

// GUARDA: o visor quadrado e os três MPR cabem na altura que sobra, sem rolar a 1280 × 800.
function ndAjustarTela(){
 var t=ndEl('nd_trabalho');
 if(!t || !t.style || !t.style.setProperty || !t.getBoundingClientRect) return;
 var H=+window.innerHeight||0, W=+window.innerWidth||0;
 if(!H || !W) return;
 var rt=t.getBoundingClientRect(), y=+window.scrollY||0;
 var al=document.querySelector ? document.querySelector('.nd-wrap > .ui-alerta') : null;
 var pe=(al && al.getBoundingClientRect) ? al.getBoundingClientRect().height+10 : 40;
 var alto=Math.floor(H-(rt.top+y)-pe-6);
 if(W<1100){
  if(t.style.removeProperty) t.style.removeProperty('height');
  t.style.setProperty('--nd-q', Math.max(260, Math.min(W-90, 560))+'px');
  t.style.setProperty('--nd-p', Math.max(110, Math.floor((W-140)/3))+'px');
  ndPadAjustar(); nd3Pedir(); return;
 }
 alto=Math.max(360, alto);
 t.style.setProperty('height', alto+'px');
 var q=Math.floor(Math.max(240, Math.min(alto-89, rt.width*0.47)));
 t.style.setProperty('--nd-q', q+'px');
 var cb=ndEl('nd_colB'), bw=(cb && cb.getBoundingClientRect) ? cb.getBoundingClientRect().width : 400;
 // GUARDA: o 3D e o mapa pedem ~210 px de altura; o MPR cede antes deles nas telas baixas.
 var lado=function(a){ return Math.floor(Math.max(96, Math.min((bw-18-16-100)/3, a*0.33, a-305))) };
 var p=lado(alto);
 t.style.setProperty('--nd-p', p+'px');
 var de=document.documentElement, sobra=(de && de.scrollHeight) ? (de.scrollHeight-H) : 0;
 if(sobra>0){ alto=Math.max(360, alto-sobra-1); t.style.setProperty('height', alto+'px');
  q=Math.floor(Math.max(240, Math.min(alto-89, rt.width*0.47))); t.style.setProperty('--nd-q', q+'px');
  p=lado(alto); t.style.setProperty('--nd-p', p+'px') }
 ndPadAjustar(); nd3Pedir();
 if(ND.principal===null){ndZoomPrender();ndZoomAplicar();ndEnquadrar()}
}

window.addEventListener('DOMContentLoaded', function(){
 var pb=ndEl('nd_procurar'); if(pb) pb.addEventListener('click', ndProcurar);
 var pt=ndEl('nd_pasta');
 if(pt) pt.addEventListener('keydown', function(ev){
  if(ev.key==='Enter'){ if(ev.preventDefault) ev.preventDefault(); ndOutra() } });
 var pa=ndEl('nd_palco');
 if(pa){
  pa.addEventListener('wheel', ndRoda, {passive:false});
  pa.addEventListener('mousedown', ndPegar);
  pa.addEventListener('mousemove', ndMoverPalco);
  pa.addEventListener('mouseup', ndLargar);
  pa.addEventListener('mouseleave', ndLargar);
 }
 [0,1,2].forEach(function(eixo){
  var cx=ndEl('nd_cx'+eixo); if(!cx) return;
  cx.addEventListener('mousedown', function(ev){ ndCaixaPegar(eixo, ev) });
  cx.addEventListener('mousemove', function(ev){ ndCaixaCursor(eixo, ev) });
 });
 window.addEventListener('mousemove', ndCaixaMover);
 window.addEventListener('mouseup', ndCaixaSoltar);
 window.addEventListener('resize', function(){ clearTimeout(ND_PAD.rz); ND_PAD.rz=setTimeout(ndAjustarTela, 120) });
 var svg=ndEl('nd_svg');
 svg.addEventListener('mousedown', ndPressionar);
 svg.addEventListener('mousemove', ndArrastar);
 svg.addEventListener('mouseup', ndSoltar);
 svg.addEventListener('mouseleave', ndSoltar);
 ndGradeDoDesenho();
 ['lao','cra'].forEach(function(k){
  var r=ndEl('nd_'+k+'_r'), e=ndEl('nd_'+k);
  if(r){
   r.addEventListener('input', function(){ ndPrever(k, +r.value||0) });
   r.addEventListener('change', function(){ ndMudarAngulo(k, +r.value||0) });
   r.addEventListener('keydown', function(ev){
    if(ev.key!=='PageUp' && ev.key!=='PageDown') return;
    if(ev.preventDefault) ev.preventDefault();
    var v=Math.max(+r.min, Math.min(+r.max, (+r.value||0)+(ev.key==='PageUp'?10:-10)));
    r.value=String(v); ndPrever(k, v); ndMudarAngulo(k, v) });
  }
  if(e){
   var aplicar=function(){ var v=parseFloat(String(e.value).replace(',','.'));
    if(isNaN(v)){ e.value=String(ND[k]); return } ndMudarAngulo(k, v) };
   e.addEventListener('change', aplicar);
   e.addEventListener('keydown', function(ev){ if(ev.key==='Enter') aplicar() });
  }
 });
 var l=ndEl('nd_laje');
 if(l){
  l.addEventListener('input', function(){
   var v=+l.value||0, lv=ndEl('nd_lajev');
   if(lv) lv.textContent=v?(v+' mm'):'todo o volume' });
  l.addEventListener('change', function(){
   if(!ND.aberta) return;
   ND.laje=+l.value||0; ndSincronizar(); ndRegistrar('laje'); ndProjetar() });
 }
 [0,1,2].forEach(function(eixo){
  var s=ndEl('nd_pos'+eixo);
  if(s) s.addEventListener('input', function(){
   ND.planos[eixo]=+s.value/100; ndCorte(eixo, false) });
  var edit=ndEl('nd_ed'+eixo);
  if(edit){edit.addEventListener('pointerdown',function(e){ndEditStart(eixo,e)});
   edit.addEventListener('pointermove',function(e){ndEditMove(eixo,e)});
   edit.addEventListener('pointerup',function(e){ndEditEnd(eixo,e)})}
 });
 var ls=ndEl('nd_series');
 if(ls) ls.addEventListener('click', function(ev){
  var b=(ev.target && ev.target.closest) ? ev.target.closest('.nd-it') : null;
  if(b) ndEscolher(b.getAttribute('data-b')) });
 var inc=ndEl('nd_incid');
 if(inc){
  inc.addEventListener('mouseover', function(ev){
   var b=(ev.target && ev.target.closest) ? ev.target.closest('.nd-bt') : null;
   ND_PAD.quente=b?[+b.getAttribute('data-lao'), +b.getAttribute('data-cra')]:null; ndPintarPad() });
  inc.addEventListener('mouseleave', function(){ ND_PAD.quente=null; ndPintarPad() });
 }
 var vs=ndEl('nd_vista');
 if(vs) vs.addEventListener('change', function(){ nd3Vista(vs.value) });
 window.addEventListener('keydown', function(ev){
  if(ev.key==='Escape' && !ND.tracando && ND.pontos.length){ ND.pontos=[]; ndPintarMarca(); ndAtualizarGuardar() } });
 ndLigarPad();
 nd3Iniciar();
 ndSincronizar(); ndTravas(); ndPintarGuardadas(); ndAjustarTela();
 ndAbrirEscolha();
});
"""

JS = (radai_recon3d_gl.JS + radai_nidus.JS_CONVENCAO
      + JS_TELA.replace(u"@LADO@", str(LADO_DA_TELA))
      .replace(u"@MODALIDADES@", json.dumps(list(MODALIDADES)))
      .replace(u"@MIN_CORTES@", str(int(MIN_CORTES)))
      .replace(u"@INCIDENCIAS_JS@", json.dumps(
          [[n, int(a), int(b)] for n, a, b in radai_nidus.INCIDENCIAS],
          ensure_ascii=False))
      .replace(u"@LADO_PREVIA@", str(LADO_DA_PREVIA)))

AJUDA_PROJECAO_PARALELA = (
    u"A projeção é paralela, sem ampliação. A sala mostra a posição do arco "
    u"para quem estuda, sem distância fonte–detector e sem colisão.")

AJUDA_CONVENCAO = (
    u"Convenção dos ângulos: a do arco em C (DICOM). LAO põe o detector do lado "
    u"esquerdo do paciente; CRA o inclina para a cabeça.")

AJUDA_PREVIA = (
    u"Enquanto um ângulo é arrastado, chega uma prévia em baixa resolução; o "
    u"lápis espera a projeção cheia.")

AJUDA_3D = (
    u"O 3D da caixa mostra o que está dentro dela: o vaso por limiar (sem o "
    u"osso da segmentação do ContourLab), o osso dessa segmentação e a pele. "
    u"Ele pode mostrar o rosto: fica nesta máquina e não se exporta. A "
    u"interseção não aparece no 3D.")


AJUDA_LINHAS = (
    u"A cor de cada linha diz de qual incidência ela veio. A linha mais forte "
    u"é onde todas se cruzam. A linha verde é uma sugestão geométrica: "
    u"temperatura 0 usa a união estrelada, e 100 usa a interseção total. "
    u"Os ajustes intermediários reduzem a máscara por distâncias no plano "
    u"das projeções, sem indicar probabilidade ou precisão clínica. "
    u"Após gravar as incidências, cada MPR pode ocupar o visor principal. "
    u"A sugestão pode ser editada por plano e exportada em RTSTRUCT não "
    u"aprovado, na referência original, para revisão do usuário no TPS.")


def _cabeca():
    import radai_ui
    ajuda = radai_ui.ajuda(
        u"<b>O que esta tela &eacute;, e o que ela n&atilde;o &eacute;.</b>",
        radai_nidus.SEM_VOLUME, radai_nidus.LIMITACAO_CLINICA,
        radai_nidus.LIMITACAO_RM, AJUDA_PROJECAO_PARALELA, AJUDA_CONVENCAO,
        AJUDA_PREVIA, AJUDA_3D, AJUDA_LINHAS)
    return radai_ui.cabeca_de_funcao(
        u"cruzamento", u"Projeção Vascular",
        u"a mesma lesão em duas incidências, e onde as duas se cruzam",
        ajuda, u"nidus")


def _alerta():
    import radai_modules
    import radai_ui
    return radai_ui.alerta(radai_modules.MODULOS["nidus"]["linha"])


def _icones(p, nomes):
    import radai_ui
    for n in nomes:
        p = p.replace(u"@ICO_%s@" % n.upper(), radai_ui.icone(n))
    return p


def _vista():
    import radai_ui
    return radai_ui.segmentado(u"nd_vista", ((u"3d", u"3D da caixa"),
                                             (u"sala", u"Sala")),
                               valor=u"3d", rotulo=u"o que o visor menor mostra")


def _escala():
    return u"".join(
        u'<span style="left:%s%%" translate="no">%s</span>'
        % (u"%.4g" % ((a + 180) / 360.0 * 100), t)
        for a, t in ((-180, u"PA"), (-90, u"RAO 90"), (0, u"AP"),
                     (90, u"LAO 90"), (180, u"PA")))


def pagina():
    return _icones(PAGINA.replace("@CSS@", CSS)
                   .replace("@ESCOLHA@", _escolha())
                   .replace("@CARTAO@", _cartao())
                   .replace("@JS@", JS)
                   .replace("@CABECA@", _cabeca())
                   .replace("@ALERTA@", _alerta())
                   .replace("@VISTA@", _vista())
                   .replace("@ESCALA@", _escala())
                   .replace("@INCIDENCIAS@", _incidencias()),
                   (u"pasta", u"zoom_mais", u"zoom_menos", u"inverter",
                    u"caixa", u"lapis", u"cubo", u"atraves", u"detector",
                    u"guardar"))


def _incidencias():
    return u"".join(
        u'<button type="button" class="nd-bt pre%s" data-nome="%s" data-lao="%s" '
        u'data-cra="%s" aria-pressed="%s" onclick="ndIncidencia(%s,%s,\'%s\')">'
        u'<span>%s</span><small translate="no">%s</small></button>'
        % (u" on" if i == 0 else u"", nome, int(lao), int(cra),
           u"true" if i == 0 else u"false", int(lao), int(cra), nome, nome,
           radai_nidus.rotulo_do_angulo(lao, cra))
        for i, (nome, lao, cra) in enumerate(radai_nidus.INCIDENCIAS))


PAGINA = u"""<!doctype html><html><head><meta charset="utf-8">
<title>Proje&ccedil;&atilde;o Vascular &middot; NEURO RT</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>@CSS@</style></head><body><div class="nd-wrap" id="nd_wrap">

<div class="nd-cabeca">
@CABECA@
 <div class="nd-serie" id="nd_serie_cx">@CARTAO@
  <button type="button" class="nd-bt" id="nd_bt_retomar" onclick="ndRetomar()" hidden
   data-radai-frase>Tentar de novo</button></div>
</div>

<section class="nd-ferramentas" id="nd_cmd" aria-label="ferramentas">
 <div class="nd-linha">
  <div class="nd-grupo">
   <span class="t" data-radai-frase>incid&ecirc;ncia</span>
   <div class="g" id="nd_incid">@INCIDENCIAS@</div>
  </div>
 </div>
 <div class="nd-linha">
  <div class="nd-grupo">
   <span class="t" data-radai-frase>proje&ccedil;&atilde;o</span>
   <div class="g" id="nd_m">
    <button type="button" class="nd-bt on" id="nd_m_mip" onclick="ndModo('mip')">MIP</button>
    <button type="button" class="nd-bt" id="nd_m_minip" onclick="ndModo('minip')">MinIP</button>
    <button type="button" class="nd-bt on" id="nd_inverter" onclick="ndInverter()"
     aria-pressed="true">@ICO_INVERTER@<span data-radai-frase>Inverter cores</span></button>
   </div>
  </div>
  <div class="nd-grupo nd-laje"><span class="t" data-radai-frase>laje</span>
   <input type="range" id="nd_laje" min="0" max="120" value="0"
    aria-label="espessura da laje">
   <span class="sub" id="nd_lajev" data-radai-frase>todo o volume</span></div>
  <div class="nd-grupo">
   <span class="t" data-radai-frase>janela</span>
   <div class="g" id="nd_jan">
    <button type="button" class="nd-bt on" data-j="angio" onclick="ndJanela('angio')">angio</button>
    <button type="button" class="nd-bt" data-j="vaso_fino" onclick="ndJanela('vaso_fino')"
     data-radai-frase>vaso fino</button>
    <button type="button" class="nd-bt" data-j="osso" onclick="ndJanela('osso')">osso</button>
    <button type="button" class="nd-bt" data-j="parenquima" onclick="ndJanela('parenquima')"
     data-radai-frase>par&ecirc;nquima</button></div>
  </div>
  <div class="nd-grupo nd-osso">
   <span class="t" data-radai-frase>osso</span>
   <button type="button" class="nd-bt" id="nd_osso_bt" onclick="ndOssoAlternar()" hidden
    aria-pressed="false" title="vaso colado ao osso pode sair junto com ele: confira com o osso &agrave; mostra">@ICO_CUBO@<span
    data-radai-frase>Tirar o osso</span></button>
   <button type="button" class="nd-bt" id="nd_segmentar" onclick="ndSegmentar()" hidden><span
    id="nd_segmentar_txt" data-radai-frase>Segmentar primeiro (AUTO)</span></button>
   <span class="sub" id="nd_osso_txt"></span>
  </div>
 </div>
</section>

<div id="nd_msg" role="status"></div>

<div class="nd-trabalho" id="nd_trabalho">

 <section class="nd-cx nd-colA" id="nd_proj_cx" aria-label="proje&ccedil;&atilde;o">
  <div class="nd-rot"><span id="nd_principal_t" data-radai-frase>proje&ccedil;&atilde;o</span>
   <b class="nd-leitura" id="nd_rot_proj" translate="no"><span id="nd_lao_v">LAO 0&deg;</span>
    &middot; <span id="nd_cra_v">CRA 0&deg;</span></b>
   <span class="dir"><button type="button" class="nd-bt" id="nd_layout_original" onclick="ndMaximizar(null)" hidden
    data-radai-frase>Layout original</button><span class="nd-estado" id="nd_estado" role="status"><i></i><span
    id="nd_estado_t" data-radai-frase>proje&ccedil;&atilde;o cheia</span></span></span></div>
  <div id="nd_mpr_main" hidden></div>
  <div class="nd-palco inv" id="nd_palco">
   <div class="nd-zoom" id="nd_zoom">
    <img id="nd_proj" alt="" draggable="false">
    <svg id="nd_svg" viewBox="0 0 1024 1024" preserveAspectRatio="xMidYMid meet"
     aria-label="arraste contornando o ninho &middot; soltar fecha a &aacute;rea &middot; Shift ou o bot&atilde;o do meio movem a imagem ampliada">
     <path id="nd_fora" class="nd-fora" d=""/>
     <polygon id="nd_pegada" class="nd-pegada" points=""/>
     <g id="nd_marca"></g>
    </svg>
   </div>
   <div class="nd-ferr-palco">
    <button type="button" class="nd-bt" id="nd_seguir" onclick="ndSeguirAlternar()"
     aria-pressed="true" title="o visor enquadra o que est&aacute; na caixa de recorte">@ICO_CAIXA@<span
     data-radai-frase>Acompanhar a caixa</span></button>
    <button type="button" class="nd-bt nd-ic" id="nd_zoom_menos" onclick="ndZoomPasso(-1)"
     title="Afastar" aria-label="Afastar">@ICO_ZOOM_MENOS@</button>
    <button type="button" class="nd-bt nd-ic" id="nd_zoom_mais" onclick="ndZoomPasso(1)"
     title="Aproximar" aria-label="Aproximar">@ICO_ZOOM_MAIS@</button>
    <button type="button" class="nd-bt" id="nd_zoom_ajustar" onclick="ndZoomAjustar()"
     data-radai-frase>Ajustar &agrave; tela</button>
   </div>
   <span class="nd-zoomv" id="nd_zoomv">100%</span>
   <svg class="nd-eixos" id="nd_eixos" viewBox="0 0 84 84" aria-hidden="true"></svg>
  </div>
  <div class="nd-barra-v">
   <span class="rotulo" translate="no">CRA</span>
   <div class="trilho"><input type="range" id="nd_cra_r" min="-90" max="90" step="1" value="0"
    aria-label="CRA/CAU"></div>
   <span class="rotulo" translate="no">CAU</span>
   <input type="text" class="nd-ang" id="nd_cra" value="0" inputmode="decimal"
    aria-label="CRA/CAU">
  </div>
  <div class="nd-barra-h">
   <span class="lado" translate="no">RAO</span>
   <div class="trilho">
    <input type="range" id="nd_lao_r" min="-180" max="180" step="1" value="0"
     aria-label="LAO/RAO">
    <div class="escala" aria-hidden="true">@ESCALA@</div>
   </div>
   <span class="fim"><span class="lado" translate="no">LAO</span><input type="text"
    class="nd-ang" id="nd_lao" value="0" inputmode="decimal" aria-label="LAO/RAO"></span>
  </div>
 </section>

 <div class="nd-colB" id="nd_colB">
  <div class="nd-cima">
   <section class="nd-cx nd-3d" id="nd_3d_cx" aria-label="3D da caixa">
    <div class="nd-rot"><span id="nd_3d_t" data-radai-frase>3D da caixa</span>
     <span class="dir">@VISTA@</span></div>
    <div class="nd-palco3d" id="nd_palco3d">
     <canvas id="nd_gl" aria-label="3D da caixa"></canvas>
     <div class="nd-cant" id="nd_cant"></div>
     <div id="nd_etqs"></div>
     <svg class="nd-eixos" id="nd_eixos3d" viewBox="0 0 84 84" aria-hidden="true"></svg>
     <div class="nd-dica" id="nd_dica3d"></div>
    </div>
    <div class="nd-ctl3d" id="nd_ctl_3d">
     <button type="button" class="nd-bt" id="nd_detector" onclick="nd3Detector()" aria-pressed="true"
      title="o 3D olha de onde o detector olha: a mesma orienta&ccedil;&atilde;o da proje&ccedil;&atilde;o">@ICO_DETECTOR@<span
      data-radai-frase>Vista do detector</span></button>
     <button type="button" class="nd-bt" id="nd_atraves" onclick="nd3Atraves()" aria-pressed="false"
      title="osso e pele transl&uacute;cidos de uma vez">@ICO_ATRAVES@<span
      data-radai-frase>Ver atrav&eacute;s</span></button>
    </div>
    <div class="nd-ctl3d" id="nd_ctl_sala" hidden>
     <button type="button" class="nd-bt" id="nd_sala_padrao" onclick="nd3SalaPadrao()"
      data-radai-frase>Sala na vista padr&atilde;o</button>
     <span class="dica" title="a roda do mouse aproxima" data-radai-frase>arrastar move o arco &middot; Shift gira a sala</span>
    </div>
   </section>
   <section class="nd-cx nd-inc" id="nd_inc_cx" aria-label="mapa de incid&ecirc;ncias">
    <div class="nd-rot"><span data-radai-frase>mapa de incid&ecirc;ncias</span></div>
    <div class="nd-pad" id="nd_pad" tabindex="0" role="group"
     aria-label="mapa LAO/RAO por CRA/CAU: setas giram 1 grau, Shift e setas 10 graus"></div>
    <div class="nd-rot"><span data-radai-frase>incid&ecirc;ncias guardadas</span>
     <span class="dir"><span class="nd-lapis" title="arraste contornando o ninho &middot; soltar fecha a &aacute;rea">@ICO_LAPIS@<span
      data-radai-frase>l&aacute;pis</span></span></span></div>
    <div class="nd-guardadas" id="nd_guardadas"></div>
    <div class="nd-acoes">
     <button type="button" class="nd-bt nd-guardar" id="nd_bt_guardar" onclick="ndGuardar()"
      aria-disabled="true">@ICO_GUARDAR@<span data-radai-frase>Guardar incid&ecirc;ncia</span></button>
     <button type="button" class="nd-bt" id="nd_bt_limpar" onclick="ndLimparGuardadas()" hidden
      data-radai-frase>Limpar marcação</button>
     <button type="button" class="nd-bt" id="nd_bt_cruzar" onclick="ndCalcular()" hidden
      data-radai-frase>Cruzar de novo</button>
    </div>
   </section>
  </div>

  <section class="nd-cx nd-mpr" id="nd_mpr" aria-label="MPR">
   <div class="nd-rot"><span>MPR <b id="nd_mod"></b> &middot; <span data-radai-frase>caixa de recorte</span></span>
    <span class="dir">
     <button type="button" class="nd-bt" id="nd_caixa_bt" onclick="ndCaixaModo()"
      aria-pressed="false">@ICO_CAIXA@<span data-radai-frase>Caixa de recorte</span></button>
     <button type="button" class="nd-bt" id="nd_caixa_limpar" onclick="ndCaixaLimpar()"
      data-radai-frase>Limpar recorte</button></span></div>
   <div class="nd-consenso" aria-label="consenso geométrico">
    <label for="nd_temperatura" data-radai-frase>Temperatura do consenso</label>
    <input type="range" id="nd_temperatura" min="0" max="100" step="1" value="50" disabled oninput="ndTemperatura(this.value)">
    <output id="nd_temperatura_v" for="nd_temperatura">50</output>
    <small data-radai-frase>0: união estrelada · 100: interseção de todas. Critério geométrico de estudo, não probabilidade clínica.</small>
     <span class="nd-consenso-vazio" id="nd_cons_vazio" role="status" hidden data-radai-frase>Consenso vazio: as incidências não deixam voxels em comum neste ajuste. Revise a temperatura ou edite a sugestão; não há contorno para exportar.</span>
    <button type="button" class="nd-bt" id="nd_cons_editar" onclick="ndEditarConsenso()" disabled data-radai-frase>Editar sugestão</button>
    <button type="button" class="nd-bt" id="nd_cons_add" onclick="ndConsOperacao('add')" hidden aria-pressed="true" data-radai-frase>Adicionar</button>
    <button type="button" class="nd-bt" id="nd_cons_remove" onclick="ndConsOperacao('remove')" hidden aria-pressed="false" data-radai-frase>Remover</button>
    <button type="button" class="nd-bt" id="nd_cons_undo" onclick="ndConsDesfazer()" hidden data-radai-frase>Desfazer edição</button>
    <button type="button" class="nd-bt" id="nd_cons_temperatura" onclick="ndVoltarTemperatura()" hidden data-radai-frase>Voltar à temperatura</button>
    <button type="button" class="nd-bt" id="nd_cons_exportar" onclick="ndExportarConsenso()" disabled data-radai-frase>Exportar sugestão</button>
   </div>
   <div class="nd-planos">
    <div class="p" id="nd_pane0"><div class="nd-mpr-title"><span data-radai-frase>axial</span><button type="button" class="nd-bt" id="nd_max0" onclick="ndMaximizar(0)" disabled data-radai-frase>Ampliar</button></div>
     <div class="nd-palco" id="nd_pp0"><img id="nd_pl0" alt="" draggable="false">
      <svg id="nd_lin0" preserveAspectRatio="xMidYMid meet"></svg>
      <svg class="nd-cx-svg" id="nd_cx0" preserveAspectRatio="xMidYMid meet"></svg>
      <svg class="nd-edit-surface" id="nd_ed0" preserveAspectRatio="xMidYMid meet"><rect width="100%" height="100%" fill="transparent"/></svg></div>
     <input type="range" id="nd_pos0" min="0" max="100" value="50"
      aria-label="corte axial"></div><span id="nd_home0" hidden></span>
    <div class="p" id="nd_pane1"><div class="nd-mpr-title"><span data-radai-frase>coronal</span><button type="button" class="nd-bt" id="nd_max1" onclick="ndMaximizar(1)" disabled data-radai-frase>Ampliar</button></div>
     <div class="nd-palco" id="nd_pp1"><img id="nd_pl1" alt="" draggable="false">
      <svg id="nd_lin1" preserveAspectRatio="xMidYMid meet"></svg>
      <svg class="nd-cx-svg" id="nd_cx1" preserveAspectRatio="xMidYMid meet"></svg>
      <svg class="nd-edit-surface" id="nd_ed1" preserveAspectRatio="xMidYMid meet"><rect width="100%" height="100%" fill="transparent"/></svg></div>
     <input type="range" id="nd_pos1" min="0" max="100" value="50"
      aria-label="corte coronal"></div><span id="nd_home1" hidden></span>
    <div class="p" id="nd_pane2"><div class="nd-mpr-title"><span data-radai-frase>sagital</span><button type="button" class="nd-bt" id="nd_max2" onclick="ndMaximizar(2)" disabled data-radai-frase>Ampliar</button></div>
     <div class="nd-palco" id="nd_pp2"><img id="nd_pl2" alt="" draggable="false">
      <svg id="nd_lin2" preserveAspectRatio="xMidYMid meet"></svg>
      <svg class="nd-cx-svg" id="nd_cx2" preserveAspectRatio="xMidYMid meet"></svg>
      <svg class="nd-edit-surface" id="nd_ed2" preserveAspectRatio="xMidYMid meet"><rect width="100%" height="100%" fill="transparent"/></svg></div>
     <input type="range" id="nd_pos2" min="0" max="100" value="50"
      aria-label="corte sagital"></div><span id="nd_home2" hidden></span>
    <div class="nd-legenda" id="nd_legenda" aria-label="legenda do MPR"
     title="linhas finas: o que foi retroprojetado"></div>
   </div>
   <div class="nd-rodape"><span id="nd_passo"></span><span id="nd_escala"></span></div>
  </section>
 </div>

</div>

@ALERTA@

@ESCOLHA@

</div>
<script>@JS@</script>
</body></html>"""



def _escolha():
    import radai_tabela_acervo
    import radai_ui
    pasta = (u'<div class="nd-pasta"><div class="nd-pasta-campo">'
             u'<input type="text" id="nd_pasta" '
             u'spellcheck="false" autocomplete="off" aria-label="pasta" '
             u'placeholder="C:\\... ou \\\\servidor\\...">@FAV@</div>'
             u'<button type="button" class="ui-bt" id="nd_procurar">'
             u'@ICO_PASTA@<span data-radai-frase>Procurar&hellip;</span>'
             u'</button><button type="button" class="ui-bt pri" id="nd_listar" '
             u'onclick="ndOutra()"><span data-radai-frase>Listar s&eacute;ries'
             u'</span></button></div>'
             u'<div class="nd-filtro">@FILTRO@</div>'
             u'<div class="ui-vl-est" id="nd_busca" role="status" '
             u'aria-live="polite"></div>'
             u'<div class="nd-series" id="nd_series" role="listbox" '
             u'aria-label="s&eacute;ries da pasta"></div>')
    pasta = (pasta.replace(u"@FAV@", radai_ui.botao_favorita(u"nd_pasta"))
             .replace(u"@FILTRO@", radai_ui.filtro_de_data(u"nd_dias")))
    return radai_ui.popup_de_serie(
        u"nd_escolha",
        u'<div class="nd-escolha">%s</div>'
        % radai_ui.abas_de_serie(u"nd_origem",
                                 [(u"acervo", u"Acervo local",
                                   radai_tabela_acervo.html(u"nd_acervo")),
                                  (u"pasta", u"Aponte uma pasta", pasta)],
                                 cor_var=u"--mod-nidus", lembrar=True))


def _cartao():
    import radai_ui
    return radai_ui.cartao_de_serie(u"nd_escolher", u"nd_escolha",
                                    u"Carregar série",
                                    vazio=u"nenhuma série aberta",
                                    chave_modulo=u"nidus",
                                    ident_rot=u"nd_serie_rot")


def _telas_do_mpr(serie):
    import radai_nidus as N
    fora = {}
    for eixo in range(3):
        dims = [d for k, d in enumerate(serie.forma) if k != eixo]
        ml, mc = N.mm_do_corte(serie.mm, eixo)
        alt, larg, _fl, _fc = N.grade_da_tela(dims, ml, mc)
        fora[str(eixo)] = [int(alt), int(larg)]
    return fora


def _modalidade(pasta, uid=u""):
    try:
        import pydicom
        nomes = sorted(os.listdir(pasta))
    except Exception:
        return u""
    for nome in nomes[:200]:
        fp = os.path.join(pasta, nome)
        if not os.path.isfile(fp):
            continue
        try:
            ds = pydicom.dcmread(fp, stop_before_pixels=True, force=True,
                                 specific_tags=["Modality",
                                                "SeriesInstanceUID"])
        except Exception:
            continue
        mod = str(getattr(ds, "Modality", "") or "").strip().upper()
        if not mod:
            continue
        if uid and str(getattr(ds, "SeriesInstanceUID", "") or "") != uid:
            continue
        return mod
    return u""


from radai_projection_bone import (
    e_osso, osso_da_segmentacao, ORDEM_DO_OSSO,
    _pastas_da_serie, _entrega_da_serie)


def pedir_a_fila(itens):
    try:
        import radai_queue_state
    except Exception:
        return {"ok": False, "indisponivel": True}
    try:
        d = radai_queue_state.enfileirar({"itens": list(itens or ())})
    except Exception as e:
        return {"ok": False, "erro": u"%s: %s" % (type(e).__name__,
                                                  str(e)[:200])}
    return d if isinstance(d, dict) else {"ok": False, "indisponivel": True}


SOLTAR_APOS_S = 600.0

TETO_MALHAS = 9

TETO_MALHAS_MB = 24


def montar(app, host_services=None):
    if getattr(app, "_neuro_nidus_screen_mounted", False):
        return app
    import threading
    import time
    from collections import OrderedDict
    from fastapi import Request
    from fastapi.responses import HTMLResponse, JSONResponse, Response

    _SESSOES = {}
    _ORDEM = []
    TETO_SESSOES = 4
    _PROXIMA = itertools.count(1)
    TETO_INCIDENCIAS = 12

    _ABERTA = {"chave": None, "serie": None, "visto": 0.0, "relogio": None}
    _TRAVA = threading.Lock()

    _TUBOS = OrderedDict()
    _ERROS = OrderedDict()
    _RECUSADAS = OrderedDict()

    def _soltar_se_ociosa():
        with _TRAVA:
            _ABERTA["relogio"] = None
            ocioso = time.time() - _ABERTA["visto"]
            if _ABERTA["serie"] is None:
                return
            if ocioso >= SOLTAR_APOS_S:
                _ABERTA.update({"chave": None, "serie": None})
                _TUBOS.clear()
                _MALHAS.clear()
                return
            _armar(SOLTAR_APOS_S - ocioso)

    def _armar(s):
        if _ABERTA["relogio"] is not None:
            return
        r = threading.Timer(max(1.0, float(s)), _soltar_se_ociosa)
        r.daemon = True
        _ABERTA["relogio"] = r
        r.start()

    def _falhou(onde, b, e):
        import radai_nidus as N
        if isinstance(e, N.SerieRecusada):
            msg = str(e)
        else:
            msg = u"%s: %s" % (type(e).__name__, str(e)[:200])
        _ERROS[str(b or u"")] = msg
        while len(_ERROS) > 16:
            _ERROS.popitem(last=False)
        try:
            import radai_thumbnail
            radai_thumbnail.registrar_falha(u"Nidus RT, %s" % onde, e,
                                            bilhete=b)
        except Exception:
            pass
        return msg

    def _resposta_de_erro(onde, b, e):
        import radai_nidus as N
        msg = _falhou(onde, b, e)
        return JSONResponse(status_code=422 if isinstance(e, N.SerieRecusada)
                            else 500, content={"erro": msg})

    def _ler_osso(serie, pasta, uid):
        try:
            m, info = osso_da_segmentacao(serie, pasta, uid)
            if m is not None and not serie.tirar_osso(m, info):
                info = {"tem": False, "motivo": SEM_SEGMENTACAO}
            serie.osso_estado = info
        except Exception as e:
            _falhou(u"osso", u"", e)
            serie.osso_estado = {"tem": False, "motivo": u"%s: %s" % (
                type(e).__name__, str(e)[:160])}

    def _serie(b, resolvido=None):
        if resolvido is None:
            import radai_thumbnail
            resolvido = radai_thumbnail.resolver(b)
        pasta, uid = resolvido
        if not pasta:
            return None
        chave = (pasta, uid or u"")
        import radai_nidus as N
        with _TRAVA:
            if _ABERTA["chave"] == chave and _ABERTA["serie"] is not None:
                _ABERTA["visto"] = time.time()
                return _ABERTA["serie"]
            # GUARDA: série recusada pelo dado não é relida a cada pedido da tela.
            if chave in _RECUSADAS:
                raise N.SerieRecusada(_RECUSADAS[chave])
            _ABERTA.update({"chave": None, "serie": None})
            _TUBOS.clear()
            _MALHAS.clear()
            import engine
            img = engine.load_sitk(pasta, uid or None)
            try:
                serie = N.abrir(img, _modalidade(pasta, uid or u""))
            except N.SerieRecusada as e:
                _RECUSADAS[chave] = str(e)
                while len(_RECUSADAS) > 32:
                    _RECUSADAS.popitem(last=False)
                raise
            serie.chave_estavel = chave_da_serie(pasta, uid or u"")
            try:
                from neuro_rt.nidus_geometry import source_signature
                serie.nidus_source_signature = source_signature(pasta, uid)
            except (OSError, ValueError):
                serie.nidus_source_signature = None
            _ler_osso(serie, pasta, uid or u"")
            _ABERTA.update({"chave": chave, "serie": serie,
                            "visto": time.time()})
            _armar(SOLTAR_APOS_S)
            return serie

    def _estado_do_osso(serie):
        e = dict(getattr(serie, "osso_estado", None) or {"tem": False})
        e["tem"] = bool(e.get("tem")) and serie.osso is not None
        return e

    @app.get("/nidus/projecao", response_class=HTMLResponse)
    def _tela():
        return radai_menu.aplicar(pagina(), "nidus_projecao")

    def _abrir(b, resolvido=None):
        try:
            t0 = time.perf_counter()
            serie = _serie(b, resolvido)
            if serie is None:
                return {"erro": u"recarregue a lista de séries"}
            _ERROS.pop(str(b), None)
            return {"forma": list(serie.forma),
                    "geometria": radai_nidus.geometria_da_serie(serie),
                    "espacamento": list(serie.mm),
                    "passos": serie.passos(LADOS),
                    "lado_util": serie.lado_util,
                    "modalidade": serie.modalidade,
                    "hu": bool(serie.escala.get("hu", True)),
                    "telas": _telas_do_mpr(serie),
                    "osso": _estado_do_osso(serie),
                    "chave": getattr(serie, "chave_estavel", u"") or u"",
                    "ms": int(round((time.perf_counter() - t0) * 1000))}
        except Exception as e:
            return {"erro": _falhou(u"abrir", b, e)}

    @app.get("/api/nidus/forma")
    def _forma(b: str = ""):
        return _abrir(b)

    @app.post("/api/nidus/abrir")
    async def _abrir_pela_tela(request: Request):
        b = ""
        try:
            c = await request.json() or {}
            b = str(c.get("b") or "")
            resolvido = None
            if str(c.get("origem") or "") == "acervo":
                import radai_tabela_acervo
                resolvido = await radai_web.no_threadpool(
                    radai_tabela_acervo.resolver, b)
                if not resolvido or not resolvido[0]:
                    return {"erro": FORA_DO_ACERVO}
            return await radai_web.no_threadpool(_abrir, b, resolvido)
        except Exception as e:
            return {"erro": _falhou(u"abrir", b, e)}

    @app.get("/api/nidus/estado")
    def _estado(b: str = ""):
        return {"erro": _ERROS.get(str(b), u"")}

    _TRAVA_CX = threading.Lock()
    _TRAVA_PROJ = threading.Lock()
    _TRAVA_PEDIDAS = threading.Lock()
    _PEDIDAS = OrderedDict()

    def _anotar_pedida(aba, n):
        if not aba or n <= 0:
            return
        with _TRAVA_PEDIDAS:
            if n > _PEDIDAS.get(aba, 0):
                _PEDIDAS[aba] = n
                _PEDIDAS.move_to_end(aba)
            while len(_PEDIDAS) > 32:
                _PEDIDAS.popitem(last=False)

    def _pedida_velha(aba, n):
        if not aba or n <= 0:
            return False
        with _TRAVA_PEDIDAS:
            return _PEDIDAS.get(aba, 0) > n

    @app.get("/api/nidus/eixos")
    def _eixos(lao: float = 0.0, cra: float = 0.0):
        try:
            import radai_nidus as N
            return N.eixos_da_incidencia(float(lao), float(cra))
        except Exception as e:
            return {"erro": u"%s: %s" % (type(e).__name__, str(e)[:200])}

    @app.get("/api/nidus/projecao")
    def _projecao(b: str = "", lao: float = 0.0, cra: float = 0.0,
                  modo: str = "mip", janela: str = "angio", lado: int = 256,
                  laje: float = 0.0, caixa: str = "", osso: int = 0,
                  n: int = 0, t: str = ""):
        aba, seq = str(t or "")[:40], int(n or 0)
        _anotar_pedida(aba, seq)
        try:
            # GUARDA: uma projeção por vez (a grade de 1024 ocupa ~0,75 GiB); a pedida que envelheceu na espera não roda.
            with _TRAVA_PROJ:
                if _pedida_velha(aba, seq):
                    return JSONResponse(status_code=409,
                                        content={"erro": PROJECAO_VELHA},
                                        headers={"Cache-Control": "no-store"})
                import radai_nidus as N
                import radai_recon3d as R
                serie = _serie(b)
                if serie is None:
                    return JSONResponse(status_code=404, content={
                        "erro": u"recarregue a lista de séries"})
                _lado = int(lado or N.LADO_PADRAO)
                if _lado not in LADOS:
                    _lado = N.LADO_PADRAO
                cx = N.caixa_de_texto(caixa)
                modo_ = "mip" if modo == "mip" else "minip"
                amostra = serie.base(modo_, bool(osso))
                if cx is not None:
                    with _TRAVA_CX:
                        amostra = serie.img_na_caixa(cx, modo_, bool(osso))
                plano, info = N.projetar(serie.img, lao, cra, modo, janela,
                                         lado=_lado,
                                         laje_mm=(float(laje) or None),
                                         escala=serie.escala, amostra=amostra)
                png = R.para_png(plano, info["centro"], info["largura"])
            _ERROS.pop(str(b), None)
            return Response(content=png, media_type="image/png",
                            headers={"Cache-Control": "no-store"})
        except Exception as e:
            return _resposta_de_erro(u"projeção", b, e)

    @app.get("/api/nidus/corte")
    def _corte(b: str = "", eixo: int = 0, pos: float = 0.5,
               janela: str = "angio"):
        try:
            import radai_nidus as N
            import radai_recon3d as R
            serie = _serie(b)
            if serie is None:
                return JSONResponse(status_code=404, content={
                    "erro": u"recarregue a lista de séries"})
            eixo = int(eixo)
            n = serie.forma[eixo]
            i = int(round(min(1.0, max(0.0, float(pos))) * (n - 1)))
            a = N.corte(serie.v, eixo, i)
            ml, mc = N.mm_do_corte(serie.mm, eixo)
            c, l = N.janela_de(janela, serie.escala)
            return Response(content=R.para_png(N.para_a_tela(a, ml, mc), c, l),
                            media_type="image/png",
                            headers={"Cache-Control": "no-store"})
        except Exception as e:
            return _resposta_de_erro(u"corte", b, e)

    @app.post("/api/nidus/osso")
    async def _osso(request: Request):
        b = ""
        try:
            c = await request.json() or {}
            import radai_thumbnail
            b = str(c.get("b") or "")
            serie = await radai_web.no_threadpool(_serie, b)
            if serie is None:
                return {"erro": u"recarregue a lista de séries"}
            pasta, uid = radai_thumbnail.resolver(b)
            await radai_web.no_threadpool(_ler_osso, serie, pasta, uid or u"")
            return {"osso": _estado_do_osso(serie)}
        except Exception as e:
            return {"erro": _falhou(u"osso", b, e)}

    @app.post("/api/nidus/segmentar")
    async def _segmentar(request: Request):
        try:
            c = await request.json() or {}
            import radai_thumbnail
            b = str(c.get("b") or "")
            pasta, uid = radai_thumbnail.resolver(b)
            if not pasta:
                return {"ok": False, "erro": u"recarregue a lista de séries"}
            item = {"pasta": pasta, "uid": uid or u"", "modo": u"auto",
                    "chaves": {}, "copiar_rs_para": [], "origem": u"nidus",
                    "rotulo": str(c.get("rotulo") or u"")[:80]}
            if c.get("substituir") is True:
                item["substituir"] = True
            r = await radai_web.no_threadpool(pedir_a_fila, [item])
            if r.get("indisponivel"):
                return {"ok": False, "indisponivel": True,
                        "erro": FILA_INDISPONIVEL}
            if not r.get("ok"):
                return {"ok": False, "erro": str(r.get("erro") or
                                                 FILA_INDISPONIVEL)}
            cartao = (r.get("cartoes") or [{}])[0] or {}
            return {"ok": True, "id": cartao.get("id"),
                    "posicao": cartao.get("posicao")}
        except Exception as e:
            return {"ok": False, "erro": u"%s: %s" % (type(e).__name__,
                                                      str(e)[:200])}

    _TRAVA_MALHA = threading.Lock()
    _MALHAS = OrderedDict()
    _PEDIDAS_MALHA = OrderedDict()

    def _guardar_malha(stl):
        import uuid
        m = uuid.uuid4().hex
        _MALHAS[m] = stl
        tot = sum(len(v) for v in _MALHAS.values())
        while _MALHAS and (len(_MALHAS) > TETO_MALHAS
                           or tot > TETO_MALHAS_MB * 1024 * 1024):
            _k, v = _MALHAS.popitem(last=False)
            tot -= len(v)
        return m

    def _malhas_da_caixa(b, caixa, aba, seq):
        import radai_nidus as N
        import radai_recon3d as R
        with _TRAVA_MALHA:
            if aba and seq and _PEDIDAS_MALHA.get(aba, 0) > seq:
                return {"erro": u"", "velha": True, "malhas": []}
            serie = _serie(b)
            if serie is None:
                return {"erro": u"recarregue a lista de séries", "malhas": []}
            cx = N.caixa_de_texto(caixa)
            if cx is None:
                return {"erro": N.SEM_CAIXA_PARA_O_3D, "malhas": []}
            fora = []
            for qual in N.QUAIS_DA_MALHA:
                try:
                    lps, faces, info = N.malha_da_caixa(serie, cx, qual)
                except N.MalhaRecusada as e:
                    fora.append({"qual": qual, "triangulos": 0, "m": u"",
                                 "motivo": str(e)})
                    continue
                item = {"qual": qual, "triangulos": int(len(faces)), "m": u"",
                        "motivo": info.get(u"motivo") or u"",
                        "passo_mm": float(info.get(u"passo_mm") or 0.0)}
                if len(faces):
                    item["m"] = _guardar_malha(R.stl_da_malha(lps, faces))
                fora.append(item)
            return {"erro": u"", "malhas": fora,
                    "triangulos": sum(x["triangulos"] for x in fora)}

    @app.post("/api/nidus/malhas")
    async def _malhas(request: Request):
        b = ""
        try:
            c = await request.json() or {}
            b = str(c.get("b") or "")
            aba, seq = str(c.get("t") or "")[:40], int(c.get("n") or 0)
            if aba and seq > 0:
                with _TRAVA_PEDIDAS:
                    if seq > _PEDIDAS_MALHA.get(aba, 0):
                        _PEDIDAS_MALHA[aba] = seq
                        _PEDIDAS_MALHA.move_to_end(aba)
                    while len(_PEDIDAS_MALHA) > 32:
                        _PEDIDAS_MALHA.popitem(last=False)
            return await radai_web.no_threadpool(
                _malhas_da_caixa, b, str(c.get("caixa") or ""), aba, seq)
        except Exception as e:
            return {"erro": _falhou(u"3D da caixa", b, e), "malhas": []}

    @app.get("/api/nidus/malha")
    def _malha(m: str = ""):
        stl = _MALHAS.get(str(m or ""))
        if stl is None:
            return JSONResponse(status_code=404, content={
                "erro": u"a malha saiu da memória: solte a caixa de novo"})
        return Response(content=stl, media_type="application/octet-stream",
                        headers={"Cache-Control": "no-store"})

    def _tubo_da_incidencia(serie, chave_serie, lado, inc):
        lao = float(inc.get("lao") or 0)
        cra = float(inc.get("cra") or 0)
        pts = [(float(p[0]), float(p[1])) for p in (inc.get("pontos") or ())]
        chave = (chave_serie, lado, round(lao, 3), round(cra, 3),
                 tuple((round(x, 3), round(y, 3)) for x, y in pts))
        with _TRAVA:
            t = _TUBOS.get(chave)
            if t is not None:
                _TUBOS.move_to_end(chave)
                return t
        t = serie.tubo(pts, lao, cra, lado)
        with _TRAVA:
            _TUBOS[chave] = t
            while len(_TUBOS) > TETO_INCIDENCIAS:
                _TUBOS.popitem(last=False)
        return t

    @app.post("/api/nidus/tubos")
    async def _tubos(request: Request):
        b = ""
        try:
            c = await request.json() or {}
            import radai_nidus as N
            b = str(c.get("b") or "")
            t0 = time.perf_counter()
            serie = await radai_web.no_threadpool(_serie, b)
            if serie is None:
                return {"erro": u"recarregue a lista de séries"}
            chave_serie = b
            lado = int(c.get("lado") or 256)
            if lado not in LADOS:
                lado = N.LADO_PADRAO
            incs = list(c.get("incidencias") or ())[:TETO_INCIDENCIAS]
            masc = []
            angulos = []
            for inc in incs:
                masc.append(await radai_web.no_threadpool(
                    _tubo_da_incidencia, serie, chave_serie, lado, inc))
                angulos.append({"lao": float(inc.get("lao") or 0),
                                "cra": float(inc.get("cra") or 0),
                                "pontos": len(inc.get("pontos") or [])})
            if not masc:
                return {"erro": u"nenhuma incidência marcada"}
            chave = "%s|%d" % (b, next(_PROXIMA))
            _SESSOES[chave] = {"tubos": masc, "angulos": angulos,
                               "forma": serie.forma, "mm": serie.mm,
                               "b": b, "consenso": await radai_web.no_threadpool(
                                   lambda: N.consenso(serie.img, incs, lado=lado)),
                               'source_signature': getattr(serie, 'nidus_source_signature', None),
                               "inter": (N.intersecao(masc)
                                         if len(masc) > 1 else None)}
            _ORDEM.append(chave)
            while len(_ORDEM) > TETO_SESSOES:
                _SESSOES.pop(_ORDEM.pop(0), None)
            return {"sessao": chave, "incidencias": len(masc),
                    "angulos": angulos,
                    "teto": TETO_INCIDENCIAS,
                    "cruzam": bool(len(masc) > 1),
                    "ms": int(round((time.perf_counter() - t0) * 1000))}
        except Exception as e:
            return {"erro": _falhou(u"retroprojeção", b, e)}

    @app.get("/api/nidus/linhas")
    def _linhas(s: str = "", eixo: int = 0, pos: float = 0.5,
                temperatura: float = 50., editado: bool = False):
        try:
            import radai_nidus as N
            ses = _SESSOES.get(s)
            if not ses:
                return {"erro": u"sessão expirada — refaça a marcação"}
            eixo = int(eixo)
            n = ses["forma"][eixo]
            i = int(round(min(1.0, max(0.0, float(pos))) * (n - 1)))
            dims = [d for k, d in enumerate(ses["forma"]) if k != eixo]
            ml, mc = N.mm_do_corte(ses["mm"], eixo)
            alt, larg, fl, fc = N.grade_da_tela(dims, ml, mc)
            angulos = ses.get("angulos") or []
            camadas = []
            for k, m in enumerate(ses["tubos"]):
                a = angulos[k] if k < len(angulos) else {}
                camadas.append({"qual": "inc", "i": k,
                                "lao": a.get("lao"), "cra": a.get("cra"),
                                "segmentos": N.escalar(
                                    N.contorno_do_tubo(m, eixo, i), fl, fc)})
            if ses.get("inter") is not None:
                camadas.append({"qual": "inter", "i": -1,
                                "segmentos": N.escalar(N.contorno_do_tubo(
                                    ses["inter"], eixo, i), fl, fc)})
            if ses.get("consenso") is not None:
                from neuro_rt.nidus_geometry import contour_segments
                candidato = ses.get('candidato') if editado else None
                plano = (candidato.plane(eixo, i) if candidato is not None else
                         ses['consenso'].plane(temperatura, eixo, i))
                camadas.append({'qual': 'consenso', 'i': -2,
                    'segmentos': N.escalar(contour_segments(plano), fl, fc)})
            empty = None
            if editado and ses.get('candidato') is not None:
                empty = not bool(ses['candidato'].packed.bits.any())
            elif temperatura == 100:
                common = ses.get('inter') if len(ses['tubos']) > 1 else ses['tubos'][0]
                empty = common is not None and not bool(common.bits.any())
            return {"altura": alt, "largura": larg,
                    "camadas": camadas, "corte": i, "n": n,
                    "incidencias": len(ses["tubos"]), 'indice': i,
                    'temperatura': temperatura, 'consenso_vazio': empty}
        except Exception as e:
            return {"erro": u"%s: %s" % (type(e).__name__, str(e)[:200])}

    if host_services is not None:
        from integration.nidus_consensus import attach_consensus_api
        def resolver_consenso(b):
            import radai_thumbnail
            return radai_thumbnail.resolver(b)
        attach_consensus_api(app, _SESSOES, resolver_consenso)
    app._neuro_nidus_screen_mounted = True
    return app
