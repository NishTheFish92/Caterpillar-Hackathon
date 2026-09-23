import { useEffect, useState } from "react";
import { api } from "../api";

const SKILL_LEVELS = ["All", "Beginner", "Intermediate", "Advanced"];
const FORMAT_LABEL = {
  article: "Article",
  "e-learning-video": "E-Learning Video",
  simulation: "Simulation",
  "instructor-led": "Instructor-Led",
};

export default function Training() {
  const [articles, setArticles] = useState([]);
  const [skillLevel, setSkillLevel] = useState("All");
  const [openId, setOpenId] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const [bookingForm, setBookingForm] = useState({
    operator_id: "OP-001",
    article_id: "ART-010",
    preferred_datetime: "",
    notes: "",
  });
  const [bookingResult, setBookingResult] = useState(null);
  const [bookingError, setBookingError] = useState(null);
  const [booking, setBooking] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api
      .getArticles(skillLevel === "All" ? {} : { skill_level: skillLevel })
      .then(setArticles)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [skillLevel]);

  async function submitBooking(e) {
    e.preventDefault();
    setBooking(true);
    setBookingError(null);
    try {
      const result = await api.bookSession(bookingForm);
      setBookingResult(result);
    } catch (err) {
      setBookingError(err.message);
    } finally {
      setBooking(false);
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1>Training Hub</h1>
        <p>A wiki of short articles, videos, simulations, and instructor sessions — tiered by experience level.</p>
      </div>

      <div className="panel panel--yellow-edge">
        <div className="field-row">
          <label className="field">
            Skill Level
            <select value={skillLevel} onChange={(e) => setSkillLevel(e.target.value)}>
              {SKILL_LEVELS.map((lvl) => (
                <option key={lvl}>{lvl}</option>
              ))}
            </select>
          </label>
        </div>

        {loading && <div className="empty-state">Loading articles…</div>}
        {error && <div className="error-state">Error: {error}</div>}

        {articles.map((a) => (
          <div key={a.article_id} className="article-card">
            <div className="article-card__meta">
              <span className="badge badge--neutral">{a.category}</span>
              <span className="badge badge--neutral">{FORMAT_LABEL[a.format] || a.format}</span>
              <span className="badge badge--neutral">{a.skill_level}</span>
              <span>{a.read_time_min} min</span>
            </div>
            <h3 style={{ margin: "0 0 6px", border: "none", padding: 0 }}>{a.title}</h3>
            <div>{a.summary}</div>
            <button
              className="btn"
              style={{ marginTop: 10 }}
              onClick={() => setOpenId(openId === a.article_id ? null : a.article_id)}
            >
              {openId === a.article_id ? "Hide" : "Read Article"}
            </button>
            {openId === a.article_id && <div className="article-card__content">{a.content}</div>}
          </div>
        ))}
      </div>

      <div className="panel">
        <h3>Book an Instructor-Led Session</h3>
        <form onSubmit={submitBooking}>
          <div className="field-row">
            <label className="field">
              Operator ID
              <input
                value={bookingForm.operator_id}
                onChange={(e) => setBookingForm((f) => ({ ...f, operator_id: e.target.value }))}
              />
            </label>
            <label className="field">
              Article ID
              <input
                value={bookingForm.article_id}
                onChange={(e) => setBookingForm((f) => ({ ...f, article_id: e.target.value }))}
              />
            </label>
            <label className="field">
              Preferred Date/Time
              <input
                type="datetime-local"
                value={bookingForm.preferred_datetime}
                onChange={(e) => setBookingForm((f) => ({ ...f, preferred_datetime: e.target.value }))}
              />
            </label>
            <button className="btn btn--primary" type="submit" disabled={booking}>
              {booking ? "Booking…" : "Book"}
            </button>
          </div>
        </form>
        {bookingError && <div className="error-state">Error: {bookingError}</div>}
        {bookingResult && (
          <div className="article-card">
            <div className="article-card__meta">
              <strong>{bookingResult.booking_id}</strong>
              <span className="badge badge--ok">{bookingResult.status}</span>
            </div>
            <div>
              {bookingResult.operator_id} · {bookingResult.article_id}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
