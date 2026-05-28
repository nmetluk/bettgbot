// ============================================================
// Экран входа — логин/пароль (без саморегистрации)
// ============================================================

function PageLogin({ onLogin }) {
  const [err, setErr] = useState(false);
  return (
    <div className="login-wrap">
      <div className="login-card">
        <div className="login-brand">
          <span className="bg-mark lg"><Icon name="insights" size={22} /></span>
          <div>
            <b>Прогнозы</b>
            <span>панель управления</span>
          </div>
        </div>
        <h1 className="pv-page-title" style={{ fontSize: 20, marginBottom: 4 }}>Вход в админку</h1>
        <p className="pv-page-sub" style={{ marginBottom: 20 }}>Доступ только для администраторов</p>
        <div className="pv-stack">
          <Field label="Логин">
            <input className="pv-input" defaultValue="nikolay" autoFocus />
          </Field>
          <Field label="Пароль">
            <input className="pv-input" type="password" defaultValue="••••••••" />
          </Field>
          {err ? (
            <div className="pv-field-help" style={{ color: "var(--pv-danger)" }}>
              <Icon name="error" style={{ fontSize: 14, verticalAlign: "-2px" }} /> Неверный логин или пароль
            </div>
          ) : null}
          <Btn variant="primary" size="lg" icon="login" onClick={onLogin}>Войти</Btn>
        </div>
        <div className="login-foot">
          <Icon name="shield" style={{ fontSize: 14, verticalAlign: "-2px" }} /> Защищённое соединение · сессия 8 часов
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { PageLogin });
