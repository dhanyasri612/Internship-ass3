import React, { useState, useEffect } from "react";
import {
  BrowserRouter as Router,
  Routes,
  Route,
  NavLink,
  useNavigate,
} from "react-router-dom";
import UploadForm from "./UploadForm";
import ClauseDisplay from "./ClauseDisplay";

import Login from "./pages/Login";
import Register from "./pages/Register";

import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";

// ---------------------------------------------------------
// COLORS FOR CHARTS
// ---------------------------------------------------------
const COLORS = [
  "#0088FE",
  "#00C49F",
  "#FFBB28",
  "#FF8042",
  "#A28CF0",
  "#FF6699",
  "#33CC99",
  "#9966FF",
  "#FF4444",
  "#FFCC00",
  "#66CCFF",
  "#99FF99",
  "#FF9966",
  "#CC99FF",
  "#66FFCC",
  "#FF66B2",
];

// ---------------------------------------------------------
// LOGIN STATE HOOK
// ---------------------------------------------------------
const useAuth = () => {
  const [loggedIn, setLoggedIn] = useState(
    () => !!localStorage.getItem("token")
  );
  useEffect(() => {
    const interval = setInterval(() => {
      setLoggedIn(!!localStorage.getItem("token"));
    }, 500);
    return () => clearInterval(interval);
  }, []);
  return loggedIn;
};

// ---------------------------------------------------------
// NAVBAR
// ---------------------------------------------------------
const Navbar = () => {
  const loggedIn = useAuth();

  return (
    <nav className="navbar navbar-expand-lg navbar-dark bg-primary sticky-top shadow">
      <div className="container">
        <NavLink className="navbar-brand fw-bold" to="/">
          📜 Legal Compliance Analyzer
        </NavLink>

        <button
          className="navbar-toggler"
          type="button"
          data-bs-toggle="collapse"
          data-bs-target="#navbarNav"
        >
          <span className="navbar-toggler-icon"></span>
        </button>

        <div className="collapse navbar-collapse" id="navbarNav">
          <ul className="navbar-nav ms-auto">
            {loggedIn ? (
              <>
                <li className="nav-item">
                  <NavLink className="nav-link" to="/">
                    Home
                  </NavLink>
                </li>
                <li className="nav-item">
                  <NavLink className="nav-link" to="/phase1">
                    Phase 1
                  </NavLink>
                </li>
                <li className="nav-item">
                  <NavLink className="nav-link" to="/phase2">
                    Phase 2
                  </NavLink>
                </li>
                <li className="nav-item">
                  <NavLink className="nav-link" to="/dashboard">
                    Dashboard
                  </NavLink>
                </li>
              </>
            ) : (
              <>
                <li className="nav-item">
                  <NavLink className="nav-link" to="/login">
                    Login
                  </NavLink>
                </li>
                <li className="nav-item">
                  <NavLink className="nav-link" to="/register">
                    Register
                  </NavLink>
                </li>
              </>
            )}
          </ul>
        </div>
      </div>
    </nav>
  );
};

// ---------------------------------------------------------
// PROTECTED ROUTE
// ---------------------------------------------------------
const ProtectedRoute = ({ children }) => {
  const navigate = useNavigate();
  const loggedIn = !!localStorage.getItem("token");

  useEffect(() => {
    if (!loggedIn) navigate("/login");
  }, [loggedIn]);

  return loggedIn ? children : null;
};

// ---------------------------------------------------------
// DASHBOARD
// ---------------------------------------------------------
const Dashboard = () => {
  const navigate = useNavigate();
  let email = "Unknown";
  const token = localStorage.getItem("token");

  if (token) {
    try {
      email = JSON.parse(atob(token.split(".")[1])).email;
    } catch {}
  }

  const logout = () => {
    localStorage.removeItem("token");
    navigate("/login");
  };

  return (
    <div className="text-center mt-4">
      <h2 className="fw-bold text-primary">User Dashboard</h2>
      <p className="mt-3">
        Logged in as: <b>{email}</b>
      </p>

      <button
        className="btn btn-success mt-3 me-3"
        onClick={() => navigate("/")}
      >
        Upload Contract
      </button>
      <button className="btn btn-danger mt-3" onClick={logout}>
        Logout
      </button>
    </div>
  );
};

// ---------------------------------------------------------
// PIE DATA PARSER
// ---------------------------------------------------------
const getPieData = (results, keyPath) => {
  const counts = results.reduce((acc, clause) => {
    const key = keyPath
      .split(".")
      .reduce((o, k) => (o && o[k] ? o[k] : "Unknown"), clause);
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
  return Object.entries(counts).map(([name, value]) => ({ name, value }));
};

// ---------------------------------------------------------
// LEGEND COMPONENT
// ---------------------------------------------------------
const LegendContainer = ({ data }) => (
  <div
    style={{
      maxHeight: 300,
      overflowY: "auto",
      border: "1px solid #ccc",
      borderRadius: 6,
      padding: 10,
      minWidth: 180,
      backgroundColor: "#f9f9f9",
    }}
  >
    {data.map((entry, index) => (
      <div
        key={index}
        style={{ display: "flex", alignItems: "center", marginBottom: 6 }}
      >
        <div
          style={{
            width: 14,
            height: 14,
            backgroundColor: COLORS[index % COLORS.length],
            marginRight: 8,
            borderRadius: 3,
          }}
        />
        <span style={{ fontSize: 13 }}>
          {entry.name} ({entry.value})
        </span>
      </div>
    ))}
  </div>
);

// ---------------------------------------------------------
// MAIN APP
// ---------------------------------------------------------
const App = () => {
  const [results, setResults] = useState([]);
  const [totalClauses, setTotalClauses] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notifications, setNotifications] = useState([]);

  // Poll backend for notifications (simple SSE alternative)
  useEffect(() => {
    let interval = null;
    const token = localStorage.getItem("token");
    if (token) {
      const fetchLatest = () => {
        fetch("http://localhost:5000/notifications/latest")
          .then((r) => r.json())
          .then((data) => {
            if (data && Array.isArray(data.notifications)) {
              setNotifications(data.notifications);
            }
          })
          .catch(() => {});
      };

      fetchLatest();
      interval = setInterval(fetchLatest, 3000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, []);

  return (
    <Router>
      <Navbar />
      <main className="py-5 bg-light min-vh-100">
        <div className="container">
          {/* Notifications area */}
          {notifications && notifications.length > 0 && (
            <div className="mb-3">
              {notifications.map((n, idx) => (
                <div
                  key={n.timestamp || idx}
                  className="alert alert-warning alert-dismissible fade show"
                  role="alert"
                >
                  <strong>Notification:</strong>&nbsp;{n.message}
                  <button
                    type="button"
                    className="btn-close"
                    aria-label="Close"
                    onClick={async () => {
                      // Optimistically remove locally
                      setNotifications((prev) =>
                        prev.filter((_, i) => i !== idx)
                      );
                      // Attempt to dismiss on server so it doesn't reappear
                      try {
                        const token = localStorage.getItem("token");
                        await fetch(
                          "http://localhost:5000/notifications/dismiss",
                          {
                            method: "POST",
                            headers: {
                              "Content-Type": "application/json",
                              ...(token ? { Authorization: token } : {}),
                            },
                            body: JSON.stringify({ timestamp: n.timestamp }),
                          }
                        );
                      } catch (e) {
                        // ignore errors — local removal still gives good UX
                        console.error(
                          "Failed to dismiss notification on server",
                          e
                        );
                      }
                    }}
                  ></button>
                </div>
              ))}
            </div>
          )}
          <Routes>
            {/* HOME */}
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <div className="text-center">
                    <h2 className="fw-bold text-primary mb-3">
                      Upload Your Contract
                    </h2>

                    <div
                      className="card shadow-sm mx-auto"
                      style={{ maxWidth: "600px" }}
                    >
                      <div className="card-body">
                        <UploadForm
                          setResults={setResults}
                          setTotalClauses={setTotalClauses}
                          setError={setError}
                          setLoading={setLoading}
                        />
                      </div>
                    </div>

                    {error && (
                      <div className="alert alert-danger mt-4 w-75 mx-auto">
                        {error}
                      </div>
                    )}
                    {loading && (
                      <div className="text-muted mt-4">
                        🔍 Analyzing document...
                      </div>
                    )}
                    {!loading && results.length > 0 && (
                      <div className="alert alert-success mt-4 w-75 mx-auto fw-semibold">
                        ✅ Analysis Complete: {totalClauses} Clauses Found
                      </div>
                    )}
                  </div>
                </ProtectedRoute>
              }
            />

            {/* PHASE 1 & PHASE 2 */}
            {["phase1", "phase2"].map((phase) => {
              const isPhase1 = phase === "phase1";
              const pieData = getPieData(
                results,
                isPhase1 ? "phase1.predicted_clause_type" : "phase3.risk_level"
              );

              return (
                <Route
                  key={phase}
                  path={`/${phase}`}
                  element={
                    <ProtectedRoute>
                      <div className="mt-4">
                        <h2 className="text-center text-primary fw-bold mb-4">
                          {isPhase1
                            ? "Phase 1 - Clause Type Classification"
                            : "Phase 2 - Risk Analysis"}
                        </h2>

                        {results.length > 0 ? (
                          <>
                            {/* Chart + Legend side-by-side */}
                            <div className="d-flex justify-content-center mb-5 flex-wrap gap-4">
                              <div style={{ width: 300, height: 300 }}>
                                <ResponsiveContainer width="100%" height="100%">
                                  <PieChart>
                                    <Pie
                                      data={pieData}
                                      dataKey="value"
                                      nameKey="name"
                                      cx="50%"
                                      cy="50%"
                                      outerRadius={100}
                                      label
                                    >
                                      {pieData.map((entry, index) => (
                                        <Cell
                                          key={index}
                                          fill={COLORS[index % COLORS.length]}
                                        />
                                      ))}
                                    </Pie>
                                    <Tooltip />
                                  </PieChart>
                                </ResponsiveContainer>
                              </div>
                              <LegendContainer data={pieData} />
                            </div>

                            {/* Clause Cards */}
                            <div className="row g-4">
                              {results.map((clause, i) => (
                                <div key={i} className="col-md-6">
                                  <ClauseDisplay
                                    data={clause}
                                    index={i}
                                    phase={phase}
                                  />
                                </div>
                              ))}
                            </div>
                          </>
                        ) : (
                          <p className="text-center text-muted">
                            Upload a contract first.
                          </p>
                        )}
                      </div>
                    </ProtectedRoute>
                  }
                />
              );
            })}

            {/* LOGIN / REGISTER */}
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />

            {/* DASHBOARD */}
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute>
                  <Dashboard />
                </ProtectedRoute>
              }
            />

            {/* Admin UI removed per request */}
          </Routes>
        </div>
      </main>
    </Router>
  );
};

export default App;
