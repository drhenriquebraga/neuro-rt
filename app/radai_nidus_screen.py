# -*- coding: utf-8 -*-
import hashlib
import itertools
import json
import os

import radai_menu
import radai_nidus
import radai_web

LADOS = (256, 512, 768, radai_nidus.LADO_ALTA)

LADO_DA_TELA = radai_nidus.LADO_ALTA

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
.nd-wrap{max-width:1760px;margin:0 auto;padding:0 18px 6px}
.nd-ferramentas{display:flex;flex-direction:column;gap:5px;
 margin:0 0 4px;padding:6px 12px;background:var(--panel);
 border:1px solid var(--line);border-radius:var(--r-2xl,12px)}
.nd-linha{display:flex;flex-wrap:wrap;gap:5px 18px;align-items:center}
.nd-ferramentas .nd-bt{padding:3px 8px;min-height:26px}
@media (max-width:1440px){
 .nd-ferramentas .nd-grupo > span.t{display:none}
 .nd-linha{gap:5px 12px}
 .nd-angulo input[type=range]{width:96px !important}
 .nd-ang{width:44px}
 .nd-laje input[type=range]{width:72px}
 .nd-ferramentas .nd-bt{padding:3px 6px}
}
.nd-ferramentas .nd-grupo{display:flex;align-items:center;gap:6px;flex-wrap:wrap;
 padding:0;border:0}
.nd-grupo > .t{font:400 10px/1 var(--font-mono,monospace);letter-spacing:.14em;
 text-transform:uppercase;color:var(--text-dim)}
.nd-grupo .g{display:flex;gap:4px;align-items:center;flex-wrap:wrap}
.nd-grupo .sub{font-size:11px;color:var(--text-dim);line-height:1.45}
.nd-angulo input[type=range]{width:130px}
.nd-angv{min-width:62px;font:500 11.5px/1 var(--font-mono,monospace);color:var(--text)}
.nd-ang{width:52px;height:26px;box-sizing:border-box;padding:0 6px;text-align:right;
 font-family:var(--font-mono,monospace)}
.nd-laje input[type=range]{width:96px}
.nd-lapis{display:inline-flex;align-items:center;gap:5px;font-size:11px;color:var(--accent)}
.nd-lapis .ui-ic{position:static;width:1em;height:1em}
#nd_msg{min-height:18px;font-size:12px;line-height:1.45;margin:2px 0 6px}
#nd_msg.erro{color:var(--perigo,#E96A5C)}
#nd_msg.ok{color:var(--success,#5BC57F)}

.nd-trabalho{display:grid;grid-template-columns:auto auto minmax(220px,1fr);gap:12px;
 align-items:start}
@media (max-width:1100px){.nd-trabalho{grid-template-columns:1fr}}
.nd-cx{border:1px solid var(--line);border-radius:var(--r-xl,11px);
 padding:9px;background:var(--panel)}
.nd-cx > .rot{font-family:var(--font-mono,monospace);font-size:10px;height:14px;
 letter-spacing:.11em;text-transform:uppercase;color:var(--text-dim);
 display:flex;justify-content:space-between;align-items:baseline;gap:10px;
 margin-bottom:7px;white-space:nowrap;overflow:hidden}
.nd-cx > .rot b{font-weight:400;color:var(--text-muted)}

.nd-palco{position:relative;background:var(--img-fundo,#000);border-radius:var(--r-lg,8px);
 overflow:hidden;display:flex;align-items:center;justify-content:center}
.nd-proj .nd-palco{width:var(--nd-h,560px);height:var(--nd-h,560px)}
.nd-palco img{width:100%;height:100%;object-fit:contain;display:block;
 image-rendering:pixelated;user-select:none}
.nd-palco svg{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}
.nd-palco.desenhavel{cursor:crosshair}
.nd-palco.desenhavel #nd_svg{pointer-events:auto}
.nd-palco.arrastando{cursor:grabbing}
.nd-zoom{position:absolute;inset:0;transform-origin:0 0;will-change:transform}
.nd-palco.inv{background:#fff}
.nd-palco.inv .nd-zoom img{filter:invert(1)}
.nd-ferr-palco{position:absolute;top:8px;right:8px;z-index:3;display:flex;gap:4px}
.nd-ferr-palco .nd-bt{background:rgba(6,13,26,.74);border-color:rgba(230,237,247,.16);
 color:var(--img-texto,#e6edf7)}
.nd-ferr-palco .nd-bt:hover{color:var(--img-texto,#e6edf7);border-color:rgba(230,237,247,.4)}
.nd-bt.nd-ic{width:30px;padding:0;display:inline-flex;align-items:center;
 justify-content:center;font-size:15px}
.nd-zoomv{position:absolute;left:8px;top:8px;z-index:3;
 font:400 10px/1 var(--font-mono,monospace);color:var(--img-texto,#e6edf7);
 background:rgba(0,0,0,.72);padding:4px 6px;border-radius:4px;pointer-events:none}
.nd-bt .ui-ic{position:static;inset:auto;width:1em;height:1em;pointer-events:none}
.nd-palco .nd-eixos{position:absolute;inset:auto 6px 6px auto;width:84px;height:84px;
 z-index:3;pointer-events:none}
.nd-eixos line{stroke:#8fa6c8;stroke-width:1.5;stroke-linecap:round}
.nd-eixos text{fill:#dce6f5;font:600 11px var(--font-mono,monospace);
 text-anchor:middle;dominant-baseline:central}
.nd-palco.inv .nd-eixos line{stroke:#46607f}
.nd-palco.inv .nd-eixos text{fill:#1b2a40}

.nd-mpr .nd-planos{display:grid;grid-template-rows:repeat(3,minmax(0,1fr));gap:6px;
 height:var(--nd-h,560px);width:calc((var(--nd-h,560px) - 12px) / 3)}
.nd-mpr .p{position:relative;min-height:0}
.nd-mpr .nd-palco{width:100%;height:100%}
.nd-mpr .p > span{position:absolute;left:5px;top:4px;z-index:4;
 font-family:var(--font-mono,monospace);font-size:9.5px;color:var(--img-texto,#e6edf7);
 background:rgba(0,0,0,.72);padding:1px 5px;border-radius:4px}
.nd-mpr .p input[type=range]{position:absolute;left:6px;right:6px;bottom:3px;
 width:calc(100% - 12px);margin:0;z-index:4}
.nd-cx-svg{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}
.nd-cx-svg.on{pointer-events:auto;cursor:crosshair}
.nd-caixa{fill:rgba(227,155,79,.07);stroke:var(--mod-nidus,#E39B4F);stroke-width:1.5;
 stroke-dasharray:6 4;vector-effect:non-scaling-stroke}
.nd-cx-svg.on .nd-caixa{stroke-dasharray:none}
.nd-alca{fill:var(--mod-nidus,#E39B4F)}

.nd-lado{display:flex;flex-direction:column;gap:0;padding:4px 12px;min-width:0;
 max-height:calc(var(--nd-h,560px) + 41px);overflow-y:auto;box-sizing:border-box}
.nd-lado .nd-grupo{display:flex;flex-direction:column;gap:6px;padding:9px 0;
 border-bottom:1px solid var(--line)}
.nd-lado .nd-grupo:last-child{border-bottom:0}
.nd-lado .g{display:flex;gap:5px;align-items:center;flex-wrap:wrap}
.nd-lado input[type=text],.nd-lado select{width:100%;min-width:0;height:30px;
 box-sizing:border-box;padding:0 8px;border-radius:var(--r-md,6px);
 border:1px solid var(--line-strong);background:var(--panel-2);color:var(--text);
 font-size:12px}
.nd-lado input[type=text]{font-family:var(--font-mono,monospace)}
.nd-lado input:focus,.nd-lado select:focus{outline:0;border-color:var(--accent)}
.nd-lado .ui-bt{height:30px;white-space:nowrap}
.nd-legenda{font-size:11px;color:var(--text-dim);margin:0;line-height:1.5}
.nd-osso b{font-weight:500;color:var(--text)}

.nd-tubo{fill:none;stroke-width:1.1;vector-effect:non-scaling-stroke;opacity:.85}
.nd-c0{stroke:var(--mod-nidus,#E39B4F)}
.nd-c1{stroke:var(--mod-nidus-b,#7FD1D6)}
.nd-c2{stroke:#B886F0}
.nd-c3{stroke:#6FD08C}
.nd-c4{stroke:#F0846F}
.nd-c5{stroke:#D8C24F}
.nd-inter{fill:none;stroke:var(--accent,#4DA3FF);stroke-width:2;
 vector-effect:non-scaling-stroke}

.nd-lista{list-style:none;margin:0 0 6px;padding:0;display:flex;
 flex-direction:column;gap:4px;max-height:200px;overflow-y:auto}
.nd-lista li{display:flex;align-items:center;gap:8px;font-size:11.5px;
 padding:5px 8px;border-radius:var(--r-md,6px);
 background:var(--panel,#0c1322);border:1px solid var(--line,#1e293b)}
.nd-lista li i{width:9px;height:9px;border-radius:50%;flex:none;
 font-style:normal;background:currentColor}
.nd-lista li.nd-c0{color:var(--mod-nidus,#E39B4F)}
.nd-lista li.nd-c1{color:var(--mod-nidus-b,#7FD1D6)}
.nd-lista li.nd-c2{color:#B886F0}
.nd-lista li.nd-c3{color:#6FD08C}
.nd-lista li.nd-c4{color:#F0846F}
.nd-lista li.nd-c5{color:#D8C24F}
.nd-lista li b{color:var(--text,#e6edf7);font-weight:600}
.nd-lista li.pend{border-style:dashed}
.nd-pt{color:var(--text-dim,#72829b);margin-left:auto;font-size:10.5px}
.nd-x{background:none;border:0;color:var(--text-dim,#72829b);cursor:pointer;
 font-size:15px;line-height:1;padding:0 2px}
.nd-x:hover{color:var(--perigo,#E96A5C)}
.nd-teto{font-size:10.5px;color:var(--aviso,#E8A33D);margin:0 0 6px}
.nd-marca{fill:none;stroke:var(--mod-nidus,#E39B4F);stroke-width:1;
 stroke-dasharray:2 2;stroke-linecap:round;vector-effect:non-scaling-stroke}

.nd-bt{font-size:11px;padding:4px 9px;border-radius:var(--r-md,7px);
 cursor:pointer;border:1px solid var(--line);background:var(--panel);
 color:var(--text-dim);min-height:28px}
.nd-bt.on{border-color:var(--accent);color:var(--accent)}
.nd-bt:disabled,.ui-bt:disabled{opacity:.45;cursor:not-allowed}
.nd-bt:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.nd-bt[hidden]{display:none}
.nd-chip{display:inline-flex;align-items:center;gap:7px;font-size:11.5px;
 padding:5px 11px;border-radius:var(--r-pill,999px);border:1px solid var(--line);
 background:var(--panel-2,#0f1729)}
.nd-chip.vazio{color:var(--text-dim);border-style:dashed}
.nd-lado .ui-cartao{padding:10px 12px;gap:10px;min-height:0}
.nd-escolha{display:flex;flex-direction:column;gap:10px;min-width:0}
.nd-escolha .nd-pasta{display:flex;gap:6px;align-items:center;flex-wrap:wrap;
 margin:0 0 8px}
.nd-escolha input[type=text]{flex:1 1 260px;min-width:0;height:30px;
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
"""

JS = u"""
var ND_PADROES = {lao:0, cra:0, modo:'mip', jan:'angio', laje:0, inverter:true,
                  osso:true};
var ND = {b:'', chave:'', desc:'', lista:[], lado:@LADO@, tem_osso:false,
          ossoInfo:null, tracando:false, pontos:[], guardadas:[], sessao:null,
          planos:{0:0.5,1:0.5,2:0.5}, forma:null,
          passos:null, lado_util:0, teto:12,
          zoom:{k:1, x:0, y:0},
          caixa:null, caixaOn:false, telas:null, abrindo:false,
          aberta:false, motivo:'', projetando:false, cruzando:false,
          recruzar:false, voltando:false, refeitas:0, recuperavel:false,
          bom:null, historico:[], fila:null, restaurou:false, ultima:null,
          substituirOsso:false, seqProj:0,
          tabela:null, escolhendo:false};
ndPadroes();
var ND_MODALIDADES = @MODALIDADES@;
var ND_ABA = Math.random().toString(36).slice(2, 10);

var ND_EPS = 0.5, ND_TETO_VERTICES = 120, ND_PASSO_MIN = 0.6;
var ND_TETO_HISTORICO = 60, ND_FILA_A_CADA_MS = 15000, ND_FILA_TENTATIVAS = 960;
var ND_FILA_FALHAS = 4;
var ND_TRAVAVEIS = ['nd_lao','nd_cra','nd_lao_r','nd_cra_r','nd_m_mip','nd_m_minip',
 'nd_inverter','nd_osso_bt','nd_segmentar','nd_laje','nd_caixa_bt','nd_caixa_limpar',
 'nd_bt_guardar','nd_bt_cruzar'];

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

function ndAng(v, pos, neg){
 var n=Math.round(+v||0);
 return (n<0?neg:pos)+' '+Math.abs(n)+'°';
}
function ndRotulo(g){ return ndAng(g.lao,'LAO','RAO')+' / '+ndAng(g.cra,'CRA','CAU') }
function ndCopia(o){ return JSON.parse(JSON.stringify(o)) }

function ndFoto(){
 return ndCopia({lao:ND.lao, cra:ND.cra, modo:ND.modo, jan:ND.jan, laje:ND.laje,
  inverter:ND.inverter, osso:ND.osso, caixa:ND.caixa, guardadas:ND.guardadas,
  pontos:ND.pontos, sessao:ND.sessao});
}
function ndPadroes(){
 for(var k in ND_PADROES) ND[k]=ND_PADROES[k];
 ND.planos={0:0.5,1:0.5,2:0.5};
}
// GUARDA: a chave é a impressão do UID que o servidor manda; o bilhete muda a cada processo.
function ndChaveSalva(){ return 'radai_nidus_'+ND.chave }
function ndRegistrar(acao){
 if(!ND.chave) return;
 var f=ndFoto();
 ND.historico.push({acao:acao, foto:f});
 while(ND.historico.length>ND_TETO_HISTORICO) ND.historico.shift();
 // GUARDA: só na aba (sessionStorage): o desenho não vai a disco nem a outra máquina.
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
 var c=ndEl('nd_bt_cruzar');
 if(c){
  c.hidden=!ND.guardadas.some(function(x){ return x && x.pendente });
  c.disabled=!aberta || ND.cruzando;
 }
 var rt=ndEl('nd_bt_retomar');
 if(rt) rt.hidden=!(ND.recuperavel && ND.ultima && !aberta && !ND.abrindo);
 var p=ndEl('nd_palco');
 if(p) p.classList.toggle('desenhavel', ndPodeDesenhar());
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
 ndFrases(alvo, ['carregando…']);
 fetch('/api/nidus/series',{method:'POST',
   headers:{'Content-Type':'application/json'},
   body:JSON.stringify({pasta:pasta||''})})
  .then(function(r){return r.json()}).then(function(d){
   ND.lista=d.series||[];
   if(!ND.lista.length){
    ndFrases(alvo, [d.erro||'nenhuma série nesta pasta'].concat(d.avisos||[]));
    return }
   alvo.innerHTML=ND.lista.map(function(s,i){
    return '<button type="button" class="nd-it" role="option" data-i="'+i+'">'
      +ndRotuloDaLista(s)+'</button>';
   }).join('')+(d.avisos||[]).map(function(t){
    return '<p class="sub" data-radai-frase>'+ndEsc(t)+'</p>' }).join('');
   if(window.radaiRetraduzir) window.radaiRetraduzir();
  }).catch(function(e){ ndFrases(alvo, ['não consegui listar: '+e]) });
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
function ndEscolher(i){
 var s=ND.lista[+i]; if(!s) return;
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
 // GUARDA: série nova abre nos padrões; só o estado salvo DELA os muda (depois do abrir).
 ndPadroes();
 [0,1,2].forEach(function(eixo){ var r=ndEl('nd_pos'+eixo); if(r) r.value='50' });
 ndSincronizar();
 ndTravas(); ndModalidade(s.modalidade); ndZoomAjustar(); ndPintarCaixas();
 ndPintarMarca();
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
   ND.forma=d.forma; ND.telas=d.telas||null;
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
   ndPintarMarca(); ndPintarCaixas();
   ndProjetar(); ndPintarPlanos(true); ndPintarGuardadas();
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

function ndProjetar(){
 if(!ND.b || !ND.aberta) return;
 var img=ndEl('nd_proj'), b=ND.b;
 ND.projetando=true; ND.tracando=false; ndTravas();
 img.onerror=function(){ if(b!==ND.b) return;
  img.removeAttribute('src'); ND.projetando=false;
  ndCarregando(false); ndTravas(); ndFalhou('proj') };
 img.onload=function(){ if(b!==ND.b) return;
  ND.projetando=false; ND.voltando=false;
  ndCarregando(false); ndMarcarBom(); ndTravas() };
 ndCarregando(true);
 ND.seqProj++;
 img.src='/api/nidus/projecao?b='+encodeURIComponent(ND.b)
   +'&n='+ND.seqProj+'&t='+ND_ABA
   +'&lao='+ND.lao+'&cra='+ND.cra+'&modo='+ND.modo+'&janela='+ND.jan
   +'&lado='+ND.lado+(ND.laje?('&laje='+ND.laje):'')
   +'&osso='+((ND.osso && ND.tem_osso)?1:0)
   +((ND.caixa && !ndCaixaCheia(ND.caixa))?('&caixa='+ND.caixa.map(function(v){ return v.toFixed(4) }).join(',')):'');
 var r=ndEl('nd_rot_proj');
 if(r) r.textContent=ndRotulo(ND)+'  ·  '+ND.modo.toUpperCase();
 ndPedirEixos(ND.lao, ND.cra);
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

// GUARDA: os eixos vêm de `radai_nidus.eixos_da_incidencia`, a mesma rotação da projeção.
function ndPedirEixos(lao, cra){
 ND.eixosPedidos=lao+','+cra;
 fetch('/api/nidus/eixos?lao='+lao+'&cra='+cra)
  .then(function(r){return r.json()}).then(function(d){
   if(ND.eixosPedidos===lao+','+cra) ndEixos(d);
  }).catch(function(){ ndEixos(null) });
}

function ndEixos(d){
 var g=ndEl('nd_eixos'); if(!g) return;
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

// GUARDA: o desenho e a imagem estão no MESMO contêiner escalado; `ndPonto` lê o retângulo já escalado.
function ndZoomAplicar(){
 var w=ndEl('nd_zoom'), z=ND.zoom; if(!w) return;
 w.style.transform='translate('+z.x.toFixed(1)+'px,'+z.y.toFixed(1)+'px) scale('+z.k.toFixed(3)+')';
 var v=ndEl('nd_zoomv'); if(v) v.textContent=Math.round(z.k*100)+'%';
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
function ndZoomPasso(s){
 var p=ndEl('nd_palco'); if(!p) return;
 var r=p.getBoundingClientRect();
 ndZoomEm(ND.zoom.k*(s>0?1.25:0.8), r.width/2, r.height/2);
}
function ndZoomAjustar(){
 ND.zoom={k:1, x:0, y:0}; ndZoomAplicar();
}
function ndRoda(ev){
 if(!ND.b) return;
 if(ev.preventDefault) ev.preventDefault();
 var p=ndEl('nd_palco'), r=p.getBoundingClientRect();
 ndZoomEm(ND.zoom.k*(ev.deltaY<0?1.15:1/1.15), ev.clientX-r.left, ev.clientY-r.top);
}
var ND_ARRASTO=null;
function ndQuerMover(ev){ return !!(ev && (ev.button===1 || ev.shiftKey)) }
function ndPegar(ev){
 if(!ndQuerMover(ev) || ND.zoom.k<=1.001) return;
 if(ev.preventDefault) ev.preventDefault();
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

function ndSincronizar(){
 [['lao','LAO','RAO'],['cra','CRA','CAU']].forEach(function(a){
  var v=ND[a[0]], t=ndEl('nd_'+a[0]), r=ndEl('nd_'+a[0]+'_r'), l=ndEl('nd_'+a[0]+'_v');
  if(t) t.value=String(v);
  if(r) r.value=String(v);
  if(l) l.textContent=ndAng(v, a[1], a[2]);
 });
 var bs=document.querySelectorAll('#nd_incid .nd-bt');
 for(var i=0;i<bs.length;i++)
  bs[i].classList.toggle('on', +bs[i].getAttribute('data-lao')===ND.lao
   && +bs[i].getAttribute('data-cra')===ND.cra);
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
 ndPintarCaixas(); ndRegistrar('recorte');
}
function ndCaixaLimpar(){
 if(!ND.aberta) return;
 ND.caixa=null; ND.caixaOn=false;
 ndSincronizar(); ndPintarCaixas(); ndRegistrar('recorte'); ndProjetar();
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
function ndCaixaMover(ev){
 if(!ND_CX) return;
 var svg=ndEl('nd_cx'+ND_CX.eixo), p=ndPontoNoCorte(svg, ev, ND_CX.eixo);
 var dx=p[0]-ND_CX.p0[0], dy=p[1]-ND_CX.p0[1], r=ND_CX.r0.slice(), h=ND_CX.h;
 if(h.mover){
  dx=Math.max(-r[0], Math.min(1-r[2], dx)); dy=Math.max(-r[1], Math.min(1-r[3], dy));
  r[0]+=dx; r[2]+=dx; r[1]+=dy; r[3]+=dy;
 } else { if(h.a0) r[0]+=dx; if(h.a1) r[2]+=dx; if(h.b0) r[1]+=dy; if(h.b1) r[3]+=dy }
 ndCaixaDoCorte(ND_CX.eixo, r);
 ndPintarCaixas();
}
function ndCaixaSoltar(){
 if(!ND_CX) return;
 ND_CX=null;
 ndRegistrar('recorte');
 ndProjetar();
}

function ndIncidencia(lao,cra,nome){ ndAngulo(lao, cra) }

function ndAngulo(lao, cra){
 if(!ND.aberta) return;
 lao=Math.max(-180, Math.min(180, Math.round(+lao||0)));
 cra=Math.max(-90, Math.min(90, Math.round(+cra||0)));
 if(lao===ND.lao && cra===ND.cra){ ndSincronizar(); return }
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
 ndSincronizar(); ndRegistrar('girar'); ndProjetar();
 if(guardou) ndMsg('o traço da incidência anterior foi guardado antes de girar','ok');
}
function ndPrever(k, v){
 var a=(k==='lao')?['LAO','RAO']:['CRA','CAU'];
 var t=ndEl('nd_'+k), l=ndEl('nd_'+k+'_v');
 if(t) t.value=String(v);
 if(l) l.textContent=ndAng(v, a[0], a[1]);
 ndPedirEixos(k==='lao'?v:ND.lao, k==='cra'?v:ND.cra);
}
function ndMudarAngulo(k, v){
 ndAngulo(k==='lao'?v:ND.lao, k==='cra'?v:ND.cra);
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
  ND.pontos=[]; ndPintarMarca(); return;
 }
 var bruto=ND.pontos.length;
 ND.pontos=ndAfinar(ND.pontos);
 ndPintarMarca(); ndRegistrar('desenhar');
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
 if(mm==null){ e.textContent='—'; return }
 var molde = (ND.lado_util && ND.lado>ND.lado_util)
  ? '%s mm por pixel da projeção — acima do que esta série oferece: o que aparece a mais é interpolação, e não o paciente'
  : '%s mm por pixel da projeção';
 var t = molde.replace('%s', (+mm).toFixed(2).replace('.',','));
 if(window.uiTexto) window.uiTexto(e, t); else e.textContent=t;
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
  if(!auto) ndMsg('circule o ninho antes de guardar (3 pontos, no mínimo)','erro');
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

function ndCor(i){ return 'nd-c'+(i%6); }

function ndPintarGuardadas(){
 var e=ndEl('nd_guardadas'); if(!e) return;
 if(!ND.guardadas.length){
  e.innerHTML='<span class="nd-chip vazio" data-radai-frase>'
   +'nenhuma incidência guardada — gire o gantry, circule o ninho, e guarde'
   +'</span>';
  ndTravas();
  return;
 }
 var h='<ol class="nd-lista">';
 ND.guardadas.forEach(function(g,i){
  h+='<li class="'+ndCor(i)+(g.pendente?' pend':'')+'"><i></i>'
    +'<b>'+ndRotulo(g)+'</b>'
    +'<span class="nd-pt">'+g.pontos.length+' pontos</span>'
    +'<button type="button" class="nd-x" title="tirar esta incidência"'
    +' aria-label="tirar esta incidência" onclick="ndTirar('+i+')">&times;</button>'
    +'</li>';
 });
 h+='</ol>';
 if(ND.teto && ND.guardadas.length >= ND.teto){
  h+='<div class="nd-teto">'+ND.teto+' é o máximo — cada incidência é '
    +'um volume na memória.</div>';
 }
 h+='<button type="button" class="nd-bt" onclick="ndLimparGuardadas()"'
   +' data-radai-frase>Limpar marcação</button>';
 e.innerHTML=h;
 ndTravas();
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
 fetch('/api/nidus/linhas?s='+encodeURIComponent(s)
   +'&eixo='+eixo+'&pos='+ND.planos[eixo])
  .then(function(r){return r.json()}).then(function(d){
   if(s!==ND.sessao) return;
   if(!d || d.erro){
    if(ND.cruzando) return;
    // GUARDA: a sessão que falha é refeita das incidências salvas UMA vez por ato; a segunda falha avisa e para.
    if(ND.guardadas.length && ND.refeitas<1){
     ND.refeitas++; ND.sessao=null; ndCalcular(true); return }
    ndLinhasFalharam((d && d.erro) ? String(d.erro) : 'sem resposta');
    return;
   }
   g.setAttribute('viewBox','0 0 '+d.largura+' '+d.altura);
   var h='';
   (d.camadas||[]).forEach(function(cam){
    var cls = cam.qual==='inter' ? 'nd-inter' : ('nd-tubo '+ndCor(cam.i||0));
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

// GUARDA: o visor quadrado cabe na altura que sobra; os três MPR somam a mesma altura, à direita dele.
function ndAjustarTela(){
 var t=ndEl('nd_trabalho'), p=ndEl('nd_palco');
 if(!t || !p || !t.style || !t.style.setProperty || !t.getBoundingClientRect) return;
 var H=+window.innerHeight||0, W=+window.innerWidth||0;
 if(!H || !W) return;
 var rt=t.getBoundingClientRect(), rp=p.getBoundingClientRect();
 var y=+window.scrollY||0, pe=0;
 var al=document.querySelector ? document.querySelector('.nd-wrap > .ui-alerta') : null;
 if(al && al.getBoundingClientRect) pe=al.getBoundingClientRect().height+16;
 var alto=H-(rt.top+y)-(rp.top-rt.top)-pe-22;
 var largo=(W<1100) ? rt.width : (rt.width-24-230-12)*0.75;
 var s=Math.floor(Math.max(260, Math.min(alto, largo)));
 t.style.setProperty('--nd-h', s+'px');
 var de=document.documentElement;
 var sobra=(de && de.scrollHeight) ? (de.scrollHeight-H) : 0;
 if(sobra>0 && W>=1100) t.style.setProperty('--nd-h', Math.max(260, s-sobra-2)+'px');
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
 });
 window.addEventListener('mousemove', ndCaixaMover);
 window.addEventListener('mouseup', ndCaixaSoltar);
 window.addEventListener('resize', ndAjustarTela);
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
  }
  if(e) e.addEventListener('change', function(){ ndMudarAngulo(k, +e.value||0) });
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
 });
 var ls=ndEl('nd_series');
 if(ls) ls.addEventListener('click', function(ev){
  var b=(ev.target && ev.target.closest) ? ev.target.closest('.nd-it') : null;
  if(b) ndEscolher(+b.getAttribute('data-i')) });
 ndSincronizar(); ndTravas(); ndPintarGuardadas(); ndAjustarTela();
 ndAbrirEscolha();
});
""".replace(u"@LADO@", str(LADO_DA_TELA)).replace(
    u"@MODALIDADES@", json.dumps(list(MODALIDADES)))


def _cabeca():
    import radai_ui
    ajuda = radai_ui.ajuda(
        u"<b>O que esta tela &eacute;, e o que ela n&atilde;o &eacute;.</b>",
        radai_nidus.SEM_VOLUME, radai_nidus.LIMITACAO_CLINICA,
        radai_nidus.LIMITACAO_RM)
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


def pagina():
    return _icones(PAGINA.replace("@CSS@", CSS)
                   .replace("@ESCOLHA@", _escolha())
                   .replace("@CARTAO@", _cartao())
                   .replace("@JS@", JS)
                   .replace("@CABECA@", _cabeca())
                   .replace("@ALERTA@", _alerta())
                   .replace("@INCIDENCIAS@", _incidencias()),
                   (u"pasta", u"zoom_mais", u"zoom_menos", u"inverter",
                    u"caixa", u"lapis", u"cubo"))


def _incidencias():
    return u"".join(
        u'<button type="button" class="nd-bt%s" data-nome="%s" data-lao="%s" '
        u'data-cra="%s" onclick="ndIncidencia(%s,%s,\'%s\')">%s</button>'
        % (u" on" if i == 0 else u"", nome, int(lao), int(cra), lao, cra,
           nome, nome)
        for i, (nome, lao, cra) in enumerate(radai_nidus.INCIDENCIAS))


PAGINA = u"""<!doctype html><html><head><meta charset="utf-8">
<title>Proje&ccedil;&atilde;o Vascular &middot; Nidus RT</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>@CSS@</style></head><body><div class="nd-wrap">

@CABECA@

<section class="nd-ferramentas" id="nd_cmd" aria-label="ferramentas">
 <div class="nd-linha">
  <div class="nd-grupo">
   <span class="t" data-radai-frase>incid&ecirc;ncia</span>
   <div class="g" id="nd_incid">@INCIDENCIAS@</div>
  </div>
  <div class="nd-grupo nd-angulo">
   <label class="t" for="nd_lao_r" data-radai-frase>LAO/RAO</label>
   <input type="range" id="nd_lao_r" min="-180" max="180" step="1" value="0"
    aria-label="LAO/RAO">
   <input type="text" class="nd-ang" id="nd_lao" value="0" inputmode="numeric"
    aria-label="LAO/RAO">
   <span class="nd-angv" id="nd_lao_v">LAO 0°</span>
  </div>
  <div class="nd-grupo nd-angulo">
   <label class="t" for="nd_cra_r" data-radai-frase>CRA/CAU</label>
   <input type="range" id="nd_cra_r" min="-90" max="90" step="1" value="0"
    aria-label="CRA/CAU">
   <input type="text" class="nd-ang" id="nd_cra" value="0" inputmode="numeric"
    aria-label="CRA/CAU">
   <span class="nd-angv" id="nd_cra_v">CRA 0°</span>
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
   <div class="g nd-laje"><span class="sub" data-radai-frase>laje</span>
    <input type="range" id="nd_laje" min="0" max="120" value="0"
     aria-label="espessura da laje">
    <span class="sub" id="nd_lajev" data-radai-frase>todo o volume</span></div>
  </div>
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
  <div class="nd-grupo">
   <span class="t" data-radai-frase>recorte</span>
   <div class="g">
    <button type="button" class="nd-bt" id="nd_caixa_bt" onclick="ndCaixaModo()"
     aria-pressed="false">@ICO_CAIXA@<span data-radai-frase>Caixa de recorte</span></button>
    <button type="button" class="nd-bt" id="nd_caixa_limpar" onclick="ndCaixaLimpar()"
     data-radai-frase>Limpar recorte</button></div>
  </div>
  <div class="nd-grupo">
   <span class="nd-lapis" title="arraste contornando o ninho · soltar fecha a área">@ICO_LAPIS@<span
    data-radai-frase>l&aacute;pis</span></span>
   <button type="button" class="nd-bt" id="nd_bt_guardar" onclick="ndGuardar()"
    data-radai-frase>Guardar incid&ecirc;ncia</button>
  </div>
 </div>
</section>

<div id="nd_msg" role="status"></div>

<div class="nd-trabalho" id="nd_trabalho">

 <section class="nd-cx nd-proj" aria-label="proje&ccedil;&atilde;o">
  <div class="rot"><span data-radai-frase>proje&ccedil;&atilde;o</span>
   <b id="nd_rot_proj">&mdash;</b></div>
  <div class="nd-palco inv" id="nd_palco">
   <div class="nd-zoom" id="nd_zoom">
    <img id="nd_proj" alt="" draggable="false">
    <svg id="nd_svg" viewBox="0 0 1024 1024" preserveAspectRatio="xMidYMid meet">
     <g id="nd_marca"></g>
    </svg>
   </div>
   <div class="nd-ferr-palco">
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
 </section>

 <section class="nd-cx nd-mpr" id="nd_mpr" aria-label="MPR">
  <div class="rot"><span>MPR <b id="nd_mod"></b></span></div>
  <div class="nd-planos">
   <div class="p"><span>axial</span>
    <div class="nd-palco" id="nd_pp0"><img id="nd_pl0" alt="" draggable="false">
     <svg id="nd_lin0" preserveAspectRatio="xMidYMid meet"></svg>
     <svg class="nd-cx-svg" id="nd_cx0" preserveAspectRatio="xMidYMid meet"></svg></div>
    <input type="range" id="nd_pos0" min="0" max="100" value="50"
     aria-label="corte axial"></div>
   <div class="p"><span>coronal</span>
    <div class="nd-palco" id="nd_pp1"><img id="nd_pl1" alt="" draggable="false">
     <svg id="nd_lin1" preserveAspectRatio="xMidYMid meet"></svg>
     <svg class="nd-cx-svg" id="nd_cx1" preserveAspectRatio="xMidYMid meet"></svg></div>
    <input type="range" id="nd_pos1" min="0" max="100" value="50"
     aria-label="corte coronal"></div>
   <div class="p"><span>sagital</span>
    <div class="nd-palco" id="nd_pp2"><img id="nd_pl2" alt="" draggable="false">
     <svg id="nd_lin2" preserveAspectRatio="xMidYMid meet"></svg>
     <svg class="nd-cx-svg" id="nd_cx2" preserveAspectRatio="xMidYMid meet"></svg></div>
    <input type="range" id="nd_pos2" min="0" max="100" value="50"
     aria-label="corte sagital"></div>
  </div>
 </section>

 <aside class="nd-cx nd-lado" id="nd_lado" aria-label="s&eacute;rie e marca&ccedil;&atilde;o">
  <div class="nd-grupo">
   @CARTAO@
   <div class="g"><button type="button" class="nd-bt" id="nd_bt_retomar" onclick="ndRetomar()" hidden
     data-radai-frase>Tentar de novo</button></div>
   <span class="sub" id="nd_passo">&mdash;</span>
   <span class="sub" id="nd_escala"></span>
  </div>
  <div class="nd-grupo">
   <span class="t" data-radai-frase>incid&ecirc;ncias guardadas</span>
   <span class="sub" data-radai-frase>arraste contornando o ninho &middot; soltar
    fecha a &aacute;rea &middot; Shift ou o bot&atilde;o do meio movem a imagem
    ampliada</span>
   <div class="nd-guardadas" id="nd_guardadas"></div>
   <button type="button" class="nd-bt" id="nd_bt_cruzar" onclick="ndCalcular()" hidden
    data-radai-frase>Cruzar de novo</button>
  </div>
  <div class="nd-grupo nd-osso">
   <span class="t" data-radai-frase>osso</span>
   <span class="sub" id="nd_osso_txt"></span>
   <div class="g">
    <button type="button" class="nd-bt" id="nd_osso_bt" onclick="ndOssoAlternar()" hidden
     aria-pressed="false">@ICO_CUBO@<span data-radai-frase>Tirar o osso</span></button>
    <button type="button" class="nd-bt" id="nd_segmentar" onclick="ndSegmentar()" hidden><span
     id="nd_segmentar_txt" data-radai-frase>Segmentar primeiro (AUTO)</span></button></div>
   <span class="sub" data-radai-frase>vaso colado ao osso pode sair junto com ele:
    confira com o osso &agrave; mostra</span>
  </div>
  <div class="nd-grupo">
   <p class="nd-legenda"><b data-radai-frase>linhas finas: o que foi retroprojetado</b></p>
   <p class="nd-legenda"><span data-radai-frase>A cor de cada linha diz de qual
    incid&ecirc;ncia ela veio. A linha mais forte &eacute; onde as duas se
    cruzam.</span></p>
  </div>
 </aside>

</div>

@ALERTA@

@ESCOLHA@

</div>
<script>@JS@</script>
</body></html>"""


def _escolha():
    import radai_tabela_acervo
    import radai_ui
    pasta = (u'<div class="nd-pasta"><input type="text" id="nd_pasta" '
             u'spellcheck="false" autocomplete="off" aria-label="pasta" '
             u'placeholder="C:\\... ou \\\\servidor\\...">'
             u'<button type="button" class="ui-bt" id="nd_procurar">'
             u'@ICO_PASTA@<span data-radai-frase>Procurar&hellip;</span>'
             u'</button><button type="button" class="ui-bt pri" id="nd_listar" '
             u'onclick="ndOutra()"><span data-radai-frase>Listar s&eacute;ries'
             u'</span></button></div>'
             u'<div class="nd-series" id="nd_series" role="listbox" '
             u'aria-label="s&eacute;ries da pasta"></div>')
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


_PALAVRAS_DE_VASO = (u"arter", u"vein", u"vena", u"vessel", u"carotid",
                     u"aorta", u"jugular", u"sinus")


def e_osso(nome):
    import engine
    n = str(nome or u"").lower()
    # GUARDA: vaso nunca sai da projeção, ainda que o nome traga palavra de osso (A_Vertebral).
    if n.startswith((u"a_", u"v_")) or any(p in n for p in _PALAVRAS_DE_VASO):
        return False
    return engine.familia_de(n) == "osso"


def _pastas_da_serie(pasta, uid):
    fora, vistos = [], set()

    def por(p):
        if not p:
            return
        k = os.path.normcase(os.path.abspath(p))
        if k in vistos or not os.path.isdir(p):
            return
        vistos.add(k)
        fora.append(p)
    por(pasta)
    if uid:
        try:
            import radai_archive
            for reg in radai_archive.ler_acervo():
                if str(reg.get("uid") or u"") == str(uid):
                    por(radai_archive.resolver_pasta(reg.get("pasta") or u""))
        except Exception:
            pass
    return fora


def _entrega_da_serie(pastas, uid):
    try:
        import radai_sets
        import radai_viewseg as V
    except Exception:
        return u""
    for p in pastas:
        try:
            nomes = os.listdir(p)
        except Exception:
            continue
        for n in sorted(radai_sets.arquivos_da_serie(nomes, uid)):
            r = V.rotulo_do_arquivo(n)
            if r.get("entregue"):
                return str(r.get("curto") or u"")
    return u""


def osso_da_segmentacao(serie, pasta, uid):
    import radai_viewseg as V
    uid = str(uid or u"")
    if not uid:
        return None, {"tem": False, "motivo": SEM_UID}
    forma = tuple(serie.forma_do_array)
    pastas = _pastas_da_serie(pasta, uid)
    for p in pastas:
        # GUARDA: FULL e OAR têm o osso exato; o OAR_Fast (contorno reduzido) só entra sem eles e sem o mapa.
        for conjuntos, com_mapa in ORDEM_DO_OSSO:
            m, info = V.mascaras_da_serie(p, uid, serie.img, aceita=e_osso,
                                          conjuntos=conjuntos,
                                          com_mapa=com_mapa)
            if m is None or tuple(m.shape) != forma:
                continue
            return m, {"tem": True, "fonte": info.get("fonte") or u"",
                       "estruturas": int(info.get("estruturas") or 0)}
    entrega = _entrega_da_serie(pastas, uid)
    if entrega:
        return None, {"tem": False, "motivo": SEM_OSSO_NA_ENTREGA,
                      "entrega": entrega}
    return None, {"tem": False, "motivo": SEM_SEGMENTACAO}


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


def montar(app):
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

    @app.post("/api/nidus/series")
    async def _series(request: Request):
        try:
            c = await request.json() or {}
            import radai_config
            import radai_dicom
            import radai_thumbnail
            pasta = str(c.get("pasta") or "").strip() or radai_config.root_configurado()
            if not pasta:
                return {"series": [],
                        "erro": u"A pasta dos exames ainda não foi configurada: "
                                u"escolha uma pasta com «Procurar…»."}
            b = await radai_web.no_threadpool(
                radai_dicom.buscar_series, radai_dicom.caminho_longo(pasta),
                None, MODALIDADES, MIN_CORTES)
            out = [{"bilhete": radai_thumbnail.bilhete(s["pasta"], s["uid"]),
                    "curto": s["uid"][-12:], "modalidade": s["modalidade"],
                    "desc": s["descricao"], "cortes": s["cortes"],
                    "espessura_mm": s["espessura_mm"]}
                   for s in sorted(b["series"],
                                   key=lambda x: (x["data"], x["descricao"]))]
            return {"series": out,
                    "erro": u"" if out else u"nenhuma série nesta pasta",
                    "avisos": radai_dicom.avisos_da_busca(b)}
        except Exception as e:
            return {"series": [],
                    "erro": u"%s: %s" % (type(e).__name__, str(e)[:200])}

    def _abrir(b, resolvido=None):
        try:
            t0 = time.perf_counter()
            serie = _serie(b, resolvido)
            if serie is None:
                return {"erro": u"recarregue a lista de séries"}
            _ERROS.pop(str(b), None)
            return {"forma": list(serie.forma),
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
    def _linhas(s: str = "", eixo: int = 0, pos: float = 0.5):
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
            return {"altura": alt, "largura": larg,
                    "camadas": camadas, "corte": i, "n": n,
                    "incidencias": len(ses["tubos"])}
        except Exception as e:
            return {"erro": u"%s: %s" % (type(e).__name__, str(e)[:200])}

    return app
