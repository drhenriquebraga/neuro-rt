# NIDUS functional corrections for host 8.24

## Plan and causes

1. Separate the loading artwork from factual progress. The old dialog wrote the same phrase into both places. Use the requested public Thinking states recipe only in this artwork; translate progress explicitly because the removed repeated loader call had also triggered translation.
2. Reuse the loaded reference and folder inventory for acquired temporal phases. Metadata inspection stopped at 60 while the MAV folder exposes more compatible series. Inspect up to 128, deduplicate inventory, automatically open a unique same-study group, and preserve explicit choice for ambiguity. Static TOF never becomes temporal data.
3. Paint in the exact projection pixel grid. Preserve disconnected islands and erased holes as a 1024-square packed binary raster, carried through incidence persistence, backprojection and signed-distance consensus. Pencil behavior remains unchanged. Persist an entirely erased draft too.
4. Separate retained-PNG decoding from cold HTTP projection jobs. Previously an encoded cache hit waited behind expensive new projections. Keep MPR images in a separate bounded cache, retain 512 encoded entries under 192 MiB, and at most 12 decoded static projections. MPR has its own 48 MiB budget. CINE retains the bounded acquired frames needed for playback.
5. Send read-only consensus mesh previews directly to the threadpool under the session lock instead of the global segmentation queue. Edits and export retain their queue behavior. Reject stale candidate/revision responses.
6. Integrate the host editor inline through its externalScene contract. The existing NIDUS renderer stays in the 3D pane. Accept preview meshes only for matching load generation, ticket, source, SeriesInstanceUID and FrameOfReferenceUID. Reuse GPU buffers by session/ROI/geometry_revision. Enlarge only display bounds for new ROIs; never change the projection crop. Convert voxel-centre fractions correctly when centering MPR.
7. Preserve the projection draft on editor Escape/return. Return suspends the editor draft without forcing an RTSTRUCT export. Saving an incidence confirms Projection saved. Remove the standalone long suggestion-ready sentence.

## Verification

- Chrome interactions: brush and eraser on zoomed projection, exact saved raster sent to consensus, saved-button feedback, erase-all persisted across restore; MPR brush/undo/cancel/physical diameter shortcuts; folder inventory over 60, automatic TOF/CINE, current-reference discovery with no preexisting offer; stale mesh responses; UID/FoR guards; GPU reuse; crop and center mapping.
- Real host editor/API and synthetic oblique DICOM: NIDUS opens the inline editor, creates a named ROI, paints it, renders its LPS volume in the existing NIDUS 3D scene, returns without export, and resumes the same draft without reopening the series.
- Synthetic geometry: exact packed-mask roundtrip, holes and islands, rotated backprojection, consensus union/intersection endpoints, MPR planes, unchanged pencil behavior, invalid raster rejection, native oblique manual edits, CT and MR RTSTRUCT roundtrip.
- Consensus API tests: cancellation/persistence/revision safeguards and mesh previews outside the global segmentation queue.
- Cache tests: encoded cache hit completes while a cold HTTP job is held, cancellation/generation isolation, decoded/encoded memory bounds, initial readiness and preset cache reuse.
- Integrated CINE UI verified in all 12 supported languages. Thinking states rotates distinct work-related phrases, progress does not duplicate the artwork, reduced-motion guard and cleanup are exercised.

## Read-only MAV browser receipt

The full original folder was selected through the real NIDUS UI and real APIs. The source contains 68 series; the UI exposed 65 compatible series. One folder scan automatically selected original TOF and discovered one 48-phase acquired 3D temporal group.

- TOF: 204 x 512 x 512, initial volume/MPR/79-projection preparation: 169.927 s.
- Static cache after preparation: 61,557,717 bytes; 79 entries; 12 decoded.
- CINE: 48 acquired phases, prepare plus frame loading: 103.366 s.
- CINE cache: 207,245,975 bytes; 48 decoded frames. Playback and return succeeded.
- After returning to TOF, moving to the neighboring prepared incidence and back made zero projection HTTP requests.
- One folder scan, zero browser errors, zero exports, all 4,024 source files unchanged by size and mtime.

The local private screenshot and raw request receipt are not repository artifacts. The sanitized receipt is held by the host release coordinator. These engineering checks do not assert clinical accuracy.

## Motion source

The requested free recipe is https://github.com/Jakubantalik/transitions.dev/blob/main/cli/free/thinking-states.md . Its 150 ms swap, 50 ms gap, 8 px displacement, 2 px blur, 2 s shimmer and reduced-motion behavior are scoped to the new artwork. No generic motion fixer or paid recipe was used.
