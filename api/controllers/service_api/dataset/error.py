from libs.exception import BaseHTTPException


class DatasetNotInitializedError(BaseHTTPException):
    error_code = "dataset_not_initialized"
    description = "The dataset is still being initialized or indexing. Please wait a moment."
    code = 400
