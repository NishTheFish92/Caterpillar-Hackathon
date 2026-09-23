import { useState } from "react";
import { api } from "../api";
import Badge from "../components/Badge.jsx";
import StatCard from "../components/StatCard.jsx";

export default function Behavior() {
  const [operatorId, setOperatorId] = useState("OP-002");
  const [days, setDays] = useState(21);
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  async function analyze(e) {
    e?.preventDefault();
    setLoading(true);
    setError(null);
    try {
      setReport(await api.getAnomalies(operatorId.trim(), days));
    } catch (err) {
      setError(err.message);
      setReport(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1>Unusual Behavior Detection</h1>
        <p>Rule-based rollup over recent shifts: idling, seatbelt compliance, unsafe/proximity events.</p>
      </div>

      <div className="panel panel--yellow-edge">
        <form className="field-row" onSubmit={analyze}>
          <label className="field">
            Operator ID
            <input value={operatorId} onChange={(e) => setOperatorId(e.target.value)} />
          </label>
          <label className="field">
            Days
            <input
              type="number"
              min="1"
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
              style={{ width: 90 }}
            />
          </label>
          <button className="btn btn--primary" type="submit" disabled={loading}>
            {loading ? "Analyzing…" : "Analyze"}
          </button>
        </form>

        {error && <div className="error-state">Error: {error}</div>}

        {report && (
          <>
            <div className="grid cols-4" style={{ marginBottom: 18 }}>
              <StatCard label="Days Analyzed" value={report.days_analyzed} />
              <StatCard label="Avg Idle %" value={`${report.avg_idle_pct}%`} />
              <StatCard label="Seatbelt Compliance" value={`${report.avg_seatbelt_compliance_pct}%`} />
              <StatCard label="Unsafe Events" value={report.total_unsafe_events} />
            </div>

            {report.anomalies.length === 0 ? (
              <div className="empty-state">No anomalies detected — operating within normal thresholds.</div>
            ) : (
              report.anomalies.map((a, i) => (
                <div key={i} className={`alert-block ${a.severity === "Critical" ? "critical" : ""}`}>
                  <strong>
                    {a.flag} <Badge variant={a.severity}>{a.severity}</Badge>
                  </strong>
                  {a.detail}
                </div>
              ))
            )}
          </>
        )}
      </div>
    </div>
  );
}
