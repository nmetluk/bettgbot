// ============================================================
// Пользователи — список с поиском + карточка с прогнозами
// ============================================================

function UsersList({ go }) {
  const [q, setQ] = useState("");
  const rows = window.USERS.filter((u) => {
    if (!q) return true;
    const s = (u.phone + " " + (u.username || "") + " " + u.first_name + " " + (u.last_name || "")).toLowerCase();
    return s.includes(q.toLowerCase());
  });
  return (
    <div className="pv-page">
      <PageHeader title="Пользователи" sub="Проверенные по телефону через внешний реестр" />
      <div className="pv-card pv-card-flush">
        <div className="pv-toolbar">
          <div className="pv-toolbar-search">
            <Icon name="search" className="ms" />
            <input placeholder="Телефон, username или имя…" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
        </div>
        <table className="pv-table">
          <thead>
            <tr>
              <th style={{ width: 50 }}>ID</th>
              <th>Пользователь</th><th>Телефон</th><th>Telegram</th>
              <th className="pv-c-num">Прогнозов</th>
              <th>Регистрация</th><th>Доступ</th>
              <th className="pv-c-actions"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((u) => (
              <tr key={u.id} style={{ cursor: "pointer" }} onClick={() => go("users", { id: u.id })}>
                <td className="pv-mono pv-muted">{u.id}</td>
                <td>
                  <div className="pv-row" style={{ gap: 10 }}>
                    <Avatar first={u.first_name} last={u.last_name || ""} seed={u.id} size="sm" />
                    <span className="pv-row-strong">{u.first_name} {u.last_name || ""}</span>
                  </div>
                </td>
                <td className="pv-mono">{u.phone}</td>
                <td>{u.username ? <span className="pv-muted">@{u.username}</span> : <span className="pv-muted">—</span>}</td>
                <td className="pv-c-num">{u.predictions}</td>
                <td className="pv-mono pv-muted">{u.created_at}</td>
                <td>{u.is_blocked ? <Badge kind="danger" dot>заблокирован</Badge> : <Badge kind="success" dot>активен</Badge>}</td>
                <td className="pv-c-actions"><Icon name="chevron_right" style={{ color: "var(--pv-fg-subtle)" }} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function UserDetail({ id, go }) {
  const u = window.USERS.find((x) => x.id === +id);
  if (!u) return <div className="pv-page"><Empty icon="person_off" title="Пользователь не найден" /></div>;
  const preds = window.USER_PREDICTIONS[u.id] || [];

  return (
    <div className="pv-page">
      <PageHeader
        crumbs={[{ label: "Пользователи", onClick: () => go("users") }, { label: "#" + u.id }]}
        title={u.first_name + " " + (u.last_name || "")}
        sub={u.username ? "@" + u.username : "без username"}
        actions={u.is_blocked
          ? <Btn variant="primary" icon="lock_open">Разблокировать</Btn>
          : <Btn variant="danger" icon="block">Заблокировать</Btn>}
      />

      <div className="pv-grid c-1-2">
        {/* Профиль */}
        <div className="pv-card">
          <div className="pv-row" style={{ gap: 14, marginBottom: 16 }}>
            <Avatar first={u.first_name} last={u.last_name || ""} seed={u.id} size="lg" />
            <div>
              <div style={{ fontWeight: 700, color: "var(--pv-fg)", fontSize: 16 }}>{u.first_name} {u.last_name || ""}</div>
              {u.is_blocked ? <Badge kind="danger" dot>доступ ограничен</Badge> : <Badge kind="success" dot>активен</Badge>}
            </div>
          </div>
          <div className="pv-stack" style={{ gap: 10 }}>
            <div className="pv-row"><span className="pv-muted pv-grow">Телефон</span><span className="pv-mono">{u.phone}</span></div>
            <div className="pv-row"><span className="pv-muted pv-grow">Telegram ID</span><span className="pv-mono">{u.tg_user_id}</span></div>
            <div className="pv-row"><span className="pv-muted pv-grow">Username</span><span>{u.username ? "@" + u.username : "—"}</span></div>
            <div className="pv-row"><span className="pv-muted pv-grow">Регистрация</span><span className="pv-mono">{u.created_at}</span></div>
            <div className="pv-row"><span className="pv-muted pv-grow">Был онлайн</span><span className="pv-mono">{u.last_seen_at.slice(5)}</span></div>
          </div>
          <div className="pv-divider"></div>
          <div className="pv-row">
            <div className="pv-grow">
              <div className="pv-caps">Точность</div>
              <div className="pv-num-lg">{Math.round(u.accuracy * 100)}%</div>
            </div>
            <div className="pv-grow">
              <div className="pv-caps">Прогнозов</div>
              <div className="pv-num-lg">{u.predictions}</div>
            </div>
          </div>
        </div>

        {/* Прогнозы */}
        <div className="pv-card pv-card-flush">
          <div className="pv-card-head"><h3>Прогнозы пользователя</h3><span className="pv-card-meta">{preds.length} записей</span></div>
          {preds.length === 0 ? <Empty icon="checklist" title="Пока нет прогнозов" /> : (
            <table className="pv-table">
              <thead>
                <tr><th>Событие</th><th>Категория</th><th>Выбор</th><th>Статус события</th><th>Результат</th></tr>
              </thead>
              <tbody>
                {preds.map((p, i) => (
                  <tr key={i}>
                    <td className="pv-row-strong">{p.event}</td>
                    <td>{p.category}</td>
                    <td>{p.outcome}</td>
                    <td><EventStatusBadge status={p.status} /></td>
                    <td>{p.is_correct == null
                      ? <span className="pv-muted">—</span>
                      : p.is_correct
                        ? <Badge kind="success" icon="check">сбылся</Badge>
                        : <Badge kind="danger" icon="close">не сбылся</Badge>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { UsersList, UserDetail });
