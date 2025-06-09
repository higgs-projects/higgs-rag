import base64
import enum
import hashlib
import hmac
import json
import os
import pickle
import re
import time
from json import JSONDecodeError
from typing import cast

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped

from configs import dify_config
from core.rag.index_processor.constant.built_in_field import BuiltInField, MetadataDataSource
from services.entities.knowledge_entities.knowledge_entities import ParentMode, Rule

from .account import Account
from .base import Base
from .engine import db
from .model import UploadFile
from .types import StringUUID


class DatasetPermissionEnum(enum.StrEnum):
    ONLY_ME = "only_me"
    ALL_TEAM = "all_team_members"
    PARTIAL_TEAM = "partial_members"


class Dataset(Base):
    __tablename__ = "datasets"
    __table_args__ = (
        db.PrimaryKeyConstraint("id", name="dataset_pkey"),
        db.Index("dataset_tenant_idx", "tenant_id"),
        db.Index("retrieval_model_idx", "retrieval_model", postgresql_using="gin"),
    )

    INDEXING_TECHNIQUE_LIST = ["high_quality", "economy", None]
    PROVIDER_LIST = ["vendor", "external", None]

    id = db.Column(StringUUID, server_default=db.text("uuid_generate_v4()"))
    tenant_id = db.Column(StringUUID, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    provider = db.Column(db.String(255), nullable=False, server_default=db.text("'vendor'::character varying"))
    permission = db.Column(db.String(255), nullable=False, server_default=db.text("'only_me'::character varying"))
    data_source_type = db.Column(db.String(255))
    indexing_technique = db.Column(db.String(255), nullable=True)
    index_struct = db.Column(db.Text, nullable=True)
    created_by = db.Column(StringUUID, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, server_default=func.current_timestamp())
    updated_by = db.Column(StringUUID, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=False, server_default=func.current_timestamp())
    embedding_model = db.Column(db.String(255), nullable=True)
    embedding_model_provider = db.Column(db.String(255), nullable=True)
    collection_binding_id = db.Column(StringUUID, nullable=True)
    retrieval_model = db.Column(JSONB, nullable=True)
    built_in_field_enabled = db.Column(db.Boolean, nullable=False, server_default=db.text("false"))

    @property
    def index_struct_dict(self):
        return json.loads(self.index_struct) if self.index_struct else None

    @staticmethod
    def gen_collection_name_by_id(dataset_id: str) -> str:
        normalized_dataset_id = dataset_id.replace("-", "_")
        return f"Vector_index_{normalized_dataset_id}_Node"


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        db.PrimaryKeyConstraint("id", name="document_pkey"),
        db.Index("document_dataset_id_idx", "dataset_id"),
        db.Index("document_is_paused_idx", "is_paused"),
        db.Index("document_tenant_idx", "tenant_id"),
        db.Index("document_metadata_idx", "doc_metadata", postgresql_using="gin"),
    )

    # initial fields
    id = db.Column(StringUUID, nullable=False, server_default=db.text("uuid_generate_v4()"))
    tenant_id = db.Column(StringUUID, nullable=False)
    dataset_id = db.Column(StringUUID, nullable=False)
    position = db.Column(db.Integer, nullable=False)
    data_source_type = db.Column(db.String(255), nullable=False)
    data_source_info = db.Column(db.Text, nullable=True)
    dataset_process_rule_id = db.Column(StringUUID, nullable=True)
    batch = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    created_from = db.Column(db.String(255), nullable=False)
    created_by = db.Column(StringUUID, nullable=False)
    created_api_request_id = db.Column(StringUUID, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, server_default=func.current_timestamp())

    # start processing
    processing_started_at = db.Column(db.DateTime, nullable=True)

    # parsing
    file_id = db.Column(db.Text, nullable=True)
    word_count = db.Column(db.Integer, nullable=True)
    parsing_completed_at = db.Column(db.DateTime, nullable=True)

    # cleaning
    cleaning_completed_at = db.Column(db.DateTime, nullable=True)

    # split
    splitting_completed_at = db.Column(db.DateTime, nullable=True)

    # indexing
    tokens = db.Column(db.Integer, nullable=True)
    indexing_latency = db.Column(db.Float, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)

    # pause
    is_paused = db.Column(db.Boolean, nullable=True, server_default=db.text("false"))
    paused_by = db.Column(StringUUID, nullable=True)
    paused_at = db.Column(db.DateTime, nullable=True)

    # error
    error = db.Column(db.Text, nullable=True)
    stopped_at = db.Column(db.DateTime, nullable=True)

    # basic fields
    indexing_status = db.Column(db.String(255), nullable=False, server_default=db.text("'waiting'::character varying"))
    enabled = db.Column(db.Boolean, nullable=False, server_default=db.text("true"))
    disabled_at = db.Column(db.DateTime, nullable=True)
    disabled_by = db.Column(StringUUID, nullable=True)
    archived = db.Column(db.Boolean, nullable=False, server_default=db.text("false"))
    archived_reason = db.Column(db.String(255), nullable=True)
    archived_by = db.Column(StringUUID, nullable=True)
    archived_at = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=False, server_default=func.current_timestamp())
    doc_type = db.Column(db.String(40), nullable=True)
    doc_metadata = db.Column(JSONB, nullable=True)
    doc_form = db.Column(db.String(255), nullable=False, server_default=db.text("'text_model'::character varying"))
    doc_language = db.Column(db.String(255), nullable=True)

    DATA_SOURCES = ["upload_file", "notion_import", "website_crawl"]

    @property
    def display_status(self):
        status = None
        if self.indexing_status == "waiting":
            status = "queuing"
        elif self.indexing_status not in {"completed", "error", "waiting"} and self.is_paused:
            status = "paused"
        elif self.indexing_status in {"parsing", "cleaning", "splitting", "indexing"}:
            status = "indexing"
        elif self.indexing_status == "error":
            status = "error"
        elif self.indexing_status == "completed" and not self.archived and self.enabled:
            status = "available"
        elif self.indexing_status == "completed" and not self.archived and not self.enabled:
            status = "disabled"
        elif self.indexing_status == "completed" and self.archived:
            status = "archived"
        return status

    @property
    def data_source_info_dict(self):
        if self.data_source_info:
            try:
                data_source_info_dict = json.loads(self.data_source_info)
            except JSONDecodeError:
                data_source_info_dict = {}

            return data_source_info_dict
        return None

    @property
    def data_source_detail_dict(self):
        if self.data_source_info:
            if self.data_source_type == "upload_file":
                data_source_info_dict = json.loads(self.data_source_info)
                file_detail = (
                    db.session.query(UploadFile)
                    .filter(UploadFile.id == data_source_info_dict["upload_file_id"])
                    .one_or_none()
                )
                if file_detail:
                    return {
                        "upload_file": {
                            "id": file_detail.id,
                            "name": file_detail.name,
                            "size": file_detail.size,
                            "extension": file_detail.extension,
                            "mime_type": file_detail.mime_type,
                            "created_by": file_detail.created_by,
                            "created_at": file_detail.created_at.timestamp(),
                        }
                    }
            elif self.data_source_type in {"notion_import", "website_crawl"}:
                return json.loads(self.data_source_info)
        return {}

    @property
    def average_segment_length(self):
        if self.word_count and self.word_count != 0 and self.segment_count and self.segment_count != 0:
            return self.word_count // self.segment_count
        return 0

    @property
    def dataset(self):
        return db.session.query(Dataset).filter(Dataset.id == self.dataset_id).one_or_none()

    @property
    def segment_count(self):
        return db.session.query(DocumentSegment).filter(DocumentSegment.document_id == self.id).count()

    @property
    def hit_count(self):
        return (
            db.session.query(DocumentSegment)
            .with_entities(func.coalesce(func.sum(DocumentSegment.hit_count)))
            .filter(DocumentSegment.document_id == self.id)
            .scalar()
        )

    @property
    def uploader(self):
        user = db.session.query(Account).filter(Account.id == self.created_by).first()
        return user.name if user else None

    @property
    def upload_date(self):
        return self.created_at

    @property
    def last_update_date(self):
        return self.updated_at

    @property
    def process_rule_dict(self):
        if self.dataset_process_rule_id:
            return self.dataset_process_rule.to_dict()
        return None

    def get_built_in_fields(self):
        built_in_fields = []
        built_in_fields.append(
            {
                "id": "built-in",
                "name": BuiltInField.document_name,
                "type": "string",
                "value": self.name,
            }
        )
        built_in_fields.append(
            {
                "id": "built-in",
                "name": BuiltInField.uploader,
                "type": "string",
                "value": self.uploader,
            }
        )
        built_in_fields.append(
            {
                "id": "built-in",
                "name": BuiltInField.upload_date,
                "type": "time",
                "value": self.created_at.timestamp(),
            }
        )
        built_in_fields.append(
            {
                "id": "built-in",
                "name": BuiltInField.last_update_date,
                "type": "time",
                "value": self.updated_at.timestamp(),
            }
        )
        built_in_fields.append(
            {
                "id": "built-in",
                "name": BuiltInField.source,
                "type": "string",
                "value": MetadataDataSource[self.data_source_type].value,
            }
        )
        return built_in_fields

    def to_dict(self):
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "dataset_id": self.dataset_id,
            "position": self.position,
            "data_source_type": self.data_source_type,
            "data_source_info": self.data_source_info,
            "dataset_process_rule_id": self.dataset_process_rule_id,
            "batch": self.batch,
            "name": self.name,
            "created_from": self.created_from,
            "created_by": self.created_by,
            "created_api_request_id": self.created_api_request_id,
            "created_at": self.created_at,
            "processing_started_at": self.processing_started_at,
            "file_id": self.file_id,
            "word_count": self.word_count,
            "parsing_completed_at": self.parsing_completed_at,
            "cleaning_completed_at": self.cleaning_completed_at,
            "splitting_completed_at": self.splitting_completed_at,
            "tokens": self.tokens,
            "indexing_latency": self.indexing_latency,
            "completed_at": self.completed_at,
            "is_paused": self.is_paused,
            "paused_by": self.paused_by,
            "paused_at": self.paused_at,
            "error": self.error,
            "stopped_at": self.stopped_at,
            "indexing_status": self.indexing_status,
            "enabled": self.enabled,
            "disabled_at": self.disabled_at,
            "disabled_by": self.disabled_by,
            "archived": self.archived,
            "archived_reason": self.archived_reason,
            "archived_by": self.archived_by,
            "archived_at": self.archived_at,
            "updated_at": self.updated_at,
            "doc_type": self.doc_type,
            "doc_metadata": self.doc_metadata,
            "doc_form": self.doc_form,
            "doc_language": self.doc_language,
            "display_status": self.display_status,
            "data_source_info_dict": self.data_source_info_dict,
            "average_segment_length": self.average_segment_length,
            "dataset_process_rule": self.dataset_process_rule.to_dict() if self.dataset_process_rule else None,
            "dataset": self.dataset.to_dict() if self.dataset else None,
            "segment_count": self.segment_count,
            "hit_count": self.hit_count,
        }

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            id=data.get("id"),
            tenant_id=data.get("tenant_id"),
            dataset_id=data.get("dataset_id"),
            position=data.get("position"),
            data_source_type=data.get("data_source_type"),
            data_source_info=data.get("data_source_info"),
            dataset_process_rule_id=data.get("dataset_process_rule_id"),
            batch=data.get("batch"),
            name=data.get("name"),
            created_from=data.get("created_from"),
            created_by=data.get("created_by"),
            created_api_request_id=data.get("created_api_request_id"),
            created_at=data.get("created_at"),
            processing_started_at=data.get("processing_started_at"),
            file_id=data.get("file_id"),
            word_count=data.get("word_count"),
            parsing_completed_at=data.get("parsing_completed_at"),
            cleaning_completed_at=data.get("cleaning_completed_at"),
            splitting_completed_at=data.get("splitting_completed_at"),
            tokens=data.get("tokens"),
            indexing_latency=data.get("indexing_latency"),
            completed_at=data.get("completed_at"),
            is_paused=data.get("is_paused"),
            paused_by=data.get("paused_by"),
            paused_at=data.get("paused_at"),
            error=data.get("error"),
            stopped_at=data.get("stopped_at"),
            indexing_status=data.get("indexing_status"),
            enabled=data.get("enabled"),
            disabled_at=data.get("disabled_at"),
            disabled_by=data.get("disabled_by"),
            archived=data.get("archived"),
            archived_reason=data.get("archived_reason"),
            archived_by=data.get("archived_by"),
            archived_at=data.get("archived_at"),
            updated_at=data.get("updated_at"),
            doc_type=data.get("doc_type"),
            doc_metadata=data.get("doc_metadata"),
            doc_form=data.get("doc_form"),
            doc_language=data.get("doc_language"),
        )


class DocumentSegment(Base):
    __tablename__ = "document_segments"
    __table_args__ = (
        db.PrimaryKeyConstraint("id", name="document_segment_pkey"),
        db.Index("document_segment_dataset_id_idx", "dataset_id"),
        db.Index("document_segment_document_id_idx", "document_id"),
        db.Index("document_segment_tenant_dataset_idx", "dataset_id", "tenant_id"),
        db.Index("document_segment_tenant_document_idx", "document_id", "tenant_id"),
        db.Index("document_segment_node_dataset_idx", "index_node_id", "dataset_id"),
        db.Index("document_segment_tenant_idx", "tenant_id"),
    )

    # initial fields
    id = db.Column(StringUUID, nullable=False, server_default=db.text("uuid_generate_v4()"))
    tenant_id = db.Column(StringUUID, nullable=False)
    dataset_id = db.Column(StringUUID, nullable=False)
    document_id = db.Column(StringUUID, nullable=False)
    position: Mapped[int]
    content = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=True)
    word_count = db.Column(db.Integer, nullable=False)
    tokens = db.Column(db.Integer, nullable=False)

    # indexing fields
    keywords = db.Column(db.JSON, nullable=True)
    index_node_id = db.Column(db.String(255), nullable=True)
    index_node_hash = db.Column(db.String(255), nullable=True)

    # basic fields
    hit_count = db.Column(db.Integer, nullable=False, default=0)
    enabled = db.Column(db.Boolean, nullable=False, server_default=db.text("true"))
    disabled_at = db.Column(db.DateTime, nullable=True)
    disabled_by = db.Column(StringUUID, nullable=True)
    status = db.Column(db.String(255), nullable=False, server_default=db.text("'waiting'::character varying"))
    created_by = db.Column(StringUUID, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, server_default=func.current_timestamp())
    updated_by = db.Column(StringUUID, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=False, server_default=func.current_timestamp())
    indexing_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    error = db.Column(db.Text, nullable=True)
    stopped_at = db.Column(db.DateTime, nullable=True)

    @property
    def dataset(self):
        return db.session.query(Dataset).filter(Dataset.id == self.dataset_id).first()

    @property
    def document(self):
        return db.session.query(Document).filter(Document.id == self.document_id).first()

    @property
    def previous_segment(self):
        return (
            db.session.query(DocumentSegment)
            .filter(DocumentSegment.document_id == self.document_id, DocumentSegment.position == self.position - 1)
            .first()
        )

    @property
    def next_segment(self):
        return (
            db.session.query(DocumentSegment)
            .filter(DocumentSegment.document_id == self.document_id, DocumentSegment.position == self.position + 1)
            .first()
        )

    @property
    def child_chunks(self):
        process_rule = self.document.dataset_process_rule
        if process_rule.mode == "hierarchical":
            rules = Rule(**process_rule.rules_dict)
            if rules.parent_mode and rules.parent_mode != ParentMode.FULL_DOC:
                child_chunks = (
                    db.session.query(ChildChunk)
                    .filter(ChildChunk.segment_id == self.id)
                    .order_by(ChildChunk.position.asc())
                    .all()
                )
                return child_chunks or []
            else:
                return []
        else:
            return []

    def get_child_chunks(self):
        process_rule = self.document.dataset_process_rule
        if process_rule.mode == "hierarchical":
            rules = Rule(**process_rule.rules_dict)
            if rules.parent_mode:
                child_chunks = (
                    db.session.query(ChildChunk)
                    .filter(ChildChunk.segment_id == self.id)
                    .order_by(ChildChunk.position.asc())
                    .all()
                )
                return child_chunks or []
            else:
                return []
        else:
            return []

    @property
    def sign_content(self):
        return self.get_sign_content()

    def get_sign_content(self):
        signed_urls = []
        text = self.content

        # For data before v0.10.0
        pattern = r"/files/([a-f0-9\-]+)/image-preview"
        matches = re.finditer(pattern, text)
        for match in matches:
            upload_file_id = match.group(1)
            nonce = os.urandom(16).hex()
            timestamp = str(int(time.time()))
            data_to_sign = f"image-preview|{upload_file_id}|{timestamp}|{nonce}"
            secret_key = dify_config.SECRET_KEY.encode() if dify_config.SECRET_KEY else b""
            sign = hmac.new(secret_key, data_to_sign.encode(), hashlib.sha256).digest()
            encoded_sign = base64.urlsafe_b64encode(sign).decode()

            params = f"timestamp={timestamp}&nonce={nonce}&sign={encoded_sign}"
            signed_url = f"{match.group(0)}?{params}"
            signed_urls.append((match.start(), match.end(), signed_url))

        # For data after v0.10.0
        pattern = r"/files/([a-f0-9\-]+)/file-preview"
        matches = re.finditer(pattern, text)
        for match in matches:
            upload_file_id = match.group(1)
            nonce = os.urandom(16).hex()
            timestamp = str(int(time.time()))
            data_to_sign = f"file-preview|{upload_file_id}|{timestamp}|{nonce}"
            secret_key = dify_config.SECRET_KEY.encode() if dify_config.SECRET_KEY else b""
            sign = hmac.new(secret_key, data_to_sign.encode(), hashlib.sha256).digest()
            encoded_sign = base64.urlsafe_b64encode(sign).decode()

            params = f"timestamp={timestamp}&nonce={nonce}&sign={encoded_sign}"
            signed_url = f"{match.group(0)}?{params}"
            signed_urls.append((match.start(), match.end(), signed_url))

        # Reconstruct the text with signed URLs
        offset = 0
        for start, end, signed_url in signed_urls:
            text = text[: start + offset] + signed_url + text[end + offset :]
            offset += len(signed_url) - (end - start)

        return text


class ChildChunk(Base):
    __tablename__ = "child_chunks"
    __table_args__ = (
        db.PrimaryKeyConstraint("id", name="child_chunk_pkey"),
        db.Index("child_chunk_dataset_id_idx", "tenant_id", "dataset_id", "document_id", "segment_id", "index_node_id"),
        db.Index("child_chunks_node_idx", "index_node_id", "dataset_id"),
        db.Index("child_chunks_segment_idx", "segment_id"),
    )

    # initial fields
    id = db.Column(StringUUID, nullable=False, server_default=db.text("uuid_generate_v4()"))
    tenant_id = db.Column(StringUUID, nullable=False)
    dataset_id = db.Column(StringUUID, nullable=False)
    document_id = db.Column(StringUUID, nullable=False)
    segment_id = db.Column(StringUUID, nullable=False)
    position = db.Column(db.Integer, nullable=False)
    content = db.Column(db.Text, nullable=False)
    word_count = db.Column(db.Integer, nullable=False)
    # indexing fields
    index_node_id = db.Column(db.String(255), nullable=True)
    index_node_hash = db.Column(db.String(255), nullable=True)
    type = db.Column(db.String(255), nullable=False, server_default=db.text("'automatic'::character varying"))
    created_by = db.Column(StringUUID, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.text("CURRENT_TIMESTAMP(0)"))
    updated_by = db.Column(StringUUID, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=False, server_default=db.text("CURRENT_TIMESTAMP(0)"))
    indexing_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    error = db.Column(db.Text, nullable=True)

    @property
    def dataset(self):
        return db.session.query(Dataset).filter(Dataset.id == self.dataset_id).first()

    @property
    def document(self):
        return db.session.query(Document).filter(Document.id == self.document_id).first()

    @property
    def segment(self):
        return db.session.query(DocumentSegment).filter(DocumentSegment.id == self.segment_id).first()


class Embedding(Base):
    __tablename__ = "embeddings"
    __table_args__ = (
        db.PrimaryKeyConstraint("id", name="embedding_pkey"),
        db.UniqueConstraint("model_name", "hash", "provider_name", name="embedding_hash_idx"),
        db.Index("created_at_idx", "created_at"),
    )

    id = db.Column(StringUUID, primary_key=True, server_default=db.text("uuid_generate_v4()"))
    model_name = db.Column(
        db.String(255), nullable=False, server_default=db.text("'text-embedding-ada-002'::character varying")
    )
    hash = db.Column(db.String(64), nullable=False)
    embedding = db.Column(db.LargeBinary, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, server_default=func.current_timestamp())
    provider_name = db.Column(db.String(255), nullable=False, server_default=db.text("''::character varying"))

    def set_embedding(self, embedding_data: list[float]):
        self.embedding = pickle.dumps(embedding_data, protocol=pickle.HIGHEST_PROTOCOL)

    def get_embedding(self) -> list[float]:
        return cast(list[float], pickle.loads(self.embedding))  # noqa: S301


class DatasetCollectionBinding(Base):
    __tablename__ = "dataset_collection_bindings"
    __table_args__ = (
        db.PrimaryKeyConstraint("id", name="dataset_collection_bindings_pkey"),
        db.Index("provider_model_name_idx", "provider_name", "model_name"),
    )

    id = db.Column(StringUUID, primary_key=True, server_default=db.text("uuid_generate_v4()"))
    provider_name = db.Column(db.String(255), nullable=False)
    model_name = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(40), server_default=db.text("'dataset'::character varying"), nullable=False)
    collection_name = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, server_default=func.current_timestamp())


class TidbAuthBinding(Base):
    __tablename__ = "tidb_auth_bindings"
    __table_args__ = (
        db.PrimaryKeyConstraint("id", name="tidb_auth_bindings_pkey"),
        db.Index("tidb_auth_bindings_tenant_idx", "tenant_id"),
        db.Index("tidb_auth_bindings_active_idx", "active"),
        db.Index("tidb_auth_bindings_created_at_idx", "created_at"),
        db.Index("tidb_auth_bindings_status_idx", "status"),
    )
    id = db.Column(StringUUID, primary_key=True, server_default=db.text("uuid_generate_v4()"))
    tenant_id = db.Column(StringUUID, nullable=True)
    cluster_id = db.Column(db.String(255), nullable=False)
    cluster_name = db.Column(db.String(255), nullable=False)
    active = db.Column(db.Boolean, nullable=False, server_default=db.text("false"))
    status = db.Column(db.String(255), nullable=False, server_default=db.text("CREATING"))
    account = db.Column(db.String(255), nullable=False)
    password = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, server_default=func.current_timestamp())


class Whitelist(Base):
    __tablename__ = "whitelists"
    __table_args__ = (
        db.PrimaryKeyConstraint("id", name="whitelists_pkey"),
        db.Index("whitelists_tenant_idx", "tenant_id"),
    )
    id = db.Column(StringUUID, primary_key=True, server_default=db.text("uuid_generate_v4()"))
    tenant_id = db.Column(StringUUID, nullable=True)
    category = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, server_default=func.current_timestamp())


class DatasetPermission(Base):
    __tablename__ = "dataset_permissions"
    __table_args__ = (
        db.PrimaryKeyConstraint("id", name="dataset_permission_pkey"),
        db.Index("idx_dataset_permissions_dataset_id", "dataset_id"),
        db.Index("idx_dataset_permissions_account_id", "account_id"),
        db.Index("idx_dataset_permissions_tenant_id", "tenant_id"),
    )

    id = db.Column(StringUUID, server_default=db.text("uuid_generate_v4()"), primary_key=True)
    dataset_id = db.Column(StringUUID, nullable=False)
    account_id = db.Column(StringUUID, nullable=False)
    tenant_id = db.Column(StringUUID, nullable=False)
    has_permission = db.Column(db.Boolean, nullable=False, server_default=db.text("true"))
    created_at = db.Column(db.DateTime, nullable=False, server_default=func.current_timestamp())
