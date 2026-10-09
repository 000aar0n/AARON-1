"""Animated robot avatar for AARON-1 (no LLM, no external services).

Streamlit component uses browser speech synthesis when available, and provides
a guaranteed visual-only animation option independent of audio permissions.
"""
import json
import streamlit.components.v1 as components


def render_face(text="Hello! I am AARON-1.", key="face"):
    # Encode response as a JS string literal, without exposing an HTML/script tag.
    message = json.dumps(str(text), ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e")
    source = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<style>
* { box-sizing:border-box; }
body { margin:0; font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; color:#eaf5ff; background:transparent; }
.panel { max-width:640px; margin:0 auto; padding:18px; background:radial-gradient(circle at 50% 15%,#253a5d 0%,#131d33 58%,#101729 100%); border:1px solid #354567; border-radius:24px; text-align:center; }
.robot { width:min(100%,285px); height:283px; overflow:visible; filter:drop-shadow(0 12px 20px #0007); }
#head { transform-origin:150px 150px; animation:float 3.5s ease-in-out infinite; }
@keyframes float { 0%,100% { transform:translateY(2px); } 50% { transform:translateY(-4px); } }
.eye { transform-box:fill-box; transform-origin:center; animation:blink 6s infinite; }
@keyframes blink { 0%,92%,96%,100% { transform:scaleY(1); } 94% { transform:scaleY(.12); } }
#mouth-open { opacity:0; }
#mouth-idle { opacity:1; }
body.talking #mouth-idle { opacity:0; }
body.talking #mouth-open { opacity:1; animation:chatter .2s ease-in-out infinite alternate; transform-box:fill-box; transform-origin:center; }
body.talking #eye-left,body.talking #eye-right { fill:#9dffe3; }
@keyframes chatter { from { transform:scaleY(.3); } to { transform:scaleY(1.25); } }
.name { font-weight:800; letter-spacing:.15em; font-size:19px; margin-top:2px; }
.sub { color:#a9bddb; font-size:12px; margin:4px 0 12px; }
.answer { color:#dfeafa; font-size:14px; line-height:1.45; min-height:44px; max-height:70px; overflow:auto; margin:10px auto 16px; max-width:520px; }
.buttons { display:flex; justify-content:center; flex-wrap:wrap; gap:9px; }
button { border:0; background:#577ff2; color:#fff; font:600 13px system-ui; border-radius:11px; padding:11px 15px; cursor:pointer; }
button.secondary { background:#314361; }
button:hover { filter:brightness(1.14); }
button:focus-visible { outline:3px solid #9dd4ff; outline-offset:3px; }
#status { min-height:18px; color:#adc2df; font-size:12px; margin:12px 0 0; }
@media (prefers-reduced-motion:reduce) { #head,.eye { animation:none; } }
</style>
</head>
<body>
<div class="panel">
<svg class="robot" viewBox="0 0 300 310" role="img" aria-label="Friendly futuristic robot avatar with animated eyes and mouth">
  <ellipse cx="150" cy="280" rx="105" ry="20" fill="#030816" opacity=".25"/>
  <rect x="112" y="234" width="76" height="58" rx="15" fill="#536c94"/>
  <rect x="68" y="263" width="164" height="47" rx="24" fill="#263b60" stroke="#7992b9" stroke-width="4"/>
  <circle cx="114" cy="285" r="7" fill="#6de8f7"/>
  <circle cx="150" cy="285" r="7" fill="#8fffc0"/>
  <circle cx="186" cy="285" r="7" fill="#6de8f7"/>
  <g id="head">
    <line x1="150" y1="57" x2="150" y2="35" stroke="#849ac0" stroke-width="7" stroke-linecap="round"/>
    <circle cx="150" cy="28" r="12" fill="#67e3ff" stroke="#c9f8ff" stroke-width="4"/>
    <rect x="42" y="137" width="26" height="51" rx="12" fill="#586d94"/>
    <rect x="232" y="137" width="26" height="51" rx="12" fill="#586d94"/>
    <rect x="60" y="62" width="180" height="192" rx="40" fill="#677fa8" stroke="#9fb4d8" stroke-width="5"/>
    <rect x="75" y="79" width="150" height="152" rx="29" fill="#14253e" stroke="#4b668f" stroke-width="5"/>
    <rect x="89" y="94" width="122" height="67" rx="20" fill="#0b1527"/>
    <g class="eye">
      <rect id="eye-left" x="103" y="112" width="34" height="25" rx="10" fill="#68e5ff"/>
      <rect id="eye-right" x="163" y="112" width="34" height="25" rx="10" fill="#68e5ff"/>
    </g>
    <circle cx="150" cy="170" r="6" fill="#ffd976"/>
    <rect x="102" y="186" width="96" height="37" rx="12" fill="#071322" stroke="#6d83ab" stroke-width="3"/>
    <rect id="mouth-idle" x="119" y="201" width="62" height="7" rx="3.5" fill="#90ffbd"/>
    <rect id="mouth-open" x="127" y="192" width="46" height="25" rx="9" fill="#90ffbd"/>
    <circle cx="89" cy="207" r="4" fill="#8dacca"/>
    <circle cx="211" cy="207" r="4" fill="#8dacca"/>
  </g>
</svg>
<div class="name">AARON-1</div>
<div class="sub">INDIVIDUAL 001 · OFFLINE SYMBOLIC AI</div>
<div id="answer" class="answer" aria-live="polite"></div>
<div class="buttons">
  <button id="speak" type="button">▶ Speak reply</button>
  <button id="animate" class="secondary" type="button">◉ Test mouth</button>
  <button id="stop" class="secondary" type="button">■ Stop</button>
</div>
<div id="status" role="status">Ready · press Speak reply to hear a response</div>
</div>
<script>
const MESSAGE = __MESSAGE__;
const answer = document.getElementById("answer");
const status = document.getElementById("status");
answer.textContent = MESSAGE;
let animationTimer = null;
let speechActive = false;
let runId = 0;

function startMouth() { document.body.classList.add("talking"); }
function stopMouth() { document.body.classList.remove("talking"); }
function cancelSpeech() {
  if ("speechSynthesis" in window) {
    try { window.speechSynthesis.cancel(); } catch (_) {}
  }
}
function clearRun(cancelAudio=true) {
  runId++;
  if (animationTimer !== null) { clearTimeout(animationTimer); animationTimer = null; }
  if (cancelAudio) cancelSpeech();
  speechActive=false;
  stopMouth();
}
function beginFallbackAnimation(why) {
  const thisRun = runId;
  startMouth();
  status.textContent = why;
  const ms = Math.max(1700, Math.min(10000, MESSAGE.length * 65));
  animationTimer = setTimeout(() => {
    if (runId === thisRun && !speechActive) {
      stopMouth();
      status.textContent = "Ready";
    }
  }, ms);
}

document.getElementById("animate").addEventListener("click", () => {
  clearRun();
  beginFallbackAnimation("Visual mouth test (no audio)");
});
document.getElementById("speak").addEventListener("click", () => {
  clearRun();
  const thisRun = runId;
  // Animation starts immediately: it does not depend on a browser speech event.
  beginFallbackAnimation("Trying browser voice…");
  if (!("speechSynthesis" in window) || !("SpeechSynthesisUtterance" in window)) {
    status.textContent = "Browser speech unavailable; showing mouth animation";
    return;
  }
  try {
    const utterance = new SpeechSynthesisUtterance(MESSAGE);
    utterance.lang="en-US"; utterance.rate=.92; utterance.pitch=.82;
    utterance.onstart=() => {
      if(thisRun!==runId) return;
      speechActive=true;
      if(animationTimer!==null) { clearTimeout(animationTimer); animationTimer=null; }
      startMouth();
      status.textContent="Speaking…";
    };
    utterance.onend=() => {
      if(thisRun!==runId) return;
      speechActive=false; stopMouth(); status.textContent="Ready";
    };
    utterance.onerror=() => {
      if(thisRun!==runId) return;
      speechActive=false;
      status.textContent="Browser voice blocked; mouth animation still works";
    };
    window.speechSynthesis.speak(utterance);
  } catch (_) {
    status.textContent="Browser voice unavailable; showing mouth animation";
  }
});
document.getElementById("stop").addEventListener("click", () => {
  clearRun(); status.textContent="Stopped";
});
window.addEventListener("pagehide", () => clearRun());
</script>
</body></html>"""
    components.html(source.replace("__MESSAGE__", message), height=484, scrolling=False)
