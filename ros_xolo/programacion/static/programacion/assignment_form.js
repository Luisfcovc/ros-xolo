(() => {
  const MESSAGE = 'La pausa debe ser positiva y estar contenida en la jornada.';
  const inputValue = value => value ? value.slice(0, 16) : '';
  const isoValue = value => value ? new Date(value).toISOString() : '';
  const uuid = () => {
    if (globalThis.crypto && typeof globalThis.crypto.randomUUID === 'function') {
      return globalThis.crypto.randomUUID();
    }
    const bytes = new Uint8Array(16);
    if (globalThis.crypto && typeof globalThis.crypto.getRandomValues === 'function') {
      globalThis.crypto.getRandomValues(bytes);
    } else {
      for (let index = 0; index < bytes.length; index += 1) {
        bytes[index] = Math.floor(Math.random() * 256);
      }
    }
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const value = [...bytes].map(byte => byte.toString(16).padStart(2, '0')).join('');
    return `${value.slice(0, 8)}-${value.slice(8, 12)}-${value.slice(12, 16)}-${value.slice(16, 20)}-${value.slice(20)}`;
  };
  function validate(assignment) {
    const start = new Date(assignment.querySelector('[data-field="starts_at"]').value);
    const end = new Date(assignment.querySelector('[data-field="ends_at"]').value);
    const rows = [...assignment.querySelectorAll('.break')].map(row => ({row, start: new Date(row.querySelector('[data-break-field="starts_at"]').value), end: new Date(row.querySelector('[data-break-field="ends_at"]').value)})).sort((a, b) => a.start - b.start);
    let previousEnd = null;
    rows.forEach(item => { const invalid = !item.start.valueOf() || !item.end.valueOf() || item.end <= item.start || item.start < start || item.end > end || (previousEnd && item.start < previousEnd); item.row.querySelector('[data-break-errors="interval"]').textContent = invalid ? MESSAGE : ''; if (previousEnd === null || item.end > previousEnd) previousEnd = item.end; });
  }
  function row(data = {}) {
    const node = document.querySelector('#break-template').content.cloneNode(true), field = node.querySelector('.break');
    field.dataset.id = data.break_id || uuid();
    field.querySelector('[data-break-field="starts_at"]').value = inputValue(data.starts_at);
    field.querySelector('[data-break-field="ends_at"]').value = inputValue(data.ends_at);
    field.querySelector('[data-remove-break]').onclick = () => { const assignment = field.closest('.assignment'); field.remove(); validate(assignment); };
    field.addEventListener('input', () => validate(field.closest('.assignment')));
    return node;
  }
  window.ScheduleAssignmentForm = {
    addBreak(assignment, data = {}) { assignment.querySelector('[data-break-list]').append(row(data)); validate(assignment); },
    bind(assignment) { assignment.querySelector('[data-add-break]').onclick = () => this.addBreak(assignment); assignment.querySelectorAll('[data-field="starts_at"], [data-field="ends_at"]').forEach(input => input.addEventListener('input', () => validate(assignment))); (assignment.dataset.breaks ? JSON.parse(assignment.dataset.breaks) : []).forEach(item => this.addBreak(assignment, item)); },
    value(assignment) { return [...assignment.querySelectorAll('.break')].map(field => ({break_id: field.dataset.id, starts_at: isoValue(field.querySelector('[data-break-field="starts_at"]').value), ends_at: isoValue(field.querySelector('[data-break-field="ends_at"]').value)})); },
    validate,
  };
})();
