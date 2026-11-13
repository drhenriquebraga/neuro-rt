"""Requested Thinking states recipe, scoped to the NIDUS loading artwork.

Source: Jakub Antalik / Transitions.dev, public free thinking-states recipe.
https://github.com/Jakubantalik/transitions.dev/blob/main/cli/free/thinking-states.md
Real work phases choose the labels; no simulated percentage or invented stages.
"""

NIDUS_THINKING_JS = r"""
(function(global){
 'use strict';
 var CSS='.nd-thinking{--think-swap:150ms;--think-gap:50ms;--think-distance:8px;--think-blur:2px;--think-shimmer:2000ms;--think-base:#bdcadd;--think-highlight:#fff;--think-ease:ease-in-out;position:absolute;inset:0;display:grid;place-items:center;z-index:2;text-align:center;pointer-events:none}.nd-thinking .t-think{position:relative;display:inline-block;width:100%;min-height:3em}.nd-thinking .t-think-text{position:absolute;top:0;left:12px;right:12px;display:block;color:var(--think-base);transform:translateY(0);filter:blur(0);opacity:1;transition:transform var(--think-swap) var(--think-ease),filter var(--think-swap) var(--think-ease),opacity var(--think-swap) var(--think-ease);will-change:transform,filter,opacity}.nd-thinking .t-think-text:before{content:attr(data-text);position:absolute;inset:0;pointer-events:none;background-image:linear-gradient(90deg,transparent 0%,transparent 40%,var(--think-highlight) 50%,transparent 60%,transparent 100%);background-size:400% 100%;background-repeat:no-repeat;-webkit-background-clip:text;background-clip:text;color:transparent;-webkit-text-fill-color:transparent;animation:nd-think-shimmer var(--think-shimmer) linear infinite}@keyframes nd-think-shimmer{0%{background-position:100% 0}100%{background-position:0% 0}}.nd-thinking .t-think-text.is-exit{transform:translateY(calc(var(--think-distance)*-1));filter:blur(var(--think-blur));opacity:0}.nd-thinking .t-think-text.is-enter-start{transition:none;transform:translateY(var(--think-distance));filter:blur(var(--think-blur));opacity:0}@media(prefers-reduced-motion:reduce){.nd-thinking .t-think-text{transition:none!important;transform:none!important;filter:none!important}.nd-thinking .t-think-text:before{display:none!important}}';
 function phrases(label){
  if(label.indexOf('incidências')>=0)return ['Calculando os ângulos…','Guardando projeções no cache…','Preparando a navegação…'];
  if(label.indexOf('fases adquiridas')>=0)return ['Lendo os metadados temporais…','Agrupando fases do mesmo exame…'];
  if(label.indexOf('fases')>=0)return ['Reconstruindo as fases adquiridas…','Mantendo a mesma janela…','Preparando a reprodução…'];
  if(label.indexOf('reprodução')>=0)return ['Guardando as fases no cache…','Preparando a navegação…'];
  if(label.indexOf('projeção')>=0)return ['Construindo as vistas…','Preparando a navegação…'];
  return ['Lendo os dados DICOM…','Organizando o volume…'];
 }
 function mount(art){
  if(!document.getElementById('nd-thinking-style')){var style=document.createElement('style');style.id='nd-thinking-style';style.textContent=CSS;document.head.appendChild(style)}
  var root=document.createElement('span');root.className='nd-thinking';root.setAttribute('aria-hidden','true');
  var box=document.createElement('span');box.className='t-think';root.appendChild(box);art.appendChild(root);
  var live=null,timer=null,removeTimer=null,releaseTimer=null,closed=false,phase='',states=[],index=0;
  function show(value){
   if(closed)return;var leaving=live,next=document.createElement('span'),reduced=global.matchMedia&&global.matchMedia('(prefers-reduced-motion:reduce)').matches;
   next.className='t-think-text'+(leaving&&!reduced?' is-enter-start':'');
   var translated=global.radaiFrase?global.radaiFrase(value):value;next.textContent=translated;next.setAttribute('data-text',translated);box.appendChild(next);live=next;
   clearTimeout(removeTimer);clearTimeout(releaseTimer);
   Array.from(box.children).forEach(function(node){if(node!==live&&node!==leaving)node.remove()});
   if(leaving){if(reduced)leaving.remove();else{leaving.classList.add('is-exit');releaseTimer=setTimeout(function(){void next.offsetWidth;next.classList.remove('is-enter-start')},50);removeTimer=setTimeout(function(){leaving.remove()},200)}}
  }
  function cycle(){clearTimeout(timer);timer=setTimeout(function(){if(closed)return;index=(index+1)%states.length;show(states[index]);cycle()},2200)}
  return {step:function(label){if(label===phase)return;phase=label;states=phrases(label);index=0;show(states[0]);cycle()},close:function(){closed=true;clearTimeout(timer);clearTimeout(removeTimer);clearTimeout(releaseTimer);root.remove()}};
 }
 global.NidusThinking={mount:mount};
})(window);
"""
