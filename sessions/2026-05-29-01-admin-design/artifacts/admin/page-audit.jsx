// ============================================================
// Аудит-лог — таблица + раскрытие payload (HTMX-аналог)
// ============================================================

function AuditRow({ a }) {
  const [open, setOpen] = useState(false);
  return (
    <React.Fragment>
      <tr style={{ cursor: "pointer" }} onClick={() => setOpen(!open)}>
        <td className="pv-mono pv-muted">{a.created_at.slice(0, 16)}</td>
        <td>
          <div className="pv-row" style={{ gap: 8 }}>
            <Avatar first={a.admin} last="" seed={a.admin} size="sm" />
            <span>{a.admin}</span>
          </div>
        </td>
        <td><code>{a.action}</code></td>
        <td className="pv-muted" style={{ fontSize: 12 }}>{window.ACTION_LABELS[a.action] || ""}</td>
        <td className="pv-c-actions">
          <Icon name={open ? "expand_less" : "expand_more"} style={{ color: "var(--pv-fg-subtle)" }} />
        </td>
      </tr>
      {open ? (
        <tr>
          <td colSpan="5" style={{ background: "var(--pv-panel-2)", padding: "12px 14px" }}>
            <pre style={{ margin: 0, fontFamily: "var(--pv-font-mono, monospace)", fontSize: 12, color: "var(--pv-fg)", whiteSpace: "pre-wrap" }}>
{JSON.stringify(a.payload, null, 2)}
            </pre>
          </td>
        </tr>
      ) : null}
    </React.Fragment>
  );
}

function PageAudit() {
  const [admin, setAdmin] = useState("all");
  const [action, setAction] = useState("all");
  const admins = Array.from(new Set(window.AUDIT.map((a) => a.admin)));
  const actions = Array.from(new Set(window.AUDIT.map((a) => a.action)));

  const rows = window.AUDIT.filter((a) =>
    (admin === "all" || a.admin === admin) && (action === "all" || a.action === action));

  return (
    <div className="pv-page">
      <PageHeader title="Аудит-лог" sub="Журнал значимых действий в админке"
        actions={<Btn icon="download">Экспорт CSV</Btn>} />
      <div className="pv-card pv-card-flush">
        <div className="pv-toolbar">
          <select className="pv-select" style={{ width: "auto", height: 32 }} value={admin} onChange={(e) => setAdmin(e.target.value)}>
            <option value="all">Все администраторы</option>
            {admins.map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
          <select className="pv-select" style={{ width: "auto", height: 32 }} value={action} onChange={(e) => setAction(e.target.value)}>
            <option value="all">Все действия</option>
            {actions.map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
          <div className="pv-toolbar-grow"></div>
          <span className="pv-chip"><Icon name="calendar_today" /> Период</span>
        </div>
        <table className="pv-table">
          <thead>
            <tr>
              <th style={{ width: 150 }}>Время</th>
              <th style={{ width: 160 }}>Администратор</th>
              <th>Действие</th><th>Описание</th>
              <th className="pv-c-actions"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((a) => <AuditRow key={a.id} a={a} />)}
          </tbody>
        </table>
      </div>
    </div>
  );
}

Object.assign(window, { PageAudit });
