from __future__ import annotations

import logging

import sentry_sdk
from django.http import HttpResponse
from rest_framework import status
from rest_framework.request import Request

from sentry.integrations.discord.requests.base import DiscordRequest, DiscordRequestError
from sentry.integrations.discord.views.link_identity import DiscordLinkIdentityView
from sentry.integrations.discord.views.unlink_identity import DiscordUnlinkIdentityView
from sentry.integrations.discord.webhooks.base import DiscordInteractionsEndpoint
from sentry.middleware.integrations.parsers.base import BaseRequestParser
from sentry.models.integrations import Integration
from sentry.models.outbox import WebhookProviderIdentifier
from sentry.types.integrations import EXTERNAL_PROVIDERS, ExternalProviders
from sentry.utils.signing import unsign

logger = logging.getLogger(__name__)


class DiscordRequestParser(BaseRequestParser):
    provider = EXTERNAL_PROVIDERS[ExternalProviders.DISCORD]
    webhook_identifier = WebhookProviderIdentifier.DISCORD

    control_classes = [
        DiscordLinkIdentityView,
        DiscordUnlinkIdentityView,
    ]

    # Dynamically set to avoid RawPostDataException from double reads
    _discord_request: DiscordRequest | None = None

    @property
    def discord_request(self) -> DiscordRequest | None:
        if self._discord_request is not None:
            return self._discord_request
        if self.view_class != DiscordInteractionsEndpoint:
            return None
        drf_request: Request = DiscordInteractionsEndpoint().initialize_request(self.request)
        self._discord_request: DiscordRequest = self.view_class.discord_request_class(drf_request)
        return self._discord_request

    def get_integration_from_request(self) -> Integration | None:
        if self.view_class in self.control_classes:
            params = unsign(self.match.kwargs.get("signed_params"))
            integration_id = params.get("integration_id")

            logger.info(
                "%s.get_integration_from_request.%s",
                self.provider,
                self.view_class.__name__,
                extra={"path": self.request.path, "integration_id": integration_id},
            )
            return Integration.objects.filter(id=integration_id).first()

        discord_request = self.discord_request
        if self.view_class == DiscordInteractionsEndpoint and discord_request:
            with sentry_sdk.push_scope() as scope:
                scope.set_extra("path", self.request.path)
                scope.set_extra("guild_id", discord_request.guild_id)
                sentry_sdk.capture_message(
                    f"{self.provider}.get_integration_from_request.discord_interactions_endpoint"
                )

            return Integration.objects.filter(
                provider=self.provider,
                external_id=discord_request.guild_id,
            ).first()

        logger.info(
            "%s.get_integration_from_request.no_view_class",
            self.provider,
            extra={"path": self.request.path},
        )

        return None

    def get_response(self):
        if self.view_class in self.control_classes:
            return self.get_response_from_control_silo()

        is_discord_interactions_endpoint = self.view_class == DiscordInteractionsEndpoint

        with sentry_sdk.push_scope() as scope:
            scope.set_extra(
                "discord_request._data",
                self.discord_request._data if self.discord_request else None,
            )
            sentry_sdk.capture_message("discord.request_parser.get_response.request")

        # Handle any Requests that doesn't depend on Integration/Organization prior to fetching the Regions.
        if is_discord_interactions_endpoint and self.discord_request:
            # Discord will do automated, routine security checks against the interactions endpoint, including
            # purposefully sending invalid signatures.
            try:
                self.discord_request.validate()
            except DiscordRequestError:
                return HttpResponse(status=status.HTTP_401_UNAUTHORIZED)
            if self.discord_request.is_ping():
                return DiscordInteractionsEndpoint.respond_ping()

        regions = self.get_regions_from_organizations()
        if len(regions) == 0:
            logger.info("%s.no_regions", self.provider, extra={"path": self.request.path})
            return self.get_response_from_control_silo()

        if is_discord_interactions_endpoint and self.discord_request:
            if self.discord_request.is_command():
                return self.get_response_from_first_region()

            if self.discord_request.is_message_component():
                return self.get_response_from_all_regions()

        return self.get_response_from_control_silo()
