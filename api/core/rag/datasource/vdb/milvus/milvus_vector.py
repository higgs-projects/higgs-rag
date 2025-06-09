import json
import logging
from typing import Any, Optional

from packaging import version
from pydantic import BaseModel, model_validator
from pymilvus import AnnSearchRequest, MilvusClient, WeightedRanker  # type: ignore

from configs import dify_config
from core.rag.datasource.vdb.field import Field
from core.rag.datasource.vdb.vector_base import BaseVector
from core.rag.datasource.vdb.vector_factory import AbstractVectorFactory
from core.rag.datasource.vdb.vector_type import VectorType
from core.rag.embedding.embedding_base import Embeddings
from core.rag.models.document import Document
from models.dataset import Dataset

logger = logging.getLogger(__name__)


class MilvusConfig(BaseModel):
    """
    Configuration class for Milvus connection.
    """

    uri: str  # Milvus server URI
    token: Optional[str] = None  # Optional token for authentication
    user: Optional[str] = None  # Username for authentication
    password: Optional[str] = None  # Password for authentication
    batch_size: int = 100  # Batch size for operations
    database: str = "default"  # Database name
    enable_hybrid_search: bool = False  # Flag to enable hybrid search
    analyzer_params: Optional[str] = None  # Analyzer params

    @model_validator(mode="before")
    @classmethod
    def validate_config(cls, values: dict) -> dict:
        """
        Validate the configuration values.
        Raises ValueError if required fields are missing.
        """
        if not values.get("uri"):
            raise ValueError("config MILVUS_URI is required")
        if not values.get("token"):
            if not values.get("user"):
                raise ValueError("config MILVUS_USER is required")
            if not values.get("password"):
                raise ValueError("config MILVUS_PASSWORD is required")
        return values

    def to_milvus_params(self):
        """
        Convert the configuration to a dictionary of Milvus connection parameters.
        """
        return {
            "uri": self.uri,
            "token": self.token,
            "user": self.user,
            "password": self.password,
            "db_name": self.database,
            "analyzer_params": self.analyzer_params,
        }


class MilvusVector(BaseVector):
    """
    Milvus vector storage implementation.
    """

    def __init__(self, collection_name: str, config: MilvusConfig):
        super().__init__(collection_name)
        self._client_config = config
        self._client = self._init_client(config)
        self._consistency_level = "Session"  # Consistency level for Milvus operations
        # Check if hybrid search is supported
        self._hybrid_search_enabled = self._check_hybrid_search_support()

    def _check_hybrid_search_support(self) -> bool:
        """
        Check if the current Milvus version supports hybrid search.
        Returns True if the version is >= 2.5.0, otherwise False.
        """
        if not self._client_config.enable_hybrid_search:
            return False

        try:
            milvus_version = self._client.get_server_version()
            return version.parse(milvus_version).base_version >= version.parse("2.5.0").base_version
        except Exception as e:
            logger.warning(f"Failed to check Milvus version: {str(e)}. Disabling hybrid search.")
            return False

    def get_type(self) -> str:
        """
        Get the type of vector storage (Milvus).
        """
        return VectorType.MILVUS

    def _process_search_results(
        self, results: list[Any], output_fields: list[str], score_threshold: float = 0.0
    ) -> list[Document]:
        """
        Common method to process search results

        :param results: Search results
        :param output_fields: Fields to be output
        :param score_threshold: Score threshold for filtering
        :return: List of documents
        """
        docs = []
        for result in results[0]:
            metadata = result["entity"].get(output_fields[1], {})
            metadata["score"] = result["distance"]

            if result["distance"] > score_threshold:
                doc = Document(page_content=result["entity"].get(output_fields[0], ""), metadata=metadata)
                docs.append(doc)

        return docs

    def search_by_hybrid(self, query: str, query_vector: list[float], **kwargs: Any) -> list[Document]:
        """
        Search for documents by vector similarity.
        """
        document_ids_filter = kwargs.get("document_ids_filter")
        filter = ""
        if document_ids_filter:
            document_ids = ", ".join(f'"{id}"' for id in document_ids_filter)
            filter = f'metadata["document_id"] in [{document_ids}]'

        # Set up BM25 search request
        sparse_request = AnnSearchRequest(
            [query],
            Field.SPARSE_VECTOR.value,
            {"metric_type": "BM25"},
            limit=kwargs.get("top_k", 4),
            expr=filter,
        )

        # Set up dense vector search request
        dense_request = AnnSearchRequest(
            [query_vector],
            Field.VECTOR.value,
            {"metric_type": "IP"},
            limit=kwargs.get("top_k", 4),
            expr=filter,
        )

        results = self._client.hybrid_search(
            collection_name=self._collection_name,
            reqs=[sparse_request, dense_request],
            ranker=WeightedRanker(0.3, 0.7),
            limit=kwargs.get("top_k", 4),
            output_fields=[Field.CONTENT_KEY.value, Field.METADATA_KEY.value],
        )

        return self._process_search_results(
            results,
            output_fields=[Field.CONTENT_KEY.value, Field.METADATA_KEY.value],
            score_threshold=float(kwargs.get("score_threshold") or 0.0),
        )

    def _init_client(self, config: MilvusConfig) -> MilvusClient:
        """
        Initialize and return a Milvus client.
        """
        if config.token:
            client = MilvusClient(uri=config.uri, token=config.token, db_name=config.database)
        else:
            client = MilvusClient(uri=config.uri, user=config.user, password=config.password, db_name=config.database)
        return client


class MilvusVectorFactory(AbstractVectorFactory):
    """
    Factory class for creating MilvusVector instances.
    """

    def init_vector(self, dataset: Dataset, attributes: list, embeddings: Embeddings) -> MilvusVector:
        """
        Initialize a MilvusVector instance for the given dataset.
        """
        if dataset.index_struct_dict:
            class_prefix: str = dataset.index_struct_dict["vector_store"]["class_prefix"]
            collection_name = class_prefix
        else:
            dataset_id = dataset.id
            collection_name = Dataset.gen_collection_name_by_id(dataset_id)
            dataset.index_struct = json.dumps(self.gen_index_struct_dict(VectorType.MILVUS, collection_name))

        return MilvusVector(
            collection_name=collection_name,
            config=MilvusConfig(
                uri=dify_config.MILVUS_URI or "",
                token=dify_config.MILVUS_TOKEN or "",
                user=dify_config.MILVUS_USER or "",
                password=dify_config.MILVUS_PASSWORD or "",
                database=dify_config.MILVUS_DATABASE or "",
                enable_hybrid_search=dify_config.MILVUS_ENABLE_HYBRID_SEARCH or False,
                analyzer_params=dify_config.MILVUS_ANALYZER_PARAMS or "",
            ),
        )
