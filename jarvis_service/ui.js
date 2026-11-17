"use strict";
let csrfToken = "";
const el = id => document.getElementById(id);
async function api(path, method="GET", body) {
  const res = await fetch(path, {method, credentials:"same-origin",
    headers:{...(csrfToken ? {"X-Jarvis-CSRF":csrfToken} : {}), ...(body ? {"Content-Type":"application/json"} : {})},
    ...(body ? {body:JSON.stringify(body)} : {})});
  const value = await res.json();
  if (!res.ok) throw new Error(JSON.stringify(value));
  return value;
}
function show(id, value) { el(id).textContent = JSON.stringify(value, null, 2); }
function button(label, handler, parent) {
  const b = document.createElement("button"); b.textContent=label;
  b.onclick=()=>run(handler); parent.append(b);
}
async function run(fn) {
  el("error").textContent="";
  try { await fn(); } catch(e) { el("error").textContent=e.message; }
}
async function refresh() {
  const [status, actions, inbox, audit, tasks, setup] = await Promise.all([
    api("/api/status"), api("/api/actions"), api("/api/inbox"), api("/api/audit"), api("/api/tasks"), api("/api/setup")]);
  renderSetup(setup);
  show("status",status); show("audit",audit);
  el("tasks").replaceChildren();
  for (const task of tasks) {
    const card=document.createElement("div");card.className="card";
    const title=document.createElement("strong");title.textContent=task.instruction;card.append(title);
    const status=document.createElement("p");status.textContent="Task status: "+task.status+" · planning turns: "+task.turns;card.append(status);
    const answer=document.createElement("pre");answer.textContent=task.answer;card.append(answer);
    const notice=document.createElement("p");notice.textContent=task.notice;card.append(notice);
    if(task.action_ids.length) {
      const receipts=document.createElement("pre");
      receipts.textContent=JSON.stringify(actions.filter(a=>task.action_ids.includes(a.id)).map(a=>({
        action:a.kind,state:a.state,result:a.result
      })),null,2);
      card.append(receipts);
    }
    button("Follow up",async()=>{
      const instruction=window.prompt("Add instructions or missing details. Never paste passwords or keys.");
      if(!instruction)return;
      await api("/api/tasks/"+task.id+"/continue","POST",{instruction});await refresh();
    },card);
    el("tasks").append(card);
  }
  el("actions").replaceChildren();
  for (const a of actions) {
    const card=document.createElement("div");card.className="card";
    const heading=document.createElement("strong"); heading.textContent=a.kind+" · "+a.state;card.append(heading);
    const pre=document.createElement("pre");pre.textContent=JSON.stringify(a.payload,null,2);card.append(pre);
    if(a.state==="pending") {
      button("Approve and execute once", async()=>{
        if (!window.confirm("Execute this exact action? Any stated provider charges are approved for this action.")) return;
        show("result",await api("/api/actions/"+a.id+"/approve","POST",{digest:a.digest}));await refresh();
      },card);
      button("Reject",async()=>{await api("/api/actions/"+a.id+"/reject","POST");await refresh();},card);
    }
    if(a.result){const r=document.createElement("pre");r.textContent=JSON.stringify(a.result,null,2);card.append(r);}
    el("actions").append(card);
  }
  el("inbox").replaceChildren();
  for(const item of inbox.filter(Boolean)) {
    const card=document.createElement("div");card.className="card";
    const pre=document.createElement("pre");pre.textContent=JSON.stringify(item,null,2);card.append(pre);
    if(item.analysis.suggested_reply) {
      button("Propose saving Gmail draft",async()=>{
        show("result",await api("/api/inbox/"+encodeURIComponent(item.message.id)+"/draft","POST"));await refresh();
      },card);
    }
    el("inbox").append(card);
  }
}
function signedIn(value) {
  el("console").hidden=!value;
  for (const id of ["token","unlock","login-help","login-guide"]) el(id).hidden=value;
  el("lock").hidden=!value;
}
el("unlock").onclick=()=>run(async()=>{
  const token=el("token").value.trim();
  el("token").value="";
  const session=await api("/api/session/login","POST",{token});
  csrfToken=session.csrf_token;await refresh();signedIn(true);
});
el("lock").onclick=()=>run(async()=>{
  await api("/api/session/logout","POST");csrfToken="";signedIn(false);
  for(const id of ["status","actions","inbox","audit","result","tasks"]) el(id).replaceChildren();
});
el("refresh").onclick=()=>run(refresh);
el("connect").onclick=()=>run(async()=>{const r=await api("/api/oauth/google/start","POST");window.location.assign(r.url);});
for(const id of ["probe","monitor","pause","resume"]) el(id).onclick=()=>run(async()=>{
  show("result",await api("/api/"+id,"POST"));await refresh();});
el("propose").onclick=()=>run(async()=>{
  show("result",await api("/api/actions","POST",JSON.parse(el("proposal").value)));await refresh();});

el("task-submit").onclick=()=>run(async()=>{
  const instruction=el("task-input").value.trim();
  if(!instruction)return;
  el("task-submit").disabled=true;
  try {
    show("result",await api("/api/tasks","POST",{instruction}));
    el("task-input").value="";await refresh();
  } finally {el("task-submit").disabled=false;}
});

let modelName="gpt-4o-mini";
function renderSetup(setup) {
  modelName=setup.model.model;
  el("model-state").textContent=!setup.model.configured ? "API key needed" :
    setup.model.allowance_active ? "Key saved · usage allowance active" : "Key saved · approve an AI usage allowance below";
  el("google-state").textContent=setup.google.connected ? "Google connected · run connection checks to verify access" :
    setup.google.configured ? "Ready for your Google sign-in" : "OAuth configuration needed before sign-in";
  if(setup.google.last_error) el("google-state").textContent+=" · Google returned "+setup.google.last_error.code;
  el("phone-state").textContent=setup.phone.configured ?
    "Credentials saved · live calling still needs an approved test" : "Twilio credentials needed";
  el("redirect-uri").textContent=setup.google.redirect_uri;
  el("phone-webhook").textContent=setup.phone.webhook;
  el("connect").disabled=!setup.google.configured;
  el("monitor").disabled=!setup.google.connected;
  el("task-submit").disabled=!setup.model.configured || !setup.model.allowance_active;
  el("chat-guidance").textContent=el("task-submit").disabled ?
    "Finish AI chat setup and approve a bounded usage allowance before asking Jarvis to work." :
    "Describe what you need. Jarvis will prepare consequential actions for your approval.";
  el("setup-summary").textContent=setup.model.configured && setup.model.allowance_active ?
    "AI chat is ready to try. Connect Google and phone features below as needed." :
    "Start with AI chat. The remaining connections can be completed afterward.";
}
async function saveSettings(values,fields) {
  await api("/api/settings","PUT",values);
  for(const field of fields)el(field).value="";
  el("setup-result").textContent="Saved privately. No paid usage or external actions were started.";
  await refresh();
}
el("save-model").onclick=()=>run(()=>saveSettings({openai_key:el("openai-key").value.trim()},["openai-key"]));
el("save-google").onclick=()=>run(()=>saveSettings({
  google_client_id:el("google-client-id").value.trim(),
  google_client_secret:el("google-client-secret").value.trim()
},["google-client-id","google-client-secret"]));
el("save-phone").onclick=()=>run(()=>saveSettings({
  twilio_sid:el("twilio-sid").value.trim(),twilio_token:el("twilio-token").value.trim(),
  twilio_number:el("twilio-number").value.trim()
},["twilio-sid","twilio-token","twilio-number"]));
el("review-allowance").onclick=()=>run(async()=>{
  await api("/api/actions","POST",{kind:"inference_allowance",payload:{
    model:modelName,requests:Number(el("allowance-requests").value),
    hours:Number(el("allowance-hours").value),cost_notice:"I approve model charges for this bounded allowance"
  }});
  await refresh();el("actions").scrollIntoView({behavior:"smooth"});
});
async function restoreSession() {
  try {
    const session=await api("/api/session");csrfToken=session.csrf_token;
    await refresh();signedIn(true);
  } catch(e) {signedIn(false);}
}
restoreSession();
