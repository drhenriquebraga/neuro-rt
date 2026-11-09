"""Static allowlist; importing it never imports a scientific runtime."""
from .adapters.raidionics import RaidionicsAdapter
from .adapters.attention_unet import AttentionUNetAdapter
from .adapters.synthseg import SynthSegAdapter
from .adapters.cerebra_ants import CerebraANTsAdapter
from .adapters.raidionics_postop import RaidionicsPostopAdapter
from .adapters.buti_ct import ButiCTAdapter

ADAPTER_FACTORIES = {
    'raidionics': RaidionicsAdapter,
    'raidionics_postop': RaidionicsPostopAdapter,
    'attention_unet': AttentionUNetAdapter,
    'synthseg': SynthSegAdapter,
    'cerebra_ants': CerebraANTsAdapter,
    'buti_host': ButiCTAdapter,
}
ADAPTER_RUNTIME_IDS = {
    'raidionics': 'raidionics-onnx', 'raidionics_postop': 'raidionics-onnx',
    'attention_unet': 'neuro-scientific-cpu', 'synthseg': 'neuro-scientific-cpu',
    'cerebra_ants': 'neuro-scientific-cpu',
    'buti_host': 'host-nnunet',
}
