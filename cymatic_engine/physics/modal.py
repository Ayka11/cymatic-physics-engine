from dataclasses import dataclass, field
import numpy as np

@dataclass(frozen=True)
class PlateMaterial:
    young_modulus_pa: float = 200e9
    poisson_ratio: float = 0.30
    density_kg_m3: float = 7850.0

@dataclass(frozen=True)
class PlateModel:
    length_x_m: float = 0.30
    length_y_m: float = 0.30
    thickness_m: float = 0.001
    material: PlateMaterial = field(default_factory=PlateMaterial)
    damping_ratio: float = 0.01
    n_modes_x: int = 16
    n_modes_y: int = 16

    @property
    def rigidity_nm(self):
        E, nu, h = self.material.young_modulus_pa, self.material.poisson_ratio, self.thickness_m
        return E*h**3/(12*(1-nu**2))

    @property
    def total_mass_kg(self):
        return self.material.density_kg_m3*self.thickness_m*self.length_x_m*self.length_y_m

    @property
    def modal_mass_kg(self):
        return self.total_mass_kg/4.0

def mode_index(m, n, n_max):
    return (m-1)*n_max+(n-1)

def modal_frequency_hz(plate, m, n):
    omega = np.pi**2*np.sqrt(plate.rigidity_nm/(
        plate.material.density_kg_m3*plate.thickness_m))*(
        (m/plate.length_x_m)**2+(n/plate.length_y_m)**2)
    return float(omega/(2*np.pi))
