import logging
import time
from typing import Any, Optional

from sqlalchemy import Float, and_, or_, text
from sqlalchemy import cast as sqlalchemy_cast

from core.rag.datasource.retrieval_service import RetrievalService
from core.rag.entities.metadata_entities import Condition
from core.rag.models.document import Document
from extensions.ext_database import db
from models.account import Account
from models.dataset import Dataset, Document as DatabaseDocument


class HitTestingService:
    @classmethod
    def retrieve(
        cls,
        dataset: Dataset,
        query: str,
        account: Account,
        retrieval_setting: dict,  # FIXME drop this any
        metadata_condition: dict,
    ) -> list[dict[str, Any]]:
        start = time.perf_counter()

        all_documents = RetrievalService.retrieve(
            dataset_id=dataset.id,
            query=query,
            top_k=retrieval_setting.get("top_k", 2),
            score_threshold=retrieval_setting.get("score_threshold", 0.0),
            document_ids_filter=cls.get_document_id_filter(
                dataset.id, metadata_condition),
        )

        end = time.perf_counter()
        logging.debug(f"Hit testing retrieve in {end - start:0.4f} seconds")

        return cls.format_retrieve_response(query, all_documents)

    @classmethod
    def format_retrieve_response(cls, query: str, documents: list[Document]) -> list[dict[str, Any]]:
        retrieval_resource_list = []
        records = RetrievalService.format_retrieval_documents(documents)
        if records:
            for record in records:
                segment = record.segment
                dataset = db.session.query(Dataset).filter_by(
                    id=segment.dataset_id).first()  # type: ignore
                database_document = (
                    db.session.query(DatabaseDocument)
                    .filter(
                        DatabaseDocument.id == segment.document_id,
                        DatabaseDocument.enabled == True,
                        DatabaseDocument.archived == False,
                    )
                    .first()
                )
                if dataset and database_document:
                    source = {
                        "metadata": {
                            "_source": "knowledge",
                            "dataset_id": dataset.id,
                            "dataset_name": dataset.name,
                            "document_id": database_document.id,
                            "document_name": database_document.name,
                            "data_source_type": database_document.data_source_type,
                            "segment_id": segment.id,
                            "retriever_from": "external",
                            "segment_hit_count": segment.hit_count,
                            "segment_word_count": segment.word_count,
                            "segment_position": segment.position,
                            "segment_index_node_hash": segment.index_node_hash,
                            "doc_metadata": database_document.doc_metadata,
                        },
                        "title": database_document.name,
                        "score": record.score or 0.0,
                    }
                    if segment.answer:
                        source["content"] = f"question:{segment.get_sign_content()} \nanswer:{segment.answer}"
                    else:
                        source["content"] = segment.get_sign_content()
                    retrieval_resource_list.append(source)
        if retrieval_resource_list:
            retrieval_resource_list = sorted(
                retrieval_resource_list,
                key=lambda x: x["score"] if x.get(
                    "score") is not None else 0.0,
                reverse=True,
            )
            for position, item in enumerate(retrieval_resource_list, start=1):
                item["metadata"]["position"] = position
        return retrieval_resource_list

    @classmethod
    def get_document_id_filter(cls, dataset_id: str, metadata_condition: dict) -> list[str]:
        """Get document id filter from metadata condition."""
        from models.dataset import Document

        document_query = db.session.query(Document).filter(
            Document.dataset_id == dataset_id,
            Document.indexing_status == "completed",
            Document.enabled == True,
            Document.archived == False,
        )

        filters = []  # type: ignore
        if metadata_condition:
            conditions = []
            if metadata_condition:
                # type: ignore
                for sequence, condition in enumerate(metadata_condition):
                    metadata_name = condition.name
                    expected_value = condition.value
                    conditions.append(
                        Condition(
                            name=metadata_name,
                            comparison_operator=condition.comparison_operator,
                            value=expected_value,
                        )
                    )
                    filters = cls._process_metadata_filter_func(
                        sequence,
                        condition.comparison_operator,
                        metadata_name,
                        expected_value,
                        filters,
                    )

        if filters:
            if metadata_condition and metadata_condition.logical_operator == "and":  # type: ignore
                document_query = document_query.filter(and_(*filters))
            else:
                document_query = document_query.filter(or_(*filters))

            documents = document_query.all()
            return [document.id for document in documents]
        return None

    @classmethod
    def _process_metadata_filter_func(
        cls, sequence: int, condition: str, metadata_name: str, value: Optional[Any], filters: list
    ):
        key = f"{metadata_name}_{sequence}"
        key_value = f"{metadata_name}_{sequence}_value"
        match condition:
            case "contains":
                filters.append(
                    (text(f"documents.doc_metadata ->> :{key} LIKE :{key_value}")).params(
                        **{key: metadata_name, key_value: f"%{value}%"}
                    )
                )
            case "not contains":
                filters.append(
                    (text(f"documents.doc_metadata ->> :{key} NOT LIKE :{key_value}")).params(
                        **{key: metadata_name, key_value: f"%{value}%"}
                    )
                )
            case "start with":
                filters.append(
                    (text(f"documents.doc_metadata ->> :{key} LIKE :{key_value}")).params(
                        **{key: metadata_name, key_value: f"{value}%"}
                    )
                )
            case "end with":
                filters.append(
                    (text(f"documents.doc_metadata ->> :{key} LIKE :{key_value}")).params(
                        **{key: metadata_name, key_value: f"%{value}"}
                    )
                )
            case "=" | "is":
                if isinstance(value, str):
                    filters.append(
                        Document.doc_metadata[metadata_name] == f'"{value}"')
                else:
                    filters.append(sqlalchemy_cast(
                        Document.doc_metadata[metadata_name].astext, Float) == value)
            case "is not" | "≠":
                if isinstance(value, str):
                    filters.append(
                        Document.doc_metadata[metadata_name] != f'"{value}"')
                else:
                    filters.append(sqlalchemy_cast(
                        Document.doc_metadata[metadata_name].astext, Float) != value)
            case "empty":
                filters.append(Document.doc_metadata[metadata_name].is_(None))
            case "not empty":
                filters.append(
                    Document.doc_metadata[metadata_name].isnot(None))
            case "before" | "<":
                filters.append(sqlalchemy_cast(
                    Document.doc_metadata[metadata_name].astext, Float) < value)
            case "after" | ">":
                filters.append(sqlalchemy_cast(
                    Document.doc_metadata[metadata_name].astext, Float) > value)
            case "≤" | "<=":
                filters.append(sqlalchemy_cast(
                    Document.doc_metadata[metadata_name].astext, Float) <= value)
            case "≥" | ">=":
                filters.append(sqlalchemy_cast(
                    Document.doc_metadata[metadata_name].astext, Float) >= value)
            case _:
                pass
        return filters

    @classmethod
    def hit_testing_args_check(cls, args):
        query = args["query"]

        if not query or len(query) > 500:
            raise ValueError(
                "Query is required and cannot exceed 500 characters")
