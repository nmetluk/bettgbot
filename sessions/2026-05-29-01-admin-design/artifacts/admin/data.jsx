// ============================================================
// bettgbot admin — demo seed data (fictional, safe filler)
// Domain: Telegram-бот пользовательских прогнозов на события.
// ============================================================

const CATEGORIES = [
  { id: 1, name: "Футбол", slug: "football", sort_order: 1, is_active: true, events_count: 14, created_at: "2026-01-12" },
  { id: 2, name: "Хоккей", slug: "hockey", sort_order: 2, is_active: true, events_count: 9, created_at: "2026-01-12" },
  { id: 3, name: "Теннис", slug: "tennis", sort_order: 3, is_active: true, events_count: 6, created_at: "2026-01-20" },
  { id: 4, name: "Киберспорт", slug: "esports", sort_order: 4, is_active: true, events_count: 7, created_at: "2026-02-03" },
  { id: 5, name: "Баскетбол", slug: "basketball", sort_order: 5, is_active: true, events_count: 4, created_at: "2026-02-14" },
  { id: 6, name: "Политика", slug: "politics", sort_order: 6, is_active: false, events_count: 2, created_at: "2026-03-01" },
  { id: 7, name: "Развлечения", slug: "ent", sort_order: 7, is_active: false, events_count: 0, created_at: "2026-04-10" },
];

// status: draft | open | closed | archived
const EVENTS = [
  {
    id: 142, title: "Спартак — ЦСКА", category_id: 1, status: "open",
    description: "Матч 18-го тура РПЛ. Дерби.",
    starts_at: "2026-05-31 19:30", predictions_close_at: "2026-05-31 19:00",
    predictions_count: 318, created_by: "Николай", created_at: "2026-05-24 11:20",
    metadata: { league: "РПЛ", tour: 18, stadium: "Открытие Банк Арена", stream: "https://matchtv.ru/live" },
    outcomes: [
      { id: 1, label: "Победа Спартака", sort_order: 1, predictions: 141 },
      { id: 2, label: "Ничья", sort_order: 2, predictions: 64 },
      { id: 3, label: "Победа ЦСКА", sort_order: 3, predictions: 113 },
    ],
    result_outcome_id: null,
  },
  {
    id: 141, title: "Зенит — Краснодар", category_id: 1, status: "closed",
    description: "Матч за чемпионство.",
    starts_at: "2026-05-29 18:00", predictions_close_at: "2026-05-29 17:30",
    predictions_count: 402, created_by: "Николай", created_at: "2026-05-22 09:05",
    metadata: { league: "РПЛ", tour: 17 },
    outcomes: [
      { id: 4, label: "Победа Зенита", sort_order: 1, predictions: 188 },
      { id: 5, label: "Ничья", sort_order: 2, predictions: 97 },
      { id: 6, label: "Победа Краснодара", sort_order: 3, predictions: 117 },
    ],
    result_outcome_id: null,
  },
  {
    id: 140, title: "СКА — ЦСКА (хоккей)", category_id: 2, status: "open",
    description: "Финал Кубка Гагарина, матч 5.",
    starts_at: "2026-06-02 19:30", predictions_close_at: "2026-06-02 19:30",
    predictions_count: 156, created_by: "Мария", created_at: "2026-05-25 14:40",
    metadata: { league: "КХЛ", series: "3-1" },
    outcomes: [
      { id: 7, label: "Победа СКА", sort_order: 1, predictions: 71 },
      { id: 8, label: "Победа ЦСКА", sort_order: 2, predictions: 85 },
    ],
    result_outcome_id: null,
  },
  {
    id: 139, title: "Медведев — Алькарас", category_id: 3, status: "open",
    description: "Полуфинал Roland Garros.",
    starts_at: "2026-06-06 16:00", predictions_close_at: "2026-06-06 15:45",
    predictions_count: 94, created_by: "Мария", created_at: "2026-05-26 10:10",
    metadata: { tournament: "Roland Garros", round: "1/2" },
    outcomes: [
      { id: 9, label: "Победа Медведева", sort_order: 1, predictions: 38 },
      { id: 10, label: "Победа Алькараса", sort_order: 2, predictions: 56 },
    ],
    result_outcome_id: null,
  },
  {
    id: 138, title: "Navi — Spirit (CS2)", category_id: 4, status: "draft",
    description: "Гранд-финал PGL Major. Bo5.",
    starts_at: "2026-06-08 17:00", predictions_close_at: "2026-06-08 16:30",
    predictions_count: 0, created_by: "Николай", created_at: "2026-05-27 12:00",
    metadata: { event: "PGL Major", format: "Bo5" },
    outcomes: [
      { id: 11, label: "Победа Navi", sort_order: 1, predictions: 0 },
      { id: 12, label: "Победа Spirit", sort_order: 2, predictions: 0 },
    ],
    result_outcome_id: null,
  },
  {
    id: 137, title: "Динамо — Локомотив", category_id: 1, status: "archived",
    description: "Завершившийся матч 16-го тура.",
    starts_at: "2026-05-18 14:00", predictions_close_at: "2026-05-18 13:30",
    predictions_count: 276, created_by: "Николай", created_at: "2026-05-10 08:30",
    metadata: { league: "РПЛ", tour: 16 },
    outcomes: [
      { id: 13, label: "Победа Динамо", sort_order: 1, predictions: 90 },
      { id: 14, label: "Ничья", sort_order: 2, predictions: 71 },
      { id: 15, label: "Победа Локомотива", sort_order: 3, predictions: 115 },
    ],
    result_outcome_id: 15,
  },
  {
    id: 136, title: "Ак Барс — Авангард", category_id: 2, status: "archived",
    description: "Матч регулярного чемпионата.",
    starts_at: "2026-05-15 17:00", predictions_close_at: "2026-05-15 17:00",
    predictions_count: 134, created_by: "Мария", created_at: "2026-05-08 16:20",
    metadata: { league: "КХЛ" },
    outcomes: [
      { id: 16, label: "Победа Ак Барса", sort_order: 1, predictions: 78 },
      { id: 17, label: "Победа Авангарда", sort_order: 2, predictions: 56 },
    ],
    result_outcome_id: 16,
  },
  {
    id: 135, title: "Выборы мэра — второй тур", category_id: 6, status: "archived",
    description: "Архивировано автоматически без фиксации итога (страховочный путь).",
    starts_at: "2026-05-04 20:00", predictions_close_at: "2026-05-04 18:00",
    predictions_count: 41, created_by: "Николай", created_at: "2026-04-25 11:00",
    metadata: {},
    outcomes: [
      { id: 18, label: "Кандидат А", sort_order: 1, predictions: 22 },
      { id: 19, label: "Кандидат Б", sort_order: 2, predictions: 19 },
    ],
    result_outcome_id: null, // страховочный путь: архив без итога
  },
];

const USERS = [
  { id: 1, tg_user_id: 184920113, phone: "+79161234567", first_name: "Алексей", last_name: "Воронов", username: "voronov_a", predictions: 47, accuracy: 0.62, created_at: "2026-01-15", last_seen_at: "2026-05-28 21:14", is_blocked: false },
  { id: 2, tg_user_id: 209113847, phone: "+79031115588", first_name: "Мария", last_name: "Климова", username: "klimova", predictions: 51, accuracy: 0.71, created_at: "2026-01-18", last_seen_at: "2026-05-29 08:02", is_blocked: false },
  { id: 3, tg_user_id: 561200934, phone: "+79261239090", first_name: "Дмитрий", last_name: "Соколов", username: "dsokolov", predictions: 38, accuracy: 0.55, created_at: "2026-02-02", last_seen_at: "2026-05-27 19:40", is_blocked: false },
  { id: 4, tg_user_id: 712038475, phone: "+79051119922", first_name: "Игорь", last_name: "Панин", username: null, predictions: 12, accuracy: 0.42, created_at: "2026-03-11", last_seen_at: "2026-05-20 12:33", is_blocked: true },
  { id: 5, tg_user_id: 884733012, phone: "+79169998877", first_name: "Екатерина", last_name: "Лебедева", username: "kate_leb", predictions: 63, accuracy: 0.68, created_at: "2026-01-22", last_seen_at: "2026-05-29 07:51", is_blocked: false },
  { id: 6, tg_user_id: 330119284, phone: "+79112223344", first_name: "Павел", last_name: null, username: "pavel99", predictions: 8, accuracy: 0.50, created_at: "2026-04-19", last_seen_at: "2026-05-26 23:10", is_blocked: false },
  { id: 7, tg_user_id: 451920038, phone: "+79261110055", first_name: "Ольга", last_name: "Жукова", username: "olga_zh", predictions: 29, accuracy: 0.59, created_at: "2026-02-28", last_seen_at: "2026-05-28 18:22", is_blocked: false },
  { id: 8, tg_user_id: 198273645, phone: "+79037778811", first_name: "Сергей", last_name: "Морозов", username: "morozov_s", predictions: 44, accuracy: 0.64, created_at: "2026-01-30", last_seen_at: "2026-05-29 06:45", is_blocked: false },
];

// прогнозы конкретного пользователя (для карточки пользователя)
const USER_PREDICTIONS = {
  1: [
    { event: "Зенит — Краснодар", category: "Футбол", outcome: "Победа Зенита", status: "closed", is_correct: null },
    { event: "Динамо — Локомотив", category: "Футбол", outcome: "Победа Локомотива", status: "archived", is_correct: true },
    { event: "Ак Барс — Авангард", category: "Хоккей", outcome: "Победа Авангарда", status: "archived", is_correct: false },
    { event: "Спартак — ЦСКА", category: "Футбол", outcome: "Победа Спартака", status: "open", is_correct: null },
    { event: "Медведев — Алькарас", category: "Теннис", outcome: "Победа Медведева", status: "open", is_correct: null },
  ],
};

const AUDIT = [
  { id: 5012, admin: "Николай", action: "event.set_result", created_at: "2026-05-28 22:40", payload: { event_id: 137, outcome_id: 15, marked: 276 } },
  { id: 5011, admin: "Николай", action: "event.publish", created_at: "2026-05-28 11:25", payload: { event_id: 142 } },
  { id: 5010, admin: "Мария", action: "event.create", created_at: "2026-05-26 10:10", payload: { event_id: 139, title: "Медведев — Алькарас" } },
  { id: 5009, admin: "Мария", action: "outcome.create", created_at: "2026-05-26 10:11", payload: { event_id: 139, outcome_id: 10, label: "Победа Алькараса" } },
  { id: 5008, admin: "Николай", action: "user.block", created_at: "2026-05-25 16:02", payload: { user_id: 4, reason: "мультиаккаунт" } },
  { id: 5007, admin: "Мария", action: "event.create", created_at: "2026-05-25 14:40", payload: { event_id: 140, title: "СКА — ЦСКА (хоккей)" } },
  { id: 5006, admin: "Николай", action: "category.update", created_at: "2026-05-24 09:30", payload: { category_id: 6, is_active: false } },
  { id: 5005, admin: "Николай", action: "event.create", created_at: "2026-05-24 11:20", payload: { event_id: 142, title: "Спартак — ЦСКА" } },
  { id: 5004, admin: "Николай", action: "admin.login", created_at: "2026-05-24 09:01", payload: { ip: "85.140.12.4" } },
  { id: 5003, admin: "Мария", action: "event.set_result", created_at: "2026-05-16 12:15", payload: { event_id: 136, outcome_id: 16, marked: 134 } },
  { id: 5002, admin: "Николай", action: "category.create", created_at: "2026-04-10 10:00", payload: { category_id: 7, name: "Развлечения" } },
  { id: 5001, admin: "Мария", action: "outcome.delete", created_at: "2026-04-08 15:44", payload: { event_id: 130, outcome_id: 99 } },
];

const STATS = {
  users_total: 412,
  users_active_30d: 287,
  categories: 7,
  events_total: 42,
  events_published: 11,
  events_archived: 24,
  predictions_total: 8430,
  predictions_24h: 196,
};

const ACTION_LABELS = {
  "category.create": "Категория · создание",
  "category.update": "Категория · изменение",
  "category.delete": "Категория · удаление",
  "event.create": "Событие · создание",
  "event.update": "Событие · изменение",
  "event.publish": "Событие · публикация",
  "event.unpublish": "Событие · снятие",
  "event.set_result": "Событие · фиксация итога",
  "outcome.create": "Исход · создание",
  "outcome.update": "Исход · изменение",
  "outcome.delete": "Исход · удаление",
  "admin.login": "Вход администратора",
  "user.block": "Пользователь · блокировка",
  "user.unblock": "Пользователь · разблокировка",
};

Object.assign(window, { CATEGORIES, EVENTS, USERS, USER_PREDICTIONS, AUDIT, STATS, ACTION_LABELS });
