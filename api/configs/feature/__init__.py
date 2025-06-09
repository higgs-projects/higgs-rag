from typing import Annotated, Optional

from pydantic import (
    AliasChoices,
    Field,
    HttpUrl,
    PositiveFloat,
    PositiveInt,
    computed_field,
)
from pydantic_settings import BaseSettings

from .hosted_service import HostedServiceConfig


class SecurityConfig(BaseSettings):
    """
    Security-related configurations for the application
    """

    SECRET_KEY: str = Field(
        description="Secret key for secure session cookie signing."
        "Make sure you are changing this key for your deployment with a strong key."
        "Generate a strong key using `openssl rand -base64 42` or set via the `SECRET_KEY` environment variable.",
        default="",
    )

    ADMIN_API_KEY_ENABLE: bool = Field(
        description="Whether to enable admin api key for authentication",
        default=False,
    )

    ADMIN_API_KEY: Optional[str] = Field(
        description="admin api key for authentication",
        default=None,
    )


class PluginConfig(BaseSettings):
    """
    Plugin configs
    """

    PLUGIN_DAEMON_URL: HttpUrl = Field(
        description="Plugin API URL",
        default=HttpUrl("http://localhost:5002"),
    )

    PLUGIN_DAEMON_KEY: str = Field(
        description="Plugin API key",
        default="plugin-api-key",
    )

    INNER_API_KEY_FOR_PLUGIN: str = Field(description="Inner api key for plugin", default="inner-api-key")

    PLUGIN_REMOTE_INSTALL_HOST: str = Field(
        description="Plugin Remote Install Host",
        default="localhost",
    )

    PLUGIN_REMOTE_INSTALL_PORT: PositiveInt = Field(
        description="Plugin Remote Install Port",
        default=5003,
    )

    PLUGIN_MAX_PACKAGE_SIZE: PositiveInt = Field(
        description="Maximum allowed size for plugin packages in bytes",
        default=15728640,
    )

    PLUGIN_MAX_BUNDLE_SIZE: PositiveInt = Field(
        description="Maximum allowed size for plugin bundles in bytes",
        default=15728640 * 12,
    )


class EndpointConfig(BaseSettings):
    """
    Configuration for various application endpoints and URLs
    """

    CONSOLE_API_URL: str = Field(
        description="Base URL for the console API,"
        "used for login authentication callback or notion integration callbacks",
        default="",
    )

    CONSOLE_WEB_URL: str = Field(
        description="Base URL for the console web interface,used for frontend references and CORS configuration",
        default="",
    )

    SERVICE_API_URL: str = Field(
        description="Base URL for the service API, displayed to users for API access",
        default="",
    )

    APP_WEB_URL: str = Field(
        description="Base URL for the web application, used for frontend references",
        default="",
    )

    ENDPOINT_URL_TEMPLATE: str = Field(
        description="Template url for endpoint plugin", default="http://localhost:5002/e/{hook_id}"
    )


class HttpConfig(BaseSettings):
    """
    HTTP-related configurations for the application
    """

    API_COMPRESSION_ENABLED: bool = Field(
        description="Enable or disable gzip compression for HTTP responses",
        default=False,
    )

    inner_CONSOLE_CORS_ALLOW_ORIGINS: str = Field(
        description="Comma-separated list of allowed origins for CORS in the console",
        validation_alias=AliasChoices("CONSOLE_CORS_ALLOW_ORIGINS", "CONSOLE_WEB_URL"),
        default="",
    )

    @computed_field
    def CONSOLE_CORS_ALLOW_ORIGINS(self) -> list[str]:
        return self.inner_CONSOLE_CORS_ALLOW_ORIGINS.split(",")

    inner_WEB_API_CORS_ALLOW_ORIGINS: str = Field(
        description="",
        validation_alias=AliasChoices("WEB_API_CORS_ALLOW_ORIGINS"),
        default="*",
    )

    @computed_field
    def WEB_API_CORS_ALLOW_ORIGINS(self) -> list[str]:
        return self.inner_WEB_API_CORS_ALLOW_ORIGINS.split(",")

    HTTP_REQUEST_MAX_CONNECT_TIMEOUT: Annotated[
        PositiveInt, Field(ge=10, description="Maximum connection timeout in seconds for HTTP requests")
    ] = 10

    HTTP_REQUEST_MAX_READ_TIMEOUT: Annotated[
        PositiveInt, Field(ge=60, description="Maximum read timeout in seconds for HTTP requests")
    ] = 60

    HTTP_REQUEST_MAX_WRITE_TIMEOUT: Annotated[
        PositiveInt, Field(ge=10, description="Maximum write timeout in seconds for HTTP requests")
    ] = 20

    HTTP_REQUEST_NODE_MAX_BINARY_SIZE: PositiveInt = Field(
        description="Maximum allowed size in bytes for binary data in HTTP requests",
        default=10 * 1024 * 1024,
    )

    HTTP_REQUEST_NODE_MAX_TEXT_SIZE: PositiveInt = Field(
        description="Maximum allowed size in bytes for text data in HTTP requests",
        default=1 * 1024 * 1024,
    )

    HTTP_REQUEST_NODE_SSL_VERIFY: bool = Field(
        description="Enable or disable SSL verification for HTTP requests",
        default=True,
    )

    SSRF_DEFAULT_MAX_RETRIES: PositiveInt = Field(
        description="Maximum number of retries for network requests (SSRF)",
        default=3,
    )

    SSRF_PROXY_ALL_URL: Optional[str] = Field(
        description="Proxy URL for HTTP or HTTPS requests to prevent Server-Side Request Forgery (SSRF)",
        default=None,
    )

    SSRF_PROXY_HTTP_URL: Optional[str] = Field(
        description="Proxy URL for HTTP requests to prevent Server-Side Request Forgery (SSRF)",
        default=None,
    )

    SSRF_PROXY_HTTPS_URL: Optional[str] = Field(
        description="Proxy URL for HTTPS requests to prevent Server-Side Request Forgery (SSRF)",
        default=None,
    )

    SSRF_DEFAULT_TIME_OUT: PositiveFloat = Field(
        description="The default timeout period used for network requests (SSRF)",
        default=5,
    )

    SSRF_DEFAULT_CONNECT_TIME_OUT: PositiveFloat = Field(
        description="The default connect timeout period used for network requests (SSRF)",
        default=5,
    )

    SSRF_DEFAULT_READ_TIME_OUT: PositiveFloat = Field(
        description="The default read timeout period used for network requests (SSRF)",
        default=5,
    )

    SSRF_DEFAULT_WRITE_TIME_OUT: PositiveFloat = Field(
        description="The default write timeout period used for network requests (SSRF)",
        default=5,
    )

    RESPECT_XFORWARD_HEADERS_ENABLED: bool = Field(
        description="Enable handling of X-Forwarded-For, X-Forwarded-Proto, and X-Forwarded-Port headers"
        " when the app is behind a single trusted reverse proxy.",
        default=False,
    )


class LoggingConfig(BaseSettings):
    """
    Configuration for application logging
    """

    LOG_LEVEL: str = Field(
        description="Logging level, default to INFO. Set to ERROR for production environments.",
        default="INFO",
    )

    LOG_FILE: Optional[str] = Field(
        description="File path for log output.",
        default=None,
    )

    LOG_FILE_MAX_SIZE: PositiveInt = Field(
        description="Maximum file size for file rotation retention, the unit is megabytes (MB)",
        default=20,
    )

    LOG_FILE_BACKUP_COUNT: PositiveInt = Field(
        description="Maximum file backup count file rotation retention",
        default=5,
    )

    LOG_FORMAT: str = Field(
        description="Format string for log messages",
        default="%(asctime)s.%(msecs)03d %(levelname)s [%(threadName)s] [%(filename)s:%(lineno)d] - %(message)s",
    )

    LOG_DATEFORMAT: Optional[str] = Field(
        description="Date format string for log timestamps",
        default=None,
    )

    LOG_TZ: Optional[str] = Field(
        description="Timezone for log timestamps (e.g., 'America/New_York')",
        default="UTC",
    )


class ModelLoadBalanceConfig(BaseSettings):
    """
    Configuration for model load balancing and token counting
    """

    MODEL_LB_ENABLED: bool = Field(
        description="Enable or disable load balancing for models",
        default=False,
    )

    PLUGIN_BASED_TOKEN_COUNTING_ENABLED: bool = Field(
        description="Enable or disable plugin based token counting. If disabled, token counting will return 0.",
        default=False,
    )


class CeleryBeatConfig(BaseSettings):
    CELERY_BEAT_SCHEDULER_TIME: int = Field(
        description="Interval in days for Celery Beat scheduler execution, default to 1 day",
        default=1,
    )


class PositionConfig(BaseSettings):
    POSITION_PROVIDER_PINS: str = Field(
        description="Comma-separated list of pinned model providers",
        default="",
    )

    POSITION_PROVIDER_INCLUDES: str = Field(
        description="Comma-separated list of included model providers",
        default="",
    )

    POSITION_PROVIDER_EXCLUDES: str = Field(
        description="Comma-separated list of excluded model providers",
        default="",
    )

    POSITION_TOOL_PINS: str = Field(
        description="Comma-separated list of pinned tools",
        default="",
    )

    POSITION_TOOL_INCLUDES: str = Field(
        description="Comma-separated list of included tools",
        default="",
    )

    POSITION_TOOL_EXCLUDES: str = Field(
        description="Comma-separated list of excluded tools",
        default="",
    )

    @property
    def POSITION_PROVIDER_PINS_LIST(self) -> list[str]:
        return [item.strip() for item in self.POSITION_PROVIDER_PINS.split(",") if item.strip() != ""]

    @property
    def POSITION_PROVIDER_INCLUDES_SET(self) -> set[str]:
        return {item.strip() for item in self.POSITION_PROVIDER_INCLUDES.split(",") if item.strip() != ""}

    @property
    def POSITION_PROVIDER_EXCLUDES_SET(self) -> set[str]:
        return {item.strip() for item in self.POSITION_PROVIDER_EXCLUDES.split(",") if item.strip() != ""}

    @property
    def POSITION_TOOL_PINS_LIST(self) -> list[str]:
        return [item.strip() for item in self.POSITION_TOOL_PINS.split(",") if item.strip() != ""]

    @property
    def POSITION_TOOL_INCLUDES_SET(self) -> set[str]:
        return {item.strip() for item in self.POSITION_TOOL_INCLUDES.split(",") if item.strip() != ""}

    @property
    def POSITION_TOOL_EXCLUDES_SET(self) -> set[str]:
        return {item.strip() for item in self.POSITION_TOOL_EXCLUDES.split(",") if item.strip() != ""}


class FeatureConfig(
    # place the configs in alphabet order
    PluginConfig,
    EndpointConfig,
    HttpConfig,
    LoggingConfig,
    ModelLoadBalanceConfig,
    PositionConfig,
    SecurityConfig,
    # hosted services config
    HostedServiceConfig,
    CeleryBeatConfig,
):
    pass
