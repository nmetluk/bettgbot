// ============================================================
// Категории — CRUD-список + модалка создания/редактирования
// ============================================================

function CategoryModal({ cat, onClose }) {
  const [name, setName] = useState(cat ? cat.name : "");
  const [slug, setSlug] = useState(cat ? cat.slug : "");
  const [sort, setSort] = useState(cat ? cat.sort_order : 8);
  const [active, setActive] = useState(cat ? cat.is_active : true);
  return (
    <Modal title={cat ? "Категория «" + cat.name + "»" : "Новая категория"} onClose={onClose}
      footer={<React.Fragment>
        {cat ? <Btn variant="danger" icon="delete" disabled={cat.events_count > 0}
          title={cat.events_count > 0 ? "Нельзя удалить непустую категорию" : ""}>Удалить</Btn> : null}
        <div className="pv-grow"></div>
        <Btn onClick={onClose}>Отмена</Btn>
        <Btn variant="primary" icon="check" onClick={onClose}>Сохранить</Btn>
      </React.Fragment>}>
      <div className="pv-stack">
        <Field label="Название" required>
          <input className="pv-input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Например: Футбол" />
        </Field>
        <Field label="Slug" required help="Используется в дип-линках бота: /all?cat=…">
          <input className="pv-input pv-mono" value={slug} onChange={(e) => setSlug(e.target.value)} placeholder="football" />
        </Field>
        <div className="pv-grid c2">
          <Field label="Порядок" help="Сортировка в списках">
            <input className="pv-input pv-mono" type="number" value={sort} onChange={(e) => setSort(e.target.value)} />
          </Field>
          <Field label="Видимость">
            <div className="pv-row" style={{ height: 36 }}>
              <div className={"pv-toggle" + (active ? " on" : "")} onClick={() => setActive(!active)}></div>
              <span className="pv-muted">{active ? "Видна пользователям" : "Скрыта от бота"}</span>
            </div>
          </Field>
        </div>
        {cat && cat.events_count > 0 ? (
          <div className="pv-field-help" style={{ color: "var(--pv-warn)" }}>
            <Icon name="info" style={{ fontSize: 14, verticalAlign: "-2px" }} /> В категории {cat.events_count} событий — удаление недоступно.
          </div>
        ) : null}
      </div>
    </Modal>
  );
}

function PageCategories() {
  const [modal, setModal] = useState(null); // null | {} (new) | cat
  const cats = window.CATEGORIES;
  return (
    <div className="pv-page">
      <PageHeader title="Категории" sub="Папки событий, видимые пользователю как разделы бота"
        actions={<Btn variant="primary" icon="add" onClick={() => setModal({})}>Добавить категорию</Btn>} />

      <div className="pv-card pv-card-flush">
        <table className="pv-table">
          <thead>
            <tr>
              <th style={{ width: 60 }}>ID</th>
              <th>Название</th><th>Slug</th>
              <th className="pv-c-num">Порядок</th>
              <th className="pv-c-num">Событий</th>
              <th>Видимость</th>
              <th className="pv-c-actions">Действия</th>
            </tr>
          </thead>
          <tbody>
            {cats.map((c) => (
              <tr key={c.id}>
                <td className="pv-mono pv-muted">{c.id}</td>
                <td className="pv-row-strong">{c.name}</td>
                <td><code>{c.slug}</code></td>
                <td className="pv-c-num">{c.sort_order}</td>
                <td className="pv-c-num">{c.events_count}</td>
                <td>{c.is_active
                  ? <Badge kind="success" dot>видна</Badge>
                  : <Badge kind="neutral" dot>скрыта</Badge>}</td>
                <td className="pv-c-actions">
                  <div className="pv-row" style={{ justifyContent: "flex-end", gap: 4 }}>
                    <Btn size="sm" variant="ghost" icon="edit" onClick={() => setModal(c)} title="Редактировать" />
                    <Btn size="sm" variant="ghost" icon="delete" disabled={c.events_count > 0}
                      title={c.events_count > 0 ? "Нельзя удалить непустую категорию" : "Удалить"} />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {modal !== null ? <CategoryModal cat={modal.id ? modal : null} onClose={() => setModal(null)} /> : null}
    </div>
  );
}

Object.assign(window, { PageCategories });
