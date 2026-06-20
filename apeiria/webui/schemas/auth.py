from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class MeResponse(BaseModel):
    user_id: str
    username: str


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)


class AccountCreate(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=8, max_length=128)


class AccountResponse(BaseModel):
    id: str
    username: str
    created_at: str


class ResetPasswordRequest(BaseModel):
    password: str = Field(min_length=8, max_length=128)


class MessageResponse(BaseModel):
    detail: str
