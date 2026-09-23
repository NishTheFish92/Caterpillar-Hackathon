import { useState } from "react";
import { api } from "../api";
import Badge from "../components/Badge.jsx";
import StatCard from "../components/StatCard.jsx";

const TASK_TYPES = ["Excavation", "Grading", "Material Loading", "Trenching", "Demolition"];
const ENV_CONDITIONS = ["Clear", "Rain", "Dust Storm", "High Wind"];
const TERRAIN_TYPES = ["Soft Soil", "Hard Soil", "Rocky", "Muddy"];

export default function Estimation() {
  const [form, setForm] = useState({
    task_type: "Excavation",
    environmental_condition: "Clear",
    terrain_type: "Hard Soil",
    operator_id: "",
    machine_id: "",
  });
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  async function estimate(e) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const payload = {
        ...form,
        operator_id: form.operator_id.trim() || undefined,
        machine_id: form.machine_id.trim() || undefined,
      };
      setResult(await api.estimateTaskTime(payload));
    } catch (err) {
      setError(err.message);
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1>Task Time Estimation</h1>
        <p>ML regression model trained on historical tasks — terrain, weather, operator experience, machine health.</p>
      </div>

      <div className="panel panel--yellow-edge">
        <form onSubmit={estimate}>
          <div className="field-row">
            <label className="field">
              Task Type
              <select value={form.task_type} onChange={(e) => setForm((f) => ({ ...f, task_type: e.target.value }))}>
                {TASK_TYPES.map((t) => (
                  <option key={t}>{t}</option>
                ))}
              </select>
            </label>
            <label className="field">
              Environmental Condition
              <select
                value={form.environmental_condition}
                onChange={(e) => setForm((f) => ({ ...f, environmental_condition: e.target.value }))}
              >
                {ENV_CONDITIONS.map((t) => (
                  <option key={t}>{t}</option>
                ))}
              </select>
            </label>
            <label className="field">
              Terrain
              <select value={form.terrain_type} onChange={(e) => setForm((f) => ({ ...f, terrain_type: e.target.value }))}>
                {TERRAIN_TYPES.map((t) => (
                  <option key={t}>{t}</option>
                ))}
              </select>
            </label>
          </div>
          <div className="field-row">
            <label className="field">
              Operator ID (optional)
              <input
                placeholder="e.g. OP-001"
                value={form.operator_id}
                onChange={(e) => setForm((f) => ({ ...f, operator_id: e.target.value }))}
              />
            </label>
            <label className="field">
              Machine ID (optional)
              <input
                placeholder="e.g. MC-001"
                value={form.machine_id}
                onChange={(e) => setForm((f) => ({ ...f, machine_id: e.target.value }))}
              />
            </label>
            <button className="btn btn--primary" type="submit" disabled={loading}>
              {loading ? "Estimating…" : "Estimate"}
            </button>
          </div>
        </form>

        {error && <div className="error-state">Error: {error}</div>}

        {result && (
          <>
            <div className="grid cols-3" style={{ marginBottom: 14 }}>
              <StatCard label="Predicted Duration" value={`${result.predicted_duration_min} min`} />
              <StatCard
                label="Confidence"
                value={<Badge variant={result.confidence}>{result.confidence}</Badge>}
              />
              <StatCard
                label="Historical Benchmark"
                value={result.benchmark_mean_min != null ? `${result.benchmark_mean_min} min` : "n/a"}
              />
            </div>
            <div className="empty-state">
              {result.basis}
              {result.benchmark_sample_size > 0 &&
                ` Benchmark based on ${result.benchmark_sample_size} historical tasks matching this exact combination.`}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
