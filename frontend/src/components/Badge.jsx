const VARIANT_BY_SEVERITY = {
  ok: "ok",
  low: "low",
  warning: "warning",
  medium: "medium",
  critical: "critical",
  high: "high",
};

export default function Badge({ children, variant }) {
  const key = (variant || "neutral").toLowerCase();
  const cls = VARIANT_BY_SEVERITY[key] || "neutral";
  return <span className={`badge badge--${cls}`}>{children}</span>;
}
