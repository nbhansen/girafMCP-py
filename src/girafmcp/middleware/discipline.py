"""Discipline-aware response middleware.

Adapts AI responses for different disciplinary backgrounds
(CS, Interaction Design, Business, Health).
"""

import logging
import os

from mcp.types import TextContent

from girafmcp.core.services.multiframe_service import MultiFrameService
from girafmcp.middleware import Middleware, NextMiddleware, ToolContext

logger = logging.getLogger(__name__)


def is_discipline_feature_enabled() -> bool:
    """Check if discipline framing feature is enabled."""
    env_val = os.environ.get("GIRAF_DISCIPLINE_ENABLED", "").lower()
    return env_val in ("true", "1", "yes")


class DisciplineMiddleware(Middleware):
    """Middleware that adapts responses for different disciplines.

    When a session has a discipline set (via session metadata),
    this middleware will adapt technical responses to be more
    accessible to that discipline's background.
    """

    def __init__(self, service: MultiFrameService):
        """Initialize middleware with MultiFrameService.

        Args:
            service: MultiFrameService instance for translations
        """
        super().__init__()
        self.service = service

    def should_process(self, ctx: ToolContext) -> bool:
        """Check if this middleware should process the request.

        Only processes if:
        - Feature is enabled via environment variable
        - Session has a discipline set
        - Discipline is not CS (CS doesn't need adaptation)
        """
        if not is_discipline_feature_enabled():
            return False

        if not self.service.enabled:
            return False

        # Check if session has a non-CS discipline
        discipline = ctx.session.discipline
        return discipline is not None and discipline != "cs"

    async def process(
        self, ctx: ToolContext, next_middleware: NextMiddleware
    ) -> list[TextContent]:
        """Process request, adapting response for discipline.

        Args:
            ctx: Tool context with session info
            next_middleware: Next handler in chain

        Returns:
            Adapted response
        """
        # Get the original response
        result = await next_middleware(ctx)

        if not result:
            return result

        discipline = ctx.session.discipline
        if not discipline or discipline == "cs":
            return result

        # Adapt each text response
        adapted_results: list[TextContent] = []
        for content in result:
            if content.type == "text":
                adapted_text = self.service.adapt_response_for_discipline(
                    content.text, discipline
                )
                adapted_results.append(
                    TextContent(type="text", text=adapted_text)
                )

                # Track in metadata
                if adapted_text != content.text:
                    ctx.metadata["discipline_adapted"] = True
                    ctx.metadata["target_discipline"] = discipline
            else:
                adapted_results.append(content)

        return adapted_results
