"""Public tool availability independently of the scientific catalogue."""
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

    @property
    def display_title(self):
        return 'AutoContorno Neuro' if self.id == 'anatomia' else self.title


TOOLS = (
    Tool('nidus', 'nidus', 'Nidus RT', '/neuro/nidus', True, 'ready', ''),
    Tool('glioma', 'neuro_glioma', 'Glioma RT', '/neuro/glioma', True,
         'ready', ''),
    Tool('metastasis', 'neuro_metastasis', 'Metastasis RT', '/neuro/metastasis', True,
         'ready', ''),
    Tool('meningioma', 'neuro_meningioma', 'Meningioma RT', '/neuro/meningioma', True,
         'ready', ''),
    Tool('anatomia', 'neuro_anatomia', 'Anatomia RT', '/neuro/anatomia', True,
         'ready', ''),
)


class ToolUnavailable(ValueError):
    """The requested tool is known but not enabled in this delivery."""


def available_tools(enabled_ids=None):
    """Describe runtime readiness for each tool."""
    enabled_ids = set(enabled_ids) if enabled_ids is not None else {tool.id for tool in TOOLS}
    return [dict(asdict(tool), title=tool.display_title,
                 enabled=tool.enabled and tool.id in enabled_ids,
                 state=tool.state if tool.id in enabled_ids else 'models_missing',
                 label=tool.label if tool.id in enabled_ids else 'Requer modelos adicionais')
            for tool in TOOLS]


def require_tool(tool_id):
    """Return the enabled tool or reject a missing/unfinished tool explicitly."""
    for tool in TOOLS:
        if tool.id == tool_id:
            if not tool.enabled:
                raise ToolUnavailable(f'{tool.title} {tool.label}.')
            return tool
    raise ValueError('Ferramenta NEURO RT desconhecida.')
