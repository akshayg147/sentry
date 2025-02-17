from rest_framework.request import Request
from rest_framework.response import Response

from sentry import features
from sentry.api.api_owners import ApiOwner
from sentry.api.api_publish_status import ApiPublishStatus
from sentry.api.base import region_silo_endpoint
from sentry.api.bases import OrganizationEndpoint, OrganizationPermission
from sentry.api.serializers import serialize
from sentry.models.relay import RelayUsage


@region_silo_endpoint
class OrganizationRelayUsage(OrganizationEndpoint):
    owner = ApiOwner.OWNERS_INGEST
    publish_status = {
        "GET": ApiPublishStatus.UNKNOWN,
    }
    permission_classes = (OrganizationPermission,)

    def get(self, request: Request, organization) -> Response:
        has_relays = features.has("organizations:relay", organization, actor=request.user)
        if not has_relays:
            return Response(status=404)

        option_key = "sentry:trusted-relays"
        trusted_relays = organization.get_option(option_key)
        if trusted_relays is None or len(trusted_relays) == 0:
            return Response([], status=200)

        keys = [val.get("public_key") for val in trusted_relays]
        relay_history = list(RelayUsage.objects.filter(public_key__in=keys).order_by("-last_seen"))

        return Response(serialize(relay_history, request.user))
