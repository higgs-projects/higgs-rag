import logging

from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from .deploy import DeploymentConfig
from .feature import FeatureConfig
from .middleware import MiddlewareConfig

logger = logging.getLogger(__name__)


class DifyConfig(
    DeploymentConfig,
    FeatureConfig,
    # Middleware configs
    MiddlewareConfig,
):
    model_config = SettingsConfigDict(
        # read from dotenv format config file
        env_file=".env",
        env_file_encoding="utf-8",
        # ignore extra attributes
        extra="ignore",
    )

    # Before adding any config,
    # please consider to arrange it in the proper config group of existed or added
    # for better readability and maintainability.
    # Thanks for your concentration and consideration.

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )
