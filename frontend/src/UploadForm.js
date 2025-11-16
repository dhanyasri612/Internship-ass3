import React, { useState } from "react";
import axios from "axios";

const BACKEND_BASE = "http://localhost:5000"; // <- ensure this matches your running Flask app

/**
 * Props expected by your app:
 *  setResults(resultsArray)
 *  setTotalClauses(number)
 *  setError(string)
 *  setLoading(bool)
 */
const UploadForm = ({ setResults, setTotalClauses, setError, setLoading }) => {
  const [file, setFile] = useState(null);
  const [missingClausesLocal, setMissingClausesLocal] = useState([]);
  const [amendedContractText, setAmendedContractText] = useState("");
  const [notificationsLocal, setNotificationsLocal] = useState([]);

  const onFileChange = (e) => {
    setFile(e.target.files[0]);
    // reset any previous UI
    setMissingClausesLocal([]);
    setAmendedContractText("");
    setNotificationsLocal([]);
    setError("");
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) {
      setError("Please select a PDF or DOCX file to upload.");
      return;
    }

    setLoading(true);
    setResults([]);
    setTotalClauses(0);
    setMissingClausesLocal([]);
    setAmendedContractText("");
    setNotificationsLocal([]);
    setError("");

    try {
      const formData = new FormData();
      formData.append("file", file);

      const token = localStorage.getItem("token");
      const headers = {};
      if (token) headers["Authorization"] = token;

      const res = await axios.post(`${BACKEND_BASE}/upload`, formData, {
        headers,
        timeout: 120000,
      });

      const data = res.data;

      // Update main app state
      if (data.analysis) setResults(data.analysis);
      if (typeof data.total_clauses === "number") setTotalClauses(data.total_clauses);
      if (Array.isArray(data.notifications)) setNotificationsLocal(data.notifications);
      if (data.missing_clauses && Array.isArray(data.missing_clauses))
        setMissingClausesLocal(data.missing_clauses);

      // Handle amended contract download
      const hasAmended = data.amended_contract || data.amended_available || data.modified_contract_download;
      if (hasAmended) {
        const downloadUrl = `${BACKEND_BASE}/download/amended`;
        try {
          window.open(downloadUrl, "_blank");
          setAmendedContractText(
            data.modified_contract_filename
              ? `Modified file created on server: ${data.modified_contract_filename}`
              : `Modified contract ready for download: ${downloadUrl}`
          );
        } catch (e) {
          setAmendedContractText("Modified contract ready for download (open failed in browser)");
        }
      }
    } catch (err) {
      console.error("Upload error:", err);
      let msg = "Upload failed.";
      if (err.response && err.response.data) msg = err.response.data.error || JSON.stringify(err.response.data);
      else if (err.message) msg = err.message;
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="upload-form">
      <form onSubmit={handleSubmit} className="d-flex flex-column gap-3">
        <input type="file" accept=".pdf,.docx" onChange={onFileChange} className="form-control" />

        <button type="submit" className={`btn ${file ? "btn-primary" : "btn-secondary"}`} disabled={!file}>
          {file ? "Upload & Analyze" : "Choose a file first"}
        </button>
      </form>

      {missingClausesLocal && missingClausesLocal.length > 0 && (
        <div className="mt-3 alert alert-warning">
          <h5>Missing Clauses Detected</h5>
          <ul>
            {missingClausesLocal.map((m, idx) => {
              if (m && typeof m === "object") {
                return (
                  <li key={idx}>
                    <strong>{m.label || m[0] || `Clause ${idx + 1}`}:</strong> {m.reason || m[1] || JSON.stringify(m)}
                  </li>
                );
              }
              return <li key={idx}>{String(m)}</li>;
            })}
          </ul>
        </div>
      )}

      {amendedContractText && (
        <div className="mt-3 alert alert-success">
          <h5>Modified Contract</h5>
          <p>{amendedContractText}</p>
          <p>The modified contract should have opened in a new tab for download.</p>
        </div>
      )}

      {notificationsLocal && notificationsLocal.length > 0 && (
        <div className="mt-3">
          <h5>Notifications</h5>
          <ul>
            {notificationsLocal.map((n, i) => (
              <li key={i}>{n.message || JSON.stringify(n)}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

export default UploadForm;
