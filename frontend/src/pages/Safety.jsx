import { useState } from "react";
import { api } from "../api";
import Badge from "../components/Badge.jsx";

function fmt(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function Safety() {
  const [machineId, setMachineId] = useState("MC-001");
  const [seatbelt, setSeatbelt] = useState(null);
  const [proximity, setProximity] = useState(null);
  const [hazard, setHazard] = useState(null);
  const [liveError, setLiveError] = useState(null);
  const [liveLoading, setLiveLoading] = useState(false);

  const [allAlerts, setAllAlerts] = useState(null);
  const [alertsError, setAlertsError] = useState(null);

  const [incidents, setIncidents] = useState(null);
  const [incidentsError, setIncidentsError] = useState(null);
  const [incidentForm, setIncidentForm] = useState({
    operator_id: "OP-003",
    machine_id: "MC-002",
    incident_type: "Near-Miss",
    severity: "Medium",
    description: "",
  });
  const [logging, setLogging] = useState(false);

  async function checkMachine() {
    const id = machineId.trim();
    setLiveLoading(true);
    setLiveError(null);
    setSeatbelt(null);
    setProximity(null);
    setHazard(null);
    try {
      const [sb, prox, haz] = await Promise.all([
        api.getSeatbelt(id),
        api.getProximity(id),
        api.getHazardPrediction(id),
      ]);
      setSeatbelt(sb);
      setProximity(prox);
      setHazard(haz);
    } catch (err) {
      setLiveError(err.message);
    } finally {
      setLiveLoading(false);
    }
  }

  async function refreshAllAlerts() {
    setAlertsError(null);
    try {
      setAllAlerts(await api.getAllProximityAlerts());
    } catch (err) {
      setAlertsError(err.message);
    }
  }

  async function refreshIncidents() {
    setIncidentsError(null);
    try {
      setIncidents(await api.getIncidents());
    } catch (err) {
      setIncidentsError(err.message);
    }
  }

  async function submitIncident(e) {
    e.preventDefault();
    setLogging(true);
    try {
      await api.logIncident(incidentForm);
      setIncidentForm((f) => ({ ...f, description: "" }));
      await refreshIncidents();
    } catch (err) {
      setIncidentsError(err.message);
    } finally {
      setLogging(false);
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1>Safety</h1>
        <p>Real-time seatbelt/proximity status, forward-looking hazard prediction, and incident logging.</p>
      </div>

      <div className="panel panel--yellow-edge">
        <h3>Live Machine Check</h3>
        <div className="field-row">
          <label className="field">
            Machine ID
            <input value={machineId} onChange={(e) => setMachineId(e.target.value)} />
          </label>
          <button className="btn btn--primary" onClick={checkMachine} disabled={liveLoading}>
            {liveLoading ? "Checking…" : "Check Machine"}
          </button>
        </div>

        {liveError && <div className="error-state">Error: {liveError}</div>}

        {(seatbelt || proximity || hazard) && (
          <div className="grid cols-3">
            {seatbelt && (
              <div className="stat-card">
                <div className="stat-card__label">Seatbelt</div>
                <div className="stat-card__value">{seatbelt.seatbelt_status ?? "—"}</div>
                <Badge variant={seatbelt.compliant ? "ok" : "critical"}>
                  {seatbelt.compliant ? "Compliant" : "Not Compliant"}
                </Badge>
                <div className="empty-state">Last reading: {fmt(seatbelt.timestamp)}</div>
              </div>
            )}
            {proximity && (
              <div className="stat-card">
                <div className="stat-card__label">Proximity (current)</div>
                <div className="stat-card__value">{proximity.proximity_alert}</div>
                <Badge variant={proximity.risk_level}>{proximity.risk_level} risk</Badge>
                <div className="empty-state">
                  {proximity.speed_kmph ?? "—"} km/h · {fmt(proximity.timestamp)}
                </div>
              </div>
            )}
            {hazard && (
              <div className="stat-card">
                <div className="stat-card__label">Predicted Hazard (next 5 min)</div>
                <div className="stat-card__value">
                  {(hazard.ml_hazard_probability * 100).toFixed(0)}%
                </div>
                <Badge variant={hazard.predicted_hazard ? "critical" : "ok"}>
                  {hazard.predicted_hazard ? "Hazard Predicted" : "No Hazard Surfaced"}
                </Badge>
                <div className="empty-state">
                  {hazard.rule_conditions_met.length > 0
                    ? `${hazard.rule_conditions_met.length} rule condition(s) also held`
                    : "ML alone is not enough — no rule condition held"}
                </div>
              </div>
            )}
          </div>
        )}

        {hazard && (
          <div style={{ marginTop: 14 }}>
            <strong style={{ fontSize: "0.8rem", textTransform: "uppercase", color: "var(--cat-gray-600)" }}>
              Gate detail
            </strong>
            {hazard.rule_conditions_met.length === 0 ? (
              <div className="empty-state">No rule-based condition was met, so this prediction is not surfaced as a hazard regardless of ML confidence.</div>
            ) : (
              <ul>
                {hazard.rule_conditions_met.map((c, i) => (
                  <li key={i}>{c}</li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      <div className="panel">
        <h3>Site-Wide Active Proximity Alerts</h3>
        <button className="btn" onClick={refreshAllAlerts}>
          Refresh Alerts
        </button>
        {alertsError && <div className="error-state">Error: {alertsError}</div>}
        {allAlerts && allAlerts.length === 0 && (
          <div className="empty-state">No active proximity alerts right now.</div>
        )}
        {allAlerts && allAlerts.length > 0 && (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Machine</th>
                  <th>Operator</th>
                  <th>Speed</th>
                  <th>Risk</th>
                  <th>Time</th>
                </tr>
              </thead>
              <tbody>
                {allAlerts.map((a, i) => (
                  <tr key={i}>
                    <td>{a.machine_id}</td>
                    <td>{a.operator_id ?? "—"}</td>
                    <td>{a.speed_kmph ?? "—"} km/h</td>
                    <td>
                      <Badge variant={a.risk_level}>{a.risk_level}</Badge>
                    </td>
                    <td>{fmt(a.timestamp)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="panel">
        <h3>Log an Incident</h3>
        <form onSubmit={submitIncident}>
          <div className="field-row">
            <label className="field">
              Operator ID
              <input
                value={incidentForm.operator_id}
                onChange={(e) => setIncidentForm((f) => ({ ...f, operator_id: e.target.value }))}
              />
            </label>
            <label className="field">
              Machine ID
              <input
                value={incidentForm.machine_id}
                onChange={(e) => setIncidentForm((f) => ({ ...f, machine_id: e.target.value }))}
              />
            </label>
            <label className="field">
              Type
              <select
                value={incidentForm.incident_type}
                onChange={(e) => setIncidentForm((f) => ({ ...f, incident_type: e.target.value }))}
              >
                <option>Near-Miss</option>
                <option>Collision</option>
                <option>Seatbelt Violation</option>
                <option>Mechanical Fault</option>
              </select>
            </label>
            <label className="field">
              Severity
              <select
                value={incidentForm.severity}
                onChange={(e) => setIncidentForm((f) => ({ ...f, severity: e.target.value }))}
              >
                <option>Low</option>
                <option>Medium</option>
                <option>High</option>
                <option>Critical</option>
              </select>
            </label>
          </div>
          <div className="field-row">
            <label className="field" style={{ flex: 1, minWidth: 240 }}>
              Description
              <input
                value={incidentForm.description}
                onChange={(e) => setIncidentForm((f) => ({ ...f, description: e.target.value }))}
                placeholder="Pedestrian near swing radius"
              />
            </label>
            <button className="btn btn--primary" type="submit" disabled={logging}>
              {logging ? "Logging…" : "Log Incident"}
            </button>
          </div>
        </form>

        <h3 style={{ marginTop: 20 }}>Incident Log</h3>
        <button className="btn" onClick={refreshIncidents}>
          Refresh Incidents
        </button>
        {incidentsError && <div className="error-state">Error: {incidentsError}</div>}
        {incidents && incidents.length === 0 && (
          <div className="empty-state">No incidents logged yet.</div>
        )}
        {incidents &&
          incidents.map((inc) => (
            <div key={inc.incident_id} className="article-card">
              <div className="article-card__meta">
                <strong>{inc.incident_id}</strong>
                <span>{inc.incident_type}</span>
                <Badge variant={inc.severity}>{inc.severity}</Badge>
                <span>{fmt(inc.timestamp)}</span>
              </div>
              <div>
                {inc.operator_id} · {inc.machine_id}
              </div>
              {inc.description && <div>{inc.description}</div>}
            </div>
          ))}
      </div>
    </div>
  );
}
