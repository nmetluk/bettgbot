// ============================================================
// Карточка события — вкладки: Данные · Исходы · Результат
// ============================================================

function TabData({ ev }) {
  return (
    <div className="pv-grid c-2-1">
      <div className="pv-card">
        <div className="pv-section-title">Данные события</div>
        <div className="pv-stack">
          <Field label="Название" required>
            <input className="pv-input" defaultValue={ev.title} />
          </Field>
          <Field label="Описание">
            <textarea className="pv-textarea" defaultValue={ev.description}></textarea>
          </Field>
          <div className="pv-grid c2">
            <Field label="Категория" required>
              <select className="pv-select" defaultValue={ev.category_id}>
                {window.CATEGORIES.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </Field>
            <Field label="Старт события" required>
              <input className="pv-input pv-mono" defaultValue={ev.starts_at} />
            </Field>
          </div>
          <Field label="Дедлайн приёма прогнозов" help="Обычно ≤ начала события. По умолчанию = старту.">
            <input className="pv-input pv-mono" defaultValue={ev.predictions_close_at} />
          </Field>
          <Field label="metadata (JSON)" help="Произвольные поля для расширения без миграций.">
            <textarea className="pv-textarea pv-mono" style={{ minHeight: 110, fontSize: 12 }}
              defaultValue={JSON.stringify(ev.metadata, null, 2)}></textarea>
          </Field>
        </div>
      </div>

      <div className="pv-stack">
        <div className="pv-card">
          <div className="pv-section-title">Состояние</div>
          <div className="pv-stack" style={{ gap: 10 }}>
            <div className="pv-row"><span className="pv-muted pv-grow">Статус</span><EventStatusBadge status={ev.status} /></div>
            <div className="pv-row"><span className="pv-muted pv-grow">Исходов</span><b>{ev.outcomes.length}</b></div>
            <div className="pv-row"><span className="pv-muted pv-grow">Прогнозов</span><b>{ev.predictions_count}</b></div>
            <div className="pv-row"><span className="pv-muted pv-grow">Автор</span><span>{ev.created_by}</span></div>
            <div className="pv-row"><span className="pv-muted pv-grow">Создано</span><span className="pv-mono">{ev.created_at.slice(0,16)}</span></div>
          </div>
          <div className="pv-divider"></div>
          <div className="pv-stack" style={{ gap: 8 }}>
            <Btn variant="primary" icon="check">Сохранить</Btn>
            {ev.status === "draft" ? (
              <Btn variant="accent" icon="publish" disabled={ev.outcomes.length < 2}
                title={ev.outcomes.length < 2 ? "Нужно минимум 2 исхода" : ""}>Опубликовать</Btn>
            ) : ev.status !== "archived" ? (
              <Btn icon="unpublished">Снять с публикации</Btn>
            ) : null}
          </div>
          {ev.status === "draft" && ev.outcomes.length < 2 ? (
            <div className="pv-field-help" style={{ color: "var(--pv-warn)", marginTop: 10 }}>
              <Icon name="info" style={{ fontSize: 14, verticalAlign: "-2px" }} /> Публикация недоступна: нужно ≥ 2 исхода.
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function TabOutcomes({ ev }) {
  const locked = ev.status === "archived";
  return (
    <div className="pv-card pv-card-flush" style={{ maxWidth: 760 }}>
      <div className="pv-card-head">
        <h3>Исходы события</h3>
        <span className="pv-card-meta">удаление доступно, пока на исход нет прогнозов</span>
        {!locked ? <Btn size="sm" variant="primary" icon="add">Добавить</Btn> : null}
      </div>
      <table className="pv-table">
        <thead>
          <tr>
            <th style={{ width: 70 }}>Порядок</th>
            <th>Метка</th>
            <th className="pv-c-num">Прогнозов</th>
            <th className="pv-c-actions"></th>
          </tr>
        </thead>
        <tbody>
          {ev.outcomes.map((o) => (
            <tr key={o.id}>
              <td className="pv-mono">{o.sort_order}</td>
              <td className="pv-row-strong">{o.label}</td>
              <td className="pv-c-num">{o.predictions}</td>
              <td className="pv-c-actions">
                <div className="pv-row" style={{ justifyContent: "flex-end", gap: 4 }}>
                  <Btn size="sm" variant="ghost" icon="edit" disabled={locked} title="Изменить" />
                  <Btn size="sm" variant="ghost" icon="delete" disabled={o.predictions > 0 || locked}
                    title={o.predictions > 0 ? "Есть прогнозы — удаление запрещено" : "Удалить"} />
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TabResult({ ev }) {
  const fixed = ev.result_outcome_id != null;
  const [choice, setChoice] = useState(ev.result_outcome_id);

  // Видна, только когда событие опубликовано и приём закрыт (или уже архив с итогом)
  if (ev.status === "open" || ev.status === "draft") {
    return <div className="pv-card"><Empty icon="lock_clock"
      title="Фиксация итога недоступна"
      sub="Вкладка откроется, когда приём прогнозов закроется." /></div>;
  }

  const result = ev.outcomes.find((o) => o.id === ev.result_outcome_id);
  return (
    <div className="pv-stack" style={{ maxWidth: 620 }}>
      {fixed ? (
        <div className="pv-card" style={{ borderColor: "var(--pv-green)", background: "rgba(41,180,115,0.06)" }}>
          <div className="pv-row">
            <Icon name="check_circle" style={{ color: "var(--pv-green-2)", fontSize: 22 }} />
            <div>
              <b style={{ color: "var(--pv-fg)" }}>Итог зафиксирован: «{result ? result.label : "—"}»</b>
              <div className="pv-muted" style={{ fontSize: 13 }}>{ev.predictions_count} прогнозов проверено · переопределение не предусмотрено</div>
            </div>
          </div>
        </div>
      ) : null}

      <div className="pv-card">
        <div className="pv-section-title">Итоговый исход</div>
        <div className="pv-stack" style={{ gap: 8 }}>
          {ev.outcomes.map((o) => (
            <label key={o.id} className="result-opt"
              style={{ borderColor: choice === o.id ? "var(--pv-cta)" : "var(--pv-border)",
                       background: choice === o.id ? "rgba(54,169,225,0.06)" : "var(--pv-panel)",
                       opacity: fixed && choice !== o.id ? 0.55 : 1 }}>
              <input type="radio" name="result" disabled={fixed} checked={choice === o.id}
                onChange={() => setChoice(o.id)} />
              <span className="pv-grow" style={{ fontWeight: 700, color: "var(--pv-fg)" }}>{o.label}</span>
              <span className="pv-muted pv-mono">{o.predictions} прогн.</span>
            </label>
          ))}
        </div>
        {!fixed ? (
          <React.Fragment>
            <div className="pv-divider"></div>
            <div className="pv-row">
              <span className="pv-field-help pv-grow">
                <Icon name="warning" style={{ fontSize: 14, verticalAlign: "-2px", color: "var(--pv-warn)" }} /> Действие необратимо: все прогнозы получат отметку «сбылся / нет».
              </span>
              <Btn variant="accent" icon="task_alt" disabled={choice == null}>Зафиксировать</Btn>
            </div>
          </React.Fragment>
        ) : null}
      </div>
    </div>
  );
}

function EventDetail({ id, go }) {
  const isNew = id === "new";
  const ev = isNew ? null : window.EVENTS.find((e) => e.id === +id);
  const [tab, setTab] = useState("data");

  if (isNew) {
    return (
      <div className="pv-page">
        <PageHeader crumbs={[{ label: "События", onClick: () => go("events") }, { label: "Новое" }]}
          title="Новое событие" sub="Заполните данные, добавьте исходы, затем опубликуйте" />
        <TabData ev={{ title: "", description: "", category_id: 1, starts_at: "", predictions_close_at: "",
          metadata: {}, status: "draft", outcomes: [], predictions_count: 0, created_by: "Николай", created_at: "—" }} />
      </div>
    );
  }
  if (!ev) return <div className="pv-page"><Empty icon="error" title="Событие не найдено" /></div>;

  return (
    <div className="pv-page">
      <PageHeader
        crumbs={[{ label: "События", onClick: () => go("events") }, { label: "#" + ev.id }]}
        title={ev.title}
        sub={catName(ev.category_id) + " · старт " + ev.starts_at}
        actions={<EventStatusBadge status={ev.status} />}
      />
      <div className="pv-tabs">
        <button className={"pv-tab" + (tab === "data" ? " active" : "")} onClick={() => setTab("data")}>Данные</button>
        <button className={"pv-tab" + (tab === "outcomes" ? " active" : "")} onClick={() => setTab("outcomes")}>
          Исходы <span className="pv-muted">· {ev.outcomes.length}</span>
        </button>
        <button className={"pv-tab" + (tab === "result" ? " active" : "")} onClick={() => setTab("result")}>Результат</button>
      </div>
      {tab === "data" ? <TabData ev={ev} /> : null}
      {tab === "outcomes" ? <TabOutcomes ev={ev} /> : null}
      {tab === "result" ? <TabResult ev={ev} /> : null}
    </div>
  );
}

Object.assign(window, { EventDetail });
