/* Independent plugin update, using the host's existing action vocabulary. */
(function () {
  'use strict';
  const panel = document.getElementById('neuro-update');
  if (!panel) return;
  const installing = panel.dataset.neuroInstall === '1';
  const settings = panel.dataset.neuroSettings === '1';
  const message = document.getElementById('neuro-update-message');
  const actions = document.getElementById('neuro-update-actions');
  const progress = document.getElementById('neuro-update-progress');
  const localFolder = document.getElementById('neuro-local-folder');
  const localBrowse = document.getElementById('neuro-local-browse');
  const localInspect = document.getElementById('neuro-local-inspect');
  const localMessage = document.getElementById('neuro-local-message');
  const localDetails = document.getElementById('neuro-local-source');
  const releaseRefresh = document.getElementById('neuro-release-refresh');
  const state = {last: null, timer: null, confirm: false, posting: false, initial: '', initialToken: '', initialPid: null, initialSeen: false, targetVersion: '', started: false, attempt: 0, fileProgress: null, byteProgress: null, downloadProgress: null, verificationFileProgress: null, verificationByteProgress: null, restarting: false, awaitingRestart: false, view: '', consentKey: '', consentChecked: false, consentRequired: false, consentValid: true};
  Object.assign(state, {localSourceId: '', localSourceVersion: '', localSourceToken: '', sourceBusy: false, refreshing: false});
  const detail = document.createElement('p');
  detail.id = 'neuro-update-detail'; detail.hidden = true;
  message.after(detail);
  const consentPanel = document.createElement('section');
  consentPanel.id = 'neuro-install-consent'; consentPanel.hidden = true;
  const consentDocument = document.createElement('div');
  consentDocument.id = 'neuro-install-consent-document';
  consentDocument.setAttribute('translate', 'no'); consentDocument.className = 'notranslate';
  const consentLabel = document.createElement('label');
  Object.assign(consentLabel.style, {display: 'flex', gap: '.5rem', alignItems: 'flex-start'});
  const consentCheck = document.createElement('input');
  consentCheck.type = 'checkbox'; consentCheck.id = 'neuro-install-consent-check';
  Object.assign(consentCheck.style, {width: 'auto', flex: 'none'});
  const consentWords = document.createElement('span');
  consentLabel.append(consentCheck, consentWords);
  consentPanel.append(consentDocument, consentLabel);
  actions.before(consentPanel);
  consentCheck.addEventListener('change', () => {
    state.consentChecked = consentCheck.checked;
    refreshButtons();
  });
  const installWords = {
    'Atualizar NEURO RT': 'Instalar NEURO RT',
    'Uma nova versão do NEURO RT está disponível.': 'O plugin NEURO RT ainda não está instalado.',
    'Baixando a atualização do NEURO RT…': 'Baixando o NEURO RT…',
    'Preparando a atualização do NEURO RT…': 'Preparando a instalação do NEURO RT…',
    'Não foi possível concluir a atualização. A instalação anterior foi preservada.': 'A instalação não pôde ser concluída. A suíte continua disponível.',
    'Não foi possível verificar a atualização. A versão instalada continua disponível.': 'Não foi possível consultar a instalação. A suíte continua disponível.',
    'Atualizar quando terminar': 'Instalar quando terminar',
    'Interromper e atualizar agora': 'Interromper e instalar agora',
    'Interromper e atualizar': 'Interromper e instalar'
  };
  const T = original => {
    const installMode = installing && (!state.last || state.last.mounted !== true);
    const text = installMode && installWords[original] || original;
    const code = document.documentElement.lang || localStorage.getItem('radai_idioma') || 'pt-BR';
    const extra = window.NEURO_INSTALL_CATALOG && window.NEURO_INSTALL_CATALOG[code];
    return extra && extra[text] || (window.radaiFrase ? window.radaiFrase(text) : text);
  };

  const phases = {
    checking: 'Conferindo o pacote do NEURO RT…',
    verifying: 'Conferindo o pacote do NEURO RT…',
    copying: 'Copiando os arquivos da instalação…',
    extracting: 'Copiando os arquivos da instalação…',
    validating: 'Validando os componentes instalados…',
    publishing: 'Concluindo o preparo da versão…',
    complete: 'Pacote preparado. Aguardando reabertura da Local Suite.',
    restart: 'Reabrindo o Local Suite para ativar o NEURO RT…'
  };
  phases.resources = 'Preparando os recursos necessários…';
  phases.handoff = 'Preparando a manutenção externa…';
  const number = value => typeof value === 'number' && Number.isSafeInteger(value) && value >= 0;
  const version = value => typeof value === 'string' && /^\d+(?:\.\d+)*$/.test(value) ? value : '';
  function counters(update, doneKey, totalKey, memoKey) {
    const done = update[doneKey], total = update[totalKey];
    if (!number(done) || !number(total) || total <= 0 || done > total) return null;
    const key = typeof update.transaction_id === 'string' ? update.transaction_id : 'request:' + state.attempt;
    const old = state[memoKey];
    const value = old && old.key === key && old.total === total ? Math.max(old.done, done) : done;
    state[memoKey] = {key, total, done: value};
    return state[memoKey];
  }
  function bytes(value) {
    return value >= 1024 * 1024 * 1024 ? (value / (1024 * 1024 * 1024)).toFixed(1) + ' GiB'
      : (value / (1024 * 1024)).toFixed(1) + ' MiB';
  }
  function details(update, files, unpacked) {
    const parts = [];
    if (files) parts.push(T('Arquivos:') + ' ' + files.done + ' / ' + files.total);
    if (unpacked) parts.push(bytes(unpacked.done) + ' / ' + bytes(unpacked.total));
    const code = typeof update.error_code === 'string' && /^[A-Z][A-Z0-9_]{0,63}$/.test(update.error_code) ? update.error_code : '';
    if (code) parts.push(T('Código:') + ' ' + code);
    if (typeof update.error_stage === 'string' && /^[a-z][a-z_]{0,40}$/.test(update.error_stage))
      parts.push(T('Etapa:') + ' ' + (phases[update.error_stage] ? T(phases[update.error_stage]) : update.error_stage));
    detail.textContent = parts.join(' · '); detail.hidden = !parts.length;
  }
  function reason(update) {
    const text = update.reason;
    if (typeof text !== 'string' || text.length > 600 || /[\x00-\x1f]|[A-Za-z]:[\\/]|\\\\|(?:^|\s)\/[\w.-]+\//.test(text)) return;
    if (text.trim()) message.textContent += ' ' + T(text);
  }
  function offerLocal() {
    if (localDetails) localDetails.open = true;
    if (localMessage && !state.localSourceId) localMessage.textContent = T('Você pode usar uma fonte local verificada.');
  }
  function restartConfirmed(data) {
    if (!(state.restarting || state.awaitingRestart) || !state.initialToken || !data.token || data.token === state.initialToken ||
        data.mounted !== true || data.state !== 'ready' || !state.targetVersion ||
        version(data.active_version) !== state.targetVersion) return false;
    const pidRequired = state.initialPid !== null || Object.prototype.hasOwnProperty.call(data, 'host_pid');
    return !pidRequired || (number(state.initialPid) && state.initialPid > 0 &&
      number(data.host_pid) && data.host_pid > 0 && data.host_pid !== state.initialPid);
  }

  function consentInfo(data) {
    if (!data || !Object.prototype.hasOwnProperty.call(data, 'consent'))
      return {required: installing, valid: !installing, key: '', policy: null};
    const value = data.consent, policy = value && value.policy;
    const valid = !!(value && typeof value.installation_accepted === 'boolean' && policy &&
      policy.schema === 'neuro-rt/consent-policy/1' && policy.plugin_id === 'neuro-rt' &&
      typeof policy.version === 'string' && /^\d+(?:\.\d+)*$/.test(policy.version) &&
      typeof policy.digest === 'string' && /^[0-9a-f]{64}$/.test(policy.digest) &&
      typeof policy.title === 'string' && policy.title.trim() && Array.isArray(policy.clauses) &&
      policy.clauses.length && policy.clauses.every(c => c && typeof c.text === 'string' && c.text.trim()));
    return {required: !valid || value.installation_accepted !== true, valid,
      key: valid ? policy.version + ':' + policy.digest : '', policy: valid ? policy : null};
  }

  function refreshButtons() {
    const blocked = state.consentRequired && (!state.consentValid || !state.consentChecked);
    const unverified = !!(localFolder && localFolder.value.trim() && !state.localSourceId);
    actions.querySelectorAll('button').forEach(button => {
      button.disabled = state.posting || state.sourceBusy || ((blocked || unverified) && ['comecar', 'esperar', 'interromper'].includes(button.dataset.neuroAction));
    });
    const locked = state.posting || state.sourceBusy || (state.started && state.awaitingRestart);
    if (localFolder) localFolder.disabled = locked;
    if (localBrowse) localBrowse.disabled = locked;
    if (localInspect) localInspect.disabled = locked || !localFolder || !localFolder.value.trim();
    if (releaseRefresh) releaseRefresh.disabled = locked || state.refreshing;
  }

  function renderConsent(data) {
    const info = consentInfo(data);
    state.consentRequired = info.required; state.consentValid = info.valid;
    if (state.consentKey !== info.key) {
      state.consentKey = info.key; state.consentChecked = false;
      consentCheck.checked = false;
      consentDocument.replaceChildren();
      if (info.policy) {
        const title = document.createElement('h3');
        title.setAttribute('data-radai-t', '1');
        title.textContent = info.policy.title + ' — ' + info.policy.version;
        consentDocument.appendChild(title);
        info.policy.clauses.forEach(clause => {
          const line = document.createElement('p'); line.textContent = clause.text;
          line.setAttribute('data-radai-t', '1');
          consentDocument.appendChild(line);
        });
        const digest = document.createElement('p'); digest.style.overflowWrap = 'anywhere';
        digest.setAttribute('data-radai-t', '1');
        digest.textContent = 'SHA-256: ' + info.policy.digest; consentDocument.appendChild(digest);
      }
    }
    consentPanel.hidden = !info.required;
    consentLabel.hidden = !info.valid;
    consentCheck.disabled = state.posting;
    consentWords.textContent = T('Li e aceito o termo do plugin NEURO RT.');
    if (!info.valid) consentDocument.textContent = T('Atualize a Local Suite para exibir e aceitar o termo do plugin.');
    refreshButtons();
  }

  function view(kind, text, buttons, percent) {
    panel.hidden = kind === 'hidden' && !settings;
    message.textContent = T(text);
    detail.hidden = true; detail.textContent = '';
    progress.max = 100;
    progress.hidden = percent === undefined;
    if (percent === null) progress.removeAttribute('value');
    else if (percent !== undefined) progress.value = Math.max(0, Math.min(100, percent));
    const key = kind + ':' + (document.documentElement.lang || '') + ':' + buttons.map(b => b[0]).join(',');
    if (state.view !== key) {
      state.view = key;
      actions.replaceChildren();
      buttons.forEach(([action, label, style]) => {
        const button = document.createElement('button');
        button.type = 'button'; button.className = 'ui-bt ' + (style || '');
        button.dataset.neuroAction = action; button.textContent = T(label);
        button.addEventListener('click', () => {
          if (action === 'confirm-interrupt') { state.confirm = true; render(state.last); }
          else if (action === 'back') { state.confirm = false; render(state.last); }
          else if (action === 'read') read();
          else request(action);
        });
        actions.appendChild(button);
      });
    }
    renderConsent(state.last);
  }

  function render(data) {
    if (!data) return;
    state.last = data;
    const update = data.update || {}, release = data.release_check || {};
    if (state.localSourceId && state.localSourceToken !== data.token) {
      clearLocal();
      if (localMessage) localMessage.textContent = T('Confira novamente a fonte local.');
    }
    if (!state.initialSeen && data.token) {
      state.initialSeen = true; state.initial = version(data.active_version);
      state.initialToken = data.token;
      state.initialPid = number(data.host_pid) && data.host_pid > 0 ? data.host_pid : null;
    }
    if (state.localSourceId && !state.started) state.targetVersion = state.localSourceVersion;
    else if (version(update.version)) state.targetVersion = update.version;
    else if (!state.targetVersion && version(release.version)) state.targetVersion = release.version;
    if (!settings && installing && data.mounted === true && data.state === 'ready' && !state.started && !state.restarting && !state.awaitingRestart && (update.state === undefined || update.state === 'idle')) {
      location.replace('/neuro/'); return;
    }
    if (update.state === 'restarting') { state.restarting = true; state.awaitingRestart = true; }
    if (update.state === 'installed_pending_restart' || update.state === 'activating' || data.state === 'installed_pending_restart') state.awaitingRestart = true;
    if (restartConfirmed(data)) {
      if (!settings) { location.replace('/neuro/'); return; }
      state.started = false; state.restarting = false; state.awaitingRestart = false;
      if (localFolder) localFolder.value = '';
      if (localMessage) localMessage.textContent = '';
      clearLocal();
    }
    if (update.state === 'failed' || update.state === 'installed_pending_restart') state.restarting = false;
    if (data.state === 'checking' || data.state === 'loading') {
      const verification = data.verification && typeof data.verification === 'object' && !Array.isArray(data.verification) ? data.verification : {};
      const snapshot = Object.assign({}, verification, {transaction_id: 'verification:' + (data.token || data.host_pid || '')});
      const files = counters(snapshot, 'completed_files', 'total_files', 'verificationFileProgress');
      const unpacked = counters(snapshot, 'processed_bytes', 'total_unpacked_bytes', 'verificationByteProgress');
      view('checking', phases[verification.stage] || 'Verificando a instalação do NEURO RT.', [], files ? Math.min(99, 100 * files.done / files.total) : null);
      details(verification, files, unpacked); return;
    }
    if (update.state === 'busy') {
      if (state.confirm) {
        view('confirm', 'O trabalho em andamento será interrompido e o turno da noite será encerrado. Solicite novamente os itens cancelados do NEURO RT.',
          [['interromper', 'Interromper e atualizar', 'perigo'], ['back', 'Voltar']]);
      } else {
        view('busy', 'Atualizar agora interromperia isso. A atualização pode esperar terminar, ou interromper agora.',
          [['esperar', 'Atualizar quando terminar', 'pri'], ['confirm-interrupt', 'Interromper e atualizar agora', 'perigo']]);
      }
      return;
    }
    state.confirm = false;
    if (update.state === 'waiting') { view('waiting', 'Esperando terminar para atualizar…', [], null); return; }
    if (update.state === 'downloading') {
      const downloaded = counters(update, 'downloaded_bytes', 'total_bytes', 'downloadProgress');
      const pct = downloaded ? Math.min(99, 100 * downloaded.done / downloaded.total) : null;
      view('downloading', 'Baixando a atualização do NEURO RT…', [], pct);
      details(update, null, downloaded); return;
    }
    if (update.state === 'preparing' || update.state === 'activating') {
      const files = counters(update, 'completed_files', 'total_files', 'fileProgress');
      const unpacked = counters(update, 'processed_bytes', 'total_unpacked_bytes', 'byteProgress');
      view('preparing', phases[update.stage] || 'Preparando a atualização do NEURO RT…', [], files ? Math.min(99, 100 * files.done / files.total) : null);
      details(update, files, unpacked); return;
    }
    if (update.state === 'installed_pending_restart') {
      view('pending', 'Pacote preparado. Aguardando reabertura da Local Suite.', [['esperar', 'Reiniciar agora', 'pri']]);
      if (update.error_code) message.textContent += ' ' + T('Feche e reabra a Local Suite para ativar o NEURO RT.');
      details(update); return;
    }
    if (update.state === 'restarting' || state.restarting) {
      view('restarting', 'Reabrindo o Local Suite para ativar o NEURO RT…', [], null); return;
    }
    if (update.state === 'failed') {
      view('failed', 'Não foi possível concluir a atualização. A instalação anterior foi preservada.',
        installing || release.state === 'available' || state.localSourceId ? [['comecar', 'Atualizar NEURO RT', 'pri']] : []);
      reason(update); details(update);
      offerLocal();
      return;
    }
    if (installing && data.state === 'installed_pending_restart') {
      view('pending', 'Pacote preparado. Aguardando reabertura da Local Suite.', [['esperar', 'Reiniciar agora', 'pri']]); return;
    }
    if (state.localSourceId) {
      view('local', 'Fonte local verificada.', [['comecar', 'Atualizar NEURO RT', 'pri']]);
      message.textContent += ' ' + state.localSourceVersion; return;
    }
    if (installing && data.mounted !== true) {
      view('install', 'Uma nova versão do NEURO RT está disponível.', [['comecar', 'Atualizar NEURO RT', 'pri']]);
      if (release.state === 'unavailable') {
        if (release.reason) message.textContent += ' ' + T(release.reason);
        offerLocal();
      }
      return;
    }
    if (release.state === 'available') {
      view('available', 'Uma nova versão do NEURO RT está disponível.', [['comecar', 'Atualizar NEURO RT', 'pri']]);
      message.textContent += ' ' + release.version; return;
    }
    if (release.state === 'incompatible') {
      view('incompatible', 'Atualize o Local Suite para usar a nova versão do NEURO RT.', []); return;
    }
    if (release.state === 'unavailable') {
      view('unavailable', 'Não foi possível verificar a atualização. A versão instalada continua disponível.', []); offerLocal(); return;
    }
    view(settings ? 'current' : 'hidden', settings ? 'O NEURO RT está atualizado.' : '', []);
  }

  async function status() {
    const response = await fetch('/api/plugins/neuro-rt', {cache: 'no-store'});
    if (!response.ok) throw Error('status');
    return response.json();
  }
  function follow() { clearTimeout(state.timer); state.timer = setTimeout(read, 1000); }
  async function read() {
    try { render(await status()); }
    catch (_) { if (!state.restarting && !state.awaitingRestart) view('unavailable', 'Não foi possível verificar a atualização. A versão instalada continua disponível.', []); }
    finally { follow(); }
  }
  async function request(action) {
    if (state.posting) return;
    state.posting = true; clearTimeout(state.timer);
    actions.querySelectorAll('button').forEach(button => { button.disabled = true; });
    try {
      const current = await status();
      if (localFolder && localFolder.value.trim() && (!state.localSourceId || state.localSourceToken !== current.token)) {
        clearLocal(); state.posting = false;
        if (localMessage) localMessage.textContent = T('Confira novamente a fonte local.');
        render(current); return;
      }
      const info = consentInfo(current);
      if (info.required && (!info.valid || !state.consentChecked || state.consentKey !== info.key)) {
        state.posting = false; render(current); return;
      }
      const firstInstall = installing && current.mounted !== true && action === 'comecar';
      state.started = true; state.initialToken = current.token;
      state.initialPid = number(current.host_pid) && current.host_pid > 0 ? current.host_pid : null;
      state.initial = version(current.active_version);
      if (state.localSourceId) state.targetVersion = state.localSourceVersion;
      else if (version(current.release_check && current.release_check.version)) state.targetVersion = current.release_check.version;
      state.attempt += 1; state.fileProgress = null; state.byteProgress = null; state.downloadProgress = null;
      const payload = firstInstall ? {confirm: true} : {action};
      if (state.localSourceId) payload.source_id = state.localSourceId;
      if (info.required) payload.consent = {accepted: true, version: info.policy.version, digest: info.policy.digest};
      const response = await fetch(firstInstall ? '/api/plugins/neuro-rt/install' : '/api/plugins/neuro-rt/update', {method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-Neuro-Plugin-Token': current.token},
        body: JSON.stringify(payload)});
      if (!response.ok) throw Error('update');
      state.posting = false;
      render(Object.assign({}, current, {update: await response.json()}));
    } catch (_) {
      state.posting = false;
      view('failed', 'Não foi possível concluir a atualização. A instalação anterior foi preservada.', []);
    } finally { follow(); }
  }
  function clearLocal() {
    state.localSourceId = ''; state.localSourceVersion = ''; state.localSourceToken = '';
    refreshButtons();
  }
  async function auxiliary(path, payload) {
    const current = await status();
    const response = await fetch('/api/plugins/neuro-rt/' + path, {method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-Neuro-Plugin-Token': current.token},
      body: JSON.stringify(payload)});
    const body = await response.json();
    if (!response.ok) {
      const error = Error('maintenance');
      error.status = response.status;
      error.sourceHint = body && (body.source_hint || body.detail && body.detail.source_hint);
      throw error;
    }
    return {current, body};
  }
  if (localFolder) localFolder.addEventListener('input', () => {
    clearLocal(); if (localMessage) localMessage.textContent = '';
  });
  if (localBrowse && localBrowse.dataset.neuroHostBrowse !== '1') localBrowse.addEventListener('click', async () => {
    if (state.sourceBusy || state.posting) return;
    state.sourceBusy = true; refreshButtons();
    try {
      const result = await auxiliary('local/browse', {});
      if (typeof result.body.folder === 'string' && result.body.folder.length <= 32768 && result.body.folder) {
        localFolder.value = result.body.folder; clearLocal();
        if (localMessage) localMessage.textContent = T('Confira a fonte local antes de continuar.');
      }
    } catch (_) { if (localMessage) localMessage.textContent = T('Não foi possível conferir a fonte local.'); }
    finally { state.sourceBusy = false; refreshButtons(); }
  });
  if (localInspect) localInspect.addEventListener('click', async () => {
    if (!localFolder || !localFolder.value.trim() || state.sourceBusy || state.posting) return;
    clearLocal(); state.sourceBusy = true; refreshButtons();
    if (localMessage) localMessage.textContent = T('Conferindo a fonte local…');
    try {
      const result = await auxiliary('local/inspect', {folder: localFolder.value.trim()});
      const description = result.body.description || result.body;
      if (typeof result.body.source_id !== 'string' || !/^[A-Za-z0-9_-]{1,128}$/.test(result.body.source_id) || !version(description.version)) throw Error('source');
      state.localSourceId = result.body.source_id; state.localSourceVersion = description.version;
      state.localSourceToken = result.current.token;
      if (localMessage) localMessage.textContent = T('Fonte local verificada.') + ' ' + description.version;
      render(result.current);
    } catch (error) {
      if (localDetails) localDetails.open = true;
      if (localMessage) localMessage.textContent = T(error.sourceHint === 'extract_setup' || (error.status === 400 && !error.sourceHint)
        ? 'Extraia o SETUP/bundle e selecione a pasta que contém START_HERE.cmd e release-manifest.json.'
        : 'Não foi possível conferir a fonte local.');
    }
    finally { state.sourceBusy = false; refreshButtons(); }
  });
  if (releaseRefresh) releaseRefresh.addEventListener('click', async () => {
    if (state.refreshing || state.posting) return;
    state.refreshing = true; refreshButtons();
    try {
      const result = await auxiliary('refresh', {});
      render(Object.assign({}, result.current, {release_check: result.body.release_check || result.body}));
    } catch (_) { view('unavailable', 'Não foi possível verificar a atualização. A versão instalada continua disponível.', []); }
    finally { state.refreshing = false; refreshButtons(); }
  });
  window.addEventListener('pagehide', () => clearTimeout(state.timer));
  window.NeuroPluginUpdate = {read, request, state};
  read();
})();
