from datetime import UTC, datetime, timedelta
from enum import Enum
from functools import wraps

from flask import current_app, request
from flask_login import user_logged_in  # type: ignore
from flask_restful import Resource
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from werkzeug.exceptions import Unauthorized

from extensions.ext_database import db
from models.account import Account, Tenant, TenantAccountJoin, TenantStatus
from models.model import ApiToken


class WhereisUserArg(Enum):
    """
    Enum for whereis_user_arg.
    """

    QUERY = "query"
    JSON = "json"
    FORM = "form"


class FetchUserArg(BaseModel):
    fetch_from: WhereisUserArg
    required: bool = False


def validate_dataset_token(view=None):
    def decorator(view):
        @wraps(view)
        def decorated(*args, **kwargs):
            api_token = validate_and_get_api_token("dataset")
            tenant_account_join = (
                db.session.query(Tenant, TenantAccountJoin)
                .filter(Tenant.id == api_token.tenant_id)
                .filter(TenantAccountJoin.tenant_id == Tenant.id)
                .filter(TenantAccountJoin.role.in_(["owner"]))
                .filter(Tenant.status == TenantStatus.NORMAL)
                .one_or_none()
            )  # TODO: only owner information is required, so only one is returned.
            if tenant_account_join:
                tenant, ta = tenant_account_join
                account = db.session.query(Account).filter(Account.id == ta.account_id).first()
                # Login admin
                if account:
                    account.current_tenant = tenant
                    current_app.login_manager._update_request_context_with_user(account)  # type: ignore
                    user_logged_in.send(current_app._get_current_object(), user=account)  # type: ignore
                else:
                    raise Unauthorized("Tenant owner account does not exist.")
            else:
                raise Unauthorized("Tenant does not exist.")
            return view(api_token.tenant_id, *args, **kwargs)

        return decorated

    if view:
        return decorator(view)

    # if view is None, it means that the decorator is used without parentheses
    # use the decorator as a function for method_decorators
    return decorator


def validate_and_get_api_token(scope: str | None = None):
    """
    Validate and get API token.
    """
    auth_header = request.headers.get("Authorization")
    if auth_header is None or " " not in auth_header:
        raise Unauthorized("Authorization header must be provided and start with 'Bearer'")

    auth_scheme, auth_token = auth_header.split(None, 1)
    auth_scheme = auth_scheme.lower()

    if auth_scheme != "bearer":
        raise Unauthorized("Authorization scheme must be 'Bearer'")

    current_time = datetime.now(UTC).replace(tzinfo=None)
    cutoff_time = current_time - timedelta(minutes=1)
    with Session(db.engine, expire_on_commit=False) as session:
        # update_stmt = (
        #     update(ApiToken)
        #     .where(
        #         ApiToken.token == auth_token,
        #         (ApiToken.last_used_at.is_(None) | (ApiToken.last_used_at < cutoff_time)),
        #         ApiToken.type == scope,
        #     )
        #     .values(last_used_at=current_time)
        #     .returning(ApiToken)
        # )
        # result = session.execute(update_stmt)
        # api_token = result.scalar_one_or_none()
        api_token = None
        if not api_token:
            stmt = select(ApiToken).where(ApiToken.token == auth_token, ApiToken.type == scope)
            api_token = session.scalar(stmt)
            if not api_token:
                raise Unauthorized("Access token is invalid")
        else:
            session.commit()

    return api_token


class DatasetApiResource(Resource):
    method_decorators = [validate_dataset_token]
