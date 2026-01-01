"""Base middleware classes for tool call interception.

Provides the abstract Middleware class and ToolContext dataclass
that all middleware implementations use.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from mcp.types import TextContent

from girafmcp.core.session import SessionState


def _utcnow() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


@dataclass
class ToolContext:
    """Context passed through the middleware chain.

    Contains all information about a tool invocation, including
    mutable fields that middleware can modify.
    """

    # Immutable request data
    name: str
    arguments: dict[str, Any]
    session: SessionState
    start_time: float  # monotonic time for duration calculation

    # Mutable fields set during processing
    result: list[TextContent] | None = None
    error: Exception | None = None

    # Extensible metadata for middleware communication
    metadata: dict[str, Any] = field(default_factory=dict)

    # Timestamps for logging
    timestamp: datetime = field(default_factory=_utcnow)

    @property
    def succeeded(self) -> bool:
        """Check if the tool call succeeded."""
        return self.result is not None and self.error is None

    @property
    def response_text(self) -> str | None:
        """Get the response text if available."""
        if self.result and len(self.result) > 0:
            return self.result[0].text
        return None


# Type alias for the next middleware function
NextMiddleware = Callable[[ToolContext], Awaitable[list[TextContent]]]


class Middleware(ABC):
    """Abstract base class for middleware implementations.

    Middleware can:
    - Inspect/modify the request before dispatch
    - Short-circuit and return a response without calling next
    - Inspect/modify the response after dispatch
    - Log or track metrics
    """

    @property
    def name(self) -> str:
        """Name of this middleware for logging/debugging."""
        return self.__class__.__name__

    @abstractmethod
    async def process(
        self,
        ctx: ToolContext,
        next_middleware: NextMiddleware,
    ) -> list[TextContent]:
        """Process a tool call through this middleware.

        Args:
            ctx: The tool context with request data and mutable state
            next_middleware: Function to call the next middleware in chain

        Returns:
            The tool result (possibly modified)

        Implementations should typically:
        1. Do pre-processing (logging, checks, modifications)
        2. Call `await next_middleware(ctx)` to continue the chain
        3. Do post-processing (logging, transformations)
        4. Return the result

        To short-circuit (skip remaining middleware):
        - Return a result directly without calling next_middleware
        - Set ctx.result before returning for consistency
        """
        ...

    def should_process(self, ctx: ToolContext) -> bool:
        """Check if this middleware should process the given context.

        Override to skip processing for certain tools or conditions.
        Default: process all tool calls.
        """
        return True
