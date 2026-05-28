// ============================================================
// App shell: sidebar + topbar
// Brand mark is intentionally neutral (no company logo — OSS).
// ============================================================

const NAV = [
  { section: "Управление" },
  { id: "dashboard",  label: "Главная",        icon: "dashboard" },
  { id: "categories", label: "Категории",      icon: "folder", badge: "7" },
  { id: "events",     label: "События",        icon: "event",  badge: "11" },
  { id: "users",      label: "Пользователи",   icon: "groups", badge: "412" },
  { section: "Журнал" },
  { id: "audit",      label: "Аудит-лог",      icon: "receipt_long" },
  { section: "Развитие" },
  { id: "roadmap",    label: "Идеи интерфейсов", icon: "lightbulb" },
];

function Sidebar({ route, go, rail }) {
  return (
    <aside className="pv-sidebar">
      <div className="pv-sb-brand">
        <span className="bg-mark"><Icon name="insights" size={18} /></span>
        <div className="pv-sb-brand-text">
          <b>Прогнозы</b>
          <span>панель управления</span>
        </div>
      </div>
      <nav className="pv-sb-nav">
        {NAV.map((item, i) =>
          item.section ? (
            <div className="pv-sb-section" key={"s" + i}>{item.section}</div>
          ) : (
            <a key={item.id}
               className={"pv-sb-item" + (route === item.id ? " active" : "")}
               onClick={() => go(item.id)}>
              <Icon name={item.icon} />
              <span className="pv-sb-label">{item.label}</span>
              {item.badge ? <span className="pv-sb-badge">{item.badge}</span> : null}
            </a>
          )
        )}
      </nav>
      <div className="pv-sb-foot">
        <div className="pv-sb-foot-card">
          <div className="pv-sb-foot-text" style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span className="pv-status online" style={{ color: "#fff" }}></span>
            <b>Бот подключён</b>
          </div>
          <div className="pv-sb-foot-bar"><i style={{ width: "100%" }}></i></div>
          <div className="pv-sb-foot-text" style={{ opacity: 0.75 }}>@predictions_bot · webhook OK</div>
        </div>
      </div>
    </aside>
  );
}

function Topbar({ rail, setRail, admin, dark, setDark }) {
  const [menu, setMenu] = useState(false);
  return (
    <header className="pv-topbar">
      <Btn variant="ghost" icon="menu" onClick={() => setRail(!rail)} title="Свернуть меню" />
      <div className="pv-tb-search">
        <Icon name="search" className="ms" />
        <input placeholder="Поиск событий, пользователей, категорий…" />
        <kbd>⌘ K</kbd>
      </div>
      <div className="pv-tb-grow"></div>
      <div className="pv-tb-actions">
        <Btn variant="ghost" icon={dark ? "light_mode" : "dark_mode"} onClick={() => setDark(!dark)} title="Тема" />
        <button className="pv-tb-iconbtn" title="Уведомления">
          <Icon name="notifications" />
          <span className="pv-dot"></span>
        </button>
        <Btn variant="ghost" icon="help" title="Справка" />
        <div className="pv-tb-divider"></div>
        <div className="pv-tb-user" onClick={() => setMenu(!menu)} style={{ position: "relative" }}>
          <Avatar first="Николай" last="М" seed="nikolay" />
          <div className="pv-tb-user-meta">
            <b>Николай М.</b>
            <span>Администратор</span>
          </div>
          <Icon name="unfold_more" style={{ fontSize: 16, color: "var(--pv-fg-muted)" }} />
        </div>
      </div>
    </header>
  );
}

Object.assign(window, { Sidebar, Topbar, NAV });
