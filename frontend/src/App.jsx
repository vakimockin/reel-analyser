import React, { useEffect, useState } from "react";

const API_BASE = (
  import.meta.env.VITE_API_BASE_URL ||
  (window.location.port === "3000"
    ? `${window.location.protocol}//${window.location.hostname}:8000`
    : "")
).replace(/\/$/, "");

function normalizeUsernames(input) {
  return input
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean)
    .map((value) => (value.startsWith("@") ? value.slice(1) : value));
}

export default function App() {
  const [usernamesInput, setUsernamesInput] = useState("");
  const [limit, setLimit] = useState(15);
  const [isLoading, setIsLoading] = useState(false);
  const [status, setStatus] = useState("");
  const [statusError, setStatusError] = useState(false);
  const [result, setResult] = useState(null);
  const [historyRuns, setHistoryRuns] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  const loadHistory = async () => {
    setHistoryLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/v1/analyses?limit=20&offset=0`);
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Failed to load run history");
      }
      setHistoryRuns(Array.isArray(data) ? data : []);
    } catch (error) {
      setStatusError(true);
      setStatus(error.message || "Error");
    } finally {
      setHistoryLoading(false);
    }
  };

  const loadRunDetails = async (runId) => {
    setIsLoading(true);
    setStatusError(false);
    setStatus(`Loading run #${runId}...`);
    try {
      const response = await fetch(`${API_BASE}/api/v1/analyses/${runId}`);
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Failed to load run details");
      }
      setResult(data);
      setStatus("Done");
    } catch (error) {
      setStatusError(true);
      setStatus(error.message || "Error");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadHistory();
  }, []);

  const onSubmit = async (event) => {
    event.preventDefault();
    setIsLoading(true);
    setStatusError(false);
    setStatus("Running analysis...");

    try {
      const payload = {
        usernames: normalizeUsernames(usernamesInput),
        limit: Number(limit),
      };

      const response = await fetch(`${API_BASE}/api/v1/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Analyze request failed");
      }

      setResult(data);
      await loadHistory();
      setStatus("Done");
    } catch (error) {
      setStatusError(true);
      setStatus(error.message || "Error");
    } finally {
      setIsLoading(false);
    }
  };

  const rawCount =
    result && typeof result.raw_items_count === "number"
      ? result.raw_items_count
      : "not available for this endpoint";

  return (
    <main className="container">
      <h1>Instagram Reels Analyzer</h1>

      <section className="card">
        <h2>Run Analysis</h2>
        <form onSubmit={onSubmit}>
          <label>
            Usernames (comma-separated)
            <input
              value={usernamesInput}
              onChange={(event) => setUsernamesInput(event.target.value)}
              placeholder="@user1, @user2"
              required
            />
          </label>
          <label>
            Reels limit per account
            <input
              type="number"
              min="1"
              max="50"
              value={limit}
              onChange={(event) => setLimit(event.target.value)}
              required
            />
          </label>
          <button type="submit" disabled={isLoading}>
            {isLoading ? "Running..." : "Analyze"}
          </button>
        </form>
        <p className="status" style={{ color: statusError ? "#fca5a5" : undefined }}>
          {status}
        </p>
      </section>

      <section className="card">
        <div className="historyHeader">
          <h2>Run History</h2>
          <button type="button" onClick={loadHistory} disabled={historyLoading}>
            {historyLoading ? "Refreshing..." : "Refresh"}
          </button>
        </div>
        {historyRuns.length === 0 ? (
          <p className="muted">No saved runs yet.</p>
        ) : (
          <div className="stack">
            {historyRuns.map((run) => (
              <article className="item" key={run.run_id}>
                <h3>Run #{run.run_id}</h3>
                <p><strong>Accounts:</strong> {(run.usernames || []).map((u) => `@${u}`).join(", ")}</p>
                <p><strong>Fetched reels:</strong> {run.total_reels_fetched}</p>
                <p><strong>Viral reels:</strong> {run.viral_reels_count}</p>
                <p className="muted">
                  {run.created_at ? new Date(run.created_at).toLocaleString() : "Unknown date"}
                </p>
                <button type="button" onClick={() => loadRunDetails(run.run_id)} disabled={isLoading}>
                  Open run
                </button>
              </article>
            ))}
          </div>
        )}
      </section>

      {result && (
        <section className="card">
          <h2>Result</h2>
          <p><strong>Run ID:</strong> {result.run_id}</p>
          <p><strong>Parsed reels (before viral filter):</strong> {rawCount}</p>
          <p><strong>Viral reels:</strong> {result.viral_reels_count}</p>
          <p className="muted">{result.niche_summary || "Niche summary is disabled or not generated."}</p>

          {Array.isArray(result.raw_preview) && result.raw_preview.length > 0 && (
            <p>
              <strong>Raw preview:</strong>{" "}
              {result.raw_preview
                .map((item) => `@${item.username} (${Number(item.views).toLocaleString()} views)`)
                .join(", ")}
            </p>
          )}

          <div className="stack">
            {(result.reel_analyses || []).map((item) => (
              <article className="item" key={item.reel_id}>
                <h3>
                  @{item.reel.username} · {Number(item.reel.views).toLocaleString()} views
                </h3>
                <p><strong>Topic:</strong> {item.analysis.topic}</p>
                <p><strong>Hook:</strong> {item.analysis.hook}</p>
                <p><strong>Why it worked:</strong> {item.analysis.why_it_worked}</p>
                <p><strong>Creator script:</strong> {item.analysis.creator_script}</p>
              </article>
            ))}
          </div>
        </section>
      )}
    </main>
  );
}
