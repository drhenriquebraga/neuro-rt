"""Bounded decoded-image preparation for NIDUS, using the host's existing motion.

The screen owns readiness, geometry and clinical state. This helper only caches
rendered images and provides a cancellable opening dialog. A reset is mandatory
when the selected series or its source revision changes. It never caches a 3-D
volume and never synthesizes frames.
"""

NIDUS_PRELOAD_JS = r"""
(function(global){
 'use strict';
 function aborted(){ return new DOMException('Cancelled', 'AbortError') }
 function ensure(signal){ if(signal && signal.aborted) throw aborted() }
 function keyFor(url){
  var u=new URL(url, global.location.href);
  // Only transport sequence numbers are irrelevant. All geometry/window/source
  // parameters remain in the key, including temporal identifiers when present.
  u.searchParams.delete('n'); u.searchParams.delete('t'); u.searchParams.sort();
  return u.href;
 }
 function NidusImageCache(options){
  options=options||{};
  this.maxBytes=options.maxBytes||128*1024*1024;
  this.maxEntries=options.maxEntries||32;
  this.entries=new Map(); this.pending=new Map(); this.queue=[];
  this.bytes=0; this.generation=0; this.running=false;
  this.controller=new AbortController(); this.painted=new Map();
 }
 NidusImageCache.prototype._key=keyFor;
 NidusImageCache.prototype.get=function(url){
  var key=keyFor(url), entry=this.entries.get(key);
  if(entry){ this.entries.delete(key); this.entries.set(key,entry) }
  return entry||null;
 };
 NidusImageCache.prototype._drop=function(key, entry){
  this.entries.delete(key); this.bytes-=entry.bytes;
  URL.revokeObjectURL(entry.url); entry.image=null;
 };
 NidusImageCache.prototype._trim=function(incomingBytes){
  var iterator=this.entries.entries(), item;
  while(this.bytes+incomingBytes>this.maxBytes || this.entries.size>=this.maxEntries){
   item=iterator.next(); if(item.done) break;
   if(!item.value[1].pins) this._drop(item.value[0],item.value[1]);
  }
  return this.bytes+incomingBytes<=this.maxBytes && this.entries.size<this.maxEntries;
 };
 NidusImageCache.prototype._wanted=function(task){
  return task.clients.some(function(client){
   return !(client.signal&&client.signal.aborted) && (!client.current||client.current());
  });
 };
 NidusImageCache.prototype._prune=function(){
  var self=this;
  this.queue=this.queue.filter(function(task){
   if(self._wanted(task))return true;
   if(self.pending.get(task.key)===task)self.pending.delete(task.key);
   task.reject(aborted());return false;
  });
 };
 NidusImageCache.prototype.load=function(url, options){
  options=options||{};
  var self=this, signal=options.signal;
  if(signal && signal.aborted) return Promise.reject(aborted());
  this._prune();
  var cached=this.get(url); if(cached) return Promise.resolve(cached);
  var key=keyFor(url), task=this.pending.get(key);
  if(!task){
   task={key:key,url:url,generation:this.generation,priority:Number(options.priority)||0,
         clients:[{signal:signal,current:options.current}]};
   task.promise=new Promise(function(resolve,reject){ task.resolve=resolve;task.reject=reject });
   this.pending.set(key,task); this.queue.push(task);
   this.queue.sort(function(a,b){return b.priority-a.priority}); this._drain();
  }else{
   task.clients.push({signal:signal,current:options.current});
   if(Number(options.priority)>task.priority){
    task.priority=Number(options.priority);this.queue.sort(function(a,b){return b.priority-a.priority});
   }
  }
  if(!signal) return task.promise;
  // A caller's cancellation must not abort another viewer sharing this image.
  // reset() cancels the entire generation, including the single active fetch.
  return new Promise(function(resolve,reject){
   function cancel(){ cleanup();reject(aborted()) }
   function cleanup(){ signal.removeEventListener('abort',cancel) }
   signal.addEventListener('abort',cancel,{once:true});
   task.promise.then(function(entry){cleanup();if(signal.aborted)reject(aborted());else resolve(entry)},
                     function(error){cleanup();reject(error)});
  });
 };
 NidusImageCache.prototype._drain=async function(){
  if(this.running) return; this.running=true;
  try{
   while(this.queue.length){
    var task=this.queue.shift(), generation=this.generation, objectUrl=null;
    try{
     if(task.generation!==generation || !this._wanted(task)) throw aborted();
     var response=await fetch(task.url,{signal:this.controller.signal,cache:'no-store'});
     if(!response.ok) throw new Error('HTTP '+response.status);
     var blob=await response.blob();
     if(task.generation!==this.generation) throw aborted();
     objectUrl=URL.createObjectURL(blob);
     var image=new Image(); image.src=objectUrl;
     await image.decode();
     if(task.generation!==this.generation) throw aborted();
     var width=image.naturalWidth, height=image.naturalHeight;
     if(!width||!height) throw new Error('Invalid image');
     // Include decoded RGBA, not just tiny compressed PNGs, in the memory bound.
     var bytes=blob.size+width*height*4;
     if(!this._trim(bytes)) throw new RangeError('NIDUS image cache limit');
     var entry={key:task.key,url:objectUrl,image:image,width:width,height:height,
                bytes:bytes,pins:0,generation:generation};
     objectUrl=null;this.entries.set(task.key,entry);this.bytes+=bytes;task.resolve(entry);
    }catch(error){if(objectUrl)URL.revokeObjectURL(objectUrl);task.reject(error)}
    finally{if(this.pending.get(task.key)===task)this.pending.delete(task.key)}
   }
  }finally{this.running=false}
 };
 NidusImageCache.prototype.paint=async function(img,url,options){
  options=options||{};
  var generation=this.generation, entry=await this.load(url,options);
  ensure(options.signal);
  if(generation!==this.generation || (options.current&&!options.current())) throw aborted();
  var previous=this.painted.get(img), token={entry:entry,generation:generation};
  entry.pins++;this.painted.set(img,token);
  if(previous) previous.entry.pins=Math.max(0,previous.entry.pins-1);
  img.src=entry.url;
  try{
   await img.decode();ensure(options.signal);
   if(generation!==this.generation || this.painted.get(img)!==token ||
      (options.current&&!options.current()))throw aborted();
   return entry;
  }catch(error){
   if(this.painted.get(img)===token)this.release(img);
   throw error;
  }
 };
 NidusImageCache.prototype.release=function(img){
  var token=this.painted.get(img);
  if(token){token.entry.pins=Math.max(0,token.entry.pins-1);this.painted.delete(img)}
 };
 NidusImageCache.prototype.warm=async function(urls,options){
  options=options||{};
  var self=this, unique=Array.from(new Map(urls.map(function(url){return[keyFor(url),url]})).values());
  for(var index=0;index<unique.length;index++){
   ensure(options.signal);await self.load(unique[index],{signal:options.signal,priority:-1});
   ensure(options.signal);if(options.onProgress)options.onProgress(index+1,unique.length);
  }
  return unique.length;
 };
 NidusImageCache.prototype.reset=function(){
  this.generation++;this.controller.abort();this.controller=new AbortController();
  this.queue.splice(0).forEach(function(task){task.reject(aborted())});this.pending.clear();
  this.painted.clear();
  var self=this;this.entries.forEach(function(entry,key){self._drop(key,entry)});
 };
 NidusImageCache.prototype.stats=function(){
  return{bytes:this.bytes,entries:this.entries.size,queued:this.queue.length,
         generation:this.generation,running:this.running};
 };

 function NidusOpeningDialog(options){
  options=options||{};
  if(!global.uiModal || !global.uiCarregando) throw new Error('NIDUS host UI unavailable');
  var self=this;this.closed=false;this.completed=false;this.controller=new AbortController();
  var previousFocus=options.origin||document.activeElement;
  this.signal=this.controller.signal;
  var box=document.createElement('div'), art=document.createElement('div');
  art.style.cssText='position:relative;height:132px;border-radius:12px;overflow:hidden;margin-bottom:16px';
  var status=document.createElement('p');status.setAttribute('role','status');status.setAttribute('aria-live','polite');
  status.style.cssText='margin:0 0 12px';
  var progress=document.createElement('progress');progress.max=1;progress.removeAttribute('value');
  progress.style.cssText='display:block;width:100%;height:8px;accent-color:var(--accent);margin-bottom:16px';
  var count=document.createElement('div');count.hidden=true;
  count.style.cssText='text-align:right;font-size:.85em;margin:-8px 0 12px;opacity:.75';
  var cancel=document.createElement('button');cancel.type='button';cancel.className='ui-bt';
  cancel.setAttribute('data-radai-frase','');cancel.textContent=options.cancelLabel||'Cancelar';
  box.appendChild(art);box.appendChild(status);box.appendChild(progress);box.appendChild(count);box.appendChild(cancel);
  this._roots=(options.roots||[]).filter(Boolean).map(function(root){
   var snapshot={root:root,inert:root.inert,busy:root.getAttribute('aria-busy')};
   root.inert=true;root.setAttribute('aria-busy','true');return snapshot;
  });
  function translate(node,label){
   if(global.uiTexto)global.uiTexto(node,label);else node.textContent=label;
  }
  function restore(){
   self._roots.forEach(function(s){s.root.inert=s.inert;
    if(s.busy===null)s.root.removeAttribute('aria-busy');else s.root.setAttribute('aria-busy',s.busy)});
   global.uiCarregando(art,false);
  }
  function close(){
   if(self.closed)return;self.closed=true;restore();
   // uiModal restores focus before aoFechar; the workspace was still inert then.
   if(previousFocus&&previousFocus.focus)previousFocus.focus();
   if(!self.completed){self.controller.abort();if(options.onCancel)options.onCancel()}
  }
  this.modal=global.uiModal({titulo:options.title||'Preparando a série',no:box,largura:480,
                           fecharFora:false,origem:options.origin,aoFechar:close});
  cancel.addEventListener('click',function(){self.cancel()});
  this.step=function(label,done,total){
   if(self.closed)return;
   translate(status,label);global.uiCarregando(art,true,label);
   progress.setAttribute('aria-label',status.textContent);
   if(Number.isFinite(done)&&Number.isFinite(total)&&total>0){
    progress.max=total;progress.value=Math.min(total,Math.max(0,done));
    progress.setAttribute('aria-valuetext',String(progress.value)+' / '+String(total));
    count.textContent=String(progress.value)+' / '+String(total);count.hidden=false;
   }else{progress.removeAttribute('value');progress.removeAttribute('aria-valuetext');count.hidden=true}
  };
  this.finish=function(){if(self.closed)return;self.completed=true;self.modal.fechar();close()};
  this.cancel=function(){if(self.closed)return;self.modal.fechar();close()};
  this.step(options.initialLabel||'Lendo as imagens da série…');
 }
 global.NidusImageCache=NidusImageCache;
 global.NidusOpeningDialog=NidusOpeningDialog;
})(window);
"""
