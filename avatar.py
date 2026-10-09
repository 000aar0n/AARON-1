"""Animated face for AARON-1. Browser speech synthesis is not an LLM."""
import html
import json
import streamlit.components.v1 as components

def render_face(text="Hello! I'm AARON-1.", key="face"):
    message = json.dumps(text, ensure_ascii=False).replace("<", "\\u003c")
    # Distinct iframe gets recreated on Streamlit reruns.
    source = """<!doctype html><html><head><meta charset="utf-8">
<style>
*{box-sizing:border-box}body{margin:0;font-family:system-ui,-apple-system,sans-serif;color:#e9edf5;background:transparent}
.stage{position:relative;max-width:580px;margin:auto;padding:12px 16px 18px;border:1px solid #323c51;background:linear-gradient(155deg,#10192c,#1c2840);border-radius:24px;text-align:center;overflow:hidden}
.glow{position:absolute;inset:30px 20% auto;height:180px;border-radius:50%;background:#526edb;opacity:.10;filter:blur(35px);pointer-events:none}
.avatar{width:min(100%,285px);height:268px;filter:drop-shadow(0 9px 22px #0005)}
.head{transform-origin:150px 133px;animation:float 3.3s ease-in-out infinite}
.eye{transform-origin:center;animation:blink 5s infinite}
@keyframes blink{0%,92%,96%,100%{transform:scaleY(1)}94%{transform:scaleY(.10)}}
@keyframes float{0%,100%{transform:translateY(2px)}50%{transform:translateY(-4px)}}
#talkmouth{opacity:0}#smile{opacity:1}
body.talking #talkmouth{opacity:1;animation:mouth .19s ease-in-out infinite alternate}
body.talking #smile{opacity:0}
@keyframes mouth{from{transform:translateY(1px) scaleY(.3)}to{transform:translateY(-1px) scaleY(1.35)}}
.name{font-size:18px;font-weight:700;letter-spacing:.1em;margin:2px 0}
.caption{font-size:12px;color:#afc0d8;margin:4px 0 12px}
.text{font-size:14px;min-height:32px;color:#dae4f9;max-height:76px;overflow:auto;margin:10px auto;max-width:480px}
button{background:#607af0;border:0;border-radius:12px;color:#fff;font-weight:700;padding:11px 20px;cursor:pointer}
button.secondary{background:#313f61;margin-left:10px}button:hover{filter:brightness(1.16)}
#status{font-size:12px;color:#afc0d8;margin-top:9px}
</style></head><body>
<div class="stage"><div class="glow"></div>
<svg class="avatar" viewBox="0 0 300 300" role="img" aria-label="Friendly cartoon person with expressive eyes and animated mouth">
<g class="head">
<!-- shoulders and jacket -->
<path d="M49 298 Q53 237 117 228 L181 228 Q249 235 254 298Z" fill="#6277b4"/>
<path d="M120 234L151 275L179 232" fill="#e7d2b8"/>
<path d="M128 226L151 258L168 225" fill="#efc5a5"/>
<path d="M145 263 L157 263 L165 300 L139 300Z" fill="#343d60"/>
<!-- hair behind head -->
<ellipse cx="150" cy="133" rx="98" ry="113" fill="#282437"/>
<ellipse cx="150" cy="142" rx="83" ry="91" fill="#edb98e"/>
<ellipse cx="66" cy="162" rx="11" ry="23" fill="#dfa77e"/>
<ellipse cx="234" cy="162" rx="11" ry="23" fill="#dfa77e"/>
<!-- cheeks -->
<ellipse cx="104" cy="178" rx="17" ry="10" fill="#e89492" opacity=".37"/>
<ellipse cx="196" cy="178" rx="17" ry="10" fill="#e89492" opacity=".37"/>
<!-- hair fringe -->
<path d="M59 129 Q53 44 117 37 Q202 1 240 94L237 146Q221 112 211 86Q197 117 163 100Q125 131 89 111Q79 133 69 143Z" fill="#30283e"/>
<path d="M117 40 Q135 72 115 103M169 45 Q184 75 161 98" stroke="#524057" stroke-width="7" stroke-linecap="round" fill="none"/>
<!-- brows -->
<path d="M91 129 Q109 118 126 127 M175 127 Q194 118 211 130" stroke="#584139" stroke-width="6" stroke-linecap="round" fill="none"/>
<!-- eyes -->
<g class="eye"><ellipse cx="110" cy="148" rx="15" ry="17" fill="#faf6ef"/><ellipse cx="190" cy="148" rx="15" ry="17" fill="#faf6ef"/>
<circle cx="111" cy="149" r="9" fill="#547d91"/><circle cx="190" cy="149" r="9" fill="#547d91"/><circle cx="113" cy="145" r="3" fill="white"/><circle cx="192" cy="145" r="3" fill="white"/></g>
<path d="M149 158 Q144 174 151 174" stroke="#b88367" stroke-width="3" fill="none" stroke-linecap="round"/>
<path id="smile" d="M129 195 Q150 212 173 194" stroke="#824c4e" stroke-width="4.5" stroke-linecap="round" fill="none"/>
<ellipse id="talkmouth" cx="151" cy="200" rx="17" ry="12" fill="#713b4b"/>
</g>
</svg>
<div class="name">AARON-1</div><div class="caption">Digital individual · local symbolic AI</div>
<div class="text" id="caption"></div>
<button id="speak">▶ Speak reply</button><button class="secondary" id="stop">■ Stop</button>
<div id="status" role="status">Ready</div>
</div>
<script>
const MESSAGE=__MESSAGE__;
const caption=document.getElementById("caption");
const status=document.getElementById("status");
caption.textContent=MESSAGE;
let speaking=false;
function reset(){document.body.classList.remove("talking");speaking=false;status.textContent="Ready";}
document.getElementById("speak").addEventListener("click",()=>{
 if(!("speechSynthesis" in window)){status.textContent="Speech synthesis not supported in this browser";return;}
 window.speechSynthesis.cancel();
 const u=new SpeechSynthesisUtterance(MESSAGE);
 u.lang="en-US";u.rate=0.92;u.pitch=1.06;
 u.onstart=()=>{speaking=true;document.body.classList.add("talking");status.textContent="Speaking…";};
 u.onend=reset;u.onerror=reset;
 window.speechSynthesis.speak(u);
});
document.getElementById("stop").addEventListener("click",()=>{if("speechSynthesis" in window)window.speechSynthesis.cancel();reset();});
window.addEventListener("pagehide",()=>{if("speechSynthesis" in window)window.speechSynthesis.cancel();});
</script></body></html>"""
    components.html(source.replace("__MESSAGE__", message), height=445, scrolling=False)
