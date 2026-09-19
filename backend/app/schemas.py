from typing import Literal
from pydantic import BaseModel, Field, field_validator

class Register(BaseModel):
    name: str = Field(min_length=1,max_length=80)
    email: str = Field(min_length=3,max_length=254)
    password: str = Field(min_length=10,max_length=128)
    @field_validator('name','email')
    @classmethod
    def trim(cls,v):
        if not v.strip(): raise ValueError('빈 값은 사용할 수 없어요.')
        return v.strip()
    @field_validator('email')
    @classmethod
    def email_valid(cls,v):
        if '@' not in v or '.' not in v.split('@')[-1]: raise ValueError('이메일 주소를 확인해 주세요.')
        return v.lower()
class Login(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=128)
class AlbumCreate(BaseModel):
    name: str = Field(min_length=1,max_length=120)
    description: str = Field(default='',max_length=2000)
    timezone: str = 'Asia/Seoul'
class AlbumPatch(BaseModel):
    name: str | None = Field(default=None,min_length=1,max_length=120)
    description: str | None = Field(default=None,max_length=2000)
    timezone: str | None = None
class Join(BaseModel):
    code: str = Field(min_length=4,max_length=100)
class PersonPatch(BaseModel):
    name: str | None = Field(default=None,min_length=1,max_length=80)
    user_id: str | None = None
class PeopleSet(BaseModel):
    person_ids: list[str] = Field(max_length=100)
class PhotoPatch(BaseModel):
    purpose: Literal['undecided','share','print','keep','exclude','social','memory','profile','게시용','인화용','보관용','게시 제외'] | None = None
    selected: bool | None = None
    note: str | None = Field(default=None,max_length=4000)
class RenderSettings(BaseModel):
    brightness: float = Field(default=1,ge=0.25,le=2,allow_inf_nan=False)
    saturation: float = Field(default=1,ge=0,le=2,allow_inf_nan=False)
class VersionCreate(RenderSettings):
    name: str = Field(min_length=1,max_length=120)
    parent_id: str | None = None
class ReviewRequest(BaseModel):
    confirmed: bool
class CommentCreate(BaseModel):
    body: str = Field(min_length=1,max_length=4000)
    kind: Literal['comment','change_request'] = 'comment'
HEX_COLOR = r'^#[0-9a-fA-F]{6}$'
class LabelCreate(BaseModel):
    name: str = Field(min_length=1,max_length=40)
    color: str = Field(default='#2563eb',pattern=HEX_COLOR)
class LabelPatch(BaseModel):
    name: str | None = Field(default=None,min_length=1,max_length=40)
    color: str | None = Field(default=None,pattern=HEX_COLOR)
class LabelsSet(BaseModel):
    label_ids: list[str] = Field(default_factory=list,max_length=60)
class GroupPatch(BaseModel):
    name: str | None = Field(default=None,min_length=1,max_length=80)
    person_id: str | None = None
class GroupMerge(BaseModel):
    group_ids: list[str] = Field(min_length=2,max_length=100)
class GroupSplit(BaseModel):
    face_ids: list[str] = Field(min_length=1,max_length=10000)
