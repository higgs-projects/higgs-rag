from datetime import UTC, datetime, timedelta
from typing import cast

from werkzeug.exceptions import Unauthorized

from extensions.ext_database import db
from models.account import (
    Account,
    AccountStatus,
    TenantAccountJoin,
)


class AccountService:
    @staticmethod
    def load_user(user_id: str) -> None | Account:
        account = db.session.query(Account).filter_by(id=user_id).first()
        if not account:
            return None

        if account.status == AccountStatus.BANNED.value:
            raise Unauthorized("Account is banned.")

        current_tenant = db.session.query(TenantAccountJoin).filter_by(
            account_id=account.id, current=True).first()
        if current_tenant:
            account.set_tenant_id(current_tenant.tenant_id)
        else:
            available_ta = (
                db.session.query(TenantAccountJoin)
                .filter_by(account_id=account.id)
                .order_by(TenantAccountJoin.id.asc())
                .first()
            )
            if not available_ta:
                return None

            account.set_tenant_id(available_ta.tenant_id)
            available_ta.current = True
            db.session.commit()

        if datetime.now(UTC).replace(tzinfo=None) - account.last_active_at > timedelta(minutes=10):
            account.last_active_at = datetime.now(UTC).replace(tzinfo=None)
            db.session.commit()

        return cast(Account, account)

    @staticmethod
    def load_logged_in_account(*, account_id: str):
        return AccountService.load_user(account_id)
