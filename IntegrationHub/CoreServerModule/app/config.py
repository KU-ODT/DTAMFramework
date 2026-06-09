"""Compatibility wrapper for model.config and model.message."""
from .model.config import (  # noqa: F401
    DEFAULT_CONFIG_FILE,
    DTAMSDK_ROOT,
    FRAMEWORK_ROOT,
    ModuleEndpoint,
    ServerConfig,
    ServerEndpoint,
    load_config,
)
from .model.message import (  # noqa: F401
    DB_FOLDER_FOR_MID,
    FORWARD_RULES,
    MESSAGE_TABLE,
    MODULE_ROLES,
)
