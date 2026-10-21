"""Resilience testing middleware for research assessment.

Intercepts tool calls to implement failure injection, service unavailability,
and delayed responses for testing student verification skills.

WARNING: This middleware should only be enabled during controlled assessment
periods with proper ethical oversight.
"""

import asyncio
import logging

from mcp.types import TextContent

from girafmcp.core.features import is_resilience_enabled
from girafmcp.core.services.resilience_service import (
    ResilienceMode,
    ResilienceService,
)
from girafmcp.middleware.base import Middleware, NextMiddleware, ToolContext

logger = logging.getLogger(__name__)


class ResilienceMiddleware(Middleware):
    """Middleware that implements resilience testing scenarios.

    Supports multiple modes:
    - normal: Standard AI assistance (passthrough)
    - degraded: AI provides intentionally flawed responses
    - unavailable: AI returns "service unavailable" message
    - delayed: AI responds after significant delay

    Used for research assessment of student verification skills,
    debugging ability, and independence from AI assistance.
    """

    def __init__(self, service: ResilienceService | None = None):
        """Initialize the resilience middleware.

        Args:
            service: ResilienceService instance. If None, creates default service.
        """
        self.service = service or ResilienceService()

    @property
    def name(self) -> str:
        return "ResilienceMiddleware"

    def should_process(self, ctx: ToolContext) -> bool:
        """Check if this middleware should process the context.

        Args:
            ctx: The tool context

        Returns:
            True if resilience feature is enabled
        """
        return is_resilience_enabled()

    async def process(
        self,
        ctx: ToolContext,
        next_middleware: NextMiddleware,
    ) -> list[TextContent]:
        """Process tool call with resilience testing.

        Args:
            ctx: Tool context with request data
            next_middleware: Next middleware in chain

        Returns:
            Tool result, possibly modified by resilience testing
        """
        session = ctx.session
        team_id = session.team_id

        # Get current mode for team
        mode = self.service.get_mode(team_id)

        # Record mode in context metadata for logging
        ctx.metadata["resilience_mode"] = mode.value

        # Handle based on mode
        if mode == ResilienceMode.NORMAL:
            # Standard passthrough
            return await next_middleware(ctx)

        elif mode == ResilienceMode.UNAVAILABLE:
            return await self._handle_unavailable(ctx, next_middleware)

        elif mode == ResilienceMode.DEGRADED:
            return await self._handle_degraded(ctx, next_middleware)

        elif mode == ResilienceMode.DELAYED:
            return await self._handle_delayed(ctx, next_middleware)

        # Fallback: passthrough
        return await next_middleware(ctx)

    async def _handle_unavailable(
        self,
        ctx: ToolContext,
        next_middleware: NextMiddleware,
    ) -> list[TextContent]:
        """Handle unavailable mode.

        Some tools (documentation, past decisions) remain available.

        Args:
            ctx: Tool context
            next_middleware: Next middleware

        Returns:
            Unavailable message or tool result if tool is allowed
        """
        if self.service.is_tool_allowed(ctx.name, ctx.session.team_id):
            logger.debug(f"Resilience: allowing {ctx.name} during unavailable mode")
            return await next_middleware(ctx)

        logger.info(f"Resilience: blocking {ctx.name} (unavailable mode)")
        ctx.metadata["resilience_blocked"] = True

        return [
            TextContent(
                type="text",
                text=self.service.get_unavailable_message(),
            )
        ]

    async def _handle_degraded(
        self,
        ctx: ToolContext,
        next_middleware: NextMiddleware,
    ) -> list[TextContent]:
        """Handle degraded mode with error injection.

        Args:
            ctx: Tool context
            next_middleware: Next middleware

        Returns:
            Tool result, possibly with injected error
        """
        # Get the real result first
        result = await next_middleware(ctx)

        if not result:
            return result

        # Try to inject an error
        original_text = result[0].text
        modified_text, error = self.service.inject_error(
            response=original_text,
            tool_name=ctx.name,
            session_id=ctx.session.id,
        )

        if error:
            ctx.metadata["error_injected"] = True
            ctx.metadata["error_id"] = error.id
            ctx.metadata["error_type"] = error.error_type.value
            ctx.metadata["error_difficulty"] = error.difficulty.value
            logger.info(
                f"Resilience: injected {error.error_type.value} error "
                f"({error.difficulty.value}) in {ctx.name}"
            )
            return [TextContent(type="text", text=modified_text)]

        return result

    async def _handle_delayed(
        self,
        ctx: ToolContext,
        next_middleware: NextMiddleware,
    ) -> list[TextContent]:
        """Handle delayed mode.

        Args:
            ctx: Tool context
            next_middleware: Next middleware

        Returns:
            Tool result after delay
        """
        delay_seconds = self.service.get_delay_seconds()

        logger.info(f"Resilience: delaying {ctx.name} by {delay_seconds}s")
        ctx.metadata["resilience_delayed"] = True
        ctx.metadata["delay_seconds"] = delay_seconds

        # Wait for the delay
        await asyncio.sleep(delay_seconds)

        # Then return the real result
        return await next_middleware(ctx)


def create_resilience_middleware(
    config_path: str | None = None,
) -> ResilienceMiddleware:
    """Create a configured ResilienceMiddleware instance.

    Args:
        config_path: Optional path to resilience_tests.yaml

    Returns:
        Configured ResilienceMiddleware
    """
    from pathlib import Path

    from girafmcp.core.services.resilience_service import ResilienceConfig

    config = None
    if config_path:
        config = ResilienceConfig(Path(config_path))

    service = ResilienceService(config)
    return ResilienceMiddleware(service)
