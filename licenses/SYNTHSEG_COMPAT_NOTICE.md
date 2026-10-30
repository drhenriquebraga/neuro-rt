# Notices for the SynthSeg host compatibility port

The implementation in `neuro_rt/compat_synthseg.py` is derived from
[DIPY's SynthSeg PyTorch implementation](https://github.com/dipy/dipy/blob/407e9319cbfe3d05304682d317363ecd09a83fdc/dipy/nn/torch/synthseg.py),
revision `407e9319cbfe3d05304682d317363ecd09a83fdc`.
Its original header states that the architecture and weights are original from
[SynthSeg](https://github.com/BBillot/SynthSeg) and remain Apache-2.0 licensed.
That header is retained. The full Apache-2.0 text accompanies this distribution
in `SYNTHSEG_ARCHITECTURE_APACHE_2.txt`.

`neuro_rt/compat_synthseg_utils.py` retains algorithms from DIPY
[`dipy/nn/utils.py`](https://github.com/dipy/dipy/blob/407e9319cbfe3d05304682d317363ecd09a83fdc/dipy/nn/utils.py)
and [`dipy/segment/utils.py`](https://github.com/dipy/dipy/blob/407e9319cbfe3d05304682d317363ecd09a83fdc/dipy/segment/utils.py)
at the same revision. These helpers are BSD-3-Clause, copyright (c) 2008-2026,
dipy developers. All rights reserved. The complete copyright, redistribution
conditions and disclaimer are retained in `DIPY_SYNTHSEG_COMPAT_BSD.txt`.

Local modifications, 30 October 2026: the pinned algorithms use a private Neuro
RT namespace so that the installed DIPY 1.11 is not replaced or patched; logging
uses a local standard-library logger because the 1.12 logging module does not
exist in 1.11; the default constructor download hook is disabled. The adapter's
instance subclass binds that hook to its already verified local weights.
Architecture, prediction, preprocessing and topological algorithms are unchanged.

Weights are not included in the source or SETUP package. Their original license
and provenance remain required in each prepared model resource; this notice does
not replace the weights' Apache-2.0 license file. Neither the DIPY contributors
nor the SynthSeg authors endorse this local port.
