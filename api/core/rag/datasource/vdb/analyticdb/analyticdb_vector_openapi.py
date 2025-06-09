import json
from typing import Any, Optional

from pydantic import BaseModel, model_validator

_import_err_msg = (
    "`alibabacloud_gpdb20160503` and `alibabacloud_tea_openapi` packages not found, "
    "please run `pip install alibabacloud_gpdb20160503 alibabacloud_tea_openapi`"
)

from core.rag.models.document import Document


class AnalyticdbVectorOpenAPIConfig(BaseModel):
    access_key_id: str
    access_key_secret: str
    region_id: str
    instance_id: str
    account: str
    account_password: str
    namespace: str = "dify"
    namespace_password: Optional[str] = None
    metrics: str = "cosine"
    read_timeout: int = 60000

    @model_validator(mode="before")
    @classmethod
    def validate_config(cls, values: dict) -> dict:
        if not values["access_key_id"]:
            raise ValueError("config ANALYTICDB_KEY_ID is required")
        if not values["access_key_secret"]:
            raise ValueError("config ANALYTICDB_KEY_SECRET is required")
        if not values["region_id"]:
            raise ValueError("config ANALYTICDB_REGION_ID is required")
        if not values["instance_id"]:
            raise ValueError("config ANALYTICDB_INSTANCE_ID is required")
        if not values["account"]:
            raise ValueError("config ANALYTICDB_ACCOUNT is required")
        if not values["account_password"]:
            raise ValueError("config ANALYTICDB_PASSWORD is required")
        if not values["namespace_password"]:
            raise ValueError("config ANALYTICDB_NAMESPACE_PASSWORD is required")
        return values

    def to_analyticdb_client_params(self):
        return {
            "access_key_id": self.access_key_id,
            "access_key_secret": self.access_key_secret,
            "region_id": self.region_id,
            "read_timeout": self.read_timeout,
        }


class AnalyticdbVectorOpenAPI:
    def __init__(self, collection_name: str, config: AnalyticdbVectorOpenAPIConfig):
        try:
            from alibabacloud_gpdb20160503.client import Client  # type: ignore
            from alibabacloud_tea_openapi import models as open_api_models  # type: ignore
        except:
            raise ImportError(_import_err_msg)
        self._collection_name = collection_name.lower()
        self.config = config
        self._client_config = open_api_models.Config(user_agent="dify", **config.to_analyticdb_client_params())
        self._client = Client(self._client_config)

    def search_by_hybrid(self, query: str, query_vector: list[float], **kwargs: Any) -> list[Document]:
        from alibabacloud_gpdb20160503 import models as gpdb_20160503_models

        score_threshold = kwargs.get("score_threshold") or 0.0
        request = gpdb_20160503_models.QueryCollectionDataRequest(
            dbinstance_id=self.config.instance_id,
            region_id=self.config.region_id,
            namespace=self.config.namespace,
            namespace_password=self.config.namespace_password,
            collection=self._collection_name,
            include_values=kwargs.pop("include_values", True),
            metrics=self.config.metrics,
            vector=query_vector,
            content=None,
            top_k=kwargs.get("top_k", 4),
            filter=None,
        )
        response = self._client.query_collection_data(request)
        documents = []
        for match in response.body.matches.match:
            if match.score > score_threshold:
                metadata = json.loads(match.metadata.get("metadata_"))
                metadata["score"] = match.score
                doc = Document(
                    page_content=match.metadata.get("page_content"),
                    vector=match.values.value,
                    metadata=metadata,
                )
                documents.append(doc)
        documents = sorted(documents, key=lambda x: x.metadata["score"] if x.metadata else 0, reverse=True)
        return documents
