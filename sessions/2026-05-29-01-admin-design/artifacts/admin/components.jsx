// ============================================================
// Shared helpers + primitives for bettgbot admin
// ============================================================
const { useState, useEffect, useMemo, useRef } = React;

// ── helpers ───────────────────────────────────────────────
function Icon({ name, size, style, className }) {
  return (
    <span className={"material-symbols-rounded" + (className ? " " + className : "")}
      style={{ fontSize: size ? size : undefined, ...(style || {}) }}>{name}</span>
  );
}

function initials(first, last) {
  const a = (first || "").trim()[0] || "";
  const b = (last || "").trim()[0] || "";
  return (a + b).toUpperCase() || "?";
}
function avatarHue(seed) {
  let h = 0;
  const s = String(seed);
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return "a" + (h % 8);
}

// Status meta for events
const EVENT_STATUS = {
  draft:    { label: "черновик",          cls: "neutral" },
  open:     { label: "приём открыт",      cls: "success" },
  closed:   { label: "приём закрыт",      cls: "warn" },
  archived: { label: "архив",             cls: "info" },
};

function catName(id) {
  const c = (window.CATEGORIES || []).find((x) => x.id === id);
  return c ? c.name : "—";
}

// ── primitives ────────────────────────────────────────────
function Badge({ kind = "neutral", dot, icon, children }) {
  return (
    <span className={"pv-badge " + kind}>
      {dot ? <span className="pv-dot"></span> : null}
      {icon ? <Icon name={icon} style={{ fontSize: 13 }} /> : null}
      {children}
    </span>
  );
}

function EventStatusBadge({ status }) {
  const m = EVENT_STATUS[status] || EVENT_STATUS.draft;
  return <Badge kind={m.cls} dot>{m.label}</Badge>;
}

function Avatar({ first, last, seed, size, online }) {
  const cls = ["pv-avatar", avatarHue(seed || (first + last))];
  if (size) cls.push(size);
  return <span className={cls.join(" ")}>{initials(first, last)}</span>;
}

function Btn({ variant, size, icon, children, onClick, disabled, title, type }) {
  const cls = ["pv-btn"];
  if (variant) cls.push("pv-btn-" + variant);
  if (size) cls.push("pv-btn-" + size);
  if (icon && !children) cls.push("pv-btn-icon");
  return (
    <button className={cls.join(" ")} onClick={onClick} disabled={disabled} title={title} type={type || "button"}>
      {icon ? <Icon name={icon} /> : null}
      {children}
    </button>
  );
}

function Field({ label, required, help, children }) {
  return (
    <div className="pv-field">
      {label ? (
        <label className="pv-field-label">{label}{required ? <span className="pv-req">*</span> : null}</label>
      ) : null}
      {children}
      {help ? <div className="pv-field-help">{help}</div> : null}
    </div>
  );
}

function Modal({ title, onClose, children, footer, lg }) {
  useEffect(() => {
    const h = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, []);
  return (
    <div className="pv-modal-mask" onClick={onClose}>
      <div className={"pv-modal" + (lg ? " lg" : "")} onClick={(e) => e.stopPropagation()}>
        <div className="pv-modal-head">
          <h3>{title}</h3>
          <Btn variant="ghost" icon="close" onClick={onClose} />
        </div>
        <div className="pv-modal-body">{children}</div>
        {footer ? <div className="pv-modal-foot">{footer}</div> : null}
      </div>
    </div>
  );
}

function Empty({ icon, title, sub }) {
  return (
    <div className="pv-empty">
      <Icon name={icon || "inbox"} />
      <b>{title}</b>
      {sub ? <span>{sub}</span> : null}
    </div>
  );
}

function PageHeader({ crumbs, title, sub, actions }) {
  return (
    <div className="pv-page-header">
      <div>
        {crumbs ? (
          <div className="pv-breadcrumb">
            {crumbs.map((c, i) => (
              <React.Fragment key={i}>
                {i > 0 ? <Icon name="chevron_right" /> : null}
                {c.onClick ? <a onClick={c.onClick}>{c.label}</a> : <span>{c.label}</span>}
              </React.Fragment>
            ))}
          </div>
        ) : null}
        <h1 className="pv-page-title">{title}</h1>
        {sub ? <div className="pv-page-sub">{sub}</div> : null}
      </div>
      {actions ? <div className="pv-page-actions">{actions}</div> : null}
    </div>
  );
}

Object.assign(window, {
  Icon, initials, avatarHue, EVENT_STATUS, catName,
  Badge, EventStatusBadge, Avatar, Btn, Field, Modal, Empty, PageHeader,
});
