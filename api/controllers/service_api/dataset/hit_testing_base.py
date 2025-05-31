import logging

from flask_login import current_user
from flask_restful import marshal, reqparse
from werkzeug.exceptions import Forbidden, InternalServerError, NotFound

from controllers.service_api.dataset.error import DatasetNotInitializedError
from controllers.service_api.error import (
    CompletionRequestError,
    ProviderModelCurrentlyNotSupportError,
    ProviderNotInitializeError,
    ProviderQuotaExceededError,
)
from core.errors.error import (
    LLMBadRequestError,
    ModelCurrentlyNotSupportError,
    ProviderTokenNotInitError,
    QuotaExceededError,
)
from core.model_runtime.errors.invoke import InvokeError
from services.dataset_service import DatasetService
from services.errors.account import NoPermissionError
from services.errors.index import IndexNotInitializedError
from services.hit_testing_service import HitTestingService


class DatasetsHitTestingBase:
    @staticmethod
    def get_and_validate_dataset(dataset_id: str):
        dataset = DatasetService.get_dataset(dataset_id)
        if dataset is None:
            raise NotFound("Dataset not found.")

        try:
            DatasetService.check_dataset_permission(dataset, current_user)
        except NoPermissionError as e:
            raise Forbidden(str(e))

        return dataset

    @staticmethod
    def hit_testing_args_check(args):
        HitTestingService.hit_testing_args_check(args)

    @staticmethod
    def parse_args():
        parser = reqparse.RequestParser()
        parser.add_argument("knowledge_id", type=str, location="json")
        parser.add_argument("query", type=str, location="json")
        parser.add_argument("retrieval_setting", type=dict, location="json")
        parser.add_argument("metadata_condition", type=dict, required=False, location="json")
        return parser.parse_args()

    @staticmethod
    def perform_hit_testing(dataset, args):
        try:
            response = HitTestingService.retrieve(
                dataset=dataset,
                query=args["query"],
                account=current_user,
                retrieval_setting=args["retrieval_setting"],
                metadata_condition=args["metadata_condition"],
            )
            return {"records": marshal(response["records"])}
        except IndexNotInitializedError:
            raise DatasetNotInitializedError()
        except ProviderTokenNotInitError as ex:
            raise ProviderNotInitializeError(ex.description)
        except QuotaExceededError:
            raise ProviderQuotaExceededError()
        except ModelCurrentlyNotSupportError:
            raise ProviderModelCurrentlyNotSupportError()
        except LLMBadRequestError:
            raise ProviderNotInitializeError(
                "No Embedding Model or Reranking Model available. Please configure a valid provider "
                "in the Settings -> Model Provider."
            )
        except InvokeError as e:
            raise CompletionRequestError(e.description)
        except ValueError as e:
            raise ValueError(str(e))
        except Exception as e:
            logging.exception("Hit testing failed.")
            raise InternalServerError(str(e))
