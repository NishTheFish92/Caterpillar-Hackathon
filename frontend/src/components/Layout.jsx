import { NavLink, Outlet } from "react-router-dom";
import { useEffect, useState } from "react";
import { api } from "../api";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/safety", label: "Safety" },
  { to: "/training", label: "Training" },
  { to: "/behavior", label: "Behavior" },
  { to: "/estimation", label: "Task Time" },
];

export default function Layout() {
  const [status, setStatus] = useState("connecting");

  useEffect(() => {
    let cancelled = false;
    api
      .health()
      .then(() => !cancelled && setStatus("ok"))
      .catch(() => !cancelled && setStatus("err"));
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="app-shell">
      <header className="site-header">
        <div className="site-header__inner">
          <div className="brand">
            <div className="brand__mark">
              <span>CAT</span>
            </div>
            <div className="brand__title">
              Smart Operator Assistant
              <small>Fleet safety, training &amp; performance</small>
            </div>
          </div>
          <div className={`conn-status ${status}`}>
            <span className="conn-status__dot" />
            <span className="conn-label">
              {status === "ok" && "API Connected"}
              {status === "err" && "API Unreachable"}
              {status === "connecting" && "Connecting…"}
            </span>
          </div>
        </div>
      </header>
      <div className="hazard-stripe" />
      <nav className="site-nav">
        <div className="site-nav__inner">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => (isActive ? "active" : "")}
            >
              {item.label}
            </NavLink>
          ))}
        </div>
      </nav>
      <main className="main-content">
        <Outlet />
      </main>
      <footer className="site-footer">
        <div className="hazard-stripe" />
      </footer>
    </div>
  );
}
