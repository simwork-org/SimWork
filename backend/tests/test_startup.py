from __future__ import annotations

import pytest

from api.main import app
from investigation_logger import logger


@pytest.mark.anyio
async def test_startup_initializes_db_without_clearing_existing_sessions():
    logger.init_db()
    logger.create_session("session_existing", "candidate_1", "checkout_conversion_drop")

    async with app.router.lifespan_context(app):
        pass

    session = logger.get_session("session_existing")
    assert session is not None
    assert session["session_id"] == "session_existing"
