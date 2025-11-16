import React, { useEffect, useState } from "react";
import axios from "axios";

const Admin = () => {
  const [config, setConfig] = useState({});
  const [form, setForm] = useState({});
  const [message, setMessage] = useState("");

  useEffect(() => {
    fetchConfig();
  }, []);

  const fetchConfig = async () => {
    try {
      const token = localStorage.getItem("token");
      const res = await axios.get("http://localhost:5000/admin/config", {
        headers: { Authorization: token },
      });
      setConfig(res.data.config || {});
      setForm(res.data.config || {});
    } catch (err) {
      setMessage("Failed to fetch config. Are you an admin?");
    }
  };

  const save = async () => {
    try {
      const token = localStorage.getItem("token");
      const res = await axios.post("http://localhost:5000/admin/config", form, {
        headers: { Authorization: token },
      });
      if (res.data.ok) setMessage("Saved successfully");
      fetchConfig();
    } catch (err) {
      setMessage("Save failed: " + (err.response?.data?.error || err.message));
    }
  };

  const testEmail = async () => {
    try {
      const token = localStorage.getItem("token");
      const res = await axios.post(
        "http://localhost:5000/admin/test-email",
        {
          recipient: form.NOTIFICATION_EMAIL,
          subject: "Admin test",
          body: "Test from admin UI",
        },
        { headers: { Authorization: token } }
      );
      if (res.data.ok) setMessage("Test email sent to " + res.data.recipient);
      else setMessage("Test email failed: " + res.data.error);
    } catch (err) {
      setMessage(
        "Test email error: " + (err.response?.data?.error || err.message)
      );
    }
  };

  return (
    <div className="container mt-4">
      <h2>Admin Configuration</h2>
      {message && <div className="alert alert-info">{message}</div>}

      <div className="mb-3">
        <label className="form-label">SMTP Host</label>
        <input
          className="form-control"
          value={form.SMTP_HOST || ""}
          onChange={(e) => setForm({ ...form, SMTP_HOST: e.target.value })}
        />
      </div>
      <div className="mb-3">
        <label className="form-label">SMTP Port</label>
        <input
          className="form-control"
          value={form.SMTP_PORT || ""}
          onChange={(e) => setForm({ ...form, SMTP_PORT: e.target.value })}
        />
      </div>
      <div className="mb-3">
        <label className="form-label">Use SSL (1 or 0)</label>
        <input
          className="form-control"
          value={form.SMTP_USE_SSL || ""}
          onChange={(e) => setForm({ ...form, SMTP_USE_SSL: e.target.value })}
        />
      </div>
      <div className="mb-3">
        <label className="form-label">Email Sender</label>
        <input
          className="form-control"
          value={form.EMAIL_SENDER || ""}
          onChange={(e) => setForm({ ...form, EMAIL_SENDER: e.target.value })}
        />
      </div>
      <div className="mb-3">
        <label className="form-label">Email SMTP Password</label>
        <input
          type="password"
          className="form-control"
          value={form.EMAIL_SMTP_PASS || ""}
          onChange={(e) =>
            setForm({ ...form, EMAIL_SMTP_PASS: e.target.value })
          }
        />
      </div>
      <div className="mb-3">
        <label className="form-label">Notification Recipient (default)</label>
        <input
          className="form-control"
          value={form.NOTIFICATION_EMAIL || ""}
          onChange={(e) =>
            setForm({ ...form, NOTIFICATION_EMAIL: e.target.value })
          }
        />
      </div>
      <div className="mb-3">
        <label className="form-label">Admin Emails (comma-separated)</label>
        <input
          className="form-control"
          value={form.admin_emails || ""}
          onChange={(e) => setForm({ ...form, admin_emails: e.target.value })}
        />
      </div>

      <div className="d-flex gap-2">
        <button className="btn btn-primary" onClick={save}>
          Save Config
        </button>
        <button className="btn btn-secondary" onClick={testEmail}>
          Send Test Email
        </button>
      </div>
    </div>
  );
};

export default Admin;
