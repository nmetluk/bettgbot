// ============================================================
// События — список с фильтрами + карточка (3 вкладки)
// ============================================================

function EventsList({ go }) {
  const [cat, setCat] = useState("all");
  const [status, setStatus] = useState("all");
  const [period, setPeriod] = useState("all");

  const rows = window.EVENTS.filter((e) => {
    if (cat !== "all" && e.category_id !== +cat) return false;
    if (status !== "all" && e.status !== status) return false;
    return true;
  });

  return (
    <div className="pv-page">
      <PageHeader title="События" sub="Создание, публикация и фиксация итогов"
        actions={<Btn variant="primary" icon="add" onClick={() => go("events", { id: "new" })}>Новое событие</Btn>} />

      <div className="pv-card pv-card-flush">
        <div className="pv-toolbar">
          <div className="pv-toolbar-search">
            <Icon name="search" className="ms" />
            <input placeholder="Поиск по названию…" />
          </div>
          <div className="pv-toolbar-grow"></div>
          <select className="pv-select" style={{ width: "auto", height: 32 }} value={cat} onChange={(e) => setCat(e.target.value)}>
            <option value="all">Все категории</option>
            {window.CATEGORIES.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <select className="pv-select" style={{ width: "auto", height: 32 }} value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="all">Все статусы</option>
            <option value="draft">Черновики</option>
            <option value="open">Приём открыт</option>
            <option value="closed">Приём закрыт</option>
            <option value="archived">Архив</option>
          </select>
          <select className="pv-select" style={{ width: "auto", height: 32 }} value={period} onChange={(e) => setPeriod(e.target.value)}>
            <option value="all">Любой период</option>
            <option value="7d">Ближайшие 7 дней</option>
            <option value="past">Прошедшие</option>
          </select>
        </div>

        {rows.length === 0 ? (
          <Empty icon="event_busy" title="Ничего не найдено" sub="Попробуйте изменить фильтры или создать событие" />
        ) : (
          <table className="pv-table">
            <thead>
              <tr>
                <th style={{ width: 56 }}>ID</th>
                <th>Событие</th><th>Категория</th>
                <th>Старт</th><th>Дедлайн приёма</th>
                <th>Статус</th>
                <th className="pv-c-num">Прогнозов</th>
                <th className="pv-c-actions"></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((e) => (
                <tr key={e.id} style={{ cursor: "pointer" }} onClick={() => go("events", { id: e.id })}>
                  <td className="pv-mono pv-muted">{e.id}</td>
                  <td className="pv-row-strong">{e.title}</td>
                  <td>{catName(e.category_id)}</td>
                  <td className="pv-mono">{e.starts_at.slice(5)}</td>
                  <td className="pv-mono pv-muted">{e.predictions_close_at.slice(5)}</td>
                  <td><EventStatusBadge status={e.status} /></td>
                  <td className="pv-c-num">{e.predictions_count}</td>
                  <td className="pv-c-actions"><Icon name="chevron_right" style={{ color: "var(--pv-fg-subtle)" }} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

Object.assign(window, { EventsList });
