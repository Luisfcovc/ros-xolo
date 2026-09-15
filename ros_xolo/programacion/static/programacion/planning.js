(() => {
  const app = document.querySelector('#planning-app');
  if (!app) return;
  const list = document.querySelector('#assignments'), state = document.querySelector('#save-state');
  const errors = document.querySelector('#field-errors'), alerts = document.querySelector('#alerts');
  const branch = document.querySelector('#branch'), period = document.querySelector('#period');
  const week = document.querySelector('#week'), periodState = document.querySelector('#period-state');
  const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
  let etag = null, catalogs = {employees: [], roles: []};
  const uuid = () => globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`;
  const toInput = value => value ? value.slice(0, 16) : '';
  const toISO = value => value ? new Date(value).toISOString() : '';
  const optionMarkup = (items, selected, placeholder) => `<option value="">${placeholder}</option>${items.map(item => `<option value="${item.id}"${item.id === selected ? ' selected' : ''}>${item.label}</option>`).join('')}`;

  function row(data = {}) {
    const node = document.querySelector('#assignment-template').content.cloneNode(true), field = node.querySelector('.assignment');
    field.dataset.id = data.assignment_id || uuid();
    field.querySelector('[data-field="employee_id"]').innerHTML = optionMarkup(catalogs.employees, data.employee_id || '', 'Selecciona un empleado');
    field.querySelector('[data-field="role_id"]').innerHTML = optionMarkup(catalogs.roles, data.role_id || '', 'Sin rol');
    field.querySelector('[data-field="station_id"]').value = data.station_id || '';
    for (const key of ['starts_at', 'ends_at']) field.querySelector(`[data-field="${key}"]`).value = toInput(data[key]);
    field.dataset.breaks = JSON.stringify(data.breaks || []);
    field.querySelector('[data-remove]').onclick = () => field.remove();
    if (window.ScheduleAssignmentForm) queueMicrotask(() => window.ScheduleAssignmentForm.bind(field));
    return node;
  }
  function value() { return [...list.querySelectorAll('.assignment')].map(field => ({
    assignment_id: field.dataset.id, employee_id: field.querySelector('[data-field="employee_id"]').value,
    starts_at: toISO(field.querySelector('[data-field="starts_at"]').value), ends_at: toISO(field.querySelector('[data-field="ends_at"]').value),
    role_id: field.querySelector('[data-field="role_id"]').value || null, station_id: field.querySelector('[data-field="station_id"]').value || null,
    shift_id: null, breaks: window.ScheduleAssignmentForm ? window.ScheduleAssignmentForm.value(field) : [],
  })); }
  function draw(rows) { list.replaceChildren(); rows.forEach(item => list.append(row(item))); }
  function clearFieldErrors() { errors.textContent = ''; document.querySelectorAll('[data-field-errors]').forEach(node => { node.textContent = ''; }); }
  function renderError(error) { clearFieldErrors(); errors.textContent = error.message || 'Los cambios locales no se guardaron.'; }
  function drawAlerts(data) {
    alerts.replaceChildren();
    for (const alert of data.alerts || []) { const item = document.createElement('li'); item.textContent = `${alert.priority === 'high' ? 'Alta' : 'Media'}: ${alert.required_action}`; alerts.append(item); }
    document.querySelector('#base-version').textContent = data.base_publication ? `v${data.base_publication.version}` : 'Sin publicación';
    document.querySelector('#pending-summary').textContent = data.has_pending_changes ? 'Hay cambios guardados o de lista pendientes de publicación.' : 'No hay cambios para publicar.';
  }
  async function loadCatalogs() {
    const response = await fetch(`/api/v1/planning/branches/${branch.value}/catalogs`, {cache: 'no-store'});
    if (!response.ok) throw Error('No se pudieron cargar los catálogos de la sucursal.');
    catalogs = await response.json();
  }
  async function load() {
    if (!app.dataset.periodId) return;
    clearFieldErrors(); const response = await fetch(`/api/v1/planning/periods/${app.dataset.periodId}/draft`, {cache: 'no-store'});
    if (!response.ok) { state.textContent = 'No se pudo cargar el borrador.'; return; }
    const data = await response.json(); etag = response.headers.get('ETag'); draw(data.assignments); drawAlerts(data); state.textContent = 'Contenido guardado cargado.';
    document.dispatchEvent(new CustomEvent('schedule:draft-loaded', {detail: {pendingDraftExcluded: data.has_pending_changes && Boolean(data.base_publication)}}));
  }
  async function save() {
    if (!app.dataset.periodId) return;
    clearFieldErrors(); const response = await fetch(`/api/v1/planning/periods/${app.dataset.periodId}/draft`, {method: 'PUT', headers: {'Content-Type': 'application/json', 'If-Match': etag || '', 'X-CSRFToken': csrfToken}, body: JSON.stringify({assignments: value()})});
    const data = await response.json();
    if (response.status === 412) { state.textContent = 'La base cambió. Refresca y revisa antes de guardar.'; return; }
    if (!response.ok) { renderError(data.error || {}); state.textContent = 'Los cambios locales no se guardaron.'; return; }
    etag = response.headers.get('ETag'); state.textContent = data.saved ? 'Cambios guardados.' : 'No hubo cambios de contenido.'; await load();
  }
  async function publish() {
    if (!app.dataset.periodId) return;
    const response = await fetch(`/api/v1/planning/periods/${app.dataset.periodId}/publish`, {method: 'POST', headers: {'If-Match': etag || '', 'X-CSRFToken': csrfToken}, body: '{}'}), data = await response.json();
    if (!response.ok) { renderError(data.error || {}); state.textContent = 'No se pudo publicar; la versión vigente se conserva.'; return; }
    etag = response.headers.get('ETag') || etag; state.textContent = data.outcome === 'no_changes' ? 'No hay cambios para publicar.' : `Publicación v${data.version} completada.`; await load();
  }
  function weekBounds(value) {
    const [year, number] = value.split('-W').map(Number), jan4 = new Date(Date.UTC(year, 0, 4)), monday = new Date(jan4);
    monday.setUTCDate(jan4.getUTCDate() - ((jan4.getUTCDay() + 6) % 7) + (number - 1) * 7);
    const end = new Date(monday); end.setUTCDate(monday.getUTCDate() + 6);
    return [monday.toISOString().slice(0, 10), end.toISOString().slice(0, 10)];
  }
  async function loadPeriods() {
    period.disabled = true; period.innerHTML = '<option value="">Cargando periodos…</option>';
    const response = await fetch(`/api/v1/planning/periods?branch_id=${encodeURIComponent(branch.value)}`, {cache: 'no-store'});
    if (!response.ok) throw Error('No se pudieron cargar los periodos.');
    const data = await response.json();
    period.innerHTML = `<option value="">Selecciona un periodo</option>${data.periods.map(item => `<option value="${item.id}"${item.id === app.dataset.periodId ? ' selected' : ''}>${item.date_from} a ${item.date_to} · ${item.publication_state === 'published' ? `v${item.current_version}` : 'sin publicar'}</option>`).join('')}`;
    period.disabled = false;
  }
  async function selectBranch() { try { await loadCatalogs(); await loadPeriods(); periodState.textContent = ''; } catch (error) { periodState.textContent = error.message; } }
  async function createPeriod() {
    if (!branch.value || !week.value) { periodState.textContent = 'Elige una sucursal y una semana.'; return; }
    const [date_from, date_to] = weekBounds(week.value); periodState.textContent = 'Creando borrador…';
    const response = await fetch('/api/v1/planning/periods', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken}, body: JSON.stringify({branch_id: branch.value, date_from, date_to})});
    if (!response.ok) { const data = await response.json(); periodState.textContent = data.error?.message || 'No se pudo crear el periodo.'; return; }
    const draft = await response.json(); window.location.assign(`/planning/periods/${draft.period.id}/`);
  }
  async function bootstrap() {
    const response = await fetch('/api/v1/planning/branches', {cache: 'no-store'});
    if (!response.ok) { periodState.textContent = 'Tu sesión no permite acceder a Planeación.'; return; }
    const data = await response.json(); branch.innerHTML = `<option value="">Selecciona una sucursal</option>${data.branches.map(item => `<option value="${item.id}">${item.name}</option>`).join('')}`;
    if (!data.branches.length) { periodState.textContent = 'Tu cuenta no tiene sucursales de planeación asignadas.'; return; }
    if (app.dataset.periodId) { const draft = await fetch(`/api/v1/planning/periods/${app.dataset.periodId}/draft`, {cache: 'no-store'}).then(r => r.ok ? r.json() : null); if (draft) branch.value = draft.period.branch_id; }
    if (!branch.value) branch.value = data.branches[0].id;
    await selectBranch(); await load();
  }
  branch.addEventListener('change', selectBranch);
  period.addEventListener('change', () => { if (period.value) window.location.assign(`/planning/periods/${period.value}/`); });
  document.querySelector('#create-period').onclick = createPeriod; document.querySelector('#add-assignment').onclick = () => list.append(row());
  document.querySelector('#save-draft').onclick = save; document.querySelector('#refresh-draft').onclick = load; document.querySelector('#publish').onclick = publish;
  bootstrap();
})();
