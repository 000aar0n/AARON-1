const {test}=require("node:test");
const assert=require("node:assert/strict");
const vm=require("node:vm"),fs=require("node:fs");
function setup(extra={}) {
  const timers=new Map();let id=0;const recognitions=[],spoken=[],requests=[],states=[];
  class Recognition {
    constructor(){recognitions.push(this);}
    start(){this.onstart?.();}
    abort(){this.onend?.();}
    result(text,final=true){const r=[{transcript:text}];r.isFinal=final;this.onresult({resultIndex:0,results:[r]});}
  }
  class Utterance {constructor(text){this.text=text;}}
  const synth={cancel(){},getVoices(){return[];},speak(u){spoken.push(u);}};
  const context={setTimeout(fn,ms){timers.set(++id,{fn,ms});return id;},clearTimeout(i){timers.delete(i);},navigator:{language:"en-US"}};
  context.globalThis=context;
  vm.runInNewContext(fs.readFileSync("jarvis_service/speech.js","utf8"),context);
  const options={Recognition,synth,Utterance,isReady:()=>true,onState:(...s)=>states.push(s),
    onTranscript(){},onReply(){},request:async(text,conversation_id)=>{requests.push({text,conversation_id});return {conversation_id:"a".repeat(32),status:"ready",reply:"Hello Aaron."};},...extra};
  const speech=new context.JarvisSpeech(options);
  return {speech,spoken,recognitions,requests,states,options,
    next(){for(const [i,t] of timers)if(t.ms===250){timers.delete(i);t.fn();return;}}};
}
const flush=()=>new Promise(resolve=>setImmediate(resolve));
test("final speech invokes one turn, speaks reply and resumes microphone after playback",async()=>{
  const h=setup();h.speech.start();assert.equal(h.recognitions.length,1);
  h.recognitions[0].result("Hello",false);assert.equal(h.requests.length,0);
  h.recognitions[0].result("Hello");await flush();
  assert.equal(h.requests.length,1);assert.equal(h.spoken[0].text,"Hello Aaron.");
  h.next();assert.equal(h.recognitions.length,1);
  h.spoken[0].onend();h.next();assert.equal(h.recognitions.length,2);
  h.speech.stop();
});
test("permission denial stops with a useful message",()=>{
  const h=setup();h.speech.start();h.recognitions[0].onerror({error:"not-allowed"});
  assert.equal(h.speech.active,false);assert.match(h.states.at(-1)[1],/Allow the microphone/);h.next();assert.equal(h.recognitions.length,1);
});
test("stop discards late replies",async()=>{
  let resolve;const h=setup({request:()=>new Promise(r=>resolve=r)});
  h.speech.start();h.recognitions[0].result("hello");h.speech.stop();
  resolve({conversation_id:"a".repeat(32),reply:"late",status:"ready"});await flush();
  assert.equal(h.spoken.length,0);h.next();assert.equal(h.recognitions.length,1);
});
test("spoken stop and new topic are local and do not spend model requests",()=>{
  const h=setup();h.speech.start();h.recognitions[0].result("new topic");
  assert.equal(h.requests.length,0);h.spoken[0].onend();h.next();h.recognitions.at(-1).result("stop");
  assert.equal(h.speech.active,false);assert.equal(h.requests.length,0);
});
test("pending approval stops listening and only explicit receipt resumes",async()=>{
  const h=setup({request:async()=>({conversation_id:"a".repeat(32),reply:"Review approval.",status:"awaiting_approval",needs_approval:true})});
  h.speech.start();h.recognitions[0].result("send email");await flush();h.spoken[0].onend();h.next();
  assert.equal(h.speech.active,false);assert.equal(h.recognitions.length,1);
  h.speech.actionResult({kind:"send_email",state:"succeeded"});assert.match(h.spoken.at(-1).text,/processed successfully/);
  h.spoken.at(-1).onend();h.next();assert.equal(h.recognitions.length,2);
});
test("missing setup never opens microphone",()=>{
  let opened=false;const h=setup({isReady:()=>false,onSetupRequired:()=>opened=true});
  h.speech.start();assert.equal(opened,true);assert.equal(h.recognitions.length,0);assert.match(h.spoken[0].text,/setup/);
});
test("new topic invalidates a pending reply and clears conversation",async()=>{
  let resolve;const h=setup({request:()=>new Promise(r=>resolve=r)});
  h.speech.start();h.recognitions[0].result("hello");h.speech.newTopic();
  resolve({conversation_id:"a".repeat(32),reply:"stale",status:"ready"});await flush();
  assert.equal(h.speech.conversationId,null);assert.equal(h.spoken.length,1);
});
test("uncertain action receipt never reports success or resumes",async()=>{
  const h=setup();h.speech.awaitingApproval=true;h.speech.actionResult({kind:"send_email",state:"uncertain"});
  assert.equal(h.speech.active,false);assert.match(h.spoken[0].text,/did not finish/);
});
