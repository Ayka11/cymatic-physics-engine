import numpy as np
from dataclasses import dataclass
from .modal import PlateModel

@dataclass(frozen=True)
class PlateSequence:
    x_m: np.ndarray
    y_m: np.ndarray
    time_sec: np.ndarray
    displacement: np.ndarray
    acceleration: np.ndarray
    metadata: dict


def reconstruct_sequence(plate: PlateModel, modal_ts, nx=64, ny=64, max_frames=240):
    x=np.linspace(0,plate.length_x_m,nx); y=np.linspace(0,plate.length_y_m,ny)
    sx=np.sin(np.arange(1,plate.n_modes_x+1)[:,None]*np.pi*x[None,:]/plate.length_x_m)
    sy=np.sin(np.arange(1,plate.n_modes_y+1)[:,None]*np.pi*y[None,:]/plate.length_y_m)
    idx=np.linspace(0, modal_ts.q.shape[1]-1, min(max_frames,modal_ts.q.shape[1])).astype(int)
    disp=[]; acc=[]
    for k in idx:
        Q=modal_ts.q[:,k].reshape(plate.n_modes_x,plate.n_modes_y)
        A=modal_ts.qddot[:,k].reshape(plate.n_modes_x,plate.n_modes_y)
        disp.append(sx.T@Q@sy); acc.append(sx.T@A@sy)
    return PlateSequence(x,y,modal_ts.time_sec[idx],np.asarray(disp),np.asarray(acc),
                         {"grid":[nx,ny],"frames":len(idx),"frame_selection":"uniform"})
