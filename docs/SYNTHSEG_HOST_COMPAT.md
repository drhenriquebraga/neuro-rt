# SynthSeg compatibility with the shared host Python

The host's Python 3.10, DIPY 1.11 and PyTorch 2.5 are retained. This port does not
install Python, create a virtual environment, install DIPY 1.12, replace scientific
packages or monkeypatch the base interpreter. The plugin's scientific adapter
imports `neuro_rt.compat_synthseg.SynthSeg` and records its COMPAT_REVISION together
with the actual DIPY and PyTorch base versions in the result provenance.

The source is pinned to DIPY revision
`407e9319cbfe3d05304682d317363ecd09a83fdc`. The architecture and every scientific
method are preserved verbatim. The original `transform_img` and `recover_img`
functions in DIPY 1.11 have different signatures and implementations, and its
topological cleanup lacks `remove_holes=False`; simply importing those helpers
would either fail or change the computation. Private copies of the 1.12 helpers
provide the exact behavior without altering the installed DIPY namespace.

Local changes are limited to helper imports, a standard-library logger local to
this module, a revision identifier, and disabling the default download hook. The
adapter keeps its OfflineSynthSeg subclass and loads only the prepared, verified
checkpoint. Constructing the base SynthSeg class without that override fails
explicitly rather than accessing the internet. CPU-only behavior is preserved;
strict GPU mode is refused by the adapter.

The workflow remains the reference transformation to 1 mm and 192³, percentile
normalization, 33-channel U-Net, flip augmentation and left/right label mapping,
the original Gaussian filtering, topological cleanup with holes retained, and
nearest-neighbor recovery to the original grid. The reference's interpolation,
crop/FOV boundaries, smoothing-axis order and batch-tail behavior have not been
silently corrected. This is not a claim of equivalence to the TensorFlow SynthSeg
variants or clinical accuracy.

Audited sources and SHA-256:

| Source | SHA-256 |
| --- | --- |
| nn/torch/synthseg.py | aef78a8a9a47975c22cfcdf87dcd0ed7dc982e6c4b5fb450991286c32ec1091d |
| nn/utils.py | 8fe8d9e3f609a92801cb50aaaba25e9cfea6308a06c276986e9c7e108737878f |
| Official weights, 53,002,209 bytes | 3023c046e3996796b1e87badeb337cc7edd2da4c79794a0214afc76b63c701fe |

The segment helper was fetched through the connected GitHub source at that
revision, Git blob `b6b1708e57c05257eb26c646bbf1b63697a63e88`.
Full license texts and change notices accompany the port under `licenses/`.

`tests/test_synthseg_compat.py` compares architecture/method ASTs to the pinned
source; compares geometric helpers bit for bit for noncubic arrays, anisotropy,
rotation, reflection, translation, cropping and padding; checks nearest-neighbor
label recovery; compares cleanup to the official same-revision helper; checks
that base DIPY helpers are not replaced and default download is disabled; and
loads the official checkpoint strictly for a small 32³ CPU forward pass.
Optional reference/checkpoint tests skip when model resources are absent in CI.
All local verification uses synthetic inputs. A full 192³ adapter inference is
a separate integration gate run by the model validation harness.
