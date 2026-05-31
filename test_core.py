import numpy as np
import crypto_core as cc

rng = np.random.default_rng(0)
# test on a few shapes incl. odd dims and grayscale
imgs = {
    "rgb_64": rng.integers(0, 256, (64, 64, 3), dtype=np.uint8),
    "gray_50": rng.integers(0, 256, (50, 50), dtype=np.uint8),
    "rgb_odd": rng.integers(0, 256, (37, 41, 3), dtype=np.uint8),
}

KEY = "course-project-2026"
combos = [(c, d) for c in cc.CONFUSION for d in cc.DIFFUSION]

print("=== ROUND-TRIP EXACTNESS (must all be True) ===")
ok = True
for name, img in imgs.items():
    for c, d in combos:
        enc = cc.encrypt(img, KEY, c, d, rounds=3)
        dec = cc.decrypt(enc, KEY, c, d, rounds=3)
        same = np.array_equal(dec, img)
        ok &= same
        if not same:
            print(f"  FAIL {name} {c}/{d}")
print("all exact:", ok)

print("\n=== KEY SENSITIVITY (wrong key must NOT recover) ===")
img = imgs["rgb_64"]
enc = cc.encrypt(img, KEY, "perm", "inn", rounds=3)
dec_wrong = cc.decrypt(enc, KEY + "x", "perm", "inn", rounds=3)
print("recovers with wrong key:", np.array_equal(dec_wrong, img), "(should be False)")


# ---- metrics ----
def entropy(a):
    h = np.bincount(a.reshape(-1), minlength=256).astype(float)
    p = h / h.sum(); p = p[p > 0]
    return -(p * np.log2(p)).sum()

def npcr_uaci(c1, c2):
    d = (c1 != c2)
    npcr = 100.0 * d.mean()
    uaci = 100.0 * np.abs(c1.astype(int) - c2.astype(int)).mean() / 255.0
    return npcr, uaci

def corr_adjacent(a):
    x = a.reshape(-1).astype(float)
    return np.corrcoef(x[:-1], x[1:])[0, 1]

# build a structured (non-random) plaintext so correlation/entropy are meaningful
yy, xx = np.mgrid[0:128, 0:128]
plain = ((xx // 8 + yy // 8) % 2 * 200 + 30).astype(np.uint8)  # checkerboard-ish
plain = np.stack([plain, np.roll(plain, 10), np.roll(plain, 20)], -1)

print("\n=== METRICS (perm + inn, 3 rounds) ===")
enc = cc.encrypt(plain, KEY, "perm", "inn", rounds=3)
print(f"plain entropy : {entropy(plain):.4f}")
print(f"cipher entropy: {entropy(enc):.4f}   (ideal 8.0)")
print(f"plain adj-corr: {corr_adjacent(plain):+.4f}")
print(f"cipher adj-corr:{corr_adjacent(enc):+.4f}  (ideal ~0)")

# differential: flip one pixel in plaintext
plain2 = plain.copy(); plain2[0, 0, 0] ^= 1
enc2 = cc.encrypt(plain2, KEY, "perm", "inn", rounds=3)
n, u = npcr_uaci(enc, enc2)
print(f"NPCR: {n:.4f}%  (ideal ~99.6)   UACI: {u:.4f}%  (ideal ~33.4)")
