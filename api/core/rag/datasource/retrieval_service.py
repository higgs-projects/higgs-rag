from typing import Optional

from sqlalchemy.orm import load_only

from core.rag.datasource.vdb.vector_factory import Vector
from core.rag.embedding.retrieval import RetrievalSegments
from core.rag.index_processor.constant.index_type import IndexType
from core.rag.models.document import Document
from extensions.ext_database import db
from models.dataset import ChildChunk, Dataset, DocumentSegment
from models.dataset import Document as DatasetDocument


class RetrievalService:
    # Cache precompiled regular expressions to avoid repeated compilation
    @classmethod
    def retrieve(
        cls,
        dataset: Dataset,
        query: str,
        top_k: int,
        score_threshold: Optional[float] = 0.0,
        document_ids_filter: Optional[list[str]] = None,
    ):
        if not query:
            return []

        if not dataset:
            return []

        all_documents: list[Document] = []
        exceptions: list[str] = []

        vector_processor = Vector(dataset=dataset)

        documents = vector_processor.search_by_hybrid(
            cls.escape_query_for_search(query),
            top_k=top_k,
            score_threshold=score_threshold,
            document_ids_filter=document_ids_filter,
        )

        all_documents.extend(documents)

        if exceptions:
            raise ValueError(";\n".join(exceptions))

        return all_documents

    @staticmethod
    def escape_query_for_search(query: str) -> str:
        return query.replace('"', '\\"')

    @classmethod
    def format_retrieval_documents(cls, documents: list[Document]) -> list[RetrievalSegments]:
        """Format retrieval documents with optimized batch processing"""
        if not documents:
            return []

        try:
            # Collect document IDs
            document_ids = {doc.metadata.get("document_id") for doc in documents if "document_id" in doc.metadata}
            if not document_ids:
                return []

            # Batch query dataset documents
            dataset_documents = {
                doc.id: doc
                for doc in db.session.query(DatasetDocument)
                .filter(DatasetDocument.id.in_(document_ids))
                .options(
                    load_only(
                        DatasetDocument.id, 
                        DatasetDocument.name,
                        DatasetDocument.doc_form,
                        DatasetDocument.doc_metadata,
                        DatasetDocument.data_source_type,
                        DatasetDocument.dataset_id
                )).all()
            }

            records = []
            include_segment_ids = set()
            segment_child_map = {}

            # Process documents
            for document in documents:
                document_id = document.metadata.get("document_id")
                if document_id not in dataset_documents:
                    continue

                dataset_document = dataset_documents[document_id]
                if not dataset_document:
                    continue

                if dataset_document.doc_form == IndexType.PARENT_CHILD_INDEX:
                    # Handle parent-child documents
                    child_index_node_id = document.metadata.get("doc_id")

                    child_chunk = (
                        db.session.query(ChildChunk).filter(ChildChunk.index_node_id == child_index_node_id).first()
                    )

                    if not child_chunk:
                        continue

                    segment = (
                        db.session.query(DocumentSegment)
                        .filter(
                            DocumentSegment.dataset_id == dataset_document.dataset_id,
                            DocumentSegment.enabled == True,
                            DocumentSegment.status == "completed",
                            DocumentSegment.id == child_chunk.segment_id,
                        )
                        .options(
                            load_only(
                                DocumentSegment.id,
                                DocumentSegment.content,
                                DocumentSegment.answer,
                            )
                        )
                        .first()
                    )

                    if not segment:
                        continue

                    if segment.id not in include_segment_ids:
                        include_segment_ids.add(segment.id)
                        child_chunk_detail = {
                            "id": child_chunk.id,
                            "content": child_chunk.content,
                            "position": child_chunk.position,
                            "score": document.metadata.get("score", 0.0),
                        }
                        map_detail = {
                            "max_score": document.metadata.get("score", 0.0),
                            "child_chunks": [child_chunk_detail],
                        }
                        segment_child_map[segment.id] = map_detail
                        record = {
                            "document": dataset_document,
                            "segment": segment,
                        }
                        records.append(record)
                    else:
                        child_chunk_detail = {
                            "id": child_chunk.id,
                            "content": child_chunk.content,
                            "position": child_chunk.position,
                            "score": document.metadata.get("score", 0.0),
                        }
                        segment_child_map[segment.id]["child_chunks"].append(child_chunk_detail)
                        segment_child_map[segment.id]["max_score"] = max(
                            segment_child_map[segment.id]["max_score"], document.metadata.get("score", 0.0)
                        )
                else:
                    # Handle normal documents
                    index_node_id = document.metadata.get("doc_id")
                    if not index_node_id:
                        continue

                    segment = (
                        db.session.query(DocumentSegment)
                        .filter(
                            DocumentSegment.dataset_id == dataset_document.dataset_id,
                            DocumentSegment.enabled == True,
                            DocumentSegment.status == "completed",
                            DocumentSegment.index_node_id == index_node_id,
                        )
                        .first()
                    )

                    if not segment:
                        continue

                    include_segment_ids.add(segment.id)
                    record = {
                        "document": dataset_document,                        
                        "segment": segment,
                        "score": document.metadata.get("score"),  # type: ignore
                    }
                    records.append(record)

            # Add child chunks information to records
            for record in records:
                if record["segment"].id in segment_child_map:
                    record["child_chunks"] = segment_child_map[record["segment"].id].get("child_chunks")  # type: ignore
                    record["score"] = segment_child_map[record["segment"].id]["max_score"]

            return [RetrievalSegments(**record) for record in records]
        except Exception as e:
            db.session.rollback()
            raise e
