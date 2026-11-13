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
  this.maxDecodedEntries=options.maxDecodedEntries||this.maxEntries;
  this.entries=new Map(); this.pending=new Map(); this.queue=[];
  this.bytes=0; this.decodedEntries=0; this.generation=0; this.running=false;
  this.controller=new AbortController(); this.painted=new Map();
  this.decodeChain=Promise.resolve();
 }
 NidusImageCache.prototype._key=keyFor;
 NidusImageCache.prototype.get=function(url){
  var key=keyFor(url), entry=this.entries.get(key);
  if(entry){ this.entries.delete(key); this.entries.set(key,entry) }
  return entry||null;
 };
 NidusImageCache.prototype._drop=function(key, entry){
  if(entry.image)this.decodedEntries--;
  this.entries.delete(key); this.bytes-=entry.bytes;
  URL.revokeObjectURL(entry.url); entry.image=null;
 };
 NidusImageCache.prototype._dropDecoded=function(entry){
  if(!entry.image)return;
  entry.image.src='';entry.image=null;this.decodedEntries--;
  this.bytes-=entry.decodedBytes;entry.bytes-=entry.decodedBytes;entry.decodedBytes=0;
 };
 NidusImageCache.prototype._trim=function(incomingBytes, decoded, extraEntry, keep){
  var iterator=this.entries.entries(), item;
  // Angiography keeps the encoded full-quality rotation without retaining 72
  // decoded RGBA buffers. The default retains all CINE frames for playback.
  while(this.decodedEntries+decoded>this.maxDecodedEntries || this.bytes+incomingBytes>this.maxBytes){
   item=iterator.next();if(item.done)break;
   if(item.value[1]!==keep && !item.value[1].pins)this._dropDecoded(item.value[1]);
  }
  iterator=this.entries.entries();
  while(this.bytes+incomingBytes>this.maxBytes || this.entries.size+extraEntry>this.maxEntries){
   item=iterator.next(); if(item.done) break;
   if(item.value[1]!==keep && !item.value[1].pins) this._drop(item.value[0],item.value[1]);
  }
  return this.bytes+incomingBytes<=this.maxBytes && this.entries.size+extraEntry<=this.maxEntries
    && this.decodedEntries+decoded<=this.maxDecodedEntries;
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
  var cached=this.get(url); if(cached&&cached.image) return Promise.resolve(cached);
  var key=keyFor(url), task=this.pending.get(key);
  if(!task){
   task={key:key,url:url,generation:this.generation,priority:Number(options.priority)||0,
         clients:[{signal:signal,current:options.current}]};
   task.promise=new Promise(function(resolve,reject){ task.resolve=resolve;task.reject=reject });
   this.pending.set(key,task);
   if(cached){
    // A retained PNG must never wait behind a cold HTTP projection. Decode at
    // most one local image at a time and pin it while that short queue runs.
    cached.pins++;
    this.decodeChain=this.decodeChain.catch(function(){}).then(function(){return self._decodeStored(task,cached)});
   }else{
    this.queue.push(task);this.queue.sort(function(a,b){return b.priority-a.priority});this._drain();
   }
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
 NidusImageCache.prototype._decodeStored=async function(task,entry){
  try{
   if(task.generation!==this.generation||!this._wanted(task))throw aborted();
   var image=new Image();image.src=entry.url;await image.decode();
   if(task.generation!==this.generation||!this._wanted(task))throw aborted();
   var bytes=entry.width*entry.height*4;
   if(!this._trim(bytes,1,0,entry))throw new RangeError('NIDUS image cache limit');
   entry.image=image;entry.decodedBytes=bytes;entry.bytes+=bytes;this.bytes+=bytes;this.decodedEntries++;
   task.resolve(entry);
  }catch(error){task.reject(error)}
  finally{entry.pins=Math.max(0,entry.pins-1);if(this.pending.get(task.key)===task)this.pending.delete(task.key)}
 };
 NidusImageCache.prototype._drain=async function(){
  if(this.running) return; this.running=true;
  try{
   while(this.queue.length){
    var task=this.queue.shift(), generation=this.generation, objectUrl=null;
    try{
     if(task.generation!==generation || !this._wanted(task)) throw aborted();
     var existing=this.entries.get(task.key),blob=null;
     if(!existing){
      var response=await fetch(task.url,{signal:this.controller.signal,cache:'no-store'});
      if(!response.ok) throw new Error('HTTP '+response.status);
      blob=await response.blob();
      if(task.generation!==this.generation) throw aborted();
      objectUrl=URL.createObjectURL(blob);
     }
     var image=new Image();image.src=existing?existing.url:objectUrl;
     await image.decode();
     if(task.generation!==this.generation) throw aborted();
     var width=image.naturalWidth, height=image.naturalHeight;
     if(!width||!height) throw new Error('Invalid image');
     // Include decoded RGBA, not just tiny compressed PNGs, in the memory bound.
     var decodedBytes=width*height*4,bytes=(existing?0:blob.size)+decodedBytes;
     if(!this._trim(bytes,1,existing?0:1,existing)) throw new RangeError('NIDUS image cache limit');
     var entry=existing||{key:task.key,url:objectUrl,width:width,height:height,
                         bytes:blob.size,pins:0,generation:generation};
     entry.image=image;entry.decodedBytes=decodedBytes;entry.bytes+=decodedBytes;
     objectUrl=null;this.entries.set(task.key,entry);this.bytes+=bytes;this.decodedEntries++;task.resolve(entry);
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
         decoded:this.decodedEntries,generation:this.generation,running:this.running};
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
   var value=global.radaiFrase?global.radaiFrase(label):label;
   if(global.uiTexto)global.uiTexto(node,value);else node.textContent=value;
  }
  function restore(){
   self._roots.forEach(function(s){s.root.inert=s.inert;
    if(s.busy===null)s.root.removeAttribute('aria-busy');else s.root.setAttribute('aria-busy',s.busy)});
   global.uiCarregando(art,false);
   if(self.thinking)self.thinking.close();
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
  global.uiCarregando(art,true,'');
  if(global.NidusThinking)self.thinking=global.NidusThinking.mount(art);
  this.step=function(label,done,total){
   if(self.closed)return;
   translate(status,label);if(self.thinking)self.thinking.step(label);
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
