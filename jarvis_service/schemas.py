import re
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")

class Email(Strict):
    to: str = Field(max_length=254)
    subject: str = Field(max_length=300)
    body: str = Field(max_length=15000)
    thread_id: str | None = Field(default=None, pattern=r"^[a-zA-Z0-9_-]+$")
    in_reply_to: str | None = Field(default=None, max_length=500)

    @field_validator("to")
    @classmethod
    def email(cls, value):
        if not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+", value):
            raise ValueError("Use one explicit email address")
        return value

    @field_validator("subject", "in_reply_to")
    @classmethod
    def no_header_injection(cls, value):
        if value is not None and ("\r" in value or "\n" in value):
            raise ValueError("Header newlines are forbidden")
        return value

class Appointment(Strict):
    title: str = Field(min_length=1, max_length=200)
    start: datetime
    end: datetime
    attendee: str | None = None
    details: str = Field(default="", max_length=3000)

    @model_validator(mode="after")
    def valid_times(self):
        if not self.start.tzinfo or not self.end.tzinfo or self.end <= self.start:
            raise ValueError("Use offset-aware dates with end after start")
        if self.attendee:
            Email(to=self.attendee, subject="", body="")
        return self

class Call(Strict):
    to: str = Field(pattern=r"^\+[1-9]\d{7,14}$")
    purpose: str = Field(min_length=1, max_length=1500)
    max_seconds: int = Field(default=180, ge=30, le=600)
    model: str = Field(default="gpt-realtime", pattern=r"^[a-zA-Z0-9._-]{1,100}$")
    cost_notice: Literal["I approve Twilio and voice-model charges for this one call"]

class Receive(Call):
    pass

class Inference(Strict):
    model: str = Field(default="gpt-4o-mini", pattern=r"^[a-zA-Z0-9._-]{1,100}$")
    requests: int = Field(ge=1, le=100)
    hours: int = Field(ge=1, le=24)
    cost_notice: Literal["I approve model charges for this bounded allowance"]

class Proposal(Strict):
    kind: Literal["send_email", "save_draft", "create_appointment",
                  "place_call", "receive_call", "inference_allowance"]
    payload: dict

    def validated_payload(self):
        schema = {"send_email": Email, "save_draft": Email,
                  "create_appointment": Appointment, "place_call": Call,
                  "receive_call": Receive, "inference_allowance": Inference}[self.kind]
        return schema.model_validate(self.payload).model_dump(mode="json")

class Approval(Strict):
    digest: str = Field(pattern=r"^[a-f0-9]{64}$")

class Analysis(Strict):
    category: Literal["urgent", "action_needed", "personal", "newsletter", "other"]
    summary: str = Field(max_length=1200)
    suggested_reply: str = Field(max_length=3000)
