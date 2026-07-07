import { API }   from "./api.js";
import { Voice } from "./voice.js";

const voice = new Voice();

// ── State ──────────────────────────────────────────────────────────────────
const S = {
  pid:      null,
  lang:     "en",
  voiceOn:  false,
  module:   0,        // 0=welcome, 1-6=agents
  regStep:  0,
  reg:      {},
};

// Layer 1 Agent names for progress bar
const MODULES = [
  { id:1, icon:"📋", label:"Register"  },
  { id:2, icon:"✅", label:"Consent"   },
  { id:3, icon:"📖", label:"History"   },
  { id:4, icon:"🔍", label:"Symptoms"  },
  { id:5, icon:"📅", label:"Appt."     },
  { id:6, icon:"📚", label:"Education" },
];

const $ = id => document.getElementById(id);

// ── Registration steps ────────────────────────────────────────────────────
// Order: Gender → Name → Age (years only) → DOB (calendar) → Guardian → Phone → Address
const REG = [
  { f:"child_sex", type:"choice",
    p:{ en:"Is the child Male or Female?", hi:"बच्चा Male है या Female?", hinglish:"Bachcha Male hai ya Female?" },
    options: [
      { value:"Male",   label:{ en:"👦 Male",   hi:"👦 Male",   hinglish:"👦 Male" } },
      { value:"Female", label:{ en:"👧 Female", hi:"👧 Female", hinglish:"👧 Female" } },
    ]
  },
  { f:"child_name", type:"text",
    p:{ en:"What is the child's full name?", hi:"बच्चे का पूरा नाम?", hinglish:"Bachche ka poora naam?" } },
  { f:"child_age_years", type:"text",
    p:{ en:"How old is the child? (0–18 years only)", hi:"बच्चे की उम्र? (0–18 साल)", hinglish:"Bachche ki umar? (0–18 saal)" },
    validate: async v => {
      const n = parseInt(v);
      if (isNaN(n)) return "Please enter age as a number.";
      const r = await API.validateAge(n).catch(()=>({valid:false,message:"Cannot validate age."}));
      return r.valid ? null : r.message;
    }
  },
  { f:"child_dob", type:"date",
    p:{ en:"Date of birth? (Pick from the calendar)", hi:"जन्मतिथि? (कैलेंडर से चुनें)", hinglish:"Date of birth? (Calendar se chuno)" } },
  { f:"guardian_name", type:"text",
    p:{ en:"Your name and your relation to the child? (e.g. Priya — Mother)", hi:"आपका नाम और संबंध?", hinglish:"Aapka naam aur rishta?" } },
  { f:"phone", type:"text",
    p:{ en:"Your mobile number?", hi:"मोबाइल नंबर?", hinglish:"Mobile number?" },
    validate: async v => {
      const digits = v.replace(/\D/g,"");
      if (digits.length < 10) return "Please enter a valid 10-digit mobile number.";
      return null;
    }
  },
  { f:"address", type:"text",
    p:{ en:"Address? (type 'skip' to skip)", hi:"पता? (skip लिख सकते हैं)", hinglish:"Address? ('skip' bol sakte ho)" } },
];

// ── DOM helpers ──────────────────────────────────────────────────────────────
function addMsg(text, role="assistant") {
  const d = document.createElement("div");
  d.className = `message ${role}`;
  const b = document.createElement("div");
  b.className = "bubble"; b.textContent = text;
  const t = document.createElement("span");
  t.className = "msg-time";
  t.textContent = new Date().toLocaleTimeString([],{hour:"2-digit",minute:"2-digit"});
  d.appendChild(b); d.appendChild(t);
  $("chat-box").appendChild(d);
  $("chat-box").scrollTop = $("chat-box").scrollHeight;
  if (role==="assistant" && S.voiceOn) voice.speak(text, S.lang);
}

function showTyping() {
  const d=document.createElement("div"); d.className="message assistant"; d.id="typing";
  d.innerHTML=`<div class="bubble typing-dots"><span></span><span></span><span></span></div>`;
  $("chat-box").appendChild(d); $("chat-box").scrollTop=$("chat-box").scrollHeight;
}
function hideTyping() { $("typing")?.remove(); }

// ── Progress bar ─────────────────────────────────────────────────────────────
function buildModuleBar() {
  const bar = $("module-bar"); bar.innerHTML = "";
  MODULES.forEach((m, i) => {
    const step = document.createElement("div");
    step.className = "mod-step"; step.id = `mod-${m.id}`;
    step.innerHTML = `<div class="mod-dot">${m.icon}</div><div class="mod-label">${m.label}</div>`;
    bar.appendChild(step);
    if (i < MODULES.length-1) {
      const conn = document.createElement("div");
      conn.className = "mod-connector"; conn.id = `conn-${m.id}`;
      bar.appendChild(conn);
    }
  });
}

function updateModuleBar() {
  MODULES.forEach(m => {
    const el = $(`mod-${m.id}`);
    if (!el) return;
    el.classList.toggle("done",   m.id < S.module);
    el.classList.toggle("active", m.id === S.module);
    const conn = $(`conn-${m.id}`);
    if (conn) conn.classList.toggle("done", m.id < S.module);
  });
  // Scroll active into view
  $(`mod-${S.module}`)?.scrollIntoView({behavior:"smooth", block:"nearest", inline:"center"});
}

// ── Welcome screen ──────────────────────────────────────────────────────────
function showWelcome() {
  const ws = $("welcome-screen"); if (!ws) return;
  ws.style.display = "flex";

  // AI speaks welcome after a short delay
  setTimeout(() => {
    const msg = "Welcome to Little Angels Superspecialty Eye Clinic! I am NeuroVista AI, your intelligent assistant. Please select your preferred language to begin.";
    if (voice.ok) voice.speak(msg, "en");
  }, 800);
}

function hideWelcome(lang) {
  S.lang = lang;
  const ws = $("welcome-screen");
  if (ws) { ws.style.opacity="0"; ws.style.transition="opacity .4s"; setTimeout(()=>ws.remove(), 400); }
  S.module = 1;
  updateModuleBar();
  setTimeout(() => startRegistration(), 500);
}

// ── Registration flow ────────────────────────────────────────────────────────
function startRegistration() {
  S.module=1; S.regStep=0; S.reg={};
  updateModuleBar();
  const greet = {
    en: "Hello! I'm NeuroVista AI. This clinic is for children aged 0–18 years. I'm speaking with the parent or guardian. Let's begin registration.",
    hi: "नमस्ते! मैं NeuroVista AI हूँ। यह क्लिनिक 0–18 वर्ष के बच्चों के लिए है। मैं माता-पिता से बात कर रहा हूँ। रजिस्ट्रेशन शुरू करते हैं।",
    hinglish: "Namaste! Main NeuroVista AI hoon. Yeh clinic 0–18 saal ke bachcho ke liye hai. Main parent/guardian se baat kar raha hoon. Registration shuru karte hain."
  };
  addMsg(greet[S.lang]);
  setTimeout(() => askReg(), 600);
}

function askReg() {
  if (S.regStep >= REG.length) { submitReg(); return; }
  const step = REG[S.regStep];
  addMsg(step.p[S.lang] || step.p.en);
  if (step.type === "choice")      renderChoiceWidget(step);
  else if (step.type === "date")   renderDateWidget(step);
  else                              showInputBar();
}

function hideInputBar() { const el = $("user-input")?.closest(".input-wrap"); if (el) el.style.display = "none"; }
function showInputBar() { const el = $("user-input")?.closest(".input-wrap"); if (el) el.style.display = ""; }
function removeRegWidget() { $("reg-widget")?.remove(); }

function renderChoiceWidget(step) {
  hideInputBar();
  const wrap = document.createElement("div");
  wrap.className = "message assistant"; wrap.id = "reg-widget";
  const box = document.createElement("div");
  box.className = "bubble reg-widget-box";
  box.style.display = "flex"; box.style.gap = "10px";
  step.options.forEach(opt => {
    const btn = document.createElement("button");
    btn.textContent = opt.label[S.lang] || opt.label.en;
    btn.style.cssText = "padding:10px 18px;border-radius:10px;border:1px solid var(--border,#333);background:var(--accent,#3b82f6);color:#fff;cursor:pointer;font-size:14px;";
    btn.onclick = () => { removeRegWidget(); handleRegAnswer(opt.label[S.lang] || opt.label.en, opt.value); };
    box.appendChild(btn);
  });
  wrap.appendChild(box);
  $("chat-box").appendChild(wrap);
  $("chat-box").scrollTop = $("chat-box").scrollHeight;
}

function renderDateWidget(step) {
  hideInputBar();
  const wrap = document.createElement("div");
  wrap.className = "message assistant"; wrap.id = "reg-widget";
  const box = document.createElement("div");
  box.className = "bubble reg-widget-box";
  box.style.cssText = "display:flex;gap:10px;align-items:center;flex-wrap:wrap;";
  const input = document.createElement("input");
  input.type = "date";
  input.max = new Date().toISOString().split("T")[0]; // no future DOB
  input.style.cssText = "padding:8px;border-radius:8px;border:1px solid var(--border,#333);background:#fff;color:#111;font-size:14px;";
  const btn = document.createElement("button");
  btn.textContent = { en:"Confirm ✅", hi:"पुष्टि करें ✅", hinglish:"Confirm karo ✅" }[S.lang] || "Confirm ✅";
  btn.style.cssText = "padding:8px 16px;border-radius:8px;border:none;background:var(--accent,#3b82f6);color:#fff;cursor:pointer;font-size:14px;";
  btn.onclick = () => {
    if (!input.value) return;
    const [y,m,d] = input.value.split("-");
    removeRegWidget();
    handleRegAnswer(`${d}/${m}/${y}`, input.value); // show DD/MM/YYYY, store ISO
  };
  box.appendChild(input); box.appendChild(btn);
  wrap.appendChild(box);
  $("chat-box").appendChild(wrap);
  $("chat-box").scrollTop = $("chat-box").scrollHeight;
}

async function processRegAnswer(step, storedValue, displayText) {
  if (step.validate) {
    const err = await step.validate(displayText);
    if (err) {
      $("age-warning").textContent = err;
      $("age-warning").style.display = "block";
      addMsg(`⚠️ ${err}`);
      addMsg(step.p[S.lang] || step.p.en);
      if (step.type === "choice") renderChoiceWidget(step);
      else if (step.type === "date") renderDateWidget(step);
      return false;
    }
    $("age-warning").style.display = "none";
  }
  S.reg[step.f] = storedValue;
  S.regStep++;
  setTimeout(() => askReg(), 250);
  return true;
}

async function handleRegAnswer(displayText, storedValue) {
  addMsg(displayText, "user");
  const step = REG[S.regStep];
  await processRegAnswer(step, storedValue, displayText);
}

async function submitReg() {
  showInputBar();
  addMsg("⏳ Saving details..."); showTyping();
  try {
    const r = await API.register({
      child_name:        S.reg.child_name?.trim(),
      child_age_years:   parseInt(S.reg.child_age_years)||0,
      child_dob:         S.reg.child_dob,
      child_sex:         S.reg.child_sex,
      guardian_name:     S.reg.guardian_name?.trim(),
      phone:             S.reg.phone?.trim(),
      address:           (S.reg.address||"").toLowerCase()==="skip" ? null : S.reg.address,
      language:          S.lang,
    });
    S.pid = r.patient_id;
    hideTyping();
    addMsg(`✅ Registration complete! Patient ID: #${r.patient_id}`);
    addMsg(r.greeting);
    addDownloadLink(API.registrationReportUrl(S.pid), { en:"📄 Download Registration PDF", hi:"📄 Registration PDF डाउनलोड करें", hinglish:"📄 Registration PDF download karo" });
    updatePatientCard(); updateUploadPanel();
    // Move to Module 2
    await goToModule(2);
  } catch(e) {
    hideTyping(); addMsg(`⚠️ Registration failed: ${e.message}`);
  }
}

function addDownloadLink(url, label) {
  const wrap = document.createElement("div");
  wrap.className = "message assistant";
  const b = document.createElement("div");
  b.className = "bubble";
  const a = document.createElement("a");
  a.href = url; a.target = "_blank"; a.rel = "noopener";
  a.textContent = label[S.lang] || label.en;
  a.style.cssText = "color:#fff;background:var(--accent,#3b82f6);padding:8px 14px;border-radius:8px;text-decoration:none;display:inline-block;";
  b.appendChild(a);
  wrap.appendChild(b);
  $("chat-box").appendChild(wrap);
  $("chat-box").scrollTop = $("chat-box").scrollHeight;
}

// ── Module navigation ─────────────────────────────────────────────────────────
async function goToModule(mod) {
  S.module = mod; updateModuleBar();
  showTyping();
  try {
    const r = await API.advanceModule({ patient_id: S.pid, module: mod });
    hideTyping();
    addMsg(r.greeting || `Module ${mod} started.`);
  } catch(e) {
    hideTyping(); addMsg(`Starting Module ${mod}...`);
  }
}

// ── Chat send ─────────────────────────────────────────────────────────────────
async function send(text) {
  const msg = (text || $("user-input").value).trim();
  if (!msg) return;
  $("user-input").value = "";
  addMsg(msg, "user");

  if (S.module === 0) return; // welcome — shouldn't happen

  // Registration steps (text-type only — choice/date types are handled by
  // their own widgets via handleRegAnswer, input bar is hidden for those)
  if (S.module === 1 && S.regStep < REG.length) {
    const step = REG[S.regStep];
    await processRegAnswer(step, msg, msg);
    return;
  }

  // Modules 2–6: forward to AI agent
  showTyping();
  try {
    const r = await API.chat({ patient_id:S.pid, message:msg, language:S.lang, module:S.module });
    hideTyping();
    addMsg(r.reply);

    // Reliable auto-advance: backend tells us explicitly when a module is
    // done (it drives the question sequence itself), instead of guessing
    // from the wording of the AI's reply.
    if (r.completed && S.module === 5) {
      addDownloadLink(API.appointmentReportUrl(S.pid), { en:"📄 Download Appointment PDF", hi:"📄 Appointment PDF डाउनलोड करें", hinglish:"📄 Appointment PDF download karo" });
      setTimeout(() => goToModule(6), 1800);
    } else if (r.completed && S.module < 6) {
      setTimeout(() => goToModule(S.module + 1), 1500);
    } else if (r.completed && S.module === 6) {
      addMsg("🙏 Your visit is fully registered. See you at the clinic!");
    }
  } catch(e) {
    hideTyping(); addMsg(`⚠️ ${e.message}`);
  }
}

$("send-btn").addEventListener("click", () => send());
$("user-input").addEventListener("keydown", e => {
  if (e.key==="Enter" && !e.shiftKey) { e.preventDefault(); send(); }
});

// Auto-resize textarea
$("user-input").addEventListener("input", function() {
  this.style.height = "auto";
  this.style.height = Math.min(this.scrollHeight, 100) + "px";
});

// ── Voice ─────────────────────────────────────────────────────────────────────
const vBtn = $("voice-btn");
if (!voice.ok) vBtn.classList.add("unsupported");

vBtn.addEventListener("click", async () => {
  if (!voice.ok) { addMsg("Voice not supported in this browser. Please use Chrome."); return; }
  if (voice.listening) { voice.stop(); vBtn.classList.remove("recording"); $("mic-status").textContent=""; return; }
  vBtn.classList.add("recording"); $("mic-status").textContent="🎙️ Listening...";
  const t = await voice.listen(S.lang);
  vBtn.classList.remove("recording"); $("mic-status").textContent="";
  if (t) { $("user-input").value=t; send(t); }
});

$("voice-toggle")?.addEventListener("change", e => { S.voiceOn = e.target.checked; });

// ── Info sheet (mobile) ───────────────────────────────────────────────────────
$("info-fab")?.addEventListener("click", () => {
  $("info-sheet").classList.add("open");
  $("sheet-overlay").classList.add("open");
});
$("sheet-overlay")?.addEventListener("click", () => {
  $("info-sheet").classList.remove("open");
  $("sheet-overlay").classList.remove("open");
});

// ── Patient card ─────────────────────────────────────────────────────────────
function updatePatientCard() {
  const el = $("patient-info"); if (!el) return;
  const rows = [
    ["Child",    S.reg.child_name||"—"],
    ["Age",      S.reg.child_age_years!==undefined ? `${S.reg.child_age_years} yrs`:"—"],
    ["DOB",      S.reg.child_dob||"—"],
    ["Sex",      S.reg.child_sex||"—"],
    ["Guardian", S.reg.guardian_name||"—"],
    ["Phone",    S.reg.phone||"—"],
    ["ID",       S.pid ? `#${S.pid}`:"—"],
  ];
  el.innerHTML = rows.map(([l,v])=>`<div class="info-row"><span class="lbl">${l}</span><span class="val">${v}</span></div>`).join("");
  $("patient-card-section")?.style && ($("patient-card-section").style.display="block");
}

function updateUploadPanel() {
  $("upload-panel")?.style && ($("upload-panel").style.display = "block");
}

// ── File uploads ──────────────────────────────────────────────────────────────
function setupUpload(inputId, btnId, statusId, type) {
  $(btnId)?.addEventListener("click", async () => {
    const file = $(inputId)?.files[0];
    const st   = $(statusId);
    if (!file)      { if(st) st.textContent="Select a file first."; return; }
    if (!S.pid)     { if(st) st.textContent="Complete registration first."; return; }
    if (st) st.textContent = "⏳ Uploading...";
    try {
      const r = await API.uploadFile(S.pid, file, type);
      if (st) st.textContent = `✅ ${r.original_name}`;
      const label = { clinical_sheet:"Clinical sheet", identity_proof:"ID proof" }[type] || "File";
      addMsg(`📎 ${label} uploaded: ${r.original_name}`);
      $(inputId).value="";
    } catch(e) {
      if (st) st.textContent = `❌ ${e.message}`;
    }
  });
}
// Desktop sidebar
setupUpload("file-gen", "btn-gen", "status-gen", "general");
setupUpload("file-doc", "btn-doc", "status-doc", "clinical_sheet");
setupUpload("file-id",  "btn-id",  "status-id",  "identity_proof");
// Mobile bottom sheet (previously not wired up at all)
setupUpload("file-gen-m", "btn-gen-m", "status-gen-m", "general");
setupUpload("file-doc-m", "btn-doc-m", "status-doc-m", "clinical_sheet");
setupUpload("file-id-m",  "btn-id-m",  "status-id-m",  "identity_proof");

// ── Language pill buttons ────────────────────────────────────────────────────
document.querySelectorAll(".lang-pill").forEach(btn => {
  btn.addEventListener("click", () => {
    voice.stopSpeaking();   // stop any welcome-screen voice immediately
    hideWelcome(btn.dataset.lang);
  });
});

// ── Backend status ───────────────────────────────────────────────────────────
async function checkBackend() {
  const dot = $("backend-dot");
  try {
    await API.health(); dot?.classList.add("ok"); dot?.classList.remove("error");
  } catch {
    dot?.classList.add("error"); dot?.classList.remove("ok");
    addMsg("⚠️ Backend offline. Run: cd backend && python main.py");
  }
}

// ── Init ──────────────────────────────────────────────────────────────────────
window.addEventListener("load", async () => {
  window.speechSynthesis?.getVoices();
  buildModuleBar();
  showWelcome();
  await checkBackend();
});
