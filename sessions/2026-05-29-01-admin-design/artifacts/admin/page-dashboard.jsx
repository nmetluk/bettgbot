// ============================================================
// Dashboard — счётчики + последние записи аудита
// ============================================================

function Kpi({ label, icon, value, sub, foot }) {
  return (
    <div className="pv-kpi">
      <div className="pv-kpi-label"><Icon name={icon} style={{ fontSize: 14 }} />{label}</div>
      <div className="pv-kpi-value">{value}{sub ? <small>{sub}</small> : null}</div>
      {foot ? <div className="pv-kpi-foot">{foot}</div> : null}
    </div>
  );
}

function PageDashboard({ go }) {
  const s = window.STATS;
  const audit = window.AUDIT.slice(0, 8);
  const active = window.EVENTS.filter((e) => e.status === "open" || e.status === "closed");

  return (
    <div className="pv-page">
      <PageHeader
        title="Главная"
        sub="Сводка по событиям, прогнозам и пользователям"
        actions={<React.Fragment>
          <Btn icon="download">Экспорт</Btn>
          <Btn variant="primary" icon="add" onClick={() => go("events")}>Новое событие</Btn>
        </React.Fragment>}
      />

      <div className="pv-grid c4" style={{ marginBottom: 16 }}>
        <Kpi label="Пользователей" icon="groups" value={s.users_total.toLocaleString("ru")}
          foot={<span className="pv-kpi-delta up"><Icon name="trending_up" />{s.users_active_30d} активных / 30 дн.</span>} />
        <Kpi label="Прогнозов всего" icon="checklist" value={s.predictions_total.toLocaleString("ru")}
          foot={<span className="pv-kpi-delta up"><Icon name="trending_up" />+{s.predictions_24h} за сутки</span>} />
        <Kpi label="События" icon="event" value={s.events_total}
          foot={<span className="pv-muted" style={{ fontSize: 12 }}>{s.events_published} опубл. · {s.events_archived} архив</span>} />
        <Kpi label="Категорий" icon="folder" value={s.categories}
          foot={<span className="pv-muted" style={{ fontSize: 12 }}>2 скрыты от бота</span>} />
      </div>

      <div className="pv-grid c-2-1">
        {/* Активные события */}
        <div className="pv-card pv-card-flush">
          <div className="pv-card-head">
            <h3>Активные события</h3>
            <span className="pv-card-meta">приём прогнозов открыт или только что закрыт</span>
            <Btn size="sm" variant="ghost" icon="open_in_new" onClick={() => go("events")}>Все</Btn>
          </div>
          <table className="pv-table">
            <thead>
              <tr>
                <th>Событие</th><th>Категория</th><th>Старт</th>
                <th className="pv-c-num">Прогнозов</th><th>Статус</th>
              </tr>
            </thead>
            <tbody>
              {active.map((e) => (
                <tr key={e.id} style={{ cursor: "pointer" }} onClick={() => go("events", { id: e.id })}>
                  <td className="pv-row-strong">{e.title}</td>
                  <td>{catName(e.category_id)}</td>
                  <td className="pv-mono">{e.starts_at.slice(5)}</td>
                  <td className="pv-c-num">{e.predictions_count}</td>
                  <td><EventStatusBadge status={e.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Аудит */}
        <div className="pv-card pv-card-flush">
          <div className="pv-card-head">
            <h3>Последние действия</h3>
            <Btn size="sm" variant="ghost" icon="open_in_new" onClick={() => go("audit")}>Журнал</Btn>
          </div>
          <div style={{ padding: "6px 0" }}>
            {audit.map((a) => (
              <div key={a.id} className="pv-list-row" style={{ padding: "9px 20px" }}>
                <Avatar first={a.admin} last="" seed={a.admin} size="sm" />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ color: "var(--pv-fg)", fontWeight: 700, fontSize: 13 }}>
                    {window.ACTION_LABELS[a.action] || a.action}
                  </div>
                  <div className="pv-muted" style={{ fontSize: 12 }}>{a.admin} · {a.created_at.slice(5, 16)}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { PageDashboard });
