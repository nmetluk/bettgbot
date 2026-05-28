// ============================================================
// Идеи интерфейсов — рекомендации по развитию за рамками MVP
// ============================================================

const IDEAS = [
  { icon: "monitoring", title: "Аналитика и статистика", impact: "Высокий", effort: "M",
    body: "Динамика прогнозов по дням, точность по категориям, воронка «регистрация → первый прогноз», топ-события. В MVP сознательно опущено — но это первый запрос, который появится после запуска." },
  { icon: "leaderboard", title: "Рейтинг пользователей", impact: "Высокий", effort: "S",
    body: "Лидерборд по точности и числу верных прогнозов за период. Главный геймификационный крючок: повышает удержание и частоту прогнозов. Данные уже есть в Prediction.is_correct." },
  { icon: "campaign", title: "Рассылки и анонсы", impact: "Высокий", effort: "M",
    body: "Экран составления broadcast-сообщения по сегменту (все / активные / по категории) с предпросмотром в Telegram и историей отправок. Закрывает «как сообщить о новом событии»." },
  { icon: "admin_panel_settings", title: "Управление администраторами", impact: "Средний", effort: "S",
    body: "Список админов, роли (полный / только просмотр / модератор), добавление из UI вместо скрипта. В спецификации помечено как опциональное — выносим в отдельный экран с аудитом." },
  { icon: "playlist_add", title: "Массовое создание событий", impact: "Средний", effort: "M",
    body: "Импорт тура/расписания: загрузка CSV или шаблон «матч-день», авто-создание событий с типовыми исходами (П1 / Х / П2). Снимает рутину при заведении 10+ матчей за раз." },
  { icon: "tune", title: "Настройки бота", impact: "Средний", effort: "S",
    body: "Тексты приветствия и /help, дефолтные офсеты напоминаний, дип-линки, режим обслуживания. Сейчас всё в шаблонах — выводим в редактируемый экран." },
  { icon: "hub", title: "Мониторинг внешнего реестра", impact: "Средний", effort: "S",
    body: "Состояние внешнего API проверки телефонов: доступность, латентность, последние отказы, переключение на mock. Критично для диагностики «почему пользователь не регистрируется»." },
  { icon: "verified_user", title: "Модерация и жалобы", impact: "Низкий", effort: "M",
    body: "Очередь обращений, причины блокировок с историей, временные ограничения вместо вечного бана. Развитие нынешнего флага is_blocked в полноценный инструмент." },
];

function IdeaCard({ idea }) {
  const impactKind = idea.impact === "Высокий" ? "success" : idea.impact === "Средний" ? "warn" : "neutral";
  return (
    <div className="pv-card">
      <div className="pv-row" style={{ alignItems: "flex-start", gap: 12, marginBottom: 10 }}>
        <span className="idea-medallion"><Icon name={idea.icon} size={20} /></span>
        <div className="pv-grow">
          <div className="pv-h3">{idea.title}</div>
        </div>
      </div>
      <p style={{ margin: "0 0 14px", color: "var(--pv-fg-body)", fontSize: 13, lineHeight: 1.5 }}>{idea.body}</p>
      <div className="pv-row" style={{ gap: 6 }}>
        <Badge kind={impactKind}>польза: {idea.impact}</Badge>
        <Badge kind="neutral">объём: {idea.effort}</Badge>
      </div>
    </div>
  );
}

function PageRoadmap() {
  return (
    <div className="pv-page">
      <PageHeader title="Идеи интерфейсов"
        sub="Рекомендации по развитию админки за рамками MVP — материал для cowork-сессии с архитектором" />

      <div className="pv-card" style={{ marginBottom: 16, borderLeft: "3px solid var(--pv-cta)" }}>
        <div className="pv-row" style={{ gap: 10 }}>
          <Icon name="lightbulb" style={{ color: "var(--pv-cta)", fontSize: 22 }} />
          <p style={{ margin: 0, fontSize: 13, color: "var(--pv-fg-body)", lineHeight: 1.5 }}>
            Текущий MVP покрывает CRUD событий, фиксацию итогов и просмотр пользователей. Ниже — экраны следующих
            итераций, отсортированные по соотношению пользы и объёма. Все они переиспользуют ту же дизайн-систему,
            компоненты и сетку, что и реализованные страницы.
          </p>
        </div>
      </div>

      <div className="pv-grid c3">
        {IDEAS.map((idea, i) => <IdeaCard key={i} idea={idea} />)}
      </div>
    </div>
  );
}

Object.assign(window, { PageRoadmap });
