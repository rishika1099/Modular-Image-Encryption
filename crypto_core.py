"""
crypto_core.py
Modular image encryption pipeline: swappable CONFUSION (permutation) and
DIFFUSION (value-mixing) stages, all keyed and exactly invertible over uint8.

Pipeline (per round):  confusion -> diffusion, repeated R rounds.
Everything is lossless: decrypt(encrypt(x)) == x exactly.

Modules implemented:
  Confusion:  'perm'      keyed global pixel permutation (baseline)
              'spectral'  graph-spectral block ordering (Fiedler vector)
  Diffusion:  'xor'       keyed XOR keystream (baseline)
              'latin'     keyed Latin-square additive mixing (provably balanced)
              'inn'       keyed integer coupling network (RealNVP-style, lossless)

NOTE: These are research/coursework primitives, NOT cryptographically vetted
ciphers. Use for studying confusion/diffusion behaviour, not real secrets.
"""
import hashlib
import numpy as np


# ----------------------------------------------------------------------
# Key derivation helpers
# ----------------------------------------------------------------------
def _seed(key: str, label: str) -> int:
    h = hashlib.sha256(f"{key}|{label}".encode()).digest()
    return int.from_bytes(h[:8], "big")


def _rng(key: str, label: str) -> np.random.Generator:
    return np.random.default_rng(_seed(key, label))


# ----------------------------------------------------------------------
# CONFUSION: permutation modules  (operate on a flat uint8 vector)
# ----------------------------------------------------------------------
def _perm_indices(n: int, key: str, label: str) -> np.ndarray:
    return _rng(key, label).permutation(n)


def confuse_perm(flat: np.ndarray, key: str, inverse: bool, rnd: int) -> np.ndarray:
    idx = _perm_indices(flat.size, key, f"perm{rnd}")
    if not inverse:
        return flat[idx]
    out = np.empty_like(flat)
    out[idx] = flat
    return out


def _spectral_order(m: int, key: str, label: str) -> np.ndarray:
    """Order m nodes by the Fiedler vector of a key-seeded random graph."""
    r = _rng(key, label)
    A = r.random((m, m))
    A = (A + A.T) / 2.0           # symmetric weights, content-independent
    np.fill_diagonal(A, 0.0)
    L = np.diag(A.sum(1)) - A     # graph Laplacian
    w, v = np.linalg.eigh(L)
    fiedler = v[:, 1]             # 2nd-smallest eigenvector
    return np.argsort(fiedler)


def confuse_spectral(flat: np.ndarray, shape, key: str, inverse: bool, rnd: int,
                     grid: int = 8) -> np.ndarray:
    """Reorder a grid x grid arrangement of image blocks by spectral order."""
    h, w = shape[0], shape[1]
    ch = 1 if len(shape) == 2 else shape[2]
    img = flat.reshape(shape)
    gh, gw = grid, grid
    bh, bw = h // gh, w // gw
    if bh == 0 or bw == 0:        # image too small for this grid -> fall back
        return confuse_perm(flat, key, inverse, rnd)
    H, W = bh * gh, bw * gw
    core = img[:H, :W]
    order = _spectral_order(gh * gw, key, f"spec{rnd}")
    # gather blocks
    blocks = core.reshape(gh, bh, gw, bw, ch).swapaxes(1, 2).reshape(gh * gw, bh, bw, ch)
    if not inverse:
        blocks = blocks[order]
    else:
        inv = np.empty_like(order); inv[order] = np.arange(order.size)
        blocks = blocks[inv]
    core2 = blocks.reshape(gh, gw, bh, bw, ch).swapaxes(1, 2).reshape(H, W, ch)
    out = img.copy()
    out[:H, :W] = core2.reshape(core.shape)
    return out.reshape(-1)


# ----------------------------------------------------------------------
# DIFFUSION: value-mixing modules  (operate on a flat uint8 vector)
# ----------------------------------------------------------------------
def diffuse_xor(flat: np.ndarray, key: str, inverse: bool, rnd: int) -> np.ndarray:
    ks = _rng(key, f"xor{rnd}").integers(0, 256, flat.size, dtype=np.uint8)
    return np.bitwise_xor(flat, ks)   # self-inverse


def diffuse_latin(flat: np.ndarray, key: str, inverse: bool, rnd: int) -> np.ndarray:
    """Additive mixing by a keyed Latin square  L[i] = (a*i + b) mod 256, a odd."""
    r = _rng(key, f"latin{rnd}")
    a = int(r.integers(0, 128)) * 2 + 1          # odd -> invertible mult mod 256
    b = int(r.integers(0, 256))
    i = np.arange(flat.size, dtype=np.int64)
    add = (a * i + b) % 256
    if not inverse:
        return ((flat.astype(np.int64) + add) % 256).astype(np.uint8)
    return ((flat.astype(np.int64) - add) % 256).astype(np.uint8)


def _coupling_t(a: np.ndarray, key: str, label: str) -> np.ndarray:
    """Keyed causal nonlinear mixer: t_i depends on key + all a_j (j<=i).
    Returns uint8 shift the same length as a. Recomputable identically at decrypt
    because it only ever reads the *unchanged* half a."""
    r = _rng(key, label)
    sbox = r.permutation(256).astype(np.int64)    # keyed 8-bit S-box
    k1 = int(r.integers(0, 256)) | 1
    k2 = int(r.integers(0, 256)) | 1
    k3 = int(r.integers(0, 256))
    acc = k3
    a64 = a.astype(np.int64)
    out = np.empty(a.size, dtype=np.int64)
    for i in range(a.size):                        # causal accumulation -> diffusion
        acc = (acc * k1 + a64[i] * k2 + k3) & 0xFF
        out[i] = sbox[(acc + a64[i]) & 0xFF]
    return out


def diffuse_inn(flat: np.ndarray, key: str, inverse: bool, rnd: int,
                layers: int = 4) -> np.ndarray:
    """Integer coupling network (RealNVP-style additive coupling).
    Exactly invertible over uint8; the 'weights' are the key-seeded S-box/consts."""
    n = flat.size
    half = (n + 1) // 2
    x = flat.astype(np.int64).copy()
    if not inverse:
        for L in range(layers):
            a, b = x[:half], x[half:]
            t = _coupling_t(a, key, f"inn{rnd}.{L}")[: b.size]
            x[half:] = (b + t) & 0xFF
            x = x[::-1].copy()                     # swap roles for next layer
        return x.astype(np.uint8)
    # inverse: undo layers in reverse, mirroring the swaps
    for L in reversed(range(layers)):
        x = x[::-1].copy()
        a, b = x[:half], x[half:]
        t = _coupling_t(a, key, f"inn{rnd}.{L}")[: b.size]
        x[half:] = (b - t) & 0xFF
    return x.astype(np.uint8)


# ----------------------------------------------------------------------
# Pipeline
# ----------------------------------------------------------------------
CONFUSION = {"perm": "perm", "spectral": "spectral"}
DIFFUSION = {"xor": "xor", "latin": "latin", "inn": "inn"}


def _confuse(flat, shape, key, name, inverse, rnd):
    if name == "perm":
        return confuse_perm(flat, key, inverse, rnd)
    if name == "spectral":
        return confuse_spectral(flat, shape, key, inverse, rnd)
    raise ValueError(name)


def _diffuse(flat, key, name, inverse, rnd):
    if name == "xor":
        return diffuse_xor(flat, key, inverse, rnd)
    if name == "latin":
        return diffuse_latin(flat, key, inverse, rnd)
    if name == "inn":
        return diffuse_inn(flat, key, inverse, rnd)
    raise ValueError(name)


def encrypt(img: np.ndarray, key: str, confusion="perm", diffusion="xor", rounds=2):
    shape = img.shape
    flat = img.reshape(-1).astype(np.uint8)
    for r in range(rounds):
        flat = _confuse(flat, shape, key, confusion, False, r)
        flat = _diffuse(flat, key, diffusion, False, r)
    return flat.reshape(shape)


def decrypt(img: np.ndarray, key: str, confusion="perm", diffusion="xor", rounds=2):
    shape = img.shape
    flat = img.reshape(-1).astype(np.uint8)
    for r in reversed(range(rounds)):
        flat = _diffuse(flat, key, diffusion, True, r)
        flat = _confuse(flat, shape, key, confusion, True, r)
    return flat.reshape(shape)
