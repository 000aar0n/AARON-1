"""Spoken conversation uses the same encrypted tasks and approval boundaries."""
import pytest
from fastapi.testclient import TestClient
from jarvis_service.app import create_app
from jarvis_service.spoken import Spoken, SpokenRequest
from jarvis_service.tests.test_tasks import setup, plan

def request(text="Hello",conversation_id=None,key="a"):
    return SpokenRequest(text=text,conversation_id=conversation_id,request_id=key*32)

def test_conversation_history_and_idempotency(setup):
    s,store,google,inbox,brain,tasks=setup
    brain.complete_json.return_value=plan(answer="Hello Aaron.")
    spoken=Spoken(s,store,tasks)
    first=spoken.turn(request())
    assert spoken.turn(request())==first
    assert brain.complete_json.call_count==1
    spoken.turn(request("Tell me more",first["conversation_id"],"b"))
    context=brain.complete_json.call_args.args[1]
    assert context["mode"]=="voice"
    assert context["recent_dialogue"][0]["content"]=="Hello"
    assert "Hello Aaron." not in open(store.path,"rb").read().decode(errors="ignore")

def test_pending_action_does_not_claim_send_or_accept_spoken_yes(setup):
    s,store,google,inbox,brain,tasks=setup
    brain.complete_json.return_value=plan(answer="Sent it!",proposals=[{
        "kind":"send_email","payload":{"to":"friend@example.com","subject":"Hi","body":"Hello"}}])
    spoken=Spoken(s,store,tasks)
    first=spoken.turn(request("Send email"))
    assert first["needs_approval"]
    assert "has not been sent" in first["reply"]
    brain.complete_json.return_value=plan(answer="Please review the existing approval.")
    spoken.turn(request("yes",first["conversation_id"],"b"))
    assert all(a["state"]=="pending" for a in store.actions())
    google.send.assert_not_called()

def test_pause_and_unknown_conversation_rejected(setup):
    s,store,google,inbox,brain,tasks=setup
    spoken=Spoken(s,store,tasks)
    with pytest.raises(KeyError):spoken.turn(request(conversation_id="c"*32))
    store.put("paused",True)
    with pytest.raises(PermissionError):spoken.turn(request())
    brain.complete_json.assert_not_called()

def test_voice_endpoint_owner_only_and_rejects_audio_fields(setup):
    s,store,google,inbox,brain,tasks=setup
    brain.complete_json.return_value=plan(answer="Hello.")
    with TestClient(create_app(s,google_override=google,brain_override=brain),base_url=s.public_url) as client:
        payload={"text":"Hello","request_id":"a"*32}
        assert client.post("/api/voice/turn",json=payload).status_code==401
        headers={"Authorization":"Bearer "+s.owner_token}
        result=client.post("/api/voice/turn",json=payload,headers=headers)
        assert result.status_code==200 and result.json()["reply"]=="Hello."
        payload["audio"]="raw audio not accepted"
        assert client.post("/api/voice/turn",json=payload,headers=headers).status_code==422

def test_exhausted_task_starts_fresh_bounded_task(setup):
    s,store,google,inbox,brain,tasks=setup
    brain.complete_json.return_value=plan(answer="Which date?",status="needs_input")
    spoken=Spoken(s,store,tasks)
    first=spoken.turn(request())
    task=tasks.get(first["task_id"]);task["turns"]=8;tasks.save(task)
    second=spoken.turn(request("Tomorrow",first["conversation_id"],"b"))
    assert second["task_id"]!=first["task_id"]
    assert tasks.get(second["task_id"])["turns"]==1
