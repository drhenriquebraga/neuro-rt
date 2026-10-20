# Nidus RT

**Part of the Radioterapia.AI Local Suite. Nidus RT: the same lesion in two projections and where they intersect, the logic of biplanar angiography — teaching and research material, not a medical device.**

`License: Apache-2.0` · `Component of: Radioterapia.AI Local Suite` · `Platform: Windows 10 and 11, 64-bit`

> **Teaching and research material. This is not a medical device.**
> It is **not** validated for clinical use, and it has no ANVISA registration,
> no CE mark and no FDA clearance. The intersection it shows is a geometric
> construction from what the user draws — **not a treatment volume** —, and
> its projections do not replace digital subtraction angiography. Every
> structure in the suite is an **unapproved suggestion**; defining a target,
> reviewing and approving it are a physician's act, in the planning system.

## What it does

Biplanar angiography finds a lesion by drawing it in two incidences and
seeing where the two drawings cross. Nidus RT applies that logic to an
angio‑CT, or to a contrast‑enhanced MR, on the workstation:

1. **Project** the series in the incidence you choose — LAO/RAO and CRA/CAU
   on sliders or typed in, as a MIP over the whole volume or over a slab, with
   inverted colours, at the highest resolution. The three MPR planes stay
   beside the projection.
2. **Draw** the area with the pencil, freehand; letting go closes it, from the
   last point to the first. The area becomes a tube along the direction of
   that incidence.
3. **Repeat** in a second incidence. The tubes **intersect**, and the tubes
   and their intersection are shown as outlines on the MPR planes.

**The bone can leave the projection**, so that the small contrast‑filled
vessels stand out: Nidus RT uses the segmentation ContourLab already wrote for
that series (the complete set, or the label map of a 3D study) and takes the
bones out of the MIP. A series with no segmentation keeps its bone, and the
screen offers to segment it first (AUTO), through the workstation's single
queue — it does not guess the bone from density.

Each action is kept as a state in the browser tab (the drawings of each
incidence, with angles, crop and window): if an error comes anyway, the
screen goes back on its own to the last good state and says so, and nothing
drawn is lost. The drawing never goes to disk.

The case is picked in the Suite's series pop‑up — the archive table or a
folder you point to —, which the *Load series* card on the work screen
reopens. The series must be a 3D
volume with enough slices; a colour series is refused.

## What it does not do

- It does not detect and does not segment: it projects what the physician
  circled. Nothing here is learned.
- **It does not export and does not compute a volume.** The intersection is a
  visualisation construct, and a number in cm³ beside it would be a target
  volume with extra steps: the construct becomes a number, the number becomes
  a record, and the record becomes the thing compared with the plan. The tube
  mask is never written to disk.
- It does not replace digital angiography and shows no flow dynamics: on
  angio‑CT, and on contrast MR, the draining vein enhances like the feeding
  artery. And MR signal is not Hounsfield: the windows are relative to the
  series itself, and the brightness of one series does not compare with
  another's.

## What is ours, and what is not

No model and no weight: this module does not use AI — it is geometry.
Resampling and projection use [SimpleITK][sitk] (Apache‑2.0) and NumPy, and
the PNG is written with `zlib`. The bone it removes was drawn by ContourLab's
third‑party models, credited in ContourLab's `NOTICE`. These libraries are
installed by the Suite's preparer and do not travel in this repository.

## Privacy

Everything runs locally, and nothing is exported. The projections can show
the patient's face: an image of a real series does not leave the workstation.

## Part of the Local Suite

Nidus RT does not run on its own. The shared shell — the entrance page, the
menus, the twelve languages, the Terms and the Privacy Policy, the
configuration, the case archive, DICOM reading, the viewers and the queue —
lives in the [Suite][suite], and on the workstation the suite is one program:
one process, one port, one `app` folder, assembled by the Suite's installer
from the seven repositories. The projection uses the 3D Reconstructions core
module.

To use it, install the Suite with its light installer, from the
[releases of radioterapia-ai/local-suite][rel] (the permanent link to the
newest one is [`RADIOTERAPIA_AI_LOCAL_SUITE_SETUP_LATEST.zip`][latest]);
requirements and installation are in the Suite README.

This repository has no build of its own. The Suite's packager
(`build/empacotar_instalador.py --dos-repositorios`) downloads each component
at the tag pinned in `build/componentes.lock.json`, checks its SHA‑256 and
assembles the installer — see *Build from source* in the Suite README.

## Running the batteries

The batteries (`tools/test_*.py`, listed in `componente.json`) run over
synthetic phantoms. **No patient data is used anywhere in this repository, and
none may be committed to it.**

1. Put the [Suite][suite] and the six component repositories side by side in
   one folder. Folder names do not matter: the Suite is the folder with
   `tools/_componentes.py`, and each component is found by its
   `componente.json` (or set `RADAI_COMPONENTES_DIR` to the folder that holds
   the components). The batteries import modules of the Suite and of the
   other components, so all seven are needed.
2. Create the Suite's development environment: a Python virtual environment
   in `.venv` at the Suite root, as its README describes.
3. Run every battery of this component:

   ```
   <suite>\.venv\Scripts\python.exe <suite>\tools\_componentes.py --verificar <this folder>
   ```

   or a single one, with `--rodar test_<name>.py`. Each battery ends with an
   `OK:` or a `FALHOU:` footer, and `--verificar` ends with how many failed.
   `verify.cmd`, in this folder, does the same in two clicks once
   `_python.txt` (ignored by Git) holds the path of that `python.exe`.

4. **Turn on the pre‑commit hook** (once per clone):
   `git config core.hooksPath .githooks`. It runs the Suite's
   patient‑data scan over what is staged and refuses the commit that
   carries DICOM (with or without extension), a medical volume or a run
   log — and refuses it too when the scan cannot run, without the Suite
   beside this folder or without Python.

## Licence and name

The code is licensed under the [Apache License 2.0](LICENSE). As section 6
says, the licence grants no permission to use the trade names of the
Licensor — "Radioterapia.AI", "Local Suite" and "Nidus RT" included — except
as required to describe the origin of the work. A build you adapt is yours:
name it as yours.

| | Published code | A service's own build |
|---|---|---|
| What it is | Teaching and research material | An in‑house tool the service adapts, validates and registers in its own jurisdiction |
| Medical device? | **No.** Not validated for clinical use | Whatever that service's validation and registration make it |
| Who answers for it | Whoever downloads, modifies and deploys it answers for their own build, made with the Suite's build path | The service that deploys it |

Built by Dr. Henrique Braga, radiation oncologist —
**[radioterapia.ai](https://radioterapia.ai)**.

[sitk]: https://simpleitk.org
[suite]: https://github.com/radioterapia-ai/local-suite
[rel]: https://github.com/radioterapia-ai/local-suite/releases
[latest]: https://github.com/radioterapia-ai/local-suite/releases/latest/download/RADIOTERAPIA_AI_LOCAL_SUITE_SETUP_LATEST.zip
