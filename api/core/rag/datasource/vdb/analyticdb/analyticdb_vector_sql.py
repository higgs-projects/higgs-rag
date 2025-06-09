import json
from contextlib import contextmanager
from typing import Any

import psycopg2.extras  # type: ignore
import psycopg2.pool  # type: ignore
from pydantic import BaseModel, model_validator

from core.rag.models.document import Document


class AnalyticdbVectorBySqlConfig(BaseModel):
    host: str
    port: int
    account: str
    account_password: str
    min_connection: int
    max_connection: int
    namespace: str = "dify"
    metrics: str = "cosine"

    @model_validator(mode="before")
    @classmethod
    def validate_config(cls, values: dict) -> dict:
        if not values["host"]:
            raise ValueError("config ANALYTICDB_HOST is required")
        if not values["port"]:
            raise ValueError("config ANALYTICDB_PORT is required")
        if not values["account"]:
            raise ValueError("config ANALYTICDB_ACCOUNT is required")
        if not values["account_password"]:
            raise ValueError("config ANALYTICDB_PASSWORD is required")
        if not values["min_connection"]:
            raise ValueError("config ANALYTICDB_MIN_CONNECTION is required")
        if not values["max_connection"]:
            raise ValueError("config ANALYTICDB_MAX_CONNECTION is required")
        if values["min_connection"] > values["max_connection"]:
            raise ValueError("config ANALYTICDB_MIN_CONNECTION should less than ANALYTICDB_MAX_CONNECTION")
        return values


class AnalyticdbVectorBySql:
    def __init__(self, collection_name: str, config: AnalyticdbVectorBySqlConfig):
        self._collection_name = collection_name.lower()
        self.databaseName = "knowledgebase"
        self.config = config
        self.table_name = f"{self.config.namespace}.{self._collection_name}"
        self.pool = self._create_connection_pool()

    def _create_connection_pool(self):
        return psycopg2.pool.SimpleConnectionPool(
            self.config.min_connection,
            self.config.max_connection,
            host=self.config.host,
            port=self.config.port,
            user=self.config.account,
            password=self.config.account_password,
            database=self.databaseName,
        )

    @contextmanager
    def _get_cursor(self):
        assert self.pool is not None, "Connection pool is not initialized"
        conn = self.pool.getconn()
        cur = conn.cursor()
        try:
            yield cur
        finally:
            cur.close()
            conn.commit()
            self.pool.putconn(conn)

    def search_by_hybrid(self, query: str, query_vector: list[float], **kwargs: Any) -> list[Document]:
        # TODO 修改为hybrid，现在不是
        top_k = kwargs.get("top_k", 4)
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError("top_k must be a positive integer")
        document_ids_filter = kwargs.get("document_ids_filter")
        where_clause = "WHERE 1=1"
        if document_ids_filter:
            document_ids = ", ".join(f"'{id}'" for id in document_ids_filter)
            where_clause += f"AND metadata_->>'document_id' IN ({document_ids})"
        score_threshold = float(kwargs.get("score_threshold") or 0.0)
        with self._get_cursor() as cur:
            query_vector_str = json.dumps(query_vector)
            query_vector_str = "{" + query_vector_str[1:-1] + "}"
            cur.execute(
                f"SELECT t.id AS id, t.vector AS vector, (1.0 - t.score) AS score, "
                f"t.page_content as page_content, t.metadata_ AS metadata_ "
                f"FROM (SELECT id, vector, page_content, metadata_, vector <=> %s AS score "
                f"FROM {self.table_name} {where_clause} ORDER BY score LIMIT {top_k} ) t",
                (query_vector_str,),
            )
            documents = []
            for record in cur:
                id, vector, score, page_content, metadata = record
                if score > score_threshold:
                    metadata["score"] = score
                    doc = Document(
                        page_content=page_content,
                        vector=vector,
                        metadata=metadata,
                    )
                    documents.append(doc)
        return documents
