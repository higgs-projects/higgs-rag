import logging
from typing import Optional

from extensions.ext_database import db
from models.account import TenantAccountRole
from models.dataset import (
    Dataset,
    DatasetPermission,
    DatasetPermissionEnum,
)
from services.errors.account import NoPermissionError


class DatasetService:
    @staticmethod
    def get_dataset(dataset_id) -> Optional[Dataset]:
        dataset: Optional[Dataset] = db.session.query(Dataset).filter_by(id=dataset_id).first()
        return dataset

    @staticmethod
    def check_dataset_permission(dataset, user):
        if dataset.tenant_id != user.current_tenant_id:
            logging.debug(f"User {user.id} does not have permission to access dataset {dataset.id}")
            raise NoPermissionError("You do not have permission to access this dataset.")
        if user.current_role != TenantAccountRole.OWNER:
            if dataset.permission == DatasetPermissionEnum.ONLY_ME and dataset.created_by != user.id:
                logging.debug(f"User {user.id} does not have permission to access dataset {dataset.id}")
                raise NoPermissionError("You do not have permission to access this dataset.")
            if dataset.permission == DatasetPermissionEnum.PARTIAL_TEAM:
                # For partial team permission, user needs explicit permission or be the creator
                if dataset.created_by != user.id:
                    user_permission = (
                        db.session.query(DatasetPermission).filter_by(dataset_id=dataset.id, account_id=user.id).first()
                    )
                    if not user_permission:
                        logging.debug(f"User {user.id} does not have permission to access dataset {dataset.id}")
                        raise NoPermissionError("You do not have permission to access this dataset.")
