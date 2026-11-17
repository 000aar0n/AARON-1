"""Owner-authenticated spoken turns. Browser audio never authorizes an external write."""
import threading
import time
import uuid
from pydantic import Field
from .schemas import Strict

class SpokenRequest(Strict):
    text: str = Field(min_length=1,max_length=4000)
    conversation_id: str | None = Field(default=None,pattern=r"^[a-f0-9]{32}$")
    request_id: str = Field(pattern=r"^[a-f0-9]{32}$")

class Spoken:
    def __init__(self,settings,store,tasks):
        self.s,self.store,self.tasks=settings,store,tasks
        self.lock=threading.Lock()

    def turn(self,request):
        if self.store.get("paused",False):
            raise PermissionError("Jarvis is paused. Resume it before talking.")
        if not self.lock.acquire(blocking=False):
            raise ValueError("Jarvis is already processing a spoken turn")
        try:
            saved=self.store.get("spoken_reply:"+request.request_id)
            if saved:
                return saved
            if request.conversation_id:
                conversation=self.store.get("spoken:"+request.conversation_id)
                if not conversation:
                    raise KeyError(request.conversation_id)
            else:
                conversation={"id":uuid.uuid4().hex,"messages":[],"task_id":None}
            previous=self.tasks.get(conversation["task_id"]) if conversation["task_id"] else None
            if previous and previous["status"] in ("needs_input","queued","blocked") and previous["turns"]<8:
                task=self.tasks.continue_task(previous["id"],request.text)
            else:
                task=self.tasks.create(request.text,mode="voice")
            task["mode"]="voice"
            task["recent_dialogue"]=conversation["messages"][-8:]
            self.tasks.save(task)
            task=self.tasks.run(task["id"])
            if task["status"]=="queued":
                task=self.tasks.run(task["id"])
            reply=task["answer"] or "I am still working on that. Please give me a moment."
            needs_approval=task["status"]=="awaiting_approval"
            if needs_approval:
                # Ignore model prose for action claims: approval receipts are authoritative.
                reply="I prepared something for your approval. It has not been sent, booked, or called. Please review the approval card and confirm it."
            conversation["messages"]=(conversation["messages"]+[
                {"role":"owner","content":request.text},
                {"role":"assistant","content":reply[:5000]},
            ])[-10:]
            conversation["task_id"]=task["id"]
            conversation["updated"]=time.time()
            self.store.put("spoken:"+conversation["id"],conversation)
            result={"conversation_id":conversation["id"],"task_id":task["id"],
                    "status":task["status"],"reply":reply,"needs_approval":needs_approval,
                    "action_ids":task["action_ids"],
                    "notice":"Speaking never approves an action. Use the explicit approval card."}
            self.store.put("spoken_reply:"+request.request_id,result)
            self.store.audit("spoken_turn_prepared",task["id"])
            return result
        finally:
            self.lock.release()
