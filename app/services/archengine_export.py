from __future__ import annotations

from dataclasses import replace as _replace
from datetime import datetime, timezone

from app.integrations.archengine import (
    ARCHEngineCompatibilityShim,
    CartridgeDescriptorPayload,
    CHIMERA_COMPATIBILITY_VERSION,
    TranslationError,
)
from app.models.cartridge import PersonaCartridge
from app.models.projection import RuntimeProjectionBuilder


def export_archengine_payload(
    cartridge: PersonaCartridge,
) -> CartridgeDescriptorPayload:
    """Public API: produce an ARCHEngine-compatible payload from a forged cartridge.

    The projection and compatibility shim remain internal implementation details.
    Callers interact only with this function and the returned payload.
    """
    projection = RuntimeProjectionBuilder.build(cartridge)
    payload = ARCHEngineCompatibilityShim.translate(projection)

    chimera = dict(payload.metadata.get("chimera", {}))
    chimera["schema_version"] = cartridge.manifest.schema_version
    chimera["compatibility_version"] = CHIMERA_COMPATIBILITY_VERSION
    chimera["exported_at"] = datetime.now(timezone.utc).isoformat()
    chimera["exporter"] = "CHIMERA"
    chimera["target"] = "ARCHEngine"

    new_metadata = dict(payload.metadata)
    new_metadata["chimera"] = chimera

    return _replace(payload, metadata=new_metadata)


def export_archengine_payload_json(
    cartridge: PersonaCartridge,
) -> dict:
    """Public API: produce an ARCHEngine-compatible JSON dict from a forged cartridge.

    The returned dict comes directly from the payload's to_dict().
    No serialization logic is duplicated.
    """
    payload = export_archengine_payload(cartridge)
    return payload.to_dict()
