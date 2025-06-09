from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .engine import db
from .enums import CreatorUserRole
from .types import StringUUID


class ApiToken(Base):
    __tablename__ = "api_tokens"
    __table_args__ = (
        db.PrimaryKeyConstraint("id", name="api_token_pkey"),
        db.Index("api_token_app_id_type_idx", "app_id", "type"),
        db.Index("api_token_token_idx", "token", "type"),
        db.Index("api_token_tenant_idx", "tenant_id", "type"),
    )

    id = db.Column(StringUUID, server_default=db.text("uuid_generate_v4()"))
    app_id = db.Column(StringUUID, nullable=True)
    tenant_id = db.Column(StringUUID, nullable=True)
    type = db.Column(db.String(16), nullable=False)
    token = db.Column(db.String(255), nullable=False)
    last_used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, server_default=func.current_timestamp())


class UploadFile(Base):
    __tablename__ = "upload_files"
    __table_args__ = (
        db.PrimaryKeyConstraint("id", name="upload_file_pkey"),
        db.Index("upload_file_tenant_idx", "tenant_id"),
    )

    id: Mapped[str] = db.Column(StringUUID, server_default=db.text("uuid_generate_v4()"))
    tenant_id: Mapped[str] = db.Column(StringUUID, nullable=False)
    storage_type: Mapped[str] = db.Column(db.String(255), nullable=False)
    key: Mapped[str] = db.Column(db.String(255), nullable=False)
    name: Mapped[str] = db.Column(db.String(255), nullable=False)
    size: Mapped[int] = db.Column(db.Integer, nullable=False)
    extension: Mapped[str] = db.Column(db.String(255), nullable=False)
    mime_type: Mapped[str] = db.Column(db.String(255), nullable=True)
    created_by_role: Mapped[str] = db.Column(
        db.String(255), nullable=False, server_default=db.text("'account'::character varying")
    )
    created_by: Mapped[str] = db.Column(StringUUID, nullable=False)
    created_at: Mapped[datetime] = db.Column(db.DateTime, nullable=False, server_default=func.current_timestamp())
    used: Mapped[bool] = db.Column(db.Boolean, nullable=False, server_default=db.text("false"))
    used_by: Mapped[str | None] = db.Column(StringUUID, nullable=True)
    used_at: Mapped[datetime | None] = db.Column(db.DateTime, nullable=True)
    hash: Mapped[str | None] = db.Column(db.String(255), nullable=True)
    source_url: Mapped[str] = mapped_column(sa.TEXT, default="")

    def __init__(
        self,
        *,
        tenant_id: str,
        storage_type: str,
        key: str,
        name: str,
        size: int,
        extension: str,
        mime_type: str,
        created_by_role: CreatorUserRole,
        created_by: str,
        created_at: datetime,
        used: bool,
        used_by: str | None = None,
        used_at: datetime | None = None,
        hash: str | None = None,
        source_url: str = "",
    ):
        self.tenant_id = tenant_id
        self.storage_type = storage_type
        self.key = key
        self.name = name
        self.size = size
        self.extension = extension
        self.mime_type = mime_type
        self.created_by_role = created_by_role.value
        self.created_by = created_by
        self.created_at = created_at
        self.used = used
        self.used_by = used_by
        self.used_at = used_at
        self.hash = hash
        self.source_url = source_url