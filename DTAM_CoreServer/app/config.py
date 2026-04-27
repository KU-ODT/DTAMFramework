"""호환 래퍼 — model.config 으로 이전됨."""
from .model.config import *  # noqa: F401,F403
from .model.message import *  # noqa: F401,F403
from .model.config import (  # noqa: F401 — DSE_main.py 에서 직접 import
    DEFAULT_CONFIG_FILE,
    DEFAULT_DB_ROOT,
    DTAM_SDK_ROOT,
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
