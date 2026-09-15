(() => {
  const root = document.querySelector('#personal-schedule'); if (!root) return;
  const status = document.querySelector('#schedule-status'), content = document.querySelector('#schedule-content');
  const from = document.querySelector('#schedule-from'), to = document.querySelector('#schedule-to');
  let sequence = 0, timer;
  const today = new Date().toISOString().slice(0, 10); from.value = today; to.value = today;
  function hide(message) { content.hidden = true; content.replaceChildren(); status.textContent = message; }
  async function verify() {
    if (!from.value || !to.value || from.value > to.value) { hide('Elige un rango de fechas válido.'); return; }
    const token = ++sequence; hide('Verificando programación…'); const controller = new AbortController(), timeout = setTimeout(() => controller.abort(), 5000);
    try {
      const response = await fetch(`${root.dataset.api}?from=${encodeURIComponent(from.value)}&to=${encodeURIComponent(to.value)}`, {cache: 'no-store', signal: controller.signal});
      if (token !== sequence) return; if (response.status === 401) { hide('Tu sesión venció. Inicia sesión nuevamente.'); return; }
      if (!response.ok) throw Error(); const data = await response.json(); if (token !== sequence) return;
      const next = data.assignments[0]; content.textContent = next ? `Próxima jornada: ${next.starts_at} — ${next.labels.role || next.labels.station || 'Sin detalle'} (v${next.version})` : (data.periods.some(item => item.publication_state === 'published') ? 'Sin jornadas asignadas en esta versión.' : 'Sin programación publicada para este periodo.');
      content.hidden = false; status.textContent = `Verificado: ${data.verified_at}`;
    } catch (_) { if (token === sequence) hide('No se puede verificar la programación vigente. Reintenta cuando tengas conexión.'); }
    finally { clearTimeout(timeout); }
  }
  document.querySelector('#refresh-schedule').addEventListener('click', verify);
  window.addEventListener('offline', () => hide('No se puede verificar la programación vigente.'));
  window.addEventListener('online', verify); window.addEventListener('pageshow', verify);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) verify(); }); verify();
  timer = setInterval(() => { if (!document.hidden) verify(); }, 15000);
})();
