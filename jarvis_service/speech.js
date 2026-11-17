/* Spoken conversation controller. Audio never invokes action approval. */
(function (root) {
  "use strict";
  class JarvisSpeech {
    constructor(options) {
      this.options=options;
      this.Recognition=options.Recognition || root.SpeechRecognition || root.webkitSpeechRecognition;
      this.synth=options.synth || root.speechSynthesis;
      this.Utterance=options.Utterance || root.SpeechSynthesisUtterance;
      this.active=false;this.busy=false;this.speaking=false;
      this.recognition=null;this.timer=null;this.deadlineTimer=null;
      this.conversationId=null;this.epoch=0;this.awaitingApproval=false;
    }
    get supported() {return !!(this.Recognition && this.synth && this.Utterance);}
    state(name,text) {this.options.onState(name,text,this.active);}
    start() {
      if(this.active)return;
      if(!this.supported) {
        this.state("error","This browser does not support spoken conversation. Try Chrome or Safari on your personal device.");
        return;
      }
      if(!this.options.isReady()) {
        this.options.onSetupRequired?.();
        this.say("Finish AI setup and approve a usage allowance first. Then tap Talk to Jarvis.",false);
        return;
      }
      this.epoch++;this.active=true;this.awaitingApproval=false;
      this.deadlineTimer=root.setTimeout(()=>this.stop("Voice session ended. Tap Talk to continue."),15*60*1000);
      // First microphone request stays in the user's click gesture.
      this.listen();
    }
    stop(message="Voice is off. Tap Talk to start.") {
      this.active=false;this.busy=false;this.speaking=false;this.awaitingApproval=false;this.epoch++;
      root.clearTimeout(this.timer);root.clearTimeout(this.deadlineTimer);
      const recognition=this.recognition;this.recognition=null;
      try {recognition?.abort();} catch(e) {}
      this.synth?.cancel();
      this.state("idle",message);
    }
    newTopic() {
      const wasActive=this.active;
      this.stop();this.conversationId=null;
      if(wasActive){this.active=true;
        this.deadlineTimer=root.setTimeout(()=>this.stop("Voice session ended. Tap Talk to continue."),15*60*1000);
        this.say("New conversation. What would you like to do?");}
    }
    schedule() {
      root.clearTimeout(this.timer);
      if(this.active && !this.busy && !this.speaking)
        this.timer=root.setTimeout(()=>this.listen(),250);
    }
    listen() {
      if(!this.active || this.busy || this.speaking || this.recognition)return;
      if(!this.options.isReady()) {
        this.stop("AI usage allowance ended. Review a new allowance before continuing.");
        this.options.onSetupRequired?.();return;
      }
      const epoch=this.epoch;
      const recognition=new this.Recognition();
      this.recognition=recognition;
      recognition.lang=this.options.language || root.navigator?.language || "en-US";
      recognition.continuous=false;recognition.interimResults=true;recognition.maxAlternatives=1;
      recognition.onstart=()=>{if(this.active && epoch===this.epoch)this.state("listening","Listening… speak naturally.");};
      recognition.onresult=event=>{
        if(!this.active || epoch!==this.epoch || this.busy || this.speaking)return;
        let final="",interim="";
        for(let i=event.resultIndex||0;i<event.results.length;i++) {
          const text=event.results[i][0].transcript;
          if(event.results[i].isFinal)final+=text+" ";else interim+=text+" ";
        }
        this.options.onTranscript(final.trim() || interim.trim());
        if(final.trim())this.submit(final.trim());
      };
      recognition.onerror=event=>{
        if(epoch!==this.epoch || !this.active)return;
        if(event.error==="aborted")return;
        if(event.error==="no-speech"){this.schedule();return;}
        const messages={
          "not-allowed":"Microphone access is blocked. Allow the microphone in your browser's site permissions, then tap Talk.",
          "service-not-allowed":"The browser's speech service is blocked. Check site permissions or use your personal Chrome browser.",
          "audio-capture":"No microphone was found. Connect or enable one, then tap Talk.",
          "network":"The browser's speech service could not connect. Check your connection and tap Talk again."
        };
        this.stop(messages[event.error] || "Speech recognition stopped. Tap Talk to try again.");
      };
      recognition.onend=()=>{
        if(this.recognition===recognition)this.recognition=null;
        if(epoch===this.epoch && this.active && !this.busy && !this.speaking)this.schedule();
      };
      this.state("listening","Opening microphone…");
      try {recognition.start();} catch(e) {this.stop("Could not start the microphone. Tap Talk to try again.");}
    }
    async submit(text) {
      if(!this.active || this.busy || this.speaking)return;
      const command=text.toLowerCase().replace(/[.!?]+$/,"").trim();
      if(["stop","stop listening","stop jarvis"].includes(command)){this.stop();return;}
      if(["new topic","new conversation","start over"].includes(command)){this.newTopic();return;}
      const epoch=this.epoch;
      this.busy=true;
      try {this.recognition?.abort();} catch(e) {}
      this.recognition=null;
      this.state("thinking","Thinking…");
      try {
        const result=await this.options.request(text,this.conversationId);
        if(epoch!==this.epoch || !this.active)return;
        this.conversationId=result.conversation_id;
        this.busy=false;
        this.options.onReply(result.reply);
        if(result.status==="blocked" || result.status==="queued") {
          this.active=false;this.say(result.reply,false);return;
        }
        if(result.needs_approval) {
          this.awaitingApproval=true;
          // Pause recognition so background speech cannot be mistaken for approval.
          this.active=false;this.say(result.reply,false);return;
        }
        this.say(result.reply || "What would you like to do next?");
      } catch(e) {
        if(epoch===this.epoch)this.stop("I couldn't complete that turn. Check the connection or AI setup, then tap Talk.");
        this.options.onError?.(e);
      } finally {
        if(epoch===this.epoch)this.busy=false;
      }
    }
    say(text,listenAfter=true) {
      if(!this.synth || !this.Utterance) {
        this.stop("Spoken output is unavailable in this browser.");return;
      }
      try {this.recognition?.abort();} catch(e) {}
      this.recognition=null;
      this.synth.cancel();
      this.speaking=true;
      const epoch=this.epoch;
      const clean=String(text).replace(/https?:\/\/\S+/g,"the link on screen")
        .replace(/[*#_]/g,"").slice(0,5000);
      const utterance=new this.Utterance(clean);
      utterance.lang=this.options.language || root.navigator?.language || "en-US";
      const voices=this.synth.getVoices?.() || [];
      const voice=voices.find(v=>v.localService && v.lang===utterance.lang) ||
        voices.find(v=>v.lang===utterance.lang) || voices.find(v=>v.lang?.startsWith("en"));
      if(voice)utterance.voice=voice;
      utterance.rate=1.02;
      utterance.onend=()=>{
        if(epoch!==this.epoch)return;
        this.speaking=false;
        if(this.active && listenAfter)this.schedule();
        else this.state(this.awaitingApproval?"approval":"idle",
          this.awaitingApproval?"Review the approval card. No typing needed.":"Voice is off. Tap Talk to start.");
      };
      utterance.onerror=()=>{if(epoch===this.epoch)this.stop("I couldn't play the spoken reply. Check your speaker volume and tap Talk again.");};
      this.state("speaking","Jarvis is speaking…");
      try {this.synth.speak(utterance);} catch(e) {this.stop("Speech output could not start. Tap Talk again.");}
    }
    actionResult(action) {
      if(!this.awaitingApproval)return;
      this.awaitingApproval=false;
      const labels={send_email:"email",save_draft:"draft",create_appointment:"appointment",
        place_call:"call request",receive_call:"incoming-call permission",inference_allowance:"AI allowance"};
      const label=labels[action.kind] || "action";
      if(action.state==="succeeded") {
        this.active=this.options.isReady();this.epoch++;
        this.say("The approved "+label+" was processed successfully. "+(this.active?"What else would you like?":""),this.active);
      } else {
        this.active=false;
        this.say("The "+label+" did not finish with a verified success. Review its result before trying again.",false);
      }
    }
  }
  root.JarvisSpeech=JarvisSpeech;
})(typeof window!=="undefined"?window:globalThis);
