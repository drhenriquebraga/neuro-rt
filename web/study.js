/* Native Local Suite study screen. Only opaque tickets cross the API boundary. */
(function () {
  'use strict';
  const el = id => document.getElementById(id);
  const esc = value => String(value == null ? '' : value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const uid = () => 'n' + (window.crypto && crypto.randomUUID ? crypto.randomUUID().replace(/-/g, '') : Date.now().toString(36) + Math.random().toString(36).slice(2));
  const roles = model => (model.channels || []).map(c => typeof c === 'string' ? c : c.role);
  const messages = items => (items || []).map(x => typeof x === 'string' ? x : x.message || x.code).filter(Boolean);
  const state = {category: document.querySelector('[data-category]').dataset.category, token: '', series: [], models: [], selected: new Set(), bindings: {}, reference: '', jobs: [], job: null, scene: null, artifactMap: {}, rois: {}, generation: 0, abort: null, poll: null, selecting: false};
  const classSelections = new Map();
  const allowedModalities = ['MR', 'CT'];
  const pickerUnavailable = 'O carregador comum não está disponível. Reabra pelo Local Suite.';
  const differentExam = 'As entradas e a referência precisam pertencer ao mesmo exame e sujeito.';
  async function api(path, body, signal) {
    const options = {headers: {'X-Neuro-Token': state.token}, signal};
    if (body !== undefined) { options.method = 'POST'; options.headers['Content-Type'] = 'application/json'; options.body = JSON.stringify(body); }
    const response = await fetch('/neuro/api/' + path, options);
    if (!response.ok) { let data = {}; try { data = await response.json(); } catch (_) {} throw Error(typeof data.detail === 'string' ? data.detail : 'Não foi possível concluir esta operação.'); }
    return response.json();
  }
  function seriesLabel(series, index) {
    const description = series.description || series.label || series.series_description;
    const number = series.series_number;
    if (description) return number == null ? description : number + ' · ' + description;
    const candidates = (series.sequence_candidates || []).map(c => c.role || c.sequence).filter(Boolean);
    return ['Série ' + (number ?? index + 1), series.modality, ...candidates].filter(Boolean).join(' · ');
  }
  function modelAvailability(model, selectionState) {
    const current=selectionState||state;
    const bindings = current.bindings[model.id] || [];
    const missing = roles(model).filter(role => !bindings.some(b => b.role === role && current.series.some(s => s.ticket === b.series_ticket && s.modality === (role === 'CT' ? 'CT' : 'MR'))));
    const tickets = bindings.map(b => b.series_ticket).filter(Boolean);
    const duplicate = new Set(tickets).size !== tickets.length;
    const reasons = (model.eligibility || {}).technical_reasons || [];
    const technical = messages(reasons);
    const distribution = messages(reasons.filter(reason => reason && reason.code === 'model_not_distributed')).join(' ');
    const incompatibilities=[];
    const reference=current.series.find(s=>s.ticket===current.reference);
    const inputs=bindings.map(b=>current.series.find(s=>s.ticket===b.series_ticket)).filter(Boolean);
    if(reference && roles(model).some(role=>reference.modality!==(role==='CT'?'CT':'MR'))) incompatibilities.push('O modelo e a referência precisam ter a mesma modalidade. Transferência RM–TC não é permitida.');
    if(new Set([reference,...inputs].filter(Boolean).map(s=>s.group_key).filter(Boolean)).size>1) incompatibilities.push(differentExam);
    return {selectable: !missing.length && !duplicate && !technical.length && !incompatibilities.length, missing, duplicate, technical, distribution, incompatibilities, warnings: messages((model.eligibility || {}).warnings)};
  }
  function collectStudyRequest(selectionState) {
    const s = selectionState || state;
    const ids = Array.from(s.selected);
    if (!s.reference || !ids.length) throw Error('Escolha uma referência e ao menos um modelo.');
    const bindings = {}, exportClasses = {};
    ids.forEach(id => {
      const model = s.models.find(m => m.id === id);
      if (!model || !modelAvailability(model,s).selectable) throw Error('Confira as entradas dos modelos escolhidos.');
      bindings[id] = JSON.parse(JSON.stringify(s.bindings[id] || []));
      const classes = classSelections.get(id);
      if (classes && !classes.size) throw Error('Escolha pelo menos uma estrutura de cada modelo anatômico selecionado.');
      if (classes && classes.size < model.classes.length) exportClasses[id] = [...classes];
    });
    const item = {study_id:uid(), reference:s.reference, model_ids:ids, bindings_by_model:bindings};
    if (Object.keys(exportClasses).length) item.export_classes = exportClasses;
    return {schema:'neuro-rt/request/2', request_id:uid(), explicit_request:true, export_rtstruct:true, studies:[item]};
  }
  function updateStart() { el('start').disabled = !state.token || state.selecting || !state.reference || !state.selected.size || !Array.from(state.selected).every(id => { const m = state.models.find(m => m.id === id); return m && modelAvailability(m).selectable && classSelections.get(id)?.size !== 0; }); }
  function classOptions(model) {
    if (!model.groups.includes('anatomia') || !(model.classes || []).length) return '';
    const choices = classSelections.get(model.id);
    return '<details class="nr-class-options"' + (state.selected.has(model.id) ? '' : ' hidden') + '><summary>Estruturas no RTSTRUCT</summary>' +
      model.classes.map((item, index) => '<label><input type="checkbox" data-class-model="' + esc(model.id) + '" data-class-index="' + index + '"' +
        (!choices || choices.has(item.class_id) ? ' checked' : '') + '> ' + esc(item.label || item.class_id) + '</label>').join('') + '</details>';
  }
  function renderModelSelection(container, selectionState) {
    if(selectionState && selectionState !== state) {Object.assign(state,selectionState);state.selected=new Set(selectionState.selected||[]);}
    const groups = state.category === 'anatomia' ? [['anatomia','Estruturas anatômicas']] : [[state.category,'Lesões']];
    if (state.category !== 'anatomia' && el('include-anatomy').checked) groups.push(['anatomia','Estruturas anatômicas']);
    container.innerHTML = groups.map(([group, title]) => {
      const list = state.models.filter(model => (model.groups || []).includes(group));
      if (!list.length) return '';
      return '<h3>' + esc(title) + '</h3>' + list.map(model => {
        const available = modelAvailability(model);
        if (!available.selectable) state.selected.delete(model.id);
        const status = available.distribution || (available.incompatibilities.length ? available.incompatibilities.join(' ') : available.technical.length ? 'Instalação: ' + available.technical.join(' ') : available.missing.length ? 'Séries ausentes: ' + available.missing.join(', ') : available.duplicate ? 'Associe séries diferentes a cada canal.' : available.warnings.length ? 'Confira as associações sugeridas. ' + available.warnings.join(' ') : 'Disponível');
        return '<div class="nr-model' + (!available.selectable ? ' nr-unavailable' : '') + '"><div class="nr-model-main"><label class="nr-model-title nr-switch"><input type="checkbox" role="switch" data-model="' + esc(model.id) + '"' + (state.selected.has(model.id) ? ' checked' : '') + (!available.selectable ? ' disabled' : '') + '><span class="nr-switch-track" aria-hidden="true"></span><span class="nr-model-name">' + esc(model.label) + '<span class="nr-model-key"> (' + esc(model.id) + ')</span></span></label><p>' + esc('Entradas: ' + roles(model).join(', ')) + '</p><p' + (available.warnings.length ? ' class="nr-warning"' : '') + '>' + esc(status) + '</p><div class="nr-bindings">' + roles(model).map(role => {
          const binding = (state.bindings[model.id] || []).find(b => b.role === role);
          return '<label>' + esc(role) + '<select data-binding-model="' + esc(model.id) + '" data-role="' + esc(role) + '"><option value="">Selecionar série</option>' + state.series.map((series, index) => series.modality === (role === 'CT' ? 'CT' : 'MR') ? '<option translate="no" value="' + esc(series.ticket) + '"' + (binding && binding.series_ticket === series.ticket ? ' selected' : '') + '>' + esc(seriesLabel(series,index)) + '</option>' : '').join('') + '</select></label>';
        }).join('') + '</div>' + classOptions(model) + '</div><button type="button" class="ui-bt nr-help-trigger" data-help="' + esc(model.id) + '" aria-label="Ajuda sobre ' + esc(model.label) + '">?</button></div>';
      }).join('');
    }).join('');
    updateStart();
  }
  function seriesCard(series, index) {
    const ticket = esc(series.ticket);
    const label = esc(seriesLabel(series, index));
    const count = Number(series.slice_count);
    const details = [esc(series.modality), count > 0 ? count + ' <span data-radai-frase>Cortes</span>' : ''].filter(Boolean);
    return '<li class="nr-series"><button type="button" class="ui-cartao nr-preview" data-preview="' + ticket +
      '" aria-haspopup="dialog" aria-labelledby="nr-action-' + index + ' nr-label-' + index + '">' +
      '<span class="nr-thumb"><img alt="" loading="lazy" decoding="async" src="/api/lote/miniatura?b=' +
      esc(encodeURIComponent(series.ticket)) + '"><span class="nr-thumb-error" hidden data-radai-frase>Prévia indisponível</span></span>' +
      '<span class="nr-caption"><strong class="ui-cartao-tit" id="nr-label-' + index + '" translate="no">' + label +
      '</strong><span class="nr-series-meta">' + details.join(' · ') + '</span><span class="nr-preview-action" id="nr-action-' + index +
      '" data-radai-frase>Ampliar série</span></span></button>' +
      '<button type="button" class="ui-bt nr-remove" data-remove="' + ticket + '" aria-labelledby="nr-remove-' + index + ' nr-label-' + index +
      '"><span id="nr-remove-' + index + '" data-radai-frase>Remover</span></button></li>';
  }
  const gallery = el('series-list');
  gallery.addEventListener('error', event => {
    const image = event.target;
    if (!image.matches?.('.nr-thumb img')) return;
    image.hidden = true;
    image.nextElementSibling.hidden = false;
  }, true);
  // The shared viewer delegates pixel loading to the host. Keep a failed slice
  // navigable and clear its message as soon as another slice decodes.
  function viewerImageStatus(event) {
    const image = event.target;
    if (!image.matches?.('.ui-visor-img > img')) return;
    const frame = image.parentElement;
    const message = frame.querySelector('.nr-viewer-error');
    if (event.type === 'load') {
      message?.remove();
      return;
    }
    if (window.uiCarregando) window.uiCarregando(frame, false);
    if (!message) {
      const status = document.createElement('span');
      status.className = 'nr-viewer-error';
      status.setAttribute('role', 'status');
      status.textContent = window.radaiFrase ? window.radaiFrase('Prévia indisponível') : 'Prévia indisponível';
      frame.appendChild(status);
    }
  }
  let previewRequest = 0;
  async function openSeriesPreview(button) {
    const request = ++previewRequest;
    const index = state.series.findIndex(series => series.ticket === button.dataset.preview);
    if (index < 0) return;
    const series = state.series[index];
    const ticket = encodeURIComponent(series.ticket);
    let total = Number(series.slice_count);
    try {
      if (!window.uiVisor) throw Error(pickerUnavailable);
      if (!(total > 0)) {
        const info = await fetch('/api/lote/miniatura?b=' + ticket, {method: 'HEAD'});
        total = Number(info.headers.get('X-RadAI-Cortes'));
        if (!info.ok || !total) throw Error('Prévia indisponível');
      }
      if (request !== previewRequest || !button.isConnected) return;
      const windows = series.modality === 'MR' ? [{chave:'auto', rotulo:'automática'}] :
        [{chave:'mediastino', rotulo:'mediastino'}, {chave:'pulmao', rotulo:'pulmão'}, {chave:'osso', rotulo:'osso'}];
      const viewer = window.uiVisor({
        titulo:seriesLabel(series, index), origem:button, total, janelas:windows, cranial:series.cranial,
        cabecalho:[['Modalidade', series.modality], ['Cortes', String(total)]],
        src:(slice, windowKey) => '/api/lote/corte?b=' + ticket + '&corte=' + slice + '&janela=' + encodeURIComponent(windowKey),
        aoFechar:() => {
          document.removeEventListener('error', viewerImageStatus, true);
          document.removeEventListener('load', viewerImageStatus, true);
        },
      });
      document.addEventListener('error', viewerImageStatus, true);
      document.addEventListener('load', viewerImageStatus, true);
      viewer?.ajustar?.();
      if (series.cranial == null && viewer?.definirSentido) {
        fetch('/api/lote/sentido', {method:'POST', headers:{'Content-Type':'application/json'},
          body:JSON.stringify({b:series.ticket})})
          .then(response => response.json()).then(({cranial}) => {
            if (cranial === 1 || cranial === -1) {
              series.cranial = cranial;
              viewer.definirSentido(cranial);
            }
          }).catch(() => {});
      }
    } catch (error) {
      if (request === previewRequest && button.isConnected) el('scan-status').textContent = error.message;
    }
  }
  gallery.addEventListener('click', event => {
    const button = event.target.closest('button[data-preview]');
    if (button) openSeriesPreview(button);
  });
  function renderSeries() {
    const count = state.series.length;
    window.uiCartaoRotulo('nr-picker-open', count ? String(count) : '');
    if (count) {
      const label = document.createElement('span');
      label.setAttribute('data-radai-frase', '');
      label.textContent = 'Séries selecionadas';
      el('nr-picker-count').prepend(label, ' · ');
    }
    gallery.innerHTML = state.series.map(seriesCard).join('');
    el('reference').disabled = !state.series.length;
    el('reference').innerHTML = state.series.map((s,i) => '<option translate="no" value="' + esc(s.ticket) + '"' + (s.ticket === state.reference ? ' selected' : '') + '>' + esc(seriesLabel(s,i)) + '</option>').join('') || '<option value="">Carregue as séries</option>';
  }
  const seriesDisplay = new Map();
  function rememberSeries(row) {
    if (!row.bilhete) return;
    const display = seriesDisplay.get(row.bilhete) || {};
    if (row.desc || row.descricao) display.description = row.desc || row.descricao;
    if (Number(row.cortes) > 0) display.slice_count = Number(row.cortes);
    if (row.numero != null && row.numero !== '') display.series_number = String(row.numero);
    if (row.cranial === 1 || row.cranial === -1) display.cranial = row.cranial;
    seriesDisplay.set(row.bilhete, display);
  }
  async function loadSelection(tickets, signal, replaceExam = false) {
    const data = await api('selection', {tickets, category:state.category}, signal);
    if (signal && signal.aborted) throw new DOMException('Cancelled', 'AbortError');
    const series = (data.series || []).map(s => {
      const display = seriesDisplay.get(s.ticket) || {};
      return {...s, ...display, slice_count: s.slice_count || display.slice_count};
    });
    if (new Set(series.map(s => s.group_key).filter(Boolean)).size > 1) throw Error(differentExam);
    if (series.length !== new Set(tickets).size) throw Error('A pasta contém séries que não puderam ser identificadas.');
    const resetChoices = replaceExam || (state.series.length > 0 && series.length === 0);
    const previous = resetChoices ? {} : state.bindings;
    if (resetChoices) {
      state.reference = '';
      state.selected.clear();
      classSelections.clear();
    }
    state.series = series; state.models = data.models || []; state.bindings = {};
    state.models.forEach(m => { const bindings = new Map((m.bindings || []).map(b=>[b.role,b])); (previous[m.id] || []).filter(b=>state.series.some(s=>s.ticket===b.series_ticket)).forEach(b=>bindings.set(b.role,b)); state.bindings[m.id] = Array.from(bindings.values()).filter(b=>state.series.some(s=>s.ticket===b.series_ticket)); });
    if (!state.series.some(s => s.ticket === state.reference)) {
      const preferred = state.category === 'anatomia' ? 'T1' : 'T1c';
      const series = state.series.find(s => (s.sequence_candidates || []).some(c => c.role === preferred || c.sequence === preferred));
      state.reference = (series || state.series[0] || {}).ticket || '';
    }
    renderSeries(); renderModelSelection(el('models'));
    el('scan-status').textContent = state.series.length ? state.series.length + ' série(s) carregada(s). Confira os papéis sugeridos.' : 'Nenhuma série selecionada.';
  }
  let seriesPopup, archive, folderRequest, selectingFolder;
  function cancelFolderRequest() {
    if (folderRequest) folderRequest.abort();
    folderRequest = null;
    if (selectingFolder) {
      selectingFolder = null;
      state.selecting = false;
      updateStart();
    }
  }
  function pickerStatus(message) {
    const status = el('nr-picker-status');
    status.textContent = window.radaiFrase ? window.radaiFrase(message) : message;
    status.hidden = !message;
  }
  async function changeSeries(ticket, adding) {
    if (!state.token || state.selecting || !ticket) return;
    const current = state.series.map(s => s.ticket);
    if (adding === current.includes(ticket)) return;
    const request = adding ? new AbortController() : null;
    if (request) {
      cancelFolderRequest();
      folderRequest = request;
      selectingFolder = request.signal;
    }
    const anchor = el('nr-picker-open');
    const removals = Array.from(el('series-list').querySelectorAll('[data-remove]'));
    state.selecting = true;
    anchor.disabled = true;
    removals.forEach(button => { button.disabled = true; });
    pickerStatus('');
    updateStart();
    let applied = false;
    try {
      await loadSelection(adding ? [...current, ticket] : current.filter(b => b !== ticket), request?.signal);
      applied = true;
    } catch (error) {
      if (!request?.signal.aborted) {
        if (adding && seriesPopup.aberto()) pickerStatus(error.message);
        else el('scan-status').textContent = error.message;
      }
    } finally {
      if (!request || selectingFolder === request.signal) {
        selectingFolder = null;
        state.selecting = false;
      }
      anchor.disabled = false;
      removals.forEach(button => { button.disabled = false; });
      updateStart();
    }
    if (applied && adding) {
      seriesPopup.fechar();
      anchor.focus();
    }
  }
  function setupSeriesPicker() {
    const popupId = 'nr-series-picker';
    const shared = el(popupId + '_form') && window.uiCarregarImagens;
    if (!window.uiPopupSerie || !window.uiTabelaAcervo || !window.uiCartaoRotulo ||
        (!shared && (!window.uiVarrerLista || !window.uiExplorador))) {
      throw Error(pickerUnavailable);
    }
    const anchor = el('nr-picker-open');
    const results = el('nr-picker-results');
    const scanOptions = {uso: 'series', chave: 'neuro-study', opcoes: {modalidades: allowedModalities}};
    const seriesDescription = row => [row.modalidade, row.desc || row.curto, row.espessura_mm == null ? '' : row.espessura_mm + ' mm'].filter(Boolean).join(' · ');
    const resultButton = row => '<span translate="no">' + esc(seriesDescription(row)) + '</span>';
    const selectionLimit = 'Escolha as séries individualmente. É possível selecionar até 120 séries por exame.';
    let exams = [], individualExam, byTicket = new Map();
    function startFolderScan() {
      cancelFolderRequest();
      exams = [];
      individualExam = null;
      byTicket = new Map();
      const selectedTickets = new Set(state.series.map(s => s.ticket));
      for (const ticket of seriesDisplay.keys()) if (!selectedTickets.has(ticket)) seriesDisplay.delete(ticket);
      results.replaceChildren();
      pickerStatus('');
    }
    const belongsTo = (series, exam) => series.group_key === exam.key;
    async function chooseExam(exam, signal, singleTicket) {
      if (!exam || state.selecting || signal.aborted) return;
      const sameExam = state.series.filter(s => belongsTo(s, exam));
      const tickets = [...new Set([...sameExam.map(s => s.ticket), ...(singleTicket ? [singleTicket] : exam.tickets)])];
      if (tickets.length > 120) {
        individualExam = exam;
        if (!singleTicket) results.innerHTML = exam.tickets.map(ticket =>
          '<button type="button" class="ui-bt" data-b="' + esc(ticket) + '">' + resultButton(byTicket.get(ticket)) + '</button>').join('');
        pickerStatus(selectionLimit);
        return;
      }
      const replaceExam = state.series.length !== sameExam.length;
      selectingFolder = signal;
      state.selecting = true;
      updateStart();
      let applied = false;
      try {
        await loadSelection(tickets, signal, replaceExam);
        applied = true;
      } catch (error) {
        if (!signal.aborted) pickerStatus(error.message);
      } finally {
        if (selectingFolder === signal) {
          selectingFolder = null;
          state.selecting = false;
          updateStart();
        }
      }
      if (applied) {
        seriesPopup.fechar();
        anchor.focus();
      }
    }
    async function folderScanned(rows, scan) {
      startFolderScan();
      for (const row of rows || []) {
        if (row.bilhete && !row.carregando && allowedModalities.includes(row.modalidade)) {
          rememberSeries(row);
          byTicket.set(row.bilhete, row);
        }
      }
      if (!byTicket.size) return;
      folderRequest = new AbortController();
      const {signal} = folderRequest;
      const tickets = [...byTicket.keys()];
      const groups = new Map();
      let identified = 0;
      pickerStatus('Identificando os exames…');
      try {
        for (let start = 0; start < tickets.length; start += 120) {
          const data = await api('selection', {tickets:tickets.slice(start, start + 120),
            category:state.category, identify_only:true}, signal);
          if (signal.aborted) return;
          for (const s of data.series || []) {
            if (!s.group_key || !byTicket.has(s.ticket) || !allowedModalities.includes(s.modality)) continue;
            if (!groups.has(s.group_key)) groups.set(s.group_key, {key:s.group_key, modalities:new Set(), tickets:[]});
            const exam = groups.get(s.group_key);
            exam.modalities.add(s.modality);
            exam.tickets.push(s.ticket);
            identified++;
          }
        }
        exams = [...groups.values()];
        const partial = identified !== tickets.length;
        const incompleteScan = scan && (scan.parado || scan.erro || (scan.avisos || []).length);
        if (exams.length === 1 && !partial && !incompleteScan && state.series.every(s => belongsTo(s, exams[0]))) {
          await chooseExam(exams[0], signal);
          return;
        }
        results.innerHTML = exams.map((exam, index) => {
          const row = byTicket.get(exam.tickets[0]);
          const date = String(row.date || row.data || '').replace(/^(\d{4})(\d{2})(\d{2})$/, '$1-$2-$3');
          const details = [row.nome || row.pid, date, [...exam.modalities].sort().join(' / ')].filter(Boolean).join(' · ');
          return '<button type="button" class="ui-bt" data-exam="' + index + '"><span data-radai-frase>Exame</span> ' +
            (index + 1) + ' · <span translate="no">' + esc(details) + '</span></button>';
        }).join('');
        pickerStatus(partial ? 'A pasta contém séries que não puderam ser identificadas.' : 'Escolha um exame para carregar suas séries.');
      } catch (error) {
        if (!signal.aborted) pickerStatus(error.message);
      }
    }
    if (shared) {
      const pickerRoot = el(popupId);
      const folder = el(popupId + '_pasta');
      pickerRoot.addEventListener('submit', startFolderScan, true);
      folder.addEventListener('change', startFolderScan);
      folder.addEventListener('keydown', e => { if (e.key === 'Enter') startFolderScan(); }, true);
      el(popupId + '_dias')?.addEventListener('change', startFolderScan, true);
      el(popupId + '_fora')?.addEventListener('click', startFolderScan, true);
      window.uiCarregarImagens(popupId, {...scanOptions,
        linha: resultButton,
        aoFim: folderScanned,
        aoFechar: cancelFolderRequest,
        aoErro: () => { startFolderScan(); },
      });
    } else {
      setupLegacyFolderPicker(scanOptions, results, resultButton, startFolderScan, folderScanned);
    }
    seriesPopup = window.uiPopupSerie(popupId, {aoAbrir: () => {
      const listed = exams.length && results.querySelector('button[data-exam], button[data-b]');
      if (listed && !folderRequest) folderRequest = new AbortController();
      pickerStatus(listed ? (individualExam ? selectionLimit : 'Escolha um exame para carregar suas séries.') : '');
      if (!archive) archive = window.uiTabelaAcervo('nr-picker-archive', {
        filtro: row => !row.modalidade || allowedModalities.includes(row.modalidade),
        aoAbrir: row => {
          if (!row.modalidade || allowedModalities.includes(row.modalidade)) {
            cancelFolderRequest();
            rememberSeries(row);
            changeSeries(row.bilhete, true);
          }
        },
      });
    }});
    results.addEventListener('click', event => {
      const button = event.target.closest('button[data-exam], button[data-b]');
      if (!button || !exams.length || !results.contains(button)) return;
      if (!folderRequest) folderRequest = new AbortController();
      if (button.hasAttribute('data-exam')) chooseExam(exams[Number(button.dataset.exam)], folderRequest.signal);
      else if (individualExam?.tickets.includes(button.dataset.b)) chooseExam(individualExam, folderRequest.signal, button.dataset.b);
    });
    anchor.disabled = false;
    seriesPopup.abrir(anchor);
  }
  function setupLegacyFolderPicker(scanOptions, results, resultButton, startFolderScan, folderScanned) {
    const folder = el('nr-picker-folder');
    const browse = el('nr-picker-browse');
    let scan;
    window.uiPopupSerie('nr-series-picker', {aoFechar: () => { if (scan) scan.parar(true); cancelFolderRequest(); }});
    browse.addEventListener('click', () => window.uiExplorador({
      origem: browse, inicial: folder.value,
      aoUsar: path => { if (path) { folder.value = path; el('nr-picker-form').requestSubmit(); } },
    }));
    el('nr-picker-form').addEventListener('submit', event => {
      event.preventDefault();
      if (!folder.value.trim()) { folder.focus(); return; }
      startFolderScan();
      scan = window.uiVarrerLista({...scanOptions,
        alvo: results, estado: 'nr-picker-scan-status',
        pasta: folder.value.trim(), dias: 'nr-picker-days',
        vazio: 'Nenhuma série nesta pasta.',
        linha: resultButton,
        aoFim: folderScanned,
        aoErro: startFolderScan,
      });
    });
  }
  let helpAnchor = null;
  function localModelHelp(model) {
    const methods={anatomy_cerebra_ants:'CerebrA / ANTs: Propagação de atlas por registro deformável',anatomy_synthseg:'U-Net (SynthSeg)',glioma_attention_unet3d:'Attention U-Net 3D (WT / TC / ET)',metastasis_qtim:'Ensemble U-Net 3D (Brain-Mets-Seg / QTIM)',cranio_buti:'Buti (Local Suite)'};
    return {method:methods[model.id]||(model.id.startsWith('MRI_')?'AGU-Net (Raidionics)':''),preparation:'Entrada preparada; resultado na referência.',limitations:'Confira cada estrutura. Contornos não comprovam função ou invasão tumoral.'};
  }
  function openModelHelp(anchor, modelId) {
    const model = state.models.find(m => m.id === modelId); if (!model) return;
    const help = {...localModelHelp(model),...(model.help || {})}, availability = modelAvailability(model);
    const text = value => Array.isArray(value) ? value.map(x => typeof x === 'object' ? x.label || x.message || '' : x).join(' ') : typeof value === 'object' ? '' : value || '';
    const availabilityText = availability.distribution || (availability.incompatibilities.length ? availability.incompatibilities.join(' ') : availability.selectable ? 'Selecionável. ' + availability.warnings.join(' ') : availability.technical.length ? 'Problema de instalação: ' + availability.technical.join(' ') : availability.duplicate ? 'Associe séries diferentes aos canais de entrada.' : 'Associe as entradas ausentes: ' + availability.missing.join(', '));
    const fields = [['O que segmenta',help.summary || help.purpose || (model.classes || []).map(c => c.label || c.class_id).join(', ')],['Séries necessárias',roles(model).join(', ')],['Neste exame',availabilityText],['Método',help.method || help.architecture],['Preparação',help.preparation || help.preprocessing],['Classes', (model.classes || []).map(c => c.label || c.class_id).join(', ')],['Equipamento',help.hardware || help.device || 'Segue a preferência global de processamento e os ambientes verificados na instalação.'],['Limitações',help.limitations],['Versão',model.revision],['Licença',typeof model.license === 'string' ? model.license : Object.entries(model.license || {}).filter(([k,v]) => k !== 'sources' && v != null).map(([k,v]) => k + ': ' + v).join('; ')]];
    el('help-content').innerHTML = '<h2 id="help-title">' + esc(model.label) + '</h2>' + fields.filter(([,v]) => text(v)).map(([label,value]) => '<h3>' + esc(label) + '</h3><p>' + esc(text(value)) + '</p>').join('') + '<p>Objetivo do modelo não é diagnóstico. WT: tumor total; TC: núcleo tumoral; ET: componente com realce. Licença não comprova validação clínica. Tempo e precisão não medidos nesta instalação.</p>' + (/^https:\/\//.test(model.source_url || '') ? '<a target="_blank" rel="noopener noreferrer" href="' + esc(model.source_url) + '">Fonte e publicação</a>' : '');
    helpAnchor = anchor; el('model-help').hidden = false; el('help-close').focus();
  }
  function closeHelp() { el('model-help').hidden = true; if (helpAnchor && helpAnchor.isConnected) helpAnchor.focus(); }
  const statusLabels = {queued:'Na fila comum',preparing:'Preparando séries',running:'Segmentando',restoring:'Retornando à referência',exporting:'Exportando RTSTRUCT',visualizing:'Preparando visualização',completed:'Concluído',partial:'Resultado parcial',empty:'Máscaras vazias; isso não confirma ausência de tumor',failed:'Falha no estudo',cancelled:'Estudo cancelado',interrupted:'Estudo interrompido'};
  const terminal = status => ['completed','partial','empty','failed','cancelled','interrupted'].includes(status);
  function viewOf(job) { return job.status && !terminal(job.status) ? job : job.result || job.view || job; }
  function jobKey(job) { const v = viewOf(job); return String(v.study_id || job.id || '') + ':' + (v.revision || 0); }
  function jobId(job) { const v = viewOf(job); return v.study_id || job.id; }
  function renderJobs() {
    const selected = state.job && jobKey(state.job);
    const references=Array.from(new Set(state.jobs.map(job=>viewOf(job).reference_ticket||job.reference||jobId(job))));
    el('result-series').innerHTML = state.jobs.length ? state.jobs.map(job => { const v = viewOf(job),reference=v.reference_ticket||job.reference||jobId(job); return '<option value="' + esc(jobKey(job)) + '"' + (jobKey(job) === selected ? ' selected' : '') + '>Série ' + (references.indexOf(reference)+1) + ' · revisão ' + (v.revision || 1) + ' · ' + esc(statusLabels[job.status || v.status] || 'Na fila comum') + '</option>'; }).join('') : '<option value="">Nenhum estudo disponível</option>';
  }
  async function refreshJobs() { const data = await api('studies'),records=[...(data.results||[]),...(data.studies||(Array.isArray(data)?data:[]))]; state.jobs=Array.from(new Map(records.map(job=>[jobKey(job),job])).values()); renderJobs(); if (!state.job && state.jobs.length) await selectResultSeries(jobKey(state.jobs[state.jobs.length-1])); }
  function artifactURL(artifact) { return '/neuro/api/studies/' + encodeURIComponent(jobId(state.job)) + '/artifacts/' + encodeURIComponent(artifact.artifact_id); }
  function clearScene() {
    if (el('viewer')) delete el('viewer').dataset.contourReference;
    closeExpandedPlane();
    if (state.abort) state.abort.abort(); state.abort = new AbortController(); state.scene = null; state.rois = {}; state.artifactMap = {}; el('viewer').hidden = true;
    ['axial','coronal','sagittal'].forEach(name => el('slice-' + name).replaceChildren());
    if (window.r3gLimpar) r3gLimpar(); if (window.R3G) { R3G.anim = null; R3M.lig = {}; R3M.alfa = {}; }
  }
  async function selectResultSeries(key, revision) {
    if(revision !== undefined) key=key+':'+revision;
    else if(!String(key).includes(':')){const candidate=state.jobs.filter(job=>jobId(job)===key).sort((a,b)=>(viewOf(b).revision||0)-(viewOf(a).revision||0))[0];if(candidate)key=jobKey(candidate);}
    clearTimeout(state.poll); const generation = ++state.generation; clearScene();
    const listed = state.jobs.find(job => jobKey(job) === key); if (!listed) return;
    state.job = listed; renderJobs();
    try {
      const revision = viewOf(listed).revision;
      const data = await api('studies/' + encodeURIComponent(jobId(listed)) + (revision ? '?revision=' + encodeURIComponent(revision) : ''), undefined, state.abort.signal);
      if (generation !== state.generation) return;
      state.job = data; renderJobStatus(data); const view = viewOf(data);
      state.jobs=Array.from(new Map([...state.jobs.filter(job=>jobKey(job)!==key),data].map(job=>[jobKey(job),job])).values());renderJobs();
      if ((view.artifacts || []).length) await showStudyResult(view, generation);
      if (!terminal(data.status || view.status)) state.poll = setTimeout(() => pollJob(generation), 1500);
    } catch (e) { if (e.name !== 'AbortError' && generation === state.generation) el('job-status').textContent = e.message; }
  }
  function renderJobStatus(job) {
    const view = viewOf(job), status = job.status || view.status;
    const progress=job.progress||{},current=progress.model_id||progress.model||job.current_model;
    const results=(view.models||[]).map(result=>{const model=state.models.find(m=>m.id===result.model_id);return (model?model.label:result.model_id)+': '+(statusLabels[result.status]||result.status);});
    el('job-status').textContent = (statusLabels[status] || status || '') + (current ? ' · ' + ((state.models.find(m=>m.id===current)||{}).label||current) : '') + (view.export_status === 'failed' || view.export_status === 'incomplete' ? '. A publicação do RTSTRUCT não foi concluída.' : '') + (results.length ? '. '+results.join('; ')+'.' : '');
    el('cancel').hidden = terminal(status); el('retry').hidden = !['failed','partial','interrupted','cancelled'].includes(status);
    el('export-partial').hidden = status !== 'partial' || view.export_status !== 'pending';
    const downloads = (view.artifacts || []).filter(a => a.kind === 'derived_ct' || a.kind === 'rtstruct');
    el('downloads').innerHTML = downloads.map(a => '<a class="ui-bt" href="' + esc(artifactURL(a)) + '" download>' + (a.kind === 'derived_ct' ? 'Baixar série DICOM (ZIP)' : 'Baixar RTSTRUCT não aprovado') + '</a>').join('');
    el('result-warnings').innerHTML = (view.models || []).flatMap(model => (model.warnings || []).filter(w => w.code === 'class_lost_on_reference_grid').map(w => '<p class="nr-warning">' + esc(model.model_id + ' · ' + w.class_id) + ': Classe não vazia ficou vazia ao retornar à grade de referência. ' + esc(w.working_voxels + ' → ' + w.reference_voxels) + ' voxels. Interpolação: vizinho mais próximo.</p>')).join('');
  }
  async function pollJob(generation) {
    if (generation !== state.generation || !state.job) return;
    try { const data = await api('studies/' + encodeURIComponent(jobId(state.job)), undefined, state.abort.signal); if (generation !== state.generation) return; state.job = data; renderJobStatus(data); const view = viewOf(data); if (terminal(data.status || view.status)) { await showStudyResult(view,generation); await refreshJobs(); } else state.poll = setTimeout(() => pollJob(generation),1500); } catch(e) { if (e.name !== 'AbortError' && generation === state.generation) { el('job-status').textContent = 'Acompanhamento interrompido. Atualize para consultar o estudo.'; } }
  }
  async function artifactFetch(name, type) {
    const artifact = state.artifactMap[name]; if (!artifact) throw Error('Visualização indisponível nesta revisão.');
    const response = await fetch(artifactURL(artifact), {headers:{'X-Neuro-Token':state.token},signal:state.abort.signal}); if (!response.ok) throw Error('Não foi possível abrir a visualização.'); return response[type]();
  }
  async function showStudyResult(view, generation) {
    if(typeof generation !== 'number'){
      if(generation && view.reference_ticket && generation !== view.reference_ticket) throw Error('O resultado pertence a outra série de referência.');
      generation=++state.generation;clearScene();state.job={id:view.study_id,status:view.status,result:view};renderJobStatus(state.job);
    }
    state.artifactMap = Object.fromEntries((view.artifacts || []).map(a => [a.logical_name,a]));
    if (!state.artifactMap['view.json']) return;
    const scene = await artifactFetch('view.json','json'); if (generation !== state.generation) return;
    state.scene = scene; el('viewer').hidden = false;
    el('viewer').dataset.contourReference = view.reference_ticket || '';
    (scene.rois || []).forEach(roi => { state.rois[roi.id] = {...roi,visible:roi.visible !== false,opacity:roi.opacity == null ? .7 : roi.opacity}; });
    ['axial','coronal','sagittal'].forEach(name => { const p = scene.planes[name], range = el('range-' + name); range.max = Math.max(0,p.count-1); range.value = p.center; loadSlice(name,generation); });
    renderStructures(); initialize3D(); loadVisibleMeshes(generation);
  }
  const sliceRequests = {};
  async function loadSlice(name,generation) {
    if (!state.scene) return; const number = ++sliceRequests[name] || (sliceRequests[name] = 1), index = +el('range-' + name).value;
    el('count-' + name).textContent = (index+1) + ' / ' + state.scene.planes[name].count;
    try { const text = await artifactFetch(state.scene.planes[name].slices[index],'text'); if (generation !== state.generation || sliceRequests[name] !== number) return; const xml = new DOMParser().parseFromString(text,'image/svg+xml'); const svg = xml.documentElement; if (svg.localName !== 'svg' || svg.querySelector('script,foreignObject')) throw Error('Corte inválido.'); el('slice-' + name).replaceChildren(document.importNode(svg,true)); syncVisibility(); } catch(e) { if (e.name !== 'AbortError' && generation === state.generation) el('mesh-status').textContent = e.message; }
  }
  function filteredROIs() { const search = el('structure-search').value.toLocaleLowerCase(); return Object.values(state.rois).filter(r => r.label.toLocaleLowerCase().includes(search)); }
  function renderStructures() {
    const visible = new Set(filteredROIs().map(r => r.id));
    const format = new Intl.NumberFormat(document.documentElement.lang || 'pt-BR', {maximumSignificantDigits: 4});
    el('structures').innerHTML = Object.values(state.rois).map(r => {
      const volume = Number.isFinite(r.volume_cm3) ? ' <small>' + esc(format.format(r.volume_cm3)) + ' cm³</small>' : '';
      return '<div class="nr-roi"' + (!visible.has(r.id) ? ' hidden' : '') + '><label><input type="checkbox" data-roi-visible="' + esc(r.id) + '"' + (r.visible ? ' checked' : '') + '><span class="nr-color" style="background:rgb(' + r.color.map(Number).join(',') + ')"></span>' + esc(r.label) + volume + '</label><input type="range" min="0" max="100" value="' + Math.round(r.opacity*100) + '" data-roi-opacity="' + esc(r.id) + '" aria-label="Opacidade de ' + esc(r.label) + '"></div>';
    }).join('');
  }
  function syncVisibility() { document.querySelectorAll('.nr-slice [data-roi]').forEach(node => { const roi = state.rois[node.dataset.roi]; if (roi) { node.style.display = roi.visible ? '' : 'none'; node.style.opacity = roi.opacity; } }); if (window.R3M) Object.values(state.rois).forEach(r => { R3M.lig[r.id] = r.visible; R3M.alfa[r.id] = r.opacity; }); if(window.r3gPedir) r3gPedir(); }
  function initialize3D() {
    if (!window.r3gDetectar) { el('mesh-status').textContent = 'O visor 3D do Local Suite não está disponível.'; return; }
    window.r3El = id => el(id);
    window.r3mVisiveis = () => Object.entries(R3G.objs).filter(([id]) => state.rois[id] && state.rois[id].visible).map(([id,obj]) => [obj,state.rois[id].opacity]);
    window.r3mRecuo = () => { R3G.gl = null; el('mesh-status').textContent = '3D indisponível neste navegador. Os cortes permanecem disponíveis.'; };
    if (!R3G.gl) { const reason = r3gDetectar(); if (reason) { r3mRecuo(); return; } }
    if (!el('cvGL').dataset.bound) { r3gLigar(el('cvGL')); el('cvGL').dataset.bound = '1'; }
    R3M.modo = 'gl'; r3gCena(state.scene.bounds); el('mesh-status').textContent = 'Arraste para girar; use a roda para aproximar.'; syncVisibility();
  }
  async function loadVisibleMeshes(generation) {
    if (!window.R3G || !R3G.gl || !state.scene) return;
    for (const roi of Object.values(state.rois)) {
      if (!roi.visible || !roi.mesh || R3G.objs[roi.id] || roi.loading) continue; roi.loading = true;
      try { const bytes = await artifactFetch(roi.mesh,'arrayBuffer'); if (generation !== state.generation) return; if (roi.visible) r3gSubir(roi.id,r3gLerStl(bytes),roi.color); syncVisibility(); } catch(e) { if (e.name !== 'AbortError' && generation === state.generation) el('mesh-status').textContent = 'Uma superfície não pôde ser aberta. Os cortes continuam disponíveis.'; } finally { roi.loading = false; }
    }
  }
  let expandedPlane = null, expandedAnchor = null;
  function closeExpandedPlane() {
    if (!expandedPlane) return;
    const button = expandedPlane.querySelector('[data-enlarge]');
    expandedPlane.classList.remove('nr-expanded'); expandedPlane.removeAttribute('role');
    expandedPlane.removeAttribute('aria-modal');
    button.textContent = 'Ampliar'; button.setAttribute('aria-expanded','false');
    expandedPlane = null;
    if (expandedAnchor && expandedAnchor.isConnected) expandedAnchor.focus();
  }
  function enlargePlane(name, anchor) {
    const plane = document.querySelector('[data-plane="'+name+'"]');
    if (!plane || !state.scene) return;
    if (expandedPlane === plane) { closeExpandedPlane(); return; }
    closeExpandedPlane(); expandedAnchor = anchor; expandedPlane = plane;
    plane.classList.add('nr-expanded'); plane.setAttribute('role','dialog');
    plane.setAttribute('aria-modal','true'); plane.setAttribute('aria-label',name);
    const button = plane.querySelector('[data-enlarge]');
    button.textContent = 'Voltar'; button.setAttribute('aria-expanded','true'); button.focus();
  }
  function setPrimaryPlane(name) {
    document.querySelectorAll('[data-plane]').forEach(plane=>{
      plane.dataset.primary=String(plane.dataset.plane===name);
      plane.querySelector('[data-primary-plane]').setAttribute('aria-pressed',String(plane.dataset.plane===name));
    });
  }
  document.addEventListener('dblclick',event=>{
    const slice=event.target.closest('.nr-slice');
    if(slice){const plane=slice.closest('[data-plane]');enlargePlane(plane.dataset.plane,plane.querySelector('[data-enlarge]'));}
  });
  document.addEventListener('click', event => {
    const enlarge=event.target.closest('[data-enlarge]'); if(enlarge){enlargePlane(enlarge.dataset.enlarge,enlarge);return;}
    const primary=event.target.closest('[data-primary-plane]'); if(primary){setPrimaryPlane(primary.dataset.primaryPlane);return;}
    const help = event.target.closest('[data-help]'); if (help) { openModelHelp(help,help.dataset.help); return; }
    if (!el('model-help').hidden && !el('model-help').contains(event.target)) closeHelp();
    const remove = event.target.closest('[data-remove]'); if (remove) changeSeries(remove.dataset.remove, false);
    const view = event.target.closest('[data-view]'); if (view && window.R3G && R3G.gl) { R3G.M = r3MatrizDaVista6(view.dataset.view); R3G.anim = null; r3gPedir(); }
  });
  el('help-close').addEventListener('click',closeHelp);
  document.addEventListener('keydown',event => {
    if (!el('model-help').hidden) {if(event.key==='Escape')closeHelp();else if(event.key==='Tab'&&window.uiPrenderFoco)uiPrenderFoco(el('model-help'),event);return;}
    if(expandedPlane){if(event.key==='Escape')closeExpandedPlane();else if(event.key==='Tab'&&window.uiPrenderFoco)uiPrenderFoco(expandedPlane,event);}
  });
  el('anatomy-option').hidden = state.category === 'anatomia';
  el('include-anatomy').addEventListener('change', event => {
    if (!event.target.checked) for (const model of state.models) if (model.groups.includes('anatomia')) state.selected.delete(model.id);
    renderModelSelection(el('models'));
  });
  el('models').addEventListener('change',event => {
    const target=event.target;
    if (target.dataset.model) {
      if (target.checked) state.selected.add(target.dataset.model); else state.selected.delete(target.dataset.model);
      const classes = target.closest('.nr-model').querySelector('.nr-class-options');
      if (classes) classes.hidden = !target.checked;
      updateStart();
    }
    if (target.dataset.classModel) {
      const model = state.models.find(item => item.id === target.dataset.classModel);
      const classId = model.classes[Number(target.dataset.classIndex)].class_id;
      const classes = classSelections.get(model.id) || new Set(model.classes.map(item => item.class_id));
      if (target.checked) classes.add(classId); else classes.delete(classId);
      classSelections.set(model.id, classes);
      el('selection-status').textContent = classes.size ? '' : 'Escolha ao menos uma estrutura para a entrega deste modelo.';
      updateStart();
    }
    if (target.dataset.bindingModel) {
      const id=target.dataset.bindingModel, role=target.dataset.role;
      state.bindings[id]=(state.bindings[id]||[]).filter(b => b.role !== role);
      if (target.value) state.bindings[id].push({role,series_ticket:target.value,certainty:'certain',association_source:'manual',warnings:[]});
      renderModelSelection(el('models'));
    }
  });
  el('reference').addEventListener('change',() => {state.reference=el('reference').value;renderModelSelection(el('models'));});
  el('start').addEventListener('click',() => {
    try {
      const request=collectStudyRequest();
      if(typeof window.radaiRevAbrir !== 'function' || !el('radai_rev_corpo')) throw Error('A conferência comum não está disponível. Reabra a tela pelo Local Suite.');
      // Freeze at the explicit action, before opening the host's review dialog.
      const submit=async () => { try {el('start').disabled=true;const data=await api('studies',request);el('selection-status').textContent='Pedido enviado para a fila comum.';const created=data.studies||[];state.jobs=state.jobs.concat(created);renderJobs();if(created.length)await selectResultSeries(jobKey(created[0]));}catch(e){el('selection-status').textContent=e.message;}finally{updateStart();} };
      radaiRevAbrir(null,submit);
      el('radai_rev_sub').textContent='Uma série de referência selecionada. Nada começou ainda.';
      el('radai_rev_corpo').innerHTML='<h4>Modelos escolhidos</h4><ul>'+request.studies[0].model_ids.map(id=>'<li>'+esc((state.models.find(m=>m.id===id)||{}).label||id)+'</li>').join('')+'</ul><p>O resultado será devolvido à referência escolhida, com ROIs independentes por modelo e classe.</p>';
    } catch(e) {el('selection-status').textContent=e.message;}
  });
  el('refresh').addEventListener('click',async () => {const previous=state.job,selected=previous&&jobKey(previous),generation=state.generation;try{await refreshJobs();if(selected&&generation===state.generation){if(!state.jobs.some(job=>jobKey(job)===selected))state.jobs.push(previous);await selectResultSeries(selected);}}catch(e){if(generation===state.generation)el('job-status').textContent=e.message;}});
  el('result-series').addEventListener('change',() => selectResultSeries(el('result-series').value));
  el('cancel').addEventListener('click',async () => {if(!state.job)return;try {await api('studies/'+encodeURIComponent(jobId(state.job))+'/cancel',{});el('job-status').textContent='Cancelamento solicitado.';}catch(e){el('job-status').textContent=e.message;}});
  function repeatStudy(exportPartial) {
    if(!state.job)return;const ident=jobId(state.job);
    if(typeof window.radaiRevAbrir!=='function'||!el('radai_rev_corpo')){el('job-status').textContent='A conferência comum não está disponível. Reabra a tela pelo Local Suite.';return;}
    const request = exportPartial ? {explicit_request:true, export_partial:true} : {explicit_request:true};
    radaiRevAbrir(null,async()=>{try{const data=await api('studies/'+encodeURIComponent(ident)+'/retry',request),created=data.studies||[data.job||data];await refreshJobs();const job=created.find(j=>jobId(j)===ident)||state.jobs.find(j=>jobId(j)===ident);if(job){const byKey=new Map(state.jobs.map(j=>[jobKey(j),j]));byKey.set(jobKey(job),job);state.jobs=Array.from(byKey.values());await selectResultSeries(jobKey(job));}}catch(e){el('job-status').textContent=e.message;}});
    el('radai_rev_sub').textContent = exportPartial ? 'Exportar os contornos disponíveis como resultado parcial.' : 'Repetir os modelos que falharam neste estudo. Nada começou ainda.';
    el('radai_rev_corpo').textContent = exportPartial ? 'O RTSTRUCT incluirá as ROIs disponíveis desta execução. Os modelos que falharam não serão executados novamente.' : 'Resultados concluídos ou vazios que permanecem íntegros serão reutilizados. A fila repetirá as falhas e produzirá uma nova revisão e uma nova exportação.';
  }
  el('retry').addEventListener('click', () => repeatStudy(false));
  el('export-partial').addEventListener('click', () => repeatStudy(true));
  ['axial','coronal','sagittal'].forEach(name => {sliceRequests[name]=0;el('range-'+name).addEventListener('input',() => loadSlice(name,state.generation));});
  el('structure-search').addEventListener('input',renderStructures);
  el('structures').addEventListener('change',event => {const target=event.target;if(target.dataset.roiVisible){state.rois[target.dataset.roiVisible].visible=target.checked;syncVisibility();loadVisibleMeshes(state.generation);}});
  el('structures').addEventListener('input',event => {const target=event.target;if(target.dataset.roiOpacity){state.rois[target.dataset.roiOpacity].opacity=+target.value/100;syncVisibility();}});
  [['show-filtered',true],['hide-filtered',false]].forEach(([id,visible])=>el(id).addEventListener('click',()=>{filteredROIs().forEach(r=>{r.visible=visible;});renderStructures();syncVisibility();loadVisibleMeshes(state.generation);}));
  window.addEventListener('pagehide',()=>{clearTimeout(state.poll);clearScene();});
  window.NeuroStudy = {state,collectStudyRequest,renderModelSelection,openModelHelp,showStudyResult,selectResultSeries,modelAvailability,loadSelection};
  // Dynamic study content shares the host translator and language selection.
  // Match local phrase fragments too, so names, channel roles and counts stay
  // intact when a translated status is composed from several parts.
  let translationTimer;
  const keys=(window.NEURO_TRANSLATION_KEYS||[]).slice().sort((a,b)=>b.length-a.length);
  function translateDynamic(){
    if(!window.radaiFrase)return;
    clearTimeout(translationTimer);
    translationObserver.disconnect();
    try {
    const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT),nodes=[];
    while(walker.nextNode()){const node=walker.currentNode;if(node.parentElement&&node.parentElement.closest('.nr-wrap,#model-help,#radai_rev')&&!node.parentElement.closest('script,style,svg,[translate="no"]'))nodes.push(node);}
    function translated(value) {
      const source = value.trim();
      if (!source) return value;
      const exact = radaiFrase(source);
      if (exact !== source) return value.replace(source, () => exact);
      for (const key of keys) {
        if (!value.includes(key)) continue;
        const replacement = radaiFrase(key);
        if (replacement !== key) value = value.split(key).join(replacement);
      }
      return value;
    }
    nodes.forEach(node=>{const value=translated(node.nodeValue);if(value!==node.nodeValue)node.nodeValue=value;});
    document.querySelectorAll('.nr-wrap [aria-label],.nr-wrap [placeholder],#model-help [aria-label]').forEach(node=>['aria-label','placeholder'].forEach(attr=>{if(node.hasAttribute(attr)){const value=translated(node.getAttribute(attr));if(value!==node.getAttribute(attr))node.setAttribute(attr,value);}}));
    if(window.radaiRetraduzir)radaiRetraduzir();
    } finally {
      translationObserver.takeRecords();
      observeTranslationTargets();
    }
  }
  const translationObserver=new MutationObserver(()=>{clearTimeout(translationTimer);translationTimer=setTimeout(translateDynamic,0);});
  function observeTranslationTargets(){document.querySelectorAll('.nr-wrap,#model-help,#radai_rev').forEach(node=>translationObserver.observe(node,{childList:true,subtree:true,characterData:true}));}
  observeTranslationTargets();
  translateDynamic();
  if (window.RadaiDicomAdapters && el('viewer')) {
    window.RadaiDicomAdapters.register({scope:el('viewer'), selection:() => {
      const ticket=el('viewer').dataset.contourReference;
      return ticket ? {b:ticket,source:'thumbnail'} : null;
    }, ready:() => !!state.scene});
  }
  api('status').then(data => {
    state.token = data.token || data.csrf_token || '';
    if (!state.token) throw Error(pickerUnavailable);
    setupSeriesPicker();
  }).catch(error => { el('scan-status').textContent = error.message; })
    .then(refreshJobs).catch(error => { el('job-status').textContent = error.message; });
}());
