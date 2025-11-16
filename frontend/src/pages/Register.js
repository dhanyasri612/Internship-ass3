import React, { useState } from "react";
import axios from "axios";

function Register() {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [msg, setMsg] = useState("");

  const handleRegister = async (e) => {
    e.preventDefault();
    try {
      const res = await axios.post("http://localhost:5000/register", {
        username,
        email,
        password,
      });

      setMsg("Registration successful! Please login.");
    } catch (err) {
      console.log(err.response);
      setMsg("Registration failed: " + (err.response?.data?.error || err.message));
    }
  };

  return (
    <div style={{ padding: 20 }}>
      <h2>Create Account</h2>
      <form onSubmit={handleRegister}>

        <input
          type="text"
          placeholder="Full Name"
          onChange={(e) => setUsername(e.target.value)}
          required
        /><br /><br />

        <input
          type="email"
          placeholder="Email"
          onChange={(e) => setEmail(e.target.value)}
          required
        /><br /><br />

        <input
          type="password"
          placeholder="Password"
          onChange={(e) => setPassword(e.target.value)}
          required
        /><br /><br />

        <button type="submit">Register</button>
      </form>

      <p>{msg}</p>
    </div>
  );
}

export default Register;
