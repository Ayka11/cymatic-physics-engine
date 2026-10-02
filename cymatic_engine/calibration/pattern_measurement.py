import numpy as np

def normalize_density(image):
    x = np.asarray(image, float)
    x = np.maximum(x, 0)
    s = x.sum()
    if s == 0:
        raise ValueError("Density image has zero mass.")
    return x/s

def density_distance(a, b):
    pa, pb = normalize_density(a), normalize_density(b)
    return float(np.linalg.norm(pa-pb))
