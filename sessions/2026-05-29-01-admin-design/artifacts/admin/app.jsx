// ============================================================
// App shell — роутер + интеграция Tweaks
// ============================================================

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "dark": false,
  "accent": "#e6403a",
  "density": "regular",
  "rail": false
}/*EDITMODE-END*/;

const ACCENTS = ["#e6403a", "#36a9e1", "#29b473", "#8e44ad", "#ff6b35"];
const DENSITY_MAP = { compact: "compact", regular: "", comfy: "comfortable" };

function App() {
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const [authed, setAuthed] = useState(true);
  const [route, setRoute] = useState("dashboard");
  const [params, setParams] = useState({});

  const go = (r, p) => { setRoute(r); setParams(p || {}); window.scrollTo(0, 0);
    const m = document.querySelector(".pv-main"); if (m) m.scrollTop = 0; };

  // apply theme / density / accent
  useEffect(() => {
    const root = document.documentElement;
    root.setAttribute("data-theme", t.dark ? "dark" : "light");
    const d = DENSITY_MAP[t.density] || "";
    if (d) root.setAttribute("data-density", d); else root.removeAttribute("data-density");
    root.style.setProperty("--pv-accent", t.accent);
    // derive a darker hover + soft tint for the chosen accent
    root.style.setProperty("--pv-accent-2", "color-mix(in srgb, " + t.accent + " 82%, #000)");
    root.style.setProperty("--pv-accent-soft",
      "color-mix(in srgb, " + t.accent + " " + (t.dark ? "22%, #14141b" : "12%, #fff") + ")");
  }, [t.dark, t.density, t.accent]);

  const tweaks = (
    <TweaksPanel title="Tweaks">
      <TweakSection label="Тема" />
      <TweakToggle label="Тёмная тема" value={t.dark} onChange={(v) => setTweak("dark", v)} />
      <TweakColor label="Акцент" value={t.accent} options={ACCENTS} onChange={(v) => setTweak("accent", v)} />
      <TweakSection label="Плотность таблиц" />
      <TweakRadio label="Density" value={t.density} options={["compact", "regular", "comfy"]}
        onChange={(v) => setTweak("density", v)} />
      <TweakSection label="Навигация" />
      <TweakToggle label="Свернуть меню" value={t.rail} onChange={(v) => setTweak("rail", v)} />
    </TweaksPanel>
  );

  if (!authed) {
    return (<React.Fragment><PageLogin onLogin={() => setAuthed(true)} />{tweaks}</React.Fragment>);
  }

  let page;
  if (route === "dashboard") page = <PageDashboard go={go} />;
  else if (route === "categories") page = <PageCategories go={go} />;
  else if (route === "events") page = params.id ? <EventDetail id={params.id} go={go} /> : <EventsList go={go} />;
  else if (route === "users") page = params.id ? <UserDetail id={params.id} go={go} /> : <UsersList go={go} />;
  else if (route === "audit") page = <PageAudit go={go} />;
  else if (route === "roadmap") page = <PageRoadmap go={go} />;
  else page = <PageDashboard go={go} />;

  return (
    <React.Fragment>
      <div className="pv-app" data-rail={t.rail ? "collapsed" : "expanded"}>
        <Sidebar route={route} go={go} rail={t.rail} />
        <Topbar rail={t.rail} setRail={(v) => setTweak("rail", v)}
          dark={t.dark} setDark={(v) => setTweak("dark", v)} />
        <main className="pv-main">{page}</main>
      </div>
      {tweaks}
    </React.Fragment>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
