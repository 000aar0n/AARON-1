"""Task planning is executable with fake models; no test contacts real providers."""
import time
from unittest.mock import MagicMock
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from jarvis_service.app import create_app
from jarvis_service.config import Settings
from jarvis_service.store import Store
from jarvis_service.tasks import Tasks, ReadRequest

@pytest.fixture
def setup(tmp_path):
    s=Settings(public_url="https://jarvis.example",owner_token="x"*40,
        encryption_key=Fernet.generate_key().decode(),google_email="owner@example.com",
        data_dir=str(tmp_path),scheduler_enabled=False)
    store=Store(s.data_dir,s.encryption_key)
    google,inbox,brain=MagicMock(),MagicMock(),MagicMock()
    tasks=Tasks(s,store,google,inbox,brain)
    return s,store,google,inbox,brain,tasks

def plan(**kwargs):
    return {"answer":"Ready for your review.","reads":[],"proposals":[],**kwargs}

def test_multistep_contact_lookup_then_reviewed_send(setup):
    s,store,google,inbox,brain,tasks=setup
    google.contacts.return_value={"results":[{"email":"friend@example.com"}]}
    brain.complete_json.side_effect=[
        plan(reads=[{"tool":"contacts","query":"Friend"}]),
        plan(proposals=[{"kind":"send_email","payload":{
            "to":"friend@example.com","subject":"Lesson","body":"Would Friday work?"}}]),
    ]
    result=tasks.run(tasks.create("Look up Friend and prepare an email asking about Friday.")["id"])
    assert result["status"]=="awaiting_approval"
    assert result["turns"]==2
    google.contacts.assert_called_once_with("Friend")
    google.send.assert_not_called()
    a=store.action(result["action_ids"][0])
    assert a["state"]=="pending"
    context=brain.complete_json.call_args.args[1]
    assert "friend@example.com" in context["observations"][0]["result_data"]
    assert "owner_token" not in context and "google_credentials" not in context

def test_unknown_tools_are_not_executed(setup):
    *_,brain,tasks=setup
    brain.complete_json.return_value=plan(reads=[{"tool":"shell","query":"anything"}])
    result=tasks.run(tasks.create("Run a task")["id"])
    assert result["status"]=="needs_input"
    assert result["action_ids"]==[]

def test_planner_cannot_authorize_spending(setup):
    s,store,google,inbox,brain,tasks=setup
    brain.complete_json.return_value=plan(proposals=[{"kind":"inference_allowance","payload":{
        "model":"gpt-4o-mini","requests":100,"hours":24,
        "cost_notice":"I approve model charges for this bounded allowance"}}])
    result=tasks.run(tasks.create("Help me")["id"])
    assert result["status"]=="needs_input"
    assert store.get("inference_grant") is None
    assert result["action_ids"]==[]

def test_all_payloads_validated_before_any_action_is_created(setup):
    s,store,google,inbox,brain,tasks=setup
    brain.complete_json.return_value=plan(proposals=[
        {"kind":"send_email","payload":{"to":"friend@example.com","subject":"Hi","body":"Hello"}},
        {"kind":"send_email","payload":{"to":"not an email","subject":"Bad","body":"Rejected"}},
    ])
    result=tasks.run(tasks.create("Prepare messages")["id"])
    assert result["status"]=="needs_input" and store.actions()==[]

def test_paid_inference_block_does_not_fabricate_work(setup):
    s,store,google,inbox,brain,tasks=setup
    brain.complete_json.side_effect=PermissionError("No allowance")
    result=tasks.run(tasks.create("Help me")["id"])
    assert result["status"]=="blocked" and result["turns"]==0
    google.contacts.assert_not_called()
    google.send.assert_not_called()

def test_task_history_survives_restart(setup):
    s,store,google,inbox,brain,tasks=setup
    task=tasks.create("Remember this task")
    restarted=Tasks(s,Store(s.data_dir,s.encryption_key),google,inbox,brain)
    assert restarted.get(task["id"])["instruction"]=="Remember this task"

def test_pause_stops_task_execution(setup):
    s,store,google,inbox,brain,tasks=setup
    store.put("paused",True)
    task=tasks.run(tasks.create("Help me")["id"])
    assert task["status"]=="queued"
    brain.complete_json.assert_not_called()

def test_failed_or_uncertain_action_never_resumes_automatically(setup):
    s,store,google,inbox,brain,tasks=setup
    a=store.propose("send_email",{"to":"friend@example.com","subject":"Hello","body":"Hi"})
    store.approve(a["id"],a["digest"])
    store.claim(a["id"])
    store.finish(a["id"],"uncertain",{"error_type":"TimeoutError"})
    task=tasks.create("Send hello")
    task.update(status="awaiting_approval",action_ids=[a["id"]])
    tasks.save(task)
    tasks.tick()
    assert tasks.get(task["id"])["status"]=="needs_input"
    brain.complete_json.assert_not_called()

def test_successful_approved_step_can_resume(setup):
    s,store,google,inbox,brain,tasks=setup
    a=store.propose("send_email",{"to":"friend@example.com","subject":"Hello","body":"Hi"})
    store.approve(a["id"],a["digest"])
    store.claim(a["id"])
    store.finish(a["id"],"succeeded",{"id":"sent"})
    task=tasks.create("Prepare and send hello")
    task.update(status="awaiting_approval",action_ids=[a["id"]])
    tasks.save(task)
    brain.complete_json.return_value=plan(answer="The provider receipt reports the approved send succeeded.")
    tasks.tick()
    assert tasks.get(task["id"])["status"]=="ready"
    assert brain.complete_json.call_args.args[1]["action_receipts"][0]["state"]=="succeeded"
    google.send.assert_not_called()

def test_duplicate_proposal_is_not_recreated(setup):
    s,store,google,inbox,brain,tasks=setup
    p={"kind":"send_email","payload":{"to":"friend@example.com","subject":"Hello","body":"Hi"}}
    brain.complete_json.return_value=plan(proposals=[p])
    task=tasks.run(tasks.create("Prepare hello")["id"])
    tasks.continue_task(task["id"],"Review the same plan")
    result=tasks.run(task["id"])
    assert len(result["action_ids"])==1
    assert len(store.actions())==1

def test_calendar_read_requires_explicit_offsets_and_bounded_range(setup):
    *_,tasks=setup
    with pytest.raises(ValueError):
        tasks.read(ReadRequest(tool="calendar",start="2026-11-17T09:00:00",end="2026-11-17T10:00:00"))
    with pytest.raises(ValueError):
        tasks.read(ReadRequest(tool="calendar",start="2026-11-17T09:00:00Z",end="2027-01-17T10:00:00Z"))

def test_planning_turn_limit(setup):
    s,store,google,inbox,brain,tasks=setup
    task=tasks.create("Help")
    task["turns"]=8
    tasks.save(task)
    result=tasks.run(task["id"])
    assert result["status"]=="needs_input"
    brain.complete_json.assert_not_called()

def test_task_api_owner_only_and_plain_english(setup):
    s,store,google,inbox,brain,tasks=setup
    brain.complete_json.return_value=plan(answer="Here is a draft outline.")
    app=create_app(s,google_override=google,brain_override=brain)
    with TestClient(app,base_url=s.public_url) as client:
        assert client.get("/api/tasks").status_code==401
        assert client.post("/api/tasks",json={"instruction":"Draft an outline"}).status_code==401
        h={"Authorization":"Bearer "+s.owner_token}
        response=client.post("/api/tasks",json={"instruction":"Draft an outline"},headers=h)
        assert response.status_code==200 and response.json()["status"]=="ready"
        assert len(client.get("/api/tasks",headers=h).json())==1
        cap=client.get("/api/capabilities",headers=h).json()
        assert "code_execution" in cap["unavailable"]
