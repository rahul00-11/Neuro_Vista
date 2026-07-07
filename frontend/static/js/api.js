// NeuroVista AI — API Client
// Groq key NEVER here — stays on server
// Auto-detects backend URL (same origin on Render, localhost in dev)

const isLocal = ["localhost","127.0.0.1"].includes(location.hostname);
export const BASE = isLocal
  ? "http://localhost:8000/api"
  : `${location.origin}/api`;     // same domain on Render single deploy

async function req(path, opts = {}) {
  try {
    const res = await fetch(`${BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...opts,
    });
    if (!res.ok) {
      let msg = `HTTP ${res.status}`;
      try { const b = await res.json(); msg = b.detail || msg; } catch {}
      throw new Error(msg);
    }
    return res.json();
  } catch (e) {
    if (e.message?.includes("fetch")) throw new Error("Cannot reach backend server.");
    throw e;
  }
}

export const API = {
  health:          ()    => req("/health"),
  register:        data  => req("/patients/register",   { method:"POST", body:JSON.stringify(data) }),
  chat:            data  => req("/patients/chat",        { method:"POST", body:JSON.stringify(data) }),
  advanceModule:   data  => req("/patients/advance-module", { method:"POST", body:JSON.stringify(data) }),
  validateAge:     age   => req("/patients/validate-age",{ method:"POST", body:JSON.stringify({age_years:age}) }),
  detectLanguage: async  text => {
    try { return (await req("/patients/detect-language",{ method:"POST", body:JSON.stringify({text}) })).language; }
    catch { return "en"; }
  },
  uploadFile: (pid, file, type="general") => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("file_type", type);
    return fetch(`${BASE}/files/upload/${pid}`, { method:"POST", body:fd })
      .then(async r => { if (!r.ok) throw new Error(await r.text()); return r.json(); });
  },
  registrationReportUrl: pid => `${BASE}/patients/${pid}/report/registration`,
  appointmentReportUrl:  pid => `${BASE}/patients/${pid}/report/appointment`,
};
