"""Public tool availability for the staged Nidus-only delivery.

Keep this gate separate from the scientific catalogue: possessing model assets
does not make a tool available in the current product delivery.
"""
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Tool:
    id: str
    card_id: str
    title: str
    route: str
    enabled: bool
    state: str
    label: str


TOOLS = (
    Tool('nidus', 'nidus', 'Nidus RT', '/neuro/nidus', True, 'ready', ''),
    Tool('glioma', 'neuro_glioma', 'Glioma RT', '/neuro/glioma', False,
         'under_construction', '[em construção]'),
    Tool('metastasis', 'neuro_metastasis', 'Metastasis RT', '/neuro/metastasis', False,
         'under_construction', '[em construção]'),
    Tool('meningioma', 'neuro_meningioma', 'Meningioma RT', '/neuro/meningioma', False,
         'under_construction', '[em construção]'),
    Tool('anatomia', 'neuro_anatomia', 'Anatomia RT', '/neuro/anatomia', False,
         'under_construction', '[em construção]'),
)


class ToolUnavailable(ValueError):
    """The requested tool is known but not enabled in this delivery."""


def available_tools():
    """Return an independent JSON-ready description for the host and clients."""
    return [asdict(tool) for tool in TOOLS]


def require_tool(tool_id):
    """Return the enabled tool or reject a missing/unfinished tool explicitly."""
    for tool in TOOLS:
        if tool.id == tool_id:
            if not tool.enabled:
                raise ToolUnavailable(f'{tool.title} {tool.label}.')
            return tool
    raise ValueError('Ferramenta NEURO RT desconhecida.')
