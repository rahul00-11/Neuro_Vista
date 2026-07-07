export class Voice {
  constructor() {
    this.rec = null; this.listening = false;
    this.lmap = { en:"en-IN", hi:"hi-IN", hinglish:"hi-IN" };
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SR) { this.rec = new SR(); }
    this._queue = [];
    this._speaking = false;
    // Chrome bug workaround: speechSynthesis silently auto-pauses after ~15s
    // and never resumes on its own. A periodic resume() keeps long replies alive.
    if (window.speechSynthesis) {
      setInterval(() => {
        if (window.speechSynthesis.speaking) window.speechSynthesis.resume();
      }, 5000);
    }
  }

  listen(lang="en") {
    return new Promise(res => {
      if (!this.rec) return res(null);
      this.rec.lang = this.lmap[lang]||"en-IN";
      this.rec.continuous = true;       // keep listening across natural pauses in speech
      this.rec.interimResults = true;   // stream partial results so we can accumulate them
      this.listening = true;
      let transcript = "";
      this.rec.onresult = e => {
        transcript = "";
        for (let i = 0; i < e.results.length; i++) transcript += e.results[i][0].transcript;
      };
      this.rec.onerror = () => { this.listening=false; res(transcript || null); };
      this.rec.onend    = () => { this.listening=false; res(transcript || null); };
      try { this.rec.start(); } catch { res(null); }
    });
  }

  stop() { if (this.rec && this.listening) { this.rec.stop(); this.listening=false; } }

  // Queued instead of cancel+speak: calling speechSynthesis.cancel() immediately
  // followed by speak() repeatedly (which happens whenever multiple assistant
  // messages fire in quick succession, e.g. right after registration) is a
  // well-known Chrome bug that permanently breaks all future speech in the tab.
  // Queuing and only starting the next utterance once the previous one has
  // genuinely finished avoids triggering that bug entirely.
  speak(text, lang="en") {
    return new Promise(res => {
      if (!window.speechSynthesis) return res();
      this._queue.push({ text, lang, res });
      this._drain();
    });
  }

  _drain() {
    if (this._speaking || this._queue.length === 0) return;
    const { text, lang, res } = this._queue.shift();
    this._speaking = true;
    const u = new SpeechSynthesisUtterance(text);
    u.lang = this.lmap[lang]||"en-IN";
    u.rate = 0.88; u.pitch = 1; u.volume = 1;
    const vs = window.speechSynthesis.getVoices();
    const v = vs.find(v => v.lang.startsWith(u.lang.split("-")[0]));
    if (v) u.voice = v;
    const done = () => { this._speaking = false; res(); this._drain(); };
    u.onend = done; u.onerror = done;
    window.speechSynthesis.speak(u);
  }

  // Clears anything queued/speaking — use this instead of calling
  // speechSynthesis.cancel() directly (e.g. when the user picks a language
  // on the welcome screen), so our internal queue state stays consistent.
  stopSpeaking() {
    this._queue = [];
    this._speaking = false;
    window.speechSynthesis?.cancel();
  }

  get ok() { return !!this.rec; }
}
