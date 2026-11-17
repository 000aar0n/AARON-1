"use strict";
let ownerToken = "";
const el = id => document.getElementById(id);
async function api(path, method="GET", body) {
  const res = await fetch(path, {method, credentials:"same-origin",
    headers:{"Authorization":"Bearer "+ownerToken, ...(body ? {"Content-Type":"application/json"} : {})},
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
  const [status, actions, inbox, audit, tasks] = await Promise.all([
    api("/api/status"), api("/api/actions"), api("/api/inbox"), api("/api/audit"), api("/api/tasks")]);
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
el("unlock").onclick=()=>run(async()=>{ownerToken=el("token").value;el("token").value="";await refresh();el("console").hidden=false;});
el("lock").onclick=()=>{ownerToken="";el("token").value="";el("console").hidden=true;
  for(const id of ["status","actions","inbox","audit","result","tasks"]) el(id).replaceChildren();};
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
