# -*- coding: utf-8 -*-
import itertools
import os

import radai_menu
import radai_nidus
import radai_web

LADOS = (256, 512, 768, radai_nidus.LADO_ALTA)

MODALIDADES = ("CT", "MR")

CSS = u"""
.nd-wrap{max-width:1440px;margin:0 auto;padding:0 18px 40px}
.nd-escolha{display:flex;gap:14px 18px;align-items:flex-end;flex-wrap:wrap;
 margin:0 0 10px;padding:14px 16px;background:var(--panel);
 border:1px solid var(--line);border-radius:var(--r-2xl,12px)}
.nd-campo{display:flex;flex-direction:column;gap:6px;min-width:0}
.nd-campo.pasta{flex:1 1 420px}
.nd-campo.serie{flex:1 1 380px}
.nd-campo > label{font:400 10px/1 var(--font-mono,monospace);letter-spacing:.14em;
 text-transform:uppercase;color:var(--text-dim)}
.nd-par-linha{display:flex;gap:8px;align-items:center;min-width:0}
.nd-par-linha input[type=text],.nd-par-linha select{flex:1 1 auto;min-width:0;
 height:34px;box-sizing:border-box;padding:0 10px;border-radius:var(--r-md,6px);
 border:1px solid var(--line-strong);background:var(--panel-2);color:var(--text);
 font-size:12.5px}
.nd-par-linha input[type=text]{font-family:var(--font-mono,monospace)}
.nd-par-linha input:focus,.nd-par-linha select:focus{outline:0;border-color:var(--accent)}
.nd-par-linha .ui-bt{height:34px;white-space:nowrap;flex:none}
.nd-demo{display:inline-flex;align-items:center;gap:6px;flex:none;
 font:400 10px/1 var(--font-mono,monospace);letter-spacing:.16em;color:var(--warn);
 border:1px solid currentColor;border-radius:var(--r-pill,999px);padding:4px 4px 4px 9px}
.nd-demo[hidden]{display:none}
#nd_msg{min-height:20px}

.nd-trabalho{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:16px;
 align-items:start;margin-top:6px}
@media (max-width:1100px){.nd-trabalho{grid-template-columns:1fr}}
.nd-proj .nd-palco{width:min(100%,calc(100vh - 150px));margin:0 auto}
.nd-zoom{position:absolute;inset:0;transform-origin:0 0;will-change:transform}
.nd-palco.inv{background:#fff}
.nd-palco.inv .nd-zoom img{filter:invert(1)}
.nd-palco.pegavel{cursor:grab}
.nd-palco.arrastando{cursor:grabbing}
.nd-ferr-palco{position:absolute;top:8px;right:8px;z-index:3;display:flex;gap:4px}
.nd-ferr-palco .nd-bt{background:rgba(6,13,26,.74);border-color:rgba(230,237,247,.16);
 color:#cfd8e6}
.nd-ferr-palco .nd-bt:hover{color:#fff;border-color:rgba(230,237,247,.4)}
.nd-bt.nd-ic{width:30px;padding:0;display:inline-flex;align-items:center;
 justify-content:center;font-size:15px}
.nd-zoomv{position:absolute;left:8px;top:8px;z-index:3;
 font:400 10px/1 var(--font-mono,monospace);color:#cfd8e6;
 background:rgba(0,0,0,.55);padding:4px 6px;border-radius:4px;pointer-events:none}
.nd-ferr-palco .ui-ic{position:static;inset:auto;width:1em;height:1em;
 pointer-events:none}
.nd-palco .nd-eixos{position:absolute;inset:auto 6px 6px auto;width:84px;height:84px;
 z-index:3;pointer-events:none}
.nd-eixos line{stroke:#8fa6c8;stroke-width:1.5;stroke-linecap:round}
.nd-eixos text{fill:#dce6f5;font:600 11px var(--font-mono,monospace);
 text-anchor:middle;dominant-baseline:central}
.nd-palco.inv .nd-eixos line{stroke:#46607f}
.nd-palco.inv .nd-eixos text{fill:#1b2a40}

.nd-cmd{display:flex;flex-direction:column;background:var(--panel);
 border:1px solid var(--line);border-radius:var(--r-2xl,12px);padding:4px 14px}
.nd-grupo{display:flex;flex-direction:column;gap:7px;padding:11px 0;
 border-bottom:1px solid var(--line)}
.nd-grupo:last-child{border-bottom:0}
.nd-grupo > .t{font:400 10px/1 var(--font-mono,monospace);letter-spacing:.14em;
 text-transform:uppercase;color:var(--text-dim)}
.nd-grupo .g{display:flex;gap:5px;align-items:center;flex-wrap:wrap}
.nd-grupo .g label{font-size:11px;color:var(--text-dim)}
.nd-grupo .sub{font-size:11px;color:var(--text-dim);line-height:1.5}
.nd-grupo input[type=range]{flex:1 1 90px;min-width:80px}
.nd-cmd .nd-guardadas{margin:0;padding:0;border:0}

.nd-mpr{margin-top:16px}
.nd-mpr .nd-planos{grid-template-columns:repeat(3,minmax(0,1fr))}
@media (max-width:900px){.nd-mpr .nd-planos{grid-template-columns:1fr}}
.nd-legenda{font-size:11.5px;color:var(--text-dim);margin:8px 0 0;line-height:1.55}
.nd-cx-svg{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}
.nd-cx-svg.on{pointer-events:auto;cursor:crosshair}
.nd-caixa{fill:rgba(227,155,79,.07);stroke:var(--mod-nidus,#E39B4F);stroke-width:1.5;
 stroke-dasharray:6 4;vector-effect:non-scaling-stroke}
.nd-cx-svg.on .nd-caixa{stroke-dasharray:none}
.nd-alca{fill:var(--mod-nidus,#E39B4F)}
.nd-cx{border:1px solid var(--line);border-radius:var(--r-xl,11px);
 padding:11px;background:var(--panel)}
.nd-cx > .rot{font-family:var(--font-mono,monospace);font-size:10px;
 letter-spacing:.11em;text-transform:uppercase;color:var(--text-dim);
 display:flex;justify-content:space-between;align-items:baseline;gap:10px;
 margin-bottom:8px}
.nd-cx > .rot b{font-weight:400;color:var(--text-muted)}

.nd-palco{position:relative;background:#000;border-radius:var(--r-lg,8px);
 overflow:hidden;aspect-ratio:1/1;display:flex;align-items:center;
 justify-content:center}
.nd-palco img{width:100%;height:100%;object-fit:contain;display:block;
 image-rendering:pixelated;user-select:none}
.nd-palco svg{position:absolute;inset:0;width:100%;height:100%;
 pointer-events:none}
.nd-palco.desenhando{cursor:crosshair}
.nd-palco.desenhando svg{pointer-events:auto}

.nd-tubo{fill:none;stroke-width:1.1;vector-effect:non-scaling-stroke;
 opacity:.85}
.nd-c0{stroke:var(--mod-nidus,#E39B4F)}
.nd-c1{stroke:var(--mod-nidus-b,#7FD1D6)}
.nd-c2{stroke:#B886F0}
.nd-c3{stroke:#6FD08C}
.nd-c4{stroke:#F0846F}
.nd-c5{stroke:#D8C24F}
.nd-inter{fill:none;stroke:var(--accent,#4DA3FF);stroke-width:2;
 vector-effect:non-scaling-stroke}

.nd-lista{list-style:none;margin:0 0 8px;padding:0;display:flex;
 flex-direction:column;gap:4px;max-height:190px;overflow-y:auto}
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
.nd-pt{color:var(--text-dim,#72829b);margin-left:auto;font-size:10.5px}
.nd-x{background:none;border:0;color:var(--text-dim,#72829b);cursor:pointer;
 font-size:15px;line-height:1;padding:0 2px}
.nd-x:hover{color:var(--perigo,#E96A5C)}
.nd-teto{font-size:10.5px;color:var(--aviso,#E8A33D);margin:0 0 8px}
.nd-marca{fill:none;stroke:var(--mod-nidus,#E39B4F);stroke-width:1.4;
 stroke-dasharray:5 4;vector-effect:non-scaling-stroke}

.nd-planos{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}
.nd-planos .nd-palco{aspect-ratio:1/1}
.nd-planos .p{position:relative}
.nd-planos .p > span{position:absolute;left:6px;top:5px;z-index:2;
 font-family:var(--font-mono,monospace);font-size:9.5px;color:#cfd8e6;
 background:rgba(0,0,0,.6);padding:1px 5px;border-radius:4px}
.nd-planos input[type=range]{width:100%;margin-top:6px}

.nd-ctrl{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:10px 0}
.nd-ctrl .g{display:flex;gap:5px;align-items:center}
.nd-bt{font-size:11px;padding:4px 10px;border-radius:var(--r-md,7px);
 cursor:pointer;border:1px solid var(--line);background:var(--panel);
 color:var(--text-dim);min-height:28px}
.nd-bt.on{border-color:var(--accent);color:var(--accent)}
.nd-bt:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.nd-ang{width:66px;text-align:right;font-family:var(--font-mono,monospace)}

.nd-guardadas{display:flex;gap:10px;flex-wrap:wrap;align-items:center;
 margin-top:14px;padding-top:12px;border-top:1px solid var(--line)}
.nd-chip{display:inline-flex;align-items:center;gap:7px;font-size:11.5px;
 padding:5px 11px;border-radius:var(--r-pill,999px);border:1px solid var(--line);
 background:var(--panel-2,#0f1729)}
.nd-chip i{width:8px;height:8px;border-radius:50%;font-style:normal;flex:none}
.nd-chip.a i{background:var(--mod-nidus,#E39B4F)}
.nd-chip.b i{background:var(--mod-nidus-b,#7FD1D6)}
.nd-chip.vazio{color:var(--text-dim);border-style:dashed}

.nd-fronteira{margin-top:18px;font-size:11.5px;color:var(--text-dim);
 border-left:2px solid var(--line);padding-left:11px;line-height:1.6}
.nd-fronteira b{color:var(--text-muted)}
#nd_msg{font-size:12px;line-height:1.55;margin-top:10px}
#nd_msg.erro{color:var(--perigo,#E96A5C)}
#nd_msg.ok{color:var(--success,#5BC57F)}
"""

JS = u"""
var ND = {b:'', lista:[], lado:512, jan:'angio', modo:'mip',
          lao:0, cra:0, laje:0,
          desenhando:false, ferramenta:'clique', tracando:false,
          pontos:[], guardadas:[], sessao:null,
          planos:{0:0.5,1:0.5,2:0.5}, forma:null,
          passos:null, lado_util:0,
          zoom:{k:1, x:0, y:0}, inverter:false,
          caixa:null, caixaOn:false, telas:null, abrindo:false};

var ND_EPS = 0.5, ND_TETO_VERTICES = 120, ND_PASSO_MIN = 0.6;

function ndEl(i){ return document.getElementById(i) }
function ndEsc(t){ return String(t==null?'':t).replace(/&/g,'&amp;')
 .replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;') }
function ndMsg(t,c){ var e=ndEl('nd_msg'); if(!e) return;
 if(window.uiTexto) window.uiTexto(e, t); else e.textContent=t;
 e.className=c||'' }

function ndListar(pasta){
 var sel=ndEl('nd_serie');
 sel.innerHTML='<option value="">carregando…</option>';
 fetch('/api/nidus/series',{method:'POST',
   headers:{'Content-Type':'application/json'},
   body:JSON.stringify({pasta:pasta||''})})
  .then(function(r){return r.json()}).then(function(d){
   ND.lista=d.series||[];
   if(!ND.lista.length){ sel.innerHTML='<option value="">—</option>';
    ndMsg(d.erro||'nenhuma série nesta pasta','erro'); return }
   if(d.erro) ndMsg(d.erro,'');
   sel.innerHTML=ND.lista.map(function(s,i){
    var molde=(s.espessura_mm!=null)?'%s · %s cortes · %s mm':'%s · %s cortes';
    var vs=[ndEsc(s.desc||s.curto||'série'), s.cortes, s.espessura_mm];
    return '<option value="'+i+'">'
      +(s.demo?'DEMO · ':'')
      +(s.modalidade?(ndEsc(s.modalidade)+' · '):'')
      +molde.replace(/%s/g,function(){ return vs.shift() })+'</option>';
   }).join('');
   if(window.radaiRetraduzir) window.radaiRetraduzir();
   sel.value='0'; ndEscolher();
  }).catch(function(e){ ndMsg('não consegui listar: '+e,'erro') });
}

function ndEscolher(){
 var s=ND.lista[+ndEl('nd_serie').value]; if(!s) return;
 ND.b=s.bilhete; ND.guardadas=[]; ND.pontos=[]; ND.forma=null;
 ND.sessao=null; ND.tracando=false; ND.passos=null; ND.lado_util=0;
 ND.caixa=null; ND.telas=null; ND.abrindo=true;
 ndDemo(s); ndModalidade(s.modalidade); ndZoomAjustar(); ndPintarCaixas();
 // GUARDA: a imagem da série anterior sai já; sob o carregamento ela pareceria a nova.
 ['nd_proj','nd_pl0','nd_pl1','nd_pl2'].forEach(function(i){
  var im=ndEl(i); if(im && im.removeAttribute) im.removeAttribute('src') });
 ndCarregando(true);
 [0,1,2].forEach(function(eixo){ ndLinhas(eixo) });
 ndPasso(); ndEscala(null);
 ndMsg('abrindo a série…','');
 fetch('/api/nidus/forma?b='+encodeURIComponent(ND.b))
  .then(function(r){return r.json()}).then(function(d){
   if(d && d.erro){
    ND.forma=null; ND.abrindo=false; ndCarregando(false);
    ndMsg(String(d.erro),'erro');
    return;
   }
   ND.forma=(d&&d.forma)||null;
   if(!ND.forma){ ND.abrindo=false; ndCarregando(false);
    ndMsg('a série não pôde ser lida.','erro'); return }
   ND.telas=(d&&d.telas)||null;
   if(d && d.modalidade) ndModalidade(d.modalidade);
   ND.passos=(d&&d.passos)||null; ND.lado_util=(d&&d.lado_util)||0;
   ndPasso();
   ndEscala(d);
   ndMsg('série aberta — escolha a incidência e circule a área','');
   ndProjetar(); ndPintarPlanos();
  })
  .catch(function(e){ ND.forma=null; ND.abrindo=false; ndCarregando(false);
   ndMsg('não consegui abrir: '+e,'erro') });
 ndPintarGuardadas();
}

function ndDemo(s){
 var t=ndEl('nd_demo'), b=ndEl('nd_demo_bal'); if(!t) return;
 if(!s || !s.demo){ t.hidden=true; return }
 t.hidden=false;
 if(b) b.innerHTML='<p>'+ndEsc(s.titulo||'')+'</p><p>'+ndEsc(s.licenca||'')+'</p><p>'
   +ndEsc(s.atribuicao||'')+'</p>';
}

function ndModalidade(m){
 var e=ndEl('nd_mod'); if(e) e.textContent=m?String(m):'';
}

// GUARDA: o carregamento espera 250 ms para não piscar a cada grau girado.
var ND_T_CARGA=null;
function ndCarregando(liga, alvo){
 var e=alvo||ndEl('nd_palco');
 if(ND_T_CARGA && !alvo){ clearTimeout(ND_T_CARGA); ND_T_CARGA=null }
 if(!e || !window.uiCarregando) return;
 if(!liga){ window.uiCarregando(e, false); return }
 var txt=ND.abrindo?'abrindo a série…':'projetando…';
 if(alvo){ window.uiCarregando(e, true, txt); return }
 ND_T_CARGA=setTimeout(function(){ window.uiCarregando(e, true, txt) }, 250);
}

function ndProjetar(){
 if(!ND.b) return;
 var img=ndEl('nd_proj');
 img.onerror=function(){ img.removeAttribute('src'); ND.abrindo=false;
  ndCarregando(false) };
 img.onload=function(){ ND.abrindo=false; ndCarregando(false) };
 ndCarregando(true);
 img.src='/api/nidus/projecao?b='+encodeURIComponent(ND.b)
   +'&lao='+ND.lao+'&cra='+ND.cra+'&modo='+ND.modo+'&janela='+ND.jan
   +'&lado='+ND.lado+(ND.laje?('&laje='+ND.laje):'')
   +((ND.caixa && !ndCaixaCheia(ND.caixa))?('&caixa='+ND.caixa.map(function(v){ return v.toFixed(4) }).join(',')):'');
 var r=ndEl('nd_rot_proj');
 if(r) r.textContent='LAO/RAO '+ND.lao.toFixed(0)+'°  ·  CRA/CAU '
   +ND.cra.toFixed(0)+'°  ·  '+ND.modo.toUpperCase();
 ndPedirEixos();
}

// GUARDA: os eixos vêm de `radai_nidus.eixos_da_incidencia`, a mesma rotação da projeção.
function ndPedirEixos(){
 var lao=ND.lao, cra=ND.cra;
 fetch('/api/nidus/eixos?lao='+lao+'&cra='+cra)
  .then(function(r){return r.json()}).then(function(d){
   if(lao===ND.lao && cra===ND.cra) ndEixos(d);
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
 var p=ndEl('nd_palco');
 if(p) p.classList.toggle('pegavel', z.k>1.001 && !ND.desenhando);
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
function ndPegar(ev){
 if(ND.desenhando || ND.zoom.k<=1.001) return;
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

function ndInverter(){
 ND.inverter=!ND.inverter;
 var p=ndEl('nd_palco'), b=ndEl('nd_inverter');
 if(p) p.classList.toggle('inv', ND.inverter);
 if(b){ b.classList.toggle('on', ND.inverter);
  b.setAttribute('aria-pressed', ND.inverter?'true':'false') }
}

// GUARDA: `ND.caixa` = [s0,s1,p0,p1,l0,l1] em fração da vista S-P-L, a ordem de `radai_nidus.caixa_de_texto`.
function ndCaixaModo(){
 ND.caixaOn=!ND.caixaOn;
 if(ND.caixaOn && !ND.caixa) ND.caixa=[0,1,0,1,0,1];
 var b=ndEl('nd_caixa_bt');
 if(b){ b.classList.toggle('on', ND.caixaOn);
  b.setAttribute('aria-pressed', ND.caixaOn?'true':'false') }
 if(ND.caixaOn) ndMsg('arraste as bordas da caixa nos três planos: a projeção mostra só o que fica dentro dela','');
 ndPintarCaixas();
}
function ndCaixaLimpar(){
 ND.caixa=null; ND.caixaOn=false;
 var b=ndEl('nd_caixa_bt');
 if(b){ b.classList.remove('on'); b.setAttribute('aria-pressed','false') }
 ndPintarCaixas(); ndProjetar();
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
  svg.classList.toggle('on', !!(ND.caixaOn && t));
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
 if(!ND.caixaOn || !ND.telas || !ND.caixa) return;
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
 ndProjetar();
}

function ndResolucao(v){
 ND.lado = +v;
 ndGradeDoDesenho();
 ndPasso();
 var bs = document.querySelectorAll('#nd_res .nd-bt');
 for(var i=0;i<bs.length;i++){
  bs[i].className = 'nd-bt' + ((+bs[i].getAttribute('data-r') === ND.lado) ? ' on' : '');
 }
 if(ND.pontos && ND.pontos.length){
  ND.pontos = [];
  ndPintarMarca();
  ndMsg('a resolução mudou: o desenho foi limpo, porque os vértices eram '
        + 'da grade anterior', '');
 }
 ndProjetar();
}

function ndIncidencia(lao,cra,nome){
 ND.lao=+lao; ND.cra=+cra;
 ndEl('nd_lao').value=ND.lao; ndEl('nd_cra').value=ND.cra;
 ND.pontos=[]; ndPintarMarca();
 ndProjetar();
 var bts=document.querySelectorAll('#nd_incid .nd-bt');
 for(var i=0;i<bts.length;i++)
  bts[i].classList.toggle('on', bts[i].getAttribute('data-nome')===nome);
}

function ndGradeDoDesenho(){
 var svg=ndEl('nd_svg'); if(!svg) return;
 svg.setAttribute('viewBox','0 0 '+ND.lado+' '+ND.lado);
}

function ndFerramenta(f){
 ND.ferramenta = (f==='lapis') ? 'lapis' : 'clique';
 ND.tracando=false; ND.pontos=[]; ndPintarMarca();
 var bs=document.querySelectorAll('#nd_ferr .nd-bt');
 for(var i=0;i<bs.length;i++)
  bs[i].classList.toggle('on', bs[i].getAttribute('data-f')===ND.ferramenta);
 var c=ndEl('nd_dica_clique'), l=ndEl('nd_dica_lapis');
 if(c) c.style.display = (ND.ferramenta==='clique') ? '' : 'none';
 if(l) l.style.display = (ND.ferramenta==='lapis') ? '' : 'none';
 if(ND.desenhando) ndMsg(ndComoDesenhar(),'');
}

function ndComoDesenhar(){
 return ND.ferramenta==='lapis'
  ? 'arraste contornando o ninho · soltar fecha o traço'
  : 'clique para marcar os vértices · duplo clique fecha a área';
}

function ndDesenhar(){
 ND.desenhando=!ND.desenhando;
 ND.tracando=false;
 ndEl('nd_palco').classList.toggle('desenhando', ND.desenhando);
 ndEl('nd_bt_desenhar').classList.toggle('on', ND.desenhando);
 if(ND.desenhando){ ND.pontos=[]; ndPintarMarca(); ndMsg(ndComoDesenhar(),'') }
 ndZoomAplicar();
}

function ndPonto(ev){
 var svg=ndEl('nd_svg'), r=svg.getBoundingClientRect();
 return [(ev.clientX-r.left)/r.width*ND.lado,
         (ev.clientY-r.top)/r.height*ND.lado];
}

function ndClique(ev){
 if(!ND.desenhando || ND.ferramenta!=='clique') return;
 ND.pontos.push(ndPonto(ev)); ndPintarMarca();
}

function ndPressionar(ev){
 if(!ND.desenhando || ND.ferramenta!=='lapis') return;
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
 ndPintarMarca();
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

function ndFechar(){
 ndGuardar();
}

function ndPintarMarca(){
 var g=ndEl('nd_marca'); if(!g) return;
 var r=ND.lado/128;
 if(ND.pontos.length<2){ g.innerHTML=ND.pontos.length
   ? '<circle cx="'+ND.pontos[0][0]+'" cy="'+ND.pontos[0][1]
     +'" r="'+r+'" class="nd-marca"/>' : ''; return }
 var aberto = (ND.ferramenta==='lapis') ? ND.tracando : ND.desenhando;
 var d=ND.pontos.map(function(p,i){ return (i?'L':'M')+p[0]+' '+p[1] }).join(' ');
 g.innerHTML='<path d="'+d+(aberto?'':' Z')+'" class="nd-marca"/>';
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

function ndGuardar(){
 if(!ND.pontos || ND.pontos.length < 3){
  ndMsg('circule o ninho antes de guardar (3 pontos, no mínimo)','erro');
  return;
 }
 ND.desenhando=false; ND.tracando=false;
 ndEl('nd_palco').classList.remove('desenhando');
 ndEl('nd_bt_desenhar').classList.remove('on');
 ndZoomAplicar();
 ND.guardadas.push({lao:ND.lao, cra:ND.cra, pontos:ND.pontos.slice()});
 ND.pontos=[]; ndPintarMarca();
 ndPintarGuardadas();
 ndMsg('incidência '+ND.guardadas.length+' guardada — LAO '
   +ND.lao.toFixed(0)+'° / CRA '+ND.cra.toFixed(0)+'°','ok');
 ndCalcular();
}

function ndLimparGuardadas(){
 ND.guardadas=[]; ND.pontos=[]; ND.sessao=null;
 ndPintarMarca(); ndPintarGuardadas();
 ndPintarPlanos(); ndMsg('marcação limpa','');
}

function ndTirar(i){
 ND.guardadas.splice(i,1);
 ndPintarGuardadas();
 if(ND.guardadas.length){ ndCalcular(); }
 else { ND.sessao=null; ndPintarPlanos(); ndMsg('marcação limpa',''); }
}

function ndCor(i){ return 'nd-c'+(i%6); }

function ndPintarGuardadas(){
 var e=ndEl('nd_guardadas'); if(!e) return;
 if(!ND.guardadas.length){
  e.innerHTML='<span class="nd-chip vazio" data-radai-frase>'
   +'nenhuma incidência guardada — gire o gantry, circule o ninho, e guarde'
   +'</span>';
  return;
 }
 var h='<ol class="nd-lista">';
 ND.guardadas.forEach(function(g,i){
  h+='<li class="'+ndCor(i)+'"><i></i>'
    +'<b>LAO '+g.lao.toFixed(0)+'° / CRA '+g.cra.toFixed(0)+'°</b>'
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
}

function ndCalcular(){
 var g=ND.guardadas.filter(Boolean);
 if(!g.length || !ND.b) return;
 ND.n=g.length;
 ndMsg('retroprojetando…','');
 fetch('/api/nidus/tubos',{method:'POST',
   headers:{'Content-Type':'application/json'},
   body:JSON.stringify({b:ND.b, lado:ND.lado, incidencias:g})})
  .then(function(r){return r.json()}).then(function(d){
   if(d.erro){ ndMsg(d.erro,'erro'); return }
   ND.sessao=d.sessao; ND.teto=d.teto||12;
   var n=d.incidencias||g.length;
   if(n<2){
    ndMsg('1 incidência guardada — gire o gantry e marque outra para '
      +'começar a cruzar','');
   } else {
    ndMsg(n+' incidências cruzadas — a linha grossa é onde TODAS se '
      +'encontram; cada linha fina é uma delas','ok');
   }
   ndPintarGuardadas();
   ndPintarPlanos();
  }).catch(function(e){ ndMsg('não consegui retroprojetar: '+e,'erro') });
}

function ndPintarPlanos(){
 if(!ND.b) return;
 [0,1,2].forEach(function(eixo){
  var img=ndEl('nd_pl'+eixo); if(!img) return;
  var palco=ndEl('nd_pp'+eixo);
  if(ND.abrindo) ndCarregando(true, palco);
  img.onerror=function(){ img.removeAttribute('src'); ndCarregando(false, palco) };
  img.onload=function(){ ndCarregando(false, palco) };
  img.src='/api/nidus/corte?b='+encodeURIComponent(ND.b)
    +'&eixo='+eixo+'&pos='+ND.planos[eixo]+'&janela='+ND.jan;
  ndLinhas(eixo);
 });
 ndPintarCaixas();
}

function ndLinhas(eixo){
 var g=ndEl('nd_lin'+eixo); if(!g) return;
 if(!ND.sessao){ g.innerHTML=''; return }
 fetch('/api/nidus/linhas?s='+encodeURIComponent(ND.sessao)
   +'&eixo='+eixo+'&pos='+ND.planos[eixo])
  .then(function(r){return r.json()}).then(function(d){
   if(d.erro){ g.innerHTML=''; return }
   g.setAttribute('viewBox','0 0 '+d.largura+' '+d.altura);
   var h='';
   (d.camadas||[]).forEach(function(cam){
    var cls = cam.qual==='inter' ? 'nd-inter' : ('nd-tubo '+ndCor(cam.i||0));
    (cam.segmentos||[]).forEach(function(s){
     h+='<line x1="'+s[0][0]+'" y1="'+s[0][1]+'" x2="'+s[1][0]
       +'" y2="'+s[1][1]+'" class="'+cls+'"/>';
    });
   });
   g.innerHTML=h;
  }).catch(function(){ g.innerHTML='' });
}

function ndJanela(j){
 ND.jan=j;
 var bts=document.querySelectorAll('#nd_jan .nd-bt');
 for(var i=0;i<bts.length;i++)
  bts[i].classList.toggle('on', bts[i].getAttribute('data-j')===j);
 ndProjetar(); ndPintarPlanos();
}
function ndModo(m){
 ND.modo=m;
 ['mip','minip'].forEach(function(k){
  var b=ndEl('nd_m_'+k); if(b) b.classList.toggle('on', k===m);
 });
 ndProjetar();
}
function ndOutra(){
 var p=(ndEl('nd_pasta').value||'').trim(); if(p) ndListar(p);
}

function ndProcurar(){
 if(!window.uiExplorador) return;
 window.uiExplorador({inicial:(ndEl('nd_pasta').value||'').trim(),
  origem:ndEl('nd_procurar'),
  aoUsar:function(c){ ndEl('nd_pasta').value=c||''; ndOutra() }});
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
 ndEl('nd_svg').addEventListener('click', ndClique);
 ndEl('nd_svg').addEventListener('dblclick', function(ev){
  ev.preventDefault(); ndFechar();
 });
 ndEl('nd_svg').addEventListener('mousedown', ndPressionar);
 ndEl('nd_svg').addEventListener('mousemove', ndArrastar);
 ndEl('nd_svg').addEventListener('mouseup', ndSoltar);
 ndEl('nd_svg').addEventListener('mouseleave', ndSoltar);
 ndGradeDoDesenho();
 ndFerramenta(ND.ferramenta);
 ['lao','cra'].forEach(function(k){
  var e=ndEl('nd_'+k);
  if(e) e.addEventListener('change', function(){
   ND[k]=+e.value||0; ND.pontos=[]; ndPintarMarca(); ndProjetar();
  });
 });
 var l=ndEl('nd_laje');
 if(l) l.oninput=function(){ ND.laje=+l.value;
  ndEl('nd_lajev').textContent = ND.laje ? (ND.laje+' mm') : 'todo o volume';
  ndProjetar() };
 [0,1,2].forEach(function(eixo){
  var s=ndEl('nd_pos'+eixo);
  if(s) s.oninput=function(){ ND.planos[eixo]=+s.value/100;
   var img=ndEl('nd_pl'+eixo);
   if(img) img.src='/api/nidus/corte?b='+encodeURIComponent(ND.b)
     +'&eixo='+eixo+'&pos='+ND.planos[eixo]+'&janela='+ND.jan;
   ndLinhas(eixo);
  };
 });
 ndPintarGuardadas();
 ndListar('');
});
"""


def _cabeca():
    import radai_ui
    ajuda = radai_ui.ajuda(
        u"<b>O que esta tela &eacute;, e o que ela n&atilde;o &eacute;.</b>",
        radai_nidus.SEM_VOLUME, radai_nidus.LIMITACAO_CLINICA,
        radai_nidus.LIMITACAO_RM)
    return radai_ui.cabeca_de_funcao(
        u"◎", u"Projeção Vascular",
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
    return _icones(PAGINA.replace("@CSS@", CSS).replace("@JS@", JS)
                   .replace("@CABECA@", _cabeca())
                   .replace("@ALERTA@", _alerta())
                   .replace("@INCIDENCIAS@", _incidencias()),
                   (u"pasta", u"zoom_mais", u"zoom_menos", u"inverter", u"caixa"))


def _incidencias():
    return u"".join(
        u'<button type="button" class="nd-bt%s" data-nome="%s" '
        u'onclick="ndIncidencia(%s,%s,\'%s\')">%s</button>'
        % (u" on" if i == 0 else u"", nome, lao, cra, nome, nome)
        for i, (nome, lao, cra) in enumerate(radai_nidus.INCIDENCIAS))


PAGINA = u"""<!doctype html><html><head><meta charset="utf-8">
<title>Proje&ccedil;&atilde;o Vascular &middot; Nidus RT</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>@CSS@</style></head><body><div class="nd-wrap">

@CABECA@

<section class="nd-escolha" aria-label="s&eacute;rie">
 <div class="nd-campo pasta"><label for="nd_pasta" data-radai-frase>Pasta</label>
  <div class="nd-par-linha">
   <input type="text" id="nd_pasta" spellcheck="false" autocomplete="off"
    placeholder="C:\\... ou \\\\servidor\\...">
   <button type="button" class="ui-bt" id="nd_procurar">@ICO_PASTA@<span
    data-radai-frase>Procurar&hellip;</span></button>
   <button type="button" class="ui-bt" id="nd_listar" onclick="ndOutra()"
    data-radai-frase>Listar s&eacute;ries</button></div></div>
 <div class="nd-campo serie"><label for="nd_serie" data-radai-frase>S&eacute;rie</label>
  <div class="nd-par-linha">
   <select id="nd_serie" onchange="ndEscolher()">
    <option value="">carregando&hellip;</option></select>
   <span class="nd-demo" id="nd_demo" hidden><span>DEMO</span><span
    class="ui-ajuda dir" tabindex="0" aria-label="ajuda">?<span class="ui-balao"
    id="nd_demo_bal"></span></span></span></div></div>
</section>

<div id="nd_msg" role="status"></div>

<div class="nd-trabalho">

 <section class="nd-cx nd-proj" aria-label="proje&ccedil;&atilde;o">
  <div class="rot"><span data-radai-frase>proje&ccedil;&atilde;o</span>
   <b id="nd_rot_proj">&mdash;</b></div>
  <div class="nd-palco" id="nd_palco">
   <div class="nd-zoom" id="nd_zoom">
    <img id="nd_proj" alt="" draggable="false">
    <svg id="nd_svg" viewBox="0 0 512 512" preserveAspectRatio="xMidYMid meet">
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

 <aside class="nd-cmd" id="nd_cmd" aria-label="comandos">
  <div class="nd-grupo">
   <span class="t" data-radai-frase>incid&ecirc;ncia</span>
   <div class="g" id="nd_incid">@INCIDENCIAS@</div>
   <div class="g">
    <label for="nd_lao" data-radai-frase>LAO/RAO</label>
    <input type="text" class="nd-ang" id="nd_lao" value="0" inputmode="numeric">
    <label for="nd_cra" data-radai-frase>CRA/CAU</label>
    <input type="text" class="nd-ang" id="nd_cra" value="0" inputmode="numeric"></div>
  </div>
  <div class="nd-grupo">
   <span class="t" data-radai-frase>proje&ccedil;&atilde;o</span>
   <div class="g" id="nd_m">
    <button type="button" class="nd-bt on" id="nd_m_mip" onclick="ndModo('mip')">MIP</button>
    <button type="button" class="nd-bt" id="nd_m_minip" onclick="ndModo('minip')">MinIP</button>
    <button type="button" class="nd-bt" id="nd_inverter" onclick="ndInverter()"
     aria-pressed="false">@ICO_INVERTER@<span data-radai-frase>Inverter cores</span></button>
   </div>
   <div class="g"><span class="sub" data-radai-frase>laje</span>
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
   <span class="sub" id="nd_escala"></span>
  </div>
  <div class="nd-grupo">
   <span class="t" data-radai-frase>resolu&ccedil;&atilde;o</span>
   <div class="g" id="nd_res">
    <button type="button" class="nd-bt" data-r="256" onclick="ndResolucao(256)"
     title="a mais rápida — para girar e achar a incidência">r&aacute;pida</button>
    <button type="button" class="nd-bt on" data-r="512" onclick="ndResolucao(512)"
     title="o padrão">normal</button>
    <button type="button" class="nd-bt" data-r="1024" onclick="ndResolucao(1024)"
     data-radai-frase
     title="o dobro do detalhe no plano; ~1,5 s por projeção">alta</button></div>
   <span class="sub" id="nd_passo">&mdash;</span>
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
   <span class="t" data-radai-frase>desenho</span>
   <div class="g" id="nd_ferr">
    <button type="button" class="nd-bt on" data-f="clique"
     onclick="ndFerramenta('clique')"
     title="um vértice por clique — o desenho de precisão">cliques</button>
    <button type="button" class="nd-bt" data-f="lapis"
     onclick="ndFerramenta('lapis')"
     title="arraste contornando o ninho">l&aacute;pis</button></div>
   <div class="g">
    <button type="button" class="nd-bt" id="nd_bt_desenhar" onclick="ndDesenhar()"
     data-radai-frase>Circular a &aacute;rea</button>
    <button type="button" class="nd-bt" id="nd_bt_guardar" onclick="ndGuardar()"
     data-radai-frase>Guardar incid&ecirc;ncia</button></div>
   <span class="sub" id="nd_dica_clique" data-radai-frase>clique nos
    v&eacute;rtices &middot; duplo clique fecha</span>
   <span class="sub" id="nd_dica_lapis" style="display:none" data-radai-frase>
    arraste contornando o ninho &middot; soltar fecha o tra&ccedil;o</span>
  </div>
  <div class="nd-grupo">
   <div class="nd-guardadas" id="nd_guardadas"></div>
  </div>
 </aside>

</div>

<section class="nd-cx nd-mpr" id="nd_mpr" aria-label="MPR">
 <div class="rot"><span>MPR <b id="nd_mod"></b></span>
  <b data-radai-frase>linhas finas: o que foi retroprojetado</b></div>
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
 <p class="nd-legenda"><span data-radai-frase>A cor de cada linha diz de qual
  incid&ecirc;ncia ela veio. A linha mais forte &eacute; onde as duas se
  cruzam.</span></p>
</section>

@ALERTA@

</div>
<script>@JS@</script>
</body></html>"""


def _series_da_demo():
    try:
        import radai_demo
        import radai_thumbnail
        demos = radai_demo.demos("nidus")
    except Exception:
        return []
    fora = []
    for d in demos:
        for s in d["series"]:
            fora.append({"bilhete": radai_thumbnail.bilhete(s["pasta"], u""),
                         "curto": u"", "modalidade": s["modalidade"],
                         "desc": s["descricao"] or d["titulo"],
                         "cortes": s["cortes"], "espessura_mm": None,
                         "demo": True, "titulo": d["titulo"],
                         "licenca": d["licenca"], "atribuicao": d["atribuicao"]})
    return fora


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


SOLTAR_APOS_S = 600.0


def montar(app):
    import threading
    import time
    from collections import OrderedDict
    from fastapi import Request
    from fastapi.responses import HTMLResponse, Response

    _SESSOES = {}
    _ORDEM = []
    TETO_SESSOES = 4
    _PROXIMA = itertools.count(1)
    TETO_INCIDENCIAS = 12

    _ABERTA = {"chave": None, "serie": None, "visto": 0.0, "relogio": None}
    _TRAVA = threading.Lock()

    _TUBOS = OrderedDict()

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

    def _serie(b):
        import radai_thumbnail
        pasta, uid = radai_thumbnail.resolver(b)
        if not pasta:
            return None
        chave = (pasta, uid or u"")
        with _TRAVA:
            if _ABERTA["chave"] == chave and _ABERTA["serie"] is not None:
                _ABERTA["visto"] = time.time()
                return _ABERTA["serie"]
            _ABERTA.update({"chave": None, "serie": None})
            _TUBOS.clear()
            import engine
            import radai_nidus as N
            img = engine.load_sitk(pasta, uid or None)
            serie = N.abrir(img, _modalidade(pasta, uid or u""))
            _ABERTA.update({"chave": chave, "serie": serie,
                            "visto": time.time()})
            _armar(SOLTAR_APOS_S)
            return serie

    @app.get("/nidus/projecao", response_class=HTMLResponse)
    def _tela():
        return radai_menu.aplicar(pagina(), "nidus_projecao", com_tarefas=False)

    @app.post("/api/nidus/series")
    async def _series(request: Request):
        try:
            c = await request.json() or {}
            import radai_config
            import radai_batch
            import radai_thumbnail
            pasta = str(c.get("pasta") or "").strip() or radai_config.root_configurado()
            demo = _series_da_demo()
            if not pasta:
                return {"series": demo,
                        "erro": u"A pasta dos exames ainda não foi configurada: "
                                u"escolha uma pasta com «Procurar…»."}
            series = await radai_web.no_threadpool(
                radai_batch.varrer, pasta, modalidades=MODALIDADES,
                min_cortes=20, incluir_zips=True)
            out = []
            for s in series:
                real, erro = radai_batch.resolver_pasta(s)
                if erro or not real:
                    continue
                out.append({
                    "bilhete": radai_thumbnail.bilhete(real, s.get("uid") or ""),
                    "curto": (s.get("uid") or "")[-12:],
                    "modalidade": s.get("modalidade", ""),
                    "desc": s.get("desc", ""), "cortes": s.get("cortes", 0),
                    "espessura_mm": s.get("espessura_mm")})
            return {"series": out + demo,
                    "erro": u"" if out else u"nenhuma série nesta pasta"}
        except Exception as e:
            return {"series": [],
                    "erro": u"%s: %s" % (type(e).__name__, str(e)[:200])}

    @app.get("/api/nidus/forma")
    def _forma(b: str = ""):
        try:
            t0 = time.perf_counter()
            serie = _serie(b)
            if serie is None:
                return {"erro": u"recarregue a lista de séries"}
            return {"forma": list(serie.forma),
                    "espacamento": list(serie.mm),
                    "passos": serie.passos(LADOS),
                    "lado_util": serie.lado_util,
                    "modalidade": serie.modalidade,
                    "hu": bool(serie.escala.get("hu", True)),
                    "telas": _telas_do_mpr(serie),
                    "ms": int(round((time.perf_counter() - t0) * 1000))}
        except Exception as e:
            return {"erro": u"%s: %s" % (type(e).__name__, str(e)[:200])}

    _TRAVA_CX = threading.Lock()

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
                  laje: float = 0.0, caixa: str = ""):
        try:
            import radai_nidus as N
            import radai_recon3d as R
            serie = _serie(b)
            if serie is None:
                return Response(status_code=404, content=b"")
            _lado = int(lado or N.LADO_PADRAO)
            if _lado not in LADOS:
                _lado = N.LADO_PADRAO
            cx = N.caixa_de_texto(caixa)
            amostra = None
            if cx is not None:
                with _TRAVA_CX:
                    amostra = serie.img_na_caixa(cx, "mip" if modo == "mip" else "minip")
            plano, info = N.projetar(serie.img, lao, cra, modo, janela,
                                     lado=_lado,
                                     laje_mm=(float(laje) or None),
                                     escala=serie.escala, amostra=amostra)
            png = R.para_png(plano, info["centro"], info["largura"])
            return Response(content=png, media_type="image/png",
                            headers={"Cache-Control": "no-store"})
        except Exception:
            return Response(status_code=404, content=b"")

    @app.get("/api/nidus/corte")
    def _corte(b: str = "", eixo: int = 0, pos: float = 0.5,
               janela: str = "angio"):
        try:
            import radai_nidus as N
            import radai_recon3d as R
            serie = _serie(b)
            if serie is None:
                return Response(status_code=404, content=b"")
            eixo = int(eixo)
            n = serie.forma[eixo]
            i = int(round(min(1.0, max(0.0, float(pos))) * (n - 1)))
            a = N.corte(serie.v, eixo, i)
            ml, mc = N.mm_do_corte(serie.mm, eixo)
            c, l = N.janela_de(janela, serie.escala)
            return Response(content=R.para_png(N.para_a_tela(a, ml, mc), c, l),
                            media_type="image/png",
                            headers={"Cache-Control": "no-store"})
        except Exception:
            return Response(status_code=404, content=b"")

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
            return {"erro": u"%s: %s" % (type(e).__name__, str(e)[:200])}

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
