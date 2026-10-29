'use strict';
const $ = id => document.getElementById(id);
const base = new URL('./', location.href);
let token = '', models = [], demos = [], activeJob = '', busy = false, processingPreference='auto', exportAvailable=false;
const states = {running:'Processando',visualizing:'Montando visualização',exporting:'Gravando RTSTRUCT',completed:'Pronto para revisão',empty:'Máscara vazia',failed:'Falhou'};

function notify(type, detail = {}) {
  if (window.parent !== window) window.parent.postMessage({module:'neuro-rt',version:1,type,...detail},location.origin);
}
async function api(path, options = {}) {
  const response = await fetch(new URL(`api/${path}`,base),options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || data.detail || 'Falha na conexão local.');
  return data;
}
function error(message) { $('notice').textContent = message; $('notice').hidden = false; }
function updateRun() {
  const model = models.find(m => m.id === $('model').value);
  $('run').disabled = busy || !token || !model?.ready || !$('explicit').checked;
  $('load-demo').disabled=busy || !demos.some(d=>d.model===model?.id);
  $('sequence').textContent = model ? `Entrada exigida: ${model.sequence}.${model.ready ? '' : ' Pesos ainda não preparados.'}` : 'A sequência exigida aparece ao escolher o modelo.';
}
function renderJob(job) {
  if(job.id!==activeJob && typeof clearViewer==='function')clearViewer();
  activeJob = job.id;
  busy = ['running','visualizing','exporting'].includes(job.status);
  if((busy || job.status==='failed') && typeof clearViewer==='function')clearViewer();
  $('job-state').textContent = states[job.status] || job.status;
  $('job-state').className = busy ? 'busy' : job.status === 'failed' ? 'failed' : 'done';
  $('empty').hidden = true;
  $('result').hidden = false;
  $('result').replaceChildren();
  const text = document.createElement('p'); text.textContent = job.message; $('result').append(text);
  if(job.demo){const source=document.createElement('p'),link=document.createElement('a');link.href=job.demo.source_url;link.target='_blank';link.rel='noopener';link.textContent=job.demo.label;source.append(link,document.createTextNode(` · ${job.demo.license} · exemplo de demonstração`));$('result').append(source)}
  if (job.status === 'failed') error(job.message);
  if (job.result) {
    const volume = job.result.masks.reduce((sum,mask)=>sum+mask.volume_cm3,0);
    const metric = document.createElement('p'); metric.className = 'metric'; metric.textContent = `${volume.toLocaleString('pt-BR',{maximumFractionDigits:3})} cm³`;
    const label = document.createElement('p'); label.className = 'metric-label'; label.textContent = 'Volume previsto pelo modelo'; $('result').prepend(metric,label);
    const links = document.createElement('div'); links.className = 'download-list';
    const files = [['Tumor.nii.gz','Baixar máscara'],['manifest.json','Baixar manifesto']];
    if (job.result.rtstruct) files.push(['RS_NeuroRT.dcm','Baixar RTSTRUCT']);
    for (const [file,title] of files) { const link = document.createElement('a'); link.href = new URL(`api/jobs/${job.id}/artifacts/${file}`,base).href; link.textContent = title; link.download = file; links.append(link); }
    $('result').append(links);
    if(job.result.visualization?.available && typeof showViewer==='function')showViewer(job).catch(exc=>error(exc.message));
    if(job.result.rtstruct?.source_path){const saved=document.createElement('p');saved.textContent=`RTSTRUCT gravado na origem: ${job.result.rtstruct.source_path}`;$('result').append(saved)}
  }
  if (job.output_dir) { const path = document.createElement('div'); path.className = 'output-path'; path.textContent = job.output_dir; $('result').append(path); }
  updateRun();
}
async function poll() {
  if (!activeJob) return;
  try {
    const job = await api(`jobs/${activeJob}`); renderJob(job);
    if (busy) setTimeout(poll,1500); else notify(job.status === 'failed' ? 'failed' : 'completed',{jobId:job.id,status:job.status});
  } catch (exc) { error(`${exc.message} Tentando reconectar ao processamento.`); setTimeout(poll,4000); }
}
$('model').addEventListener('change',updateRun);
$('load-demo').addEventListener('click',async()=>{if(busy)return;$('notice').hidden=true;try{renderJob(await api(`demos/${encodeURIComponent($('model').value)}`))}catch(exc){error(exc.message)}});
$('explicit').addEventListener('change',updateRun);
$('inspect').addEventListener('click',async()=>{
  $('notice').hidden = true; $('inspect').disabled = true;
  try {
    const data = await api(`series?path=${encodeURIComponent($('input-path').value.trim())}`);
    $('series').replaceChildren(new Option('Selecione a série MR',''));
    for (const series of data.series) $('series').add(new Option(`${series.slices} cortes · ${series.uid}`,series.uid));
    if (data.series.length === 1) $('series').value = data.series[0].uid;
    if (!data.series.length) error('Nenhuma série DICOM MR encontrada nesta pasta.');
  } catch(exc) { error(exc.message); } finally { $('inspect').disabled = false; }
});
$('input-path').addEventListener('input',()=>{$('series').replaceChildren(new Option('Única série da pasta / entrada NIfTI',''));});
$('job-form').addEventListener('submit',async event=>{
  event.preventDefault(); if (busy) return;
  $('notice').hidden = true; busy = true; updateRun();
  try {
    const path=$('input-path').value.trim(),nifti=/\.nii(\.gz)?$/i.test(path);
    const job = await api('jobs',{method:'POST',headers:{'Content-Type':'application/json','X-Neuro-Token':token},body:JSON.stringify({model:$('model').value,input_path:path,series_uid:$('series').value,device:processingPreference,explicit_request:$('explicit').checked,export_rtstruct:!nifti})});
    renderJob(job); notify('status',{jobId:job.id,status:job.status}); setTimeout(poll,1000);
  } catch(exc) { busy = false; error(exc.message); updateRun(); }
});
window.addEventListener('message',event=>{
  if (event.origin !== location.origin || event.source !== window.parent || event.data?.module !== 'neuro-rt' || event.data?.version !== 1) return;
  if (event.data.type === 'theme' && ['light','dark'].includes(event.data.theme)) document.documentElement.dataset.theme = event.data.theme;
  if (event.data.type === 'context' && !busy && typeof event.data.inputPath === 'string') { $('input-path').value = event.data.inputPath; $('series').replaceChildren(new Option('Série enviada pelo Local Suite',event.data.seriesUid || '')); }
});
async function init() {
  try {
    const status = await api('status'); token = status.token; models = status.models;
    demos=status.demos || [];
    for (const model of models) { const option = new Option(model.label,model.id); option.disabled = !model.ready; $('model').add(option); }
    $('weights').replaceChildren();
    for (const model of models) { const row = document.createElement('li'); const title = document.createElement('span'); title.textContent = model.label; const state = document.createElement('span'); state.textContent = model.ready ? 'Pronto' : 'Preparar pesos'; state.className = model.ready ? 'ready' : ''; row.append(title,state); $('weights').append(row); }
    exportAvailable=status.export_available;processingPreference=status.processing_preference || 'auto';
    $('processing-note').textContent=`Processamento: ${{auto:'auto',cpu:'somente CPU',cuda:'somente GPU'}[processingPreference] || processingPreference}. Compartilhamento das configurações do Local Suite pendente.`;
    $('export-note').textContent=exportAvailable?'Série DICOM: RTSTRUCT gravado na pasta original. NIfTI: máscara e visualizações.':'Conexão com o gravador pendente; entrada NIfTI disponível.';
    $('connection').textContent = 'Motor local conectado'; $('connection').className = 'online';
    const current = status.jobs.filter(j=>!j.demo).at(-1); if (current) { renderJob(current); if (busy) poll(); }
    updateRun(); notify('ready');
  } catch(exc) { $('connection').textContent = 'Motor local indisponível'; error(exc.message); }
}
const theme = new URLSearchParams(location.search).get('theme');
if (['light','dark'].includes(theme)) document.documentElement.dataset.theme = theme;
init();
