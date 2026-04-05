"""Test configuration for unit/app tests.

Mocks the uuid_extensions module (plural) since only uuid_extension
(singular) is installed. The source code in command_handlers has
'from uuid_extensions import uuid7' which requires this mock.
"""

import sys
from unittest.mock import MagicMock


# Mock uuid_extensions module (the source uses both uuid_extension and uuid_extensions)
if "uuid_extensions" not in sys.modules:
    from uuid_extension import uuid7

    mock_uuid_extensions = MagicMock()
    mock_uuid_extensions.uuid7 = uuid7
    sys.modules["uuid_extensions"] = mock_uuid_extensions
