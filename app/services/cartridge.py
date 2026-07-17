from app.models.persona import PersonaDraft
from app.models.cartridge import PersonaCartridge


def forge(draft: PersonaDraft) -> PersonaCartridge:
    return PersonaCartridge(
        name=draft.name,
        summary=draft.summary,
        communication_style=draft.communication_style,
        core_values=draft.core_values,
        motivations=draft.motivations,
        strengths=draft.strengths,
        weaknesses=draft.weaknesses,
        goals=draft.goals,
        boundaries=draft.boundaries,
        preferences=draft.preferences,
    )
