from monitoring.mock_uss import import_environment_variable
from monitoring.mock_uss.config import KEY_INTERACTIONS_LOG_DIR

import_environment_variable(KEY_INTERACTIONS_LOG_DIR, default="output/logs")
