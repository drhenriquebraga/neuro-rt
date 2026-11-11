"""Read the existing geometric suggestion to position its three MPR slices."""
import math


def consensus_center(core, shape, temperature, candidate=None):
    import numpy as np
    if (len(shape) != 3 or any(type(n) is not int or n <= 0 for n in shape)
            or not math.isfinite(float(temperature)) or not 0 <= float(temperature) <= 100):
        raise ValueError('Referência do consenso inválida.')
    total, sums = 0, [0.0, 0.0, 0.0]
    rows, columns = np.arange(shape[1], dtype=float), np.arange(shape[2], dtype=float)
    for index in range(shape[0]):
        plane = (candidate.plane(0, index) if candidate is not None
                 else core.plane(temperature, 0, index))
        plane = np.asarray(plane, dtype=bool)
        if plane.shape != tuple(shape[1:]):
            raise ValueError('Plano do consenso fora da referência.')
        count = int(plane.sum(dtype=np.int64))
        total += count
        sums[0] += index * count
        sums[1] += float(rows @ plane.sum(axis=1, dtype=np.int64))
        sums[2] += float(columns @ plane.sum(axis=0, dtype=np.int64))
    if not total:
        return {'vazio': True, 'voxels': 0}
    center = [value / total for value in sums]
    result = {'vazio': False, 'voxels': total, 'centro': center,
              'posicoes': [max(0., min(1., center[axis] / (shape[axis] - 1)))
                           if shape[axis] > 1 else .5 for axis in range(3)]}
    if getattr(core, 'geometry', None) is not None and getattr(core, 'eixos', None) is not None:
        native = [0., 0., 0.]
        for axis, native_axis in enumerate(core.eixos[0]):
            native[native_axis] = shape[axis] - 1 - center[axis] if core.eixos[1][axis] else center[axis]
        geometry = core.geometry
        xyz = np.asarray(native[::-1]) * np.asarray(geometry['spacing'])
        physical = np.asarray(geometry['origin']) + np.asarray(geometry['direction']).reshape(3, 3) @ xyz
        result['centro_lps_mm'] = physical.tolist()
    return result
