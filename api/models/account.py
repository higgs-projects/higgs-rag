import enum
import json
from typing import Optional, cast

from flask_login import UserMixin  # type: ignore
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column, reconstructor

from models.base import Base

from .engine import db
from .types import StringUUID


class TenantAccountRole(enum.StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    EDITOR = "editor"
    NORMAL = "normal"
    DATASET_OPERATOR = "dataset_operator"

    @staticmethod
    def is_valid_role(role: str) -> bool:
        if not role:
            return False
        return role in {
            TenantAccountRole.OWNER,
            TenantAccountRole.ADMIN,
            TenantAccountRole.EDITOR,
            TenantAccountRole.NORMAL,
            TenantAccountRole.DATASET_OPERATOR,
        }

    @staticmethod
    def is_privileged_role(role: Optional["TenantAccountRole"]) -> bool:
        if not role:
            return False
        return role in {TenantAccountRole.OWNER, TenantAccountRole.ADMIN}

    @staticmethod
    def is_admin_role(role: Optional["TenantAccountRole"]) -> bool:
        if not role:
            return False
        return role == TenantAccountRole.ADMIN

    @staticmethod
    def is_non_owner_role(role: Optional["TenantAccountRole"]) -> bool:
        if not role:
            return False
        return role in {
            TenantAccountRole.ADMIN,
            TenantAccountRole.EDITOR,
            TenantAccountRole.NORMAL,
            TenantAccountRole.DATASET_OPERATOR,
        }

    @staticmethod
    def is_editing_role(role: Optional["TenantAccountRole"]) -> bool:
        if not role:
            return False
        return role in {TenantAccountRole.OWNER, TenantAccountRole.ADMIN, TenantAccountRole.EDITOR}

    @staticmethod
    def is_dataset_edit_role(role: Optional["TenantAccountRole"]) -> bool:
        if not role:
            return False
        return role in {
            TenantAccountRole.OWNER,
            TenantAccountRole.ADMIN,
            TenantAccountRole.EDITOR,
            TenantAccountRole.DATASET_OPERATOR,
        }


class AccountStatus(enum.StrEnum):
    PENDING = "pending"
    UNINITIALIZED = "uninitialized"
    ACTIVE = "active"
    BANNED = "banned"
    CLOSED = "closed"


class Account(UserMixin, Base):
    __tablename__ = "accounts"
    __table_args__ = (db.PrimaryKeyConstraint("id", name="account_pkey"), db.Index("account_email_idx", "email"))

    id: Mapped[str] = mapped_column(StringUUID, server_default=db.text("uuid_generate_v4()"))
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    password = db.Column(db.String(255), nullable=True)
    password_salt = db.Column(db.String(255), nullable=True)
    avatar = db.Column(db.String(255))
    interface_language = db.Column(db.String(255))
    interface_theme = db.Column(db.String(255))
    timezone = db.Column(db.String(255))
    last_login_at = db.Column(db.DateTime)
    last_login_ip = db.Column(db.String(255))
    last_active_at = db.Column(db.DateTime, nullable=False, server_default=func.current_timestamp())
    status = db.Column(db.String(16), nullable=False, server_default=db.text("'active'::character varying"))
    initialized_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = db.Column(db.DateTime, nullable=False, server_default=func.current_timestamp())

    @reconstructor
    def init_on_load(self):
        self.role: Optional[TenantAccountRole] = None
        self._current_tenant: Optional[Tenant] = None

    @property
    def is_password_set(self):
        return self.password is not None

    @property
    def current_tenant(self):
        return self._current_tenant

    @current_tenant.setter
    def current_tenant(self, tenant: "Tenant"):
        ta = db.session.query(TenantAccountJoin).filter_by(tenant_id=tenant.id, account_id=self.id).first()
        if ta:
            self.role = TenantAccountRole(ta.role)
            self._current_tenant = tenant
            return
        self._current_tenant = None

    @property
    def current_tenant_id(self) -> str | None:
        return self._current_tenant.id if self._current_tenant else None

    def set_tenant_id(self, tenant_id: str):
        tenant_account_join = cast(
            tuple[Tenant, TenantAccountJoin],
            (
                db.session.query(Tenant, TenantAccountJoin)
                .filter(Tenant.id == tenant_id)
                .filter(TenantAccountJoin.tenant_id == Tenant.id)
                .filter(TenantAccountJoin.account_id == self.id)
                .one_or_none()
            ),
        )

        if not tenant_account_join:
            return

        tenant, join = tenant_account_join
        self.role = join.role
        self._current_tenant = tenant

    @property
    def current_role(self):
        return self.role

    def get_status(self) -> AccountStatus:
        status_str = self.status
        return AccountStatus(status_str)

    @classmethod
    def get_by_openid(cls, provider: str, open_id: str):
        account_integrate = (
            db.session.query(AccountIntegrate)
            .filter(AccountIntegrate.provider == provider, AccountIntegrate.open_id == open_id)
            .one_or_none()
        )
        if account_integrate:
            return db.session.query(Account).filter(Account.id == account_integrate.account_id).one_or_none()
        return None

    # check current_user.current_tenant.current_role in ['admin', 'owner']
    @property
    def is_admin_or_owner(self):
        return TenantAccountRole.is_privileged_role(self.role)

    @property
    def is_admin(self):
        return TenantAccountRole.is_admin_role(self.role)

    @property
    def is_editor(self):
        return TenantAccountRole.is_editing_role(self.role)

    @property
    def is_dataset_editor(self):
        return TenantAccountRole.is_dataset_edit_role(self.role)

    @property
    def is_dataset_operator(self):
        return self.role == TenantAccountRole.DATASET_OPERATOR


class TenantStatus(enum.StrEnum):
    NORMAL = "normal"
    ARCHIVE = "archive"


class Tenant(Base):
    __tablename__ = "tenants"
    __table_args__ = (db.PrimaryKeyConstraint("id", name="tenant_pkey"),)

    id = db.Column(StringUUID, server_default=db.text("uuid_generate_v4()"))
    name = db.Column(db.String(255), nullable=False)
    encrypt_public_key = db.Column(db.Text)
    plan = db.Column(db.String(255), nullable=False, server_default=db.text("'basic'::character varying"))
    status = db.Column(db.String(255), nullable=False, server_default=db.text("'normal'::character varying"))
    custom_config = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = db.Column(db.DateTime, nullable=False, server_default=func.current_timestamp())

    def get_accounts(self) -> list[Account]:
        return (
            db.session.query(Account)
            .filter(Account.id == TenantAccountJoin.account_id, TenantAccountJoin.tenant_id == self.id)
            .all()
        )

    @property
    def custom_config_dict(self) -> dict:
        return json.loads(self.custom_config) if self.custom_config else {}

    @custom_config_dict.setter
    def custom_config_dict(self, value: dict):
        self.custom_config = json.dumps(value)


class TenantAccountJoin(Base):
    __tablename__ = "tenant_account_joins"
    __table_args__ = (
        db.PrimaryKeyConstraint("id", name="tenant_account_join_pkey"),
        db.Index("tenant_account_join_account_id_idx", "account_id"),
        db.Index("tenant_account_join_tenant_id_idx", "tenant_id"),
        db.UniqueConstraint("tenant_id", "account_id", name="unique_tenant_account_join"),
    )

    id = db.Column(StringUUID, server_default=db.text("uuid_generate_v4()"))
    tenant_id = db.Column(StringUUID, nullable=False)
    account_id = db.Column(StringUUID, nullable=False)
    current = db.Column(db.Boolean, nullable=False, server_default=db.text("false"))
    role = db.Column(db.String(16), nullable=False, server_default="normal")
    invited_by = db.Column(StringUUID, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = db.Column(db.DateTime, nullable=False, server_default=func.current_timestamp())


class AccountIntegrate(Base):
    __tablename__ = "account_integrates"
    __table_args__ = (
        db.PrimaryKeyConstraint("id", name="account_integrate_pkey"),
        db.UniqueConstraint("account_id", "provider", name="unique_account_provider"),
        db.UniqueConstraint("provider", "open_id", name="unique_provider_open_id"),
    )

    id = db.Column(StringUUID, server_default=db.text("uuid_generate_v4()"))
    account_id = db.Column(StringUUID, nullable=False)
    provider = db.Column(db.String(16), nullable=False)
    open_id = db.Column(db.String(255), nullable=False)
    encrypted_token = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = db.Column(db.DateTime, nullable=False, server_default=func.current_timestamp())
