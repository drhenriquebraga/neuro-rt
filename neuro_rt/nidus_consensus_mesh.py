"""Display-only consensus surface using the existing native mask mesher in RECON."""
import numpy as np

MAX_MESH_VOXELS = 4_000_000
MAX_MESH_TRIANGLES = 250_000


def candidate_mesh(candidate):
    import radai_recon3d as R
    bits = candidate.packed.bits
    occupied_z = np.flatnonzero(np.any(bits, axis=(1, 2)))
    if not len(occupied_z):
        return {'vertices': np.zeros((0, 3)), 'faces': np.zeros((0, 3), dtype=np.int64),
                'stl': b'', 'coordinate_system': 'LPS_mm', 'bounds_lps': None}
    occupied_y = np.flatnonzero(np.any(bits, axis=(0, 2)))
    occupied_bytes = np.flatnonzero(np.any(bits, axis=(0, 1)))
    z0, z1 = int(occupied_z[0]), int(occupied_z[-1]) + 1
    y0, y1 = int(occupied_y[0]), int(occupied_y[-1]) + 1
    b0, b1 = int(occupied_bytes[0]), int(occupied_bytes[-1]) + 1
    count_x = min((b1 - b0) * 8, candidate.packed.shape[2] - b0 * 8)
    if (z1 - z0 + 2) * (y1 - y0 + 2) * (count_x + 2) > MAX_MESH_VOXELS:
        raise ValueError('A visualização 3D excede o limite; o contorno editável foi preservado.')
    partial = np.unpackbits(bits[z0:z1, y0:y1, b0:b1], axis=-1, count=count_x).astype(bool)
    occupied_x = np.flatnonzero(np.any(partial, axis=(0, 1)))
    x_local0, x_local1 = int(occupied_x[0]), int(occupied_x[-1]) + 1
    mask = partial[:, :, x_local0:x_local1]
    # Refuse complexity instead of silently smoothing/decimating the editable contour.
    field = np.pad(np.float32(.5) - mask.astype(np.float32), 1, constant_values=.5)
    if R._triangulos_estimados(field) > MAX_MESH_TRIANGLES:
        raise ValueError('O contorno excede o limite da visualização 3D; a máscara foi preservada.')
    del field
    geometry = candidate.geometry
    spacing = np.asarray(geometry['spacing'], dtype=np.float64)
    direction = np.asarray(geometry['direction'], dtype=np.float64).reshape(3, 3)
    offset_xyz = np.array([b0 * 8 + x_local0, y0, z0], dtype=np.float64)
    origin = np.asarray(geometry['origin'], dtype=np.float64) + direction @ (offset_xyz * spacing)
    vertices, faces = R.malha_de_mascara(mask, tuple(spacing[::-1]), tuple(origin),
                                       tuple(direction.ravel()), suavizar_mm=0.)
    if len(faces) > MAX_MESH_TRIANGLES or not np.isfinite(vertices).all():
        raise ValueError('Não foi possível montar a visualização 3D dentro do limite.')
    return {'vertices': vertices, 'faces': faces, 'stl': R.stl_da_malha(vertices, faces),
            'coordinate_system': 'LPS_mm',
            'bounds_lps': [vertices.min(axis=0).tolist(), vertices.max(axis=0).tolist()] if len(vertices) else None}
