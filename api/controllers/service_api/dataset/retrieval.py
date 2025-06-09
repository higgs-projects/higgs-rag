import logging

from flask_login import current_user
from flask_restful import reqparse
from werkzeug.exceptions import Forbidden, InternalServerError, NotFound

from controllers.service_api import api
from controllers.service_api.dataset.error import DatasetNotInitializedError
from controllers.service_api.error import (
    CompletionRequestError,
    ProviderModelCurrentlyNotSupportError,
    ProviderNotInitializeError,
    ProviderQuotaExceededError,
)
from controllers.service_api.wraps import DatasetApiResource
from core.errors.error import (
    LLMBadRequestError,
    ModelCurrentlyNotSupportError,
    ProviderTokenNotInitError,
    QuotaExceededError,
)
from core.model_runtime.errors.invoke import InvokeError
from services.dataset_service import DatasetService
from services.errors.index import IndexNotInitializedError


class DatasetRetrievalApi(DatasetApiResource):
    def post(self, tenant_id):

        # 解析POST的数据
        parser = reqparse.RequestParser()
        parser.add_argument("knowledge_id", type=str, location="json")
        parser.add_argument("query", type=str, location="json")
        parser.add_argument("retrieval_setting", type=dict, location="json")
        parser.add_argument("metadata_condition", type=dict, required=False, location="json")
        args = parser.parse_args()
        
        # 校验与检查参数
        query = args["query"]

        if not query or len(query) > 500:
            raise ValueError("Query is required and cannot exceed 500 characters")

        dataset_id_str = str(args.get("knowledge_id"))

        dataset = DatasetService.get_dataset(dataset_id_str)
        if dataset is None:
            raise NotFound("Dataset not found.")

        try:
            response = DatasetService.retrieve(
                dataset=dataset,
                query=args["query"],
                account=current_user,
                retrieval_setting=args["retrieval_setting"],
                metadata_condition=args["metadata_condition"],
            )
            return {"records": response}
        
        except Forbidden as ex:
            raise Forbidden(ex)
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
            logging.exception("Dataset Retrieval failed.")
            raise InternalServerError(str(e))



api.add_resource(DatasetRetrievalApi, "/datasets/retrieval")
