/* Neuro processing uses the host's folder reader, preview and queue confirmation. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const tr = text => window.radaiFrase ? window.radaiFrase(text) : text;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
  const uid = () => 'n' + (window.crypto?.randomUUID?.().replace(/-/g, '') || Date.now().toString(36) + Math.random().toString(36).slice(2));
  const atlas = 'anatomy_cerebra_ants';
  const catalog = new Map(), plans = new Map();
  const gallery = $('series-list'), container = $('nr-plans');
  let token = '', submitting = false, pending = null;
  const protocolLabels = {
    snc_rm_simples:'SNC RM Simples', snc_rm_avancado:'SNC RM Avançado', cranio_buti:'Crânio em TC',
    anatomy_cerebra_ants:'CerebrA / ANTs',
    MRI_GBM:'Glioblastoma · pré-operatório', MRI_LGGlioma:'Glioma de baixo grau',
    MRI_Meningioma:'Meningioma', MRI_Metastasis:'Metástases',
    MRI_GBM_Postop_FV_1p:'Glioblastoma pós-operatório (1 sequência)',
    MRI_GBM_Postop_FV_3p:'Glioblastoma pós-operatório (3 sequências)',
    glioma_attention_unet3d:'Glioma · Attention U-Net 3D', metastasis_qtim:'Metástases · QTIM',
  };
  const modelLabels = {anatomy_synthseg:'SynthSeg', [atlas]:'CerebrA / ANTs', cranio_buti:'Buti'};
  const experimentalWarning = 'Modelo experimental, apenas para pesquisa. Pode deixar de detectar metástases, inclusive pequenas. Não utilizar para decisões clínicas.';
  const metastasis = id => id==='metastasis_qtim' || id==='MRI_Metastasis';
  const exams = new Map();
  function label(s) {
    const exam = exams.size>1 ? [tr('Exame') + ' ' + exams.get(s.group_key), s.date].filter(Boolean).join(' · ') : '';
    return [exam, s.series_number, s.description || [tr('Série'),s.modality].join(' ')].filter(v=>v != null && v !== '').join(' · ');
  }
  const pname = p => tr(protocolLabels[p.id] || p.label);
  const mname = m => modelLabels[m.id] || tr(protocolLabels[m.id] || m.label);
  const modalityLabel = code => tr(({CT:'TC',MR:'RM'})[code] || code);
  const roles = m => (m.channels || []).map(c=>typeof c === 'string' ? c : c.role);
  function invalidate() { pending = null; if(!submitting){delete $('selection-status').dataset.state;$('selection-status').textContent='';} }
  async function api(path, body, signal) {
    const options = {headers:{'X-Neuro-Token':token}, signal};
    if (body !== undefined) Object.assign(options, {method:'POST', body:JSON.stringify(body), headers:{...options.headers,'Content-Type':'application/json'}});
    const response = await fetch('/neuro/api/' + path, options);
    const result = await response.json().catch(()=>({}));
    if (!response.ok) throw Error(tr(typeof result.detail === 'string' ? result.detail : 'Não foi possível concluir esta operação.'));
    return result;
  }
  function context(s) {
    return [...catalog.values()].filter(other => other.group_key === s.group_key && other.modality === s.modality);
  }
  const anatomyIds = new Set(['snc_rm_simples','snc_rm_avancado',atlas,'cranio_buti']);
  const anatomyModel = key => key?.startsWith('snc_rm_') ? 'anatomy_synthseg' : key;
  function activeOptions(p) {
    return [p.protocol,...p.findings].filter(Boolean).map(key=>{
      const model=anatomyModel(key), outputs=p.outputs[key] || [], excluded=p.excluded.get(key);
      return {key,model,outputs,kept:outputs.filter(roi=>!excluded?.has(roi.class_id))};
    });
  }
  function studyPlan(p) {
    const rois = {};
    for (const entry of activeOptions(p)) rois[entry.model]=entry.kept.map(roi=>roi.class_id);
    return {anatomy:p.protocol || null,findings:[...p.findings],rois};
  }
  function canSubmit(p) {
    if (p.loading || p.error || p.series.busy) return false;
    const active = activeOptions(p).filter(item=>item.kept.length);
    return !!active.length && active.every(item=>p.models.find(m=>m.id===item.model)?.eligibility?.selectable);
  }
  function syncStart() {
    $('start').disabled = submitting || !plans.size || ![...plans.values()].every(canSubmit);
    $('nr-empty').hidden = !!plans.size;
    $('nr-table-wrap').hidden = !plans.size;
  }
  function drawGallery() {
    for (const modality of ['CT','MR']) {
      const count = [...catalog.values()].filter(s => s.modality === modality).length;
      const opener=$('nr-add-' + modality + '-open');
      if (opener.dataset.count !== String(count)) {
        window.uiCartaoRotulo(opener, count ? String(count) : '');
        opener.dataset.count=String(count);
      }
    }
    gallery.innerHTML = [...catalog.values()].map(s => {
      const id = esc(s.ticket), selected = plans.has(s.ticket);
      return '<li class="nr-series" data-selected="' + selected + '"><button type="button" class="ui-cartao nr-preview" data-select="' + id + '" aria-pressed="' + selected + '">' +
        '<span class="nr-thumb"><img alt="" loading="lazy" decoding="async" src="/api/lote/miniatura?b=' + esc(encodeURIComponent(s.ticket)) + '"><span class="nr-thumb-error" hidden>' + esc(tr('Prévia indisponível')) + '</span></span>' +
        '<span class="nr-caption"><strong translate="no">' + esc(label(s)) + '</strong><span class="nr-series-meta">' + esc([modalityLabel(s.modality), s.slice_count && s.slice_count + ' ' + tr('Cortes')].filter(Boolean).join(' · ')) + '</span>' +
        '<span class="nr-preview-action">' + esc(tr(selected ? 'Série selecionada' : 'Selecionar série')) + '</span></span></button>' +
        '<div class="nr-series-actions"><button class="ui-bt" type="button" data-preview="' + id + '" aria-label="' + esc(tr('Ampliar série') + ' ' + label(s)) + '">' + esc(tr('Ampliar')) + '</button>' +
        '<button class="ui-bt" type="button" data-remove="' + id + '" aria-label="' + esc(tr('Remover') + ' ' + label(s)) + '">' + esc(tr('Remover')) + '</button></div></li>';
    }).join('');
  }
  gallery.addEventListener('error', e => {
    if (!e.target.matches?.('.nr-thumb img')) return;
    e.target.hidden = true; e.target.nextElementSibling.hidden = false;
  }, true);
  async function preview(s, anchor) {
    const ticket = encodeURIComponent(s.ticket);
    let count = Number(s.slice_count);
    if (!(count > 0)) {
      const info = await fetch('/api/lote/miniatura?b=' + ticket, {method:'HEAD'});
      count = Number(info.headers.get('X-RadAI-Cortes'));
      if (!info.ok || count < 1) throw Error(tr('Prévia indisponível'));
    }
    if (!anchor.isConnected) return;
    const windows = s.modality === 'MR' ? ['auto'] : ['mediastino','pulmao','osso'];
    const view = window.uiVisor({titulo:label(s), origem:anchor, total:count, cranial:s.cranial,
      cabecalho:[['Paciente',s.patient],['ID',s.patientId],['Data',s.date],['Modalidade',s.modality],
        ['Cortes',String(count)],...(s.preview_header || []).filter(([k])=>!['Paciente','ID','Data','Modalidade','Cortes'].includes(k))].filter(([,v])=>v),
      janelas:windows.map(chave=>({chave,rotulo:({auto:'automática',pulmao:'pulmão'})[chave] || chave})),
      src:(slice,key)=>'/api/lote/corte?b='+ticket+'&corte='+slice+'&janela='+encodeURIComponent(key)});
    view?.ajustar?.();
    if (s.cranial == null && view?.definirSentido) {
      fetch('/api/lote/sentido', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({b:s.ticket})})
        .then(r=>r.json()).then(d=>{if ([1,-1].includes(d.cranial)) {s.cranial = d.cranial;view.definirSentido(d.cranial);}}).catch(()=>{});
    }
  }
  function reason(m) {
    if (!m) return tr('Modelo indisponível nesta estação.');
    const e = m.eligibility || {};
    if (e.selectable) return e.warnings?.length ? tr('Confira as associações sugeridas.') : '';
    if (e.missing_roles?.length) return tr('Séries ausentes:') + ' ' + e.missing_roles.join(', ');
    const reasons = e.technical_reasons || [];
    if (reasons.some(r=>r.code==='unsupported_device')) return tr('O modelo não suporta o dispositivo escolhido nas configurações.');
    if (reasons.some(r => ['missing_artifacts','model_artifacts_unavailable','runtime_unavailable','model_not_distributed'].includes(r.code))) return tr('Modelo indisponível nesta estação.');
    return tr('Série incompatível com este modelo.') + (roles(m).length ? ' ' + roles(m).join(' / ') : '');
  }
  function toggle(attr, name, checked, disabled, info='') {
    return '<div class="nr-option"><label class="nr-switch"><input type="checkbox" role="switch" ' + attr +
      (checked ? ' checked' : '') + (disabled ? ' disabled' : '') + '><span class="nr-switch-track" aria-hidden="true"></span><span>' + esc(name) +
      '</span></label>' + (info ? '<small>' + esc(info) + '</small>' : '') + '</div>';
  }
  function bindingChoices(plan, model) {
    const group = context(plan.series);
    return (plan.bindings.get(model.id) || []).map(b => {
      const fixed = model.reference_role === b.role && model.id !== atlas;
      const allowed = model.binding_options?.[b.role];
      const options = group.filter(s=>s.ticket===b.series_ticket || (!fixed && (allowed
        ? allowed.includes(s.ticket)
        : (s.sequence_candidates||[]).some(c=>c.role===b.role || (model.id===atlas && c.role==='T1c')))));
      return '<label>' + esc(b.role) + '<select data-bind-model="' + esc(model.id) + '" data-role="' + esc(b.role) + '"' + (fixed ? ' disabled' : '') + '>' +
        options.map(s=>'<option translate="no" value="' + esc(s.ticket) + '"' + (s.ticket === b.series_ticket ? ' selected' : '') + '>' + esc(label(s)) + '</option>').join('') + '</select></label>';
    }).join('');
  }
  function helpButton(kind, id, title) {
    return '<button type="button" class="ui-bt nr-task-help" aria-haspopup="dialog" data-help-kind="'+kind+'" data-help="'+esc(id)+'" aria-label="'+esc(tr('Ajuda sobre')+' '+title)+'">?</button>';
  }
  function savedReason(p, preset) {
    const needed=[anatomyModel(preset.plan.anatomy),...preset.plan.findings].filter(id=>preset.plan.rois[id]?.length);
    return needed.map(id=>p.models.find(m=>m.id===id)).filter(m=>!m?.eligibility?.selectable).map(reason).join(' ');
  }
  function renderTableRow(p) {
    const s=p.series;
    const cell=(heading,html)=>'<td data-col="'+esc(tr(heading))+'">'+html+'</td>';
    const action=(data,title)=>'<button type="button" class="ui-bt nr-mini" '+data+'>'+esc(tr(title))+'</button>';
    let status=s.status || 'livre';
    if (s.busy) status='em processamento';
    else if (s.hasRt && status==='livre') status='já tem um RTSTRUCT na pasta';
    const mode='<button type="button" class="ui-bt nr-table-mode" data-expand aria-expanded="'+(!p.node.hidden)+'" aria-controls="'+p.node.id+'">'+esc(tr('Personalizado'))+' '+(p.node.hidden?'▸':'▾')+'</button>';
    const previewButton='<button type="button" data-table-preview class="nr-table-preview" aria-label="'+esc(tr('Ampliar série')+' '+label(s))+'"><img alt="" loading="lazy" src="/api/lote/miniatura?b='+esc(encodeURIComponent(s.ticket))+'"></button>';
    const number = value => Number(value).toLocaleString(document.documentElement.lang || undefined,{maximumFractionDigits:2});
    p.row.innerHTML=cell('Paciente','<b translate="no">'+esc(s.patient || s.patientId || '—')+'</b>'+(s.patient && s.patientId?'<small translate="no">'+esc(s.patientId)+'</small>':''))+
      cell('Data',esc(s.date || '—'))+cell('Modalidade',esc(modalityLabel(s.modality)))+cell('Cortes',esc(s.slice_count || '—'))+
      cell('Espessura (mm)',s.thickness==null?'—':esc(number(s.thickness)))+cell('Descrição','<span translate="no">'+esc(s.description || '—')+'</span>')+
      cell('Série',previewButton)+cell('Situação',esc(tr(status)))+cell('Ações','<div class="nr-row-actions">'+action('data-deselect','Remover')+action('data-table-preview','Ver imagens')+'</div>')+cell('Modo',mode);
  }
  function tags(p) {
    const options=activeOptions(p), selected=options.flatMap(item=>item.kept.map(roi=>[item,roi]));
    const dropped=options.flatMap(item=>item.outputs.filter(roi=>p.excluded.get(item.key)?.has(roi.class_id)).map(roi=>[item,roi]));
    const tag=([item,roi],restore)=>{
      const name=roi.roi_name || roi.label || roi.class_id;
      return '<button type="button" class="nr-tag" data-option="'+esc(item.key)+'" '+(restore?'data-restore':'data-exclude')+'="'+esc(roi.class_id)+'" aria-label="'+esc(tr(restore?'Restaurar':'Remover')+' '+name)+'"><span translate="no">'+esc(name)+'</span><span aria-hidden="true">'+(restore?'+':'×')+'</span></button>';
    };
    return '<p class="nr-tag-count">'+selected.length+' '+esc(tr('Estruturas no RTSTRUCT'))+'</p>'+
      '<div class="nr-tags">'+selected.map(v=>tag(v,false)).join('')+'</div>'+
      (dropped.length?'<details class="nr-removed"><summary>'+esc(tr('Estruturas removidas'))+' ('+dropped.length+')</summary><div class="nr-tags">'+dropped.map(v=>tag(v,true)).join('')+'</div></details>':'');
  }
  function drawPlan(p) {
    renderTableRow(p);
    const body=p.node.querySelector('.nr-plan-body');
    body.setAttribute('aria-busy',String(!!p.loading));
    if(p.loading){body.textContent=tr('Identificando os modelos disponíveis…');return;}
    if(p.error){body.innerHTML='<p role="alert">'+esc(p.error)+'</p><button class="ui-bt" type="button" data-retry>'+esc(tr('Tentar novamente'))+'</button>';return;}
    const anatomies=p.protocols.filter(x=>anatomyIds.has(x.id));
    function control(kind,id,title,m,checked,detail) {
      const attr=kind==='anatomy'?'data-protocol':'data-finding';
      const enabled=!!m?.eligibility?.selectable;
      return '<div class="nr-task-row">'+toggle(attr+'="'+esc(id)+'"',title,checked,!enabled,reason(m) || detail)+helpButton(kind,id,title)+'</div>';
    }
    const anatomy=anatomies.map(opt=>{
      const m=p.models.find(m=>m.id===anatomyModel(opt.id));
      const notes={snc_rm_simples:'SynthSeg · 10 OARs',snc_rm_avancado:'SynthSeg · '+tr('32 estruturas anatômicas.'),cranio_buti:'Buti / nnU-Net'};
      return control('anatomy',opt.id,pname(opt),m,p.protocol===opt.id,notes[opt.id] || '');
    }).join('');
    const saved=p.saved.map(record=>{
      const why=savedReason(p,record);
      return '<div class="nr-task-row">'+toggle('data-saved="'+esc(record.id)+'"',record.name,p.savedId===record.id,!!why,why)+helpButton('saved',record.id,record.name)+'</div>';
    }).join('');
    const edit='<button type="button" class="ui-bt nr-mini" data-save'+(canSubmit(p)?'':' disabled')+'>'+esc(tr('Salvar protocolo'))+'</button>';
    const savedBlock='<div class="nr-saved"><h4>'+esc(tr('Protocolos próprios NEURO'))+'</h4>'+saved+edit+'</div>';
    const findings=p.models.filter(m=>!['anatomy_synthseg',atlas,'cranio_buti'].includes(m.id)).map(m=>{
      const credit=m.id.startsWith('MRI_')?'Raidionics':m.id==='metastasis_qtim'?'QTIM':'Attention U-Net 3D';
      return control('finding',m.id,mname(m),m,p.findings.has(m.id),credit);
    }).join('');
    const column=(name,cls,html)=>'<section class="nr-column '+cls+'"><h3>'+esc(tr(name))+'</h3>'+html+'</section>';
    const inputs=activeOptions(p).filter(item=>item.kept.length).map(item=>p.models.find(m=>m.id===item.model)).filter(m=>m && (roles(m).length>1 || m.id===atlas)).map(m=>
      '<fieldset><legend>'+esc(mname(m))+'</legend><div class="nr-bindings">'+bindingChoices(p,m)+'</div></fieldset>').join('');
    body.innerHTML='<div class="nr-columns">'+column('Protocolos anatômicos','nr-anatomy',anatomy+savedBlock)+
      column('Achados de lesões suspeitas','nr-findings',(p.models.some(m=>metastasis(m.id) && m.eligibility?.selectable)?'<p class="nr-experimental">'+esc(tr(experimentalWarning))+'</p>':'') + (findings || '<p>'+esc(tr('Nenhum modelo de achados para esta modalidade.'))+'</p>'))+
      column('STUDY','nr-delivery',tags(p))+'</div>'+inputs;
  }
  async function refreshPlan(plan, first=false) {
    plan.request?.abort();
    const request = plan.request = new AbortController();
    const group = context(plan.series);
    plan.loading = true; plan.error = ''; invalidate(); drawPlan(plan); syncStart();
    try {
      if (group.length > 120) throw Error(tr('Escolha as séries individualmente. É possível selecionar até 120 séries por exame.'));
      const data = await api('selection',{tickets:group.map(s=>s.ticket),reference:plan.series.ticket,category:'unified'}, request.signal);
      if (request.signal.aborted) return;
      plan.models=data.models || []; plan.protocols=data.protocols || []; plan.outputs=data.outputs || {};
      plan.saved=(data.saved_protocols || []).filter(record=>record.modality===plan.series.modality);
      for (const m of plan.models) {
        const manual=(plan.bindings.get(m.id) || []).filter(b=>b.association_source==='manual' &&
          group.some(s=>s.ticket===b.series_ticket) && (!m.binding_options?.[b.role] || m.binding_options[b.role].includes(b.series_ticket)));
        plan.bindings.set(m.id,(m.bindings || []).map(b=>manual.find(prev=>prev.role===b.role) || b));
      }
      const eligible=id=>plan.models.find(m=>m.id===id)?.eligibility?.selectable;
      for (const id of plan.findings) if(!eligible(id)){plan.findings.delete(id);plan.savedId='';}
      if (first) {
        const id=plan.series.modality==='CT'?'cranio_buti':'snc_rm_simples';
        if (plan.protocols.some(p=>p.id===id) && eligible(anatomyModel(id))) plan.protocol=id;
      }
      if (plan.protocol && !eligible(anatomyModel(plan.protocol))) {plan.protocol='';plan.savedId='';}
    } catch (e) {
      if (!request.signal.aborted) plan.error = e.message;
    } finally {
      if (!request.signal.aborted) { plan.loading = false; drawPlan(plan); syncStart(); }
    }
  }
  function deselect(ticket) {
    const p=plans.get(ticket);
    if (p){p.request?.abort();p.row.remove();p.node.remove();plans.delete(ticket);}
  }
  function select(series) {
    if(plans.has(series.ticket)){deselect(series.ticket);return;}
    const row=document.createElement('tr'),node=document.createElement('tr');
    row.className='nr-summary';node.className='nr-plan';node.id=uid();
    row.dataset.ticket=node.dataset.ticket=series.ticket;
    node.innerHTML='<td colspan="10"><div class="nr-plan-body"></div></td>';
    container.append(row,node);
    const p={series,row,node,models:[],protocols:[],protocol:'',findings:new Set(),bindings:new Map(),outputs:{},excluded:new Map(),saved:[],savedId:''};
    plans.set(series.ticket,p);
    refreshPlan(p,true);
  }
  gallery.addEventListener('click', async e => {
    const button=e.target.closest('button');
    if (!button || submitting) return;
    const {preview:show,select:chosen,remove} = button.dataset;
    if (show) {try { await preview(catalog.get(show),button); } catch (err) { $('scan-status').textContent=err.message; } return; }
    invalidate();
    if (chosen) select(catalog.get(chosen));
    if (remove) {
      const removed=catalog.get(remove); deselect(remove); catalog.delete(remove);
      for (const p of plans.values()) if (p.series.group_key===removed.group_key && p.series.modality===removed.modality) refreshPlan(p);
    }
    drawGallery(); syncStart();
    if (chosen) [...gallery.querySelectorAll('[data-select]')].find(el=>el.dataset.select===chosen)?.focus();
  });
  function applySaved(p,record) {
    p.protocol=record.plan.anatomy || '';
    p.findings=new Set(record.plan.findings || []);
    p.excluded.clear();
    for (const item of activeOptions(p)) {
      const included=new Set(record.plan.rois[item.model] || []);
      p.excluded.set(item.key,new Set(item.outputs.filter(roi=>!included.has(roi.class_id)).map(roi=>roi.class_id)));
    }
    p.savedId=record.id;p.originId=record.id;
  }
  function savePreset(p,button) {
    const origin=p.saved.find(record=>record.id===p.originId);
    const form=document.createElement('form');
    form.className='nr-preset-form';
    form.innerHTML='<label>'+esc(tr('Nome do protocolo'))+'<input name="name" required maxlength="80" autocomplete="off"></label>'+
      '<p class="nr-preset-feedback" role="status"></p><button type="submit" class="ui-bt pri">'+esc(tr('Salvar protocolo'))+'</button>';
    const input=form.querySelector('input'),submit=form.querySelector('button'),feedback=form.querySelector('p');
    input.value=origin?.name || '';
    const dialog=window.uiModal({titulo:tr('Salvar protocolo'),no:form,origem:button,largura:480});
    form.addEventListener('submit',async event=>{
      event.preventDefault();
      const name=input.value.trim();
      if(!name || submit.disabled) return;
      const payload={name,modality:p.series.modality,plan:studyPlan(p)};
      if(origin && origin.name===name) payload.id=origin.id;
      submit.disabled=true;
      try{
        const result=await api('protocols',payload);
        const saved=(result.protocols || []).filter(record=>record.modality===p.series.modality);
        for (const other of plans.values()) if(other.series.modality===p.series.modality) other.saved=saved;
        const current=saved.find(record=>record.name===name);
        if(current){p.savedId=current.id;p.originId=current.id;}
        dialog.fechar();
        for (const other of plans.values()) if(other.series.modality===p.series.modality)drawPlan(other);
        p.node.querySelector('[data-save]')?.focus();
      }catch(error){feedback.textContent=error.message;submit.disabled=false;}
    });
  }
  function showHelp(p,button) {
    const kind=button.dataset.helpKind,id=button.dataset.help;
    const content=document.createElement('div');
    if(kind==='saved'){
      const record=p.saved.find(row=>row.id===id);
      if(!record)return;
      const anatomy=p.protocols.find(row=>row.id===record.plan.anatomy);
      const findings=record.plan.findings.map(x=>p.models.find(m=>m.id===x)).filter(Boolean);
      const lines=[[tr('Protocolos anatômicos'),anatomy?pname(anatomy):'—'],[tr('Achados de lesões suspeitas'),findings.map(mname).join(', ') || '—'],
        ['STUDY',String(Object.values(record.plan.rois).reduce((n,rois)=>n+rois.length,0))+' '+tr('Estruturas no RTSTRUCT')]];
      content.innerHTML='<dl>'+lines.map(([k,v])=>'<dt>'+esc(k)+'</dt><dd>'+esc(v)+'</dd>').join('')+'</dl>';
      window.uiModal({titulo:record.name,no:content,origem:button,largura:520});
      return;
    }
    const modelId=kind==='anatomy'?anatomyModel(id):id;
    const m=p.models.find(m=>m.id===modelId);
    if(!m)return;
    const help=m.help || {}, option=p.protocols.find(x=>x.id===id);
    const fields=[['Séries necessárias',roles(m).join(', ')],['Método',help.method],['Preparação',help.preparation],
      ['Limitações',help.limitations],['Neste exame',reason(m)]].filter(([,v])=>typeof v==='string' && v);
    content.innerHTML='<dl>'+fields.map(([k,v])=>'<dt>'+esc(tr(k))+'</dt><dd>'+esc(tr(v))+'</dd>').join('')+'</dl>';
    const outputs=p.outputs[id] || [];
    if(outputs.length) {
      const details=document.createElement('details'),summary=document.createElement('summary'),names=document.createElement('p');
      summary.textContent=tr('Estruturas no RTSTRUCT')+' ('+outputs.length+')'; names.textContent=outputs.map(roi=>roi.roi_name || roi.label).join(', ');
      details.append(summary,names);content.appendChild(details);
    }
    if (/^https?:\/\//i.test(m.source_url || '')) {
      const link=document.createElement('a');
      link.href=m.source_url;link.target='_blank';link.rel='noopener noreferrer';link.textContent=tr('Fonte e publicação');
      content.appendChild(link);
    }
    window.uiModal({titulo:option?pname(option):mname(m),no:content,origem:button,largura:580});
  }
  function redraw(p,focus) {
    drawPlan(p);syncStart();focus?.();
  }
  container.addEventListener('click',async e=>{
    const button=e.target.closest('button'),p=plans.get(e.target.closest('tr')?.dataset.ticket);
    if(!button || !p || submitting)return;
    if(button.hasAttribute('data-table-preview')){
      try{await preview(p.series,button);}catch(err){$('selection-status').textContent=err.message;}
    }else if(button.hasAttribute('data-deselect')){
      invalidate();deselect(p.series.ticket);drawGallery();syncStart();
      [...gallery.querySelectorAll('[data-select]')].find(b=>b.dataset.select===p.series.ticket)?.focus();
    }else if(button.hasAttribute('data-expand')){
      p.node.hidden=!p.node.hidden;renderTableRow(p);p.row.querySelector('[data-expand]').focus();
    }else if(button.hasAttribute('data-retry')){
      refreshPlan(p);
    }else if(button.hasAttribute('data-save')){
      savePreset(p,button);
    }else if(button.dataset.help){
      showHelp(p,button);
    }else if(button.dataset.option){
      invalidate();
      const key=button.dataset.option, removed=p.excluded.get(key) || new Set();
      if(button.dataset.restore)removed.delete(button.dataset.restore);else removed.add(button.dataset.exclude);
      p.excluded.set(key,removed);p.savedId='';
      redraw(p,()=>{const next=p.node.querySelector('[data-exclude],.nr-removed summary');next?.focus();});
    }
  });
  container.addEventListener('change',e=>{
    const t=e.target,p=plans.get(t.closest('tr')?.dataset.ticket);
    if(!p || submitting)return;
    invalidate();
    if(t.dataset.protocol){
      p.protocol=t.checked?t.dataset.protocol:'';p.savedId='';
    }else if(t.dataset.finding){
      if(t.checked)p.findings.add(t.dataset.finding);else p.findings.delete(t.dataset.finding);
      p.savedId='';
    }else if(t.dataset.saved){
      const record=p.saved.find(row=>row.id===t.dataset.saved);
      if(t.checked && record)applySaved(p,record);
      else {p.protocol='';p.findings.clear();p.excluded.clear();p.savedId='';p.originId='';}
    }else if(t.dataset.bindModel){
      const list=p.bindings.get(t.dataset.bindModel),old=list.find(b=>b.role===t.dataset.role);
      if(list.some(b=>b!==old && b.series_ticket===t.value)){t.value=old.series_ticket;$('selection-status').textContent=tr('Associe séries diferentes a cada canal.');return;}
      Object.assign(old,{series_ticket:t.value,association_source:'manual',certainty:'certain',warnings:[]});
    }
    const attr=['protocol','finding','saved','bindModel'].find(k=>t.dataset[k]);
    redraw(p,()=>{
      if(!attr)return;
      const control=[...p.node.querySelectorAll('input,select')].find(n=>n.dataset[attr]===t.dataset[attr] && n.dataset.role===t.dataset.role);
      if(control?.type==='checkbox')control.nextElementSibling.dataset.slide=control.checked?'on':'off';
      control?.focus();
    });
  });
  function displayDate(raw) {
    const match=/^(\d{4})(\d{2})(\d{2})$/.exec(raw || '');
    if(!match)return raw || '';
    const date=new Date(Date.UTC(Number(match[1]),Number(match[2])-1,Number(match[3])));
    return date.toLocaleDateString(document.documentElement.lang || undefined,{timeZone:'UTC'});
  }
  async function ingest(rows, modality, signal) {
    const raw = new Map(rows.filter(r=>r.bilhete && r.modalidade===modality && !r.carregando).map(r=>[r.bilhete,r]));
    const tickets = [...raw.keys()].filter(ticket=>!catalog.has(ticket));
    const discovered = [], changed = new Set();
    for (let i=0;i<tickets.length;i+=120) {
      const data=await api('selection',{tickets:tickets.slice(i,i+120),category:'unified',identify_only:true},signal);
      for (const s of data.series || []) {
        if (!s.group_key || !raw.has(s.ticket) || s.modality!==modality) continue;
        const r = raw.get(s.ticket);
        const status={concluida:'já segmentada',retomavel:'parou no meio',refazer:'a refazer: marcador sem RTSTRUCT'}[r.situacao];
        const thickness=r.espessura_mm ?? s.slice_thickness ?? null;
        discovered.push({...s,slice_count:s.slice_count||r.cortes,description:s.description||r.desc||r.descricao,
          date:displayDate(s.study_date || r.date || r.data),patient:s.patient_name || r.nome || '',patientId:s.patient_id || r.pid || '',
          thickness:thickness!=null && Number.isFinite(Number(thickness))?Number(thickness):null,
          status,busy:r.situacao==='processando',hasRt:!!r.tem_rs,
          series_number:s.series_number??r.numero,cranial:r.cranial});
        changed.add(s.group_key);
      }
    }
    if (signal.aborted) return;
    for (const s of discovered) {
      catalog.set(s.ticket,s);
      if (!exams.has(s.group_key)) exams.set(s.group_key,exams.size+1);
    }
    drawGallery();
    for (const plan of plans.values()) if (changed.has(plan.series.group_key) && plan.series.modality===modality) refreshPlan(plan);
    $('scan-status').textContent = discovered.length<tickets.length ? tr('A pasta contém séries que não puderam ser identificadas.') : '';
  }
  function setupPicker(modality) {
    const id='nr-add-'+modality;
    let query, archive;
    const abort=()=>query?.abort();
    const finish=async rows=>{
      abort(); const controller=query=new AbortController();
      try {
        await ingest(rows,modality,controller.signal);
        if (!controller.signal.aborted && rows.some(r=>r.modalidade===modality && catalog.has(r.bilhete))) popup.fechar();
      } catch (err) {if (!controller.signal.aborted) $(id+'_mensagem').textContent=err.message;}
    };
    window.uiCarregarImagens(id,{uso:'series',chave:'neuro-'+modality,opcoes:{modalidades:[modality]},aoFechar:abort,aoFim:finish});
    const popup = window.uiPopupSerie(id,{aoAbrir:()=>{
      if (!archive) archive=window.uiTabelaAcervo(id+'-archive',{filtro:row=>row.modalidade===modality,aoAbrir:row=>finish([row])});
    }});
    $(id+'_form').addEventListener('submit',abort,true);
    $(id+'_pasta').addEventListener('keydown',e=>{if(e.key==='Enter')abort();},true);
    $(id+'_pasta').addEventListener('change',abort);
    $(id+'-open').disabled=false;
  }
  function requestBody(){
    return {schema:'neuro-rt/request/2',request_id:uid(),explicit_request:true,export_rtstruct:true,studies:[...plans.values()].map(p=>{
      const model_ids=activeOptions(p).filter(item=>item.kept.length).map(item=>item.model);
      return {study_id:uid(),reference:p.series.ticket,model_ids,plan:studyPlan(p),
        bindings_by_model:Object.fromEntries(model_ids.map(id=>[id,p.bindings.get(id)]))};
    })};
  }
  $('start').addEventListener('click',()=>{
    if ($('start').disabled) return;
    if (!window.radaiRevAbrir || !$('radai_rev_corpo')) {$('selection-status').textContent=tr('A conferência comum não está disponível. Reabra a tela pelo Local Suite.');return;}
    const request=pending ||= requestBody();
    window.radaiRevAbrir(null,async()=>{
      if (submitting || pending!==request) return;
      submitting=true;syncStart();
      const feedback=$('selection-status');feedback.dataset.state='saving';feedback.setAttribute('aria-busy','true');feedback.textContent=tr('Gravando o pedido na fila…');
      try {
        const receipt=await api('studies',request);
        if(receipt.request_id!==request.request_id || receipt.studies?.length!==request.studies.length) throw Error(tr('Não foi possível concluir esta operação.'));
        for (const item of request.studies)deselect(item.reference);
        pending=null;drawGallery();
        feedback.dataset.state='saved';feedback.textContent=tr('Pedido enviado para a fila comum.');
        if(typeof window.radaiFilaCarregar==='function')window.radaiFilaCarregar();
      } catch(err) {delete feedback.dataset.state;feedback.textContent=err.message;}
      finally {feedback.removeAttribute('aria-busy');submitting=false;syncStart();}
    });
    $('radai_rev_sub').textContent=tr('Séries selecionadas')+' · '+request.studies.length;
    $('radai_rev_corpo').innerHTML=[...plans.values()].map(p=>'<h4 translate="no">'+esc(label(p.series))+'</h4><ul>'+
      activeOptions(p).filter(item=>item.kept.length).map(item=>{
        const option=p.protocols.find(x=>x.id===item.key),m=p.models.find(m=>m.id===item.model);
        return '<li>'+esc(option?pname(option):mname(m))+' · '+item.kept.length+' '+esc(tr('Estruturas no RTSTRUCT'))+'</li>';
      }).join('')+'</ul>').join('');
  });
  api('status').then(data=>{
    token=data.token || data.csrf_token;
    if(!token || !window.uiCarregarImagens || !window.uiPopupSerie || !window.uiTabelaAcervo)throw Error(tr('O carregador comum não está disponível. Reabra pelo Local Suite.'));
    setupPicker('CT'); setupPicker('MR');
  }).catch(err=>{$('scan-status').textContent=err.message;});
})();
