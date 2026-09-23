import { useState } from "react";
import { api } from "../api";

function fmt(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function Dashboard() {
  const [operatorId, setOperatorId] = useState("OP-001");
  const [forDate, setForDate] = useState("");
  const [tasks, setTasks] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  async function loadTasks(e) {
    e?.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const data = await api.getTasks(operatorId.trim(), forDate || undefined);
      setTasks(data);
    } catch (err) {
      setError(err.message);
      setTasks(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1>Daily Task Dashboard</h1>
        <p>Scheduled tasks for an operator's shift.</p>
      </div>

      <div className="panel panel--yellow-edge">
        <form className="field-row" onSubmit={loadTasks}>
          <label className="field">
            Operator ID
            <input value={operatorId} onChange={(e) => setOperatorId(e.target.value)} />
          </label>
          <label className="field">
            Date (optional)
            <input type="date" value={forDate} onChange={(e) => setForDate(e.target.value)} />
          </label>
          <button className="btn btn--primary" type="submit" disabled={loading}>
            {loading ? "Loading…" : "Get Tasks"}
          </button>
        </form>

        {error && <div className="error-state">Error: {error}</div>}

        {tasks && tasks.length === 0 && (
          <div className="empty-state">No tasks found for this operator/date.</div>
        )}

        {tasks && tasks.length > 0 && (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Task</th>
                  <th>Date</th>
                  <th>Site</th>
                  <th>Machine</th>
                  <th>Type</th>
                  <th>Environment</th>
                  <th>Terrain</th>
                  <th>Start</th>
                  <th>End</th>
                  <th>Priority</th>
                </tr>
              </thead>
              <tbody>
                {tasks.map((t) => (
                  <tr key={t.task_id}>
                    <td>{t.task_id}</td>
                    <td>{t.date}</td>
                    <td>{t.site_id}</td>
                    <td>{t.machine_id}</td>
                    <td>{t.task_type}</td>
                    <td>{t.environmental_condition}</td>
                    <td>{t.terrain_type}</td>
                    <td>{fmt(t.scheduled_start)}</td>
                    <td>{fmt(t.scheduled_end)}</td>
                    <td>{t.priority}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
