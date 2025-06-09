import json
from typing import Any, Optional

import requests
import weaviate  # type: ignore
from pydantic import BaseModel, model_validator

from configs import dify_config
from core.rag.datasource.vdb.vector_base import BaseVector
from core.rag.datasource.vdb.vector_factory import AbstractVectorFactory
from core.rag.datasource.vdb.vector_type import VectorType
from core.rag.embedding.embedding_base import Embeddings
from core.rag.models.document import Document
from models.dataset import Dataset


class WeaviateConfig(BaseModel):
    endpoint: str
    api_key: Optional[str] = None
    batch_size: int = 100

    @model_validator(mode="before")
    @classmethod
    def validate_config(cls, values: dict) -> dict:
        if not values["endpoint"]:
            raise ValueError("config WEAVIATE_ENDPOINT is required")
        return values


class WeaviateVector(BaseVector):
    def __init__(self, collection_name: str, config: WeaviateConfig, attributes: list):
        super().__init__(collection_name)
        self._client = self._init_client(config)
        self._attributes = attributes

    def _init_client(self, config: WeaviateConfig) -> weaviate.Client:
        auth_config = weaviate.auth.AuthApiKey(api_key=config.api_key)

        weaviate.connect.connection.has_grpc = False

        try:
            client = weaviate.Client(
                url=config.endpoint, auth_client_secret=auth_config, timeout_config=(5, 60), startup_period=None
            )
        except requests.exceptions.ConnectionError:
            raise ConnectionError("Vector database connection error")

        client.batch.configure(
            # `batch_size` takes an `int` value to enable auto-batching
            # (`None` is used for manual batching)
            batch_size=config.batch_size,
            # dynamically update the `batch_size` based on import speed
            dynamic=True,
            # `timeout_retries` takes an `int` value to retry on time outs
            timeout_retries=3,
        )

        return client

    def get_type(self) -> str:
        return VectorType.WEAVIATE

    def search_by_hybrid(self, query: str, query_vector: list[float], **kwargs: Any) -> list[Document]:
        # TODO 实现
        raise NotImplementedError


class WeaviateVectorFactory(AbstractVectorFactory):
    def init_vector(self, dataset: Dataset, attributes: list, embeddings: Embeddings) -> WeaviateVector:
        if dataset.index_struct_dict:
            class_prefix: str = dataset.index_struct_dict["vector_store"]["class_prefix"]
            collection_name = class_prefix
        else:
            dataset_id = dataset.id
            collection_name = Dataset.gen_collection_name_by_id(dataset_id)
            dataset.index_struct = json.dumps(self.gen_index_struct_dict(VectorType.WEAVIATE, collection_name))

        return WeaviateVector(
            collection_name=collection_name,
            config=WeaviateConfig(
                endpoint=dify_config.WEAVIATE_ENDPOINT or "",
                api_key=dify_config.WEAVIATE_API_KEY,
                batch_size=dify_config.WEAVIATE_BATCH_SIZE,
            ),
            attributes=attributes,
        )
