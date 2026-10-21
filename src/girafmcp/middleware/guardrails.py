"""Guardrails middleware for scaffolded AI responses.

Intercepts tool calls to implement tiered responses, prompts for reflection,
and cooldown periods that encourage skill building over dependency.
"""

import logging

from mcp.types import TextContent

from girafmcp.core.features import is_guardrails_enabled
from girafmcp.core.services.guardrails_service import (
    GuardrailsConfig,
    GuardrailsService,
)
from girafmcp.middleware.base import Middleware, NextMiddleware, ToolContext

logger = logging.getLogger(__name__)


class GuardrailsMiddleware(Middleware):
    """Middleware that implements scaffolded responses for skill building.

    Supports multiple modes:
    - prompt: Ask "What have you tried?" before answering
    - tiered: Provide hints in escalating detail (1=hint, 2=guidance, 3=example, 4=full)
    - cooldown: Add reflection delay before full solutions

    Integrates with session state to track:
    - Current tier for tiered responses
    - Whether prompt was shown for current query
    - Cooldown expiration time
    """

    def __init__(self, service: GuardrailsService | None = None):
        """Initialize the guardrails middleware.

        Args:
            service: GuardrailsService instance. If None, creates default service.
        """
        self.service = service or GuardrailsService()

    @property
    def name(self) -> str:
        return "GuardrailsMiddleware"

    def should_process(self, ctx: ToolContext) -> bool:
        """Check if this middleware should process the context.

        Args:
            ctx: The tool context

        Returns:
            True if guardrails feature is enabled
        """
        return is_guardrails_enabled()

    async def process(
        self,
        ctx: ToolContext,
        next_middleware: NextMiddleware,
    ) -> list[TextContent]:
        """Process tool call with guardrails.

        Args:
            ctx: Tool context with request data
            next_middleware: Next middleware in chain

        Returns:
            Tool result, possibly modified by guardrails
        """
        session = ctx.session

        # Extract query text for analysis
        query_text = self._extract_query_text(ctx)

        # Get guardrail decision
        decision = self.service.get_decision(
            tool_name=ctx.name,
            query_text=query_text,
            team_id=session.team_id,
            session_tier=session.guardrail_tier,
            session_prompted=session.guardrail_prompted,
            cooldown_until=session.cooldown_until,
        )

        # Record guardrail state in context metadata for logging
        ctx.metadata["guardrail_mode"] = self.service.config.get_team_mode(
            session.team_id
        ).value
        ctx.metadata["guardrail_tier"] = session.guardrail_tier

        # Handle decision
        if decision.action == "allow":
            # No guardrail intervention, pass through
            return await next_middleware(ctx)

        elif decision.action == "prompt":
            # Show attempt-first prompt and short-circuit
            session.guardrail_prompted = True
            session.last_tool = ctx.name
            session.last_arguments = ctx.arguments.copy()

            logger.debug(f"Guardrails: prompting for {ctx.name}")
            return [TextContent(type="text", text=decision.response or "")]

        elif decision.action == "tier":
            # Get base result and append tier suffix
            result = await next_middleware(ctx)

            if decision.tier_suffix and result:
                # Append tier guidance to response
                modified_text = result[0].text + "\n" + decision.tier_suffix
                result = [TextContent(type="text", text=modified_text)]

            # Record for request_more_detail
            session.last_tool = ctx.name
            session.last_arguments = ctx.arguments.copy()
            session.last_response = result[0].text if result else None

            logger.debug(f"Guardrails: tier {decision.tier} response for {ctx.name}")
            return result

        elif decision.action == "cooldown":
            # Show reflection prompt and short-circuit
            logger.debug(f"Guardrails: in cooldown for {ctx.name}")
            return [TextContent(type="text", text=decision.response or "")]

        elif decision.action == "cooldown_start":
            # Start new cooldown and allow request
            session.cooldown_until = self.service.calculate_cooldown_end()
            logger.debug(f"Guardrails: starting cooldown for {ctx.name}")
            return await next_middleware(ctx)

        # Fallback: allow
        return await next_middleware(ctx)

    def _extract_query_text(self, ctx: ToolContext) -> str | None:
        """Extract natural language query from tool arguments.

        Args:
            ctx: The tool context

        Returns:
            Query text if found, None otherwise
        """
        args = ctx.arguments

        # Direct query parameter
        if "query" in args:
            return str(args["query"])

        # For file retrieval
        if ctx.name == "get_file" and "path" in args:
            repo = args.get("repo", "")
            path = args.get("path", "")
            return f"get file {repo}/{path}"

        return None


def create_guardrails_middleware(
    config_path: str | None = None,
) -> GuardrailsMiddleware:
    """Create a configured GuardrailsMiddleware instance.

    Args:
        config_path: Optional path to guardrails.yaml

    Returns:
        Configured GuardrailsMiddleware
    """
    from pathlib import Path

    config = None
    if config_path:
        config = GuardrailsConfig(Path(config_path))

    service = GuardrailsService(config)
    return GuardrailsMiddleware(service)
