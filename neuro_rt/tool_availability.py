"""Public tool availability for the explicitly authorized test phase.

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
    Tool('nidus', 'nidus', 'Nidus RT', '/neuro/nidus', True, 'testing', '[fase de testes]'),
    Tool('glioma', 'neuro_glioma', 'Glioma RT', '/neuro/glioma', True,
         'testing', '[fase de testes]'),
    Tool('metastasis', 'neuro_metastasis', 'Metastasis RT', '/neuro/metastasis', True,
         'testing', '[fase de testes]'),
    Tool('meningioma', 'neuro_meningioma', 'Meningioma RT', '/neuro/meningioma', True,
         'testing', '[fase de testes]'),
    Tool('anatomia', 'neuro_anatomia', 'Anatomia RT', '/neuro/anatomia', True,
         'testing', '[fase de testes]'),
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
