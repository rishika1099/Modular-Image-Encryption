"""
app.py  -  Streamlit frontend for the modular image-encryption pipeline.
Run locally:   streamlit run app.py
Run in Colab:  see the commands your assistant gave you (localtunnel).
"""
import io
import os
import glob
import numpy as np
import streamlit as st
from PIL import Image
import matplotlib.pyplot as plt

import crypto_core as cc

APP_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(APP_DIR, "assets")

st.set_page_config(page_title="Modular Image Crypto", page_icon="🔐", layout="wide")
st.title("🔐 Modular Image Encryption: Confusion x Diffusion")
st.caption("Swap primitives, encrypt/decrypt losslessly, and read the security metrics. "
           "Research/coursework tool, not a vetted cipher.")

# ---------------- metrics ----------------
def entropy(a):
    h = np.bincount(a.reshape(-1), minlength=256).astype(float)
    p = h / h.sum(); p = p[p > 0]
    return float(-(p * np.log2(p)).sum())

def corr_adjacent(a):
    x = a.reshape(-1).astype(float)
    if x.size < 2:
        return 0.0
    return float(np.corrcoef(x[:-1], x[1:])[0, 1])

def npcr_uaci(c1, c2):
    d = (c1 != c2)
    npcr = 100.0 * d.mean()
    uaci = 100.0 * np.abs(c1.astype(int) - c2.astype(int)).mean() / 255.0
    return float(npcr), float(uaci)

def hist_fig(a, title):
    fig, ax = plt.subplots(figsize=(4, 2.4))
    ax.hist(a.reshape(-1), bins=64, color="#4C78A8")
    ax.set_title(title, fontsize=9); ax.set_xlim(0, 255)
    ax.tick_params(labelsize=7)
    fig.tight_layout()
    return fig

# ---------------- step-by-step trace ----------------
def encrypt_trace(img, key, confusion, diffusion, rounds):
    """Run the same pipeline as cc.encrypt, but snapshot the flat array after
    every confusion and diffusion sub-stage so the UI can show each step.
    Uses the core's stage functions, so behaviour matches cc.encrypt exactly."""
    shape = img.shape
    flat = img.reshape(-1).astype(np.uint8)
    steps = [("Original", flat.copy())]
    for r in range(rounds):
        flat = cc._confuse(flat, shape, key, confusion, False, r)
        steps.append((f"Round {r + 1} · confusion ({confusion})", flat.copy()))
        flat = cc._diffuse(flat, key, diffusion, False, r)
        last = "Encrypted (final)" if r == rounds - 1 else f"Round {r + 1} · diffusion ({diffusion})"
        steps.append((last, flat.copy()))
    return shape, steps

def decrypt_trace(enc, key, confusion, diffusion, rounds):
    """Reverse of encrypt_trace: snapshot each inverse stage so the UI can show
    the noise being unwound back to the original. Matches cc.decrypt exactly."""
    shape = enc.shape
    flat = enc.reshape(-1).astype(np.uint8)
    steps = [("Encrypted", flat.copy())]
    for r in reversed(range(rounds)):
        flat = cc._diffuse(flat, key, diffusion, True, r)
        steps.append((f"Round {r + 1} · un-diffusion ({diffusion})", flat.copy()))
        flat = cc._confuse(flat, shape, key, confusion, True, r)
        last = "Decrypted (final)" if r == 0 else f"Round {r + 1} · un-confusion ({confusion})"
        steps.append((last, flat.copy()))
    return shape, steps

# ---------------- sidebar controls ----------------
with st.sidebar:
    st.header("Settings")
    key = st.text_input("Secret key", value="wheresmyfoodkaren", type="password")
    confusion = st.selectbox("Confusion (permutation)", list(cc.CONFUSION),
                             help="perm = global pixel shuffle · spectral = graph-Fiedler block order")
    diffusion = st.selectbox("Diffusion (value mixing)", list(cc.DIFFUSION), index=2,
                             help="xor = keystream · latin = balanced additive · inn = integer coupling net")
    rounds = st.slider("Rounds", 1, 6, 3)
    show_steps = st.checkbox("Show every step", value=True,
                             help="Render each confusion/diffusion stage of every round.")
    up = st.file_uploader("Upload image", type=["png", "jpg", "jpeg", "bmp"])

# ---------------- load image ----------------
def load_default_image():
    """Load the default image from assets/. Prefers assets/default.*, else
    uses the first image file found. No fallback: if assets/ has no usable
    image, the app asks for an upload instead."""
    exts = ("jpg", "jpeg", "png", "bmp", "JPG", "JPEG", "PNG", "BMP")
    preferred = [p for e in exts for p in glob.glob(os.path.join(ASSETS_DIR, f"default.{e}"))]
    others = sorted(p for e in exts for p in glob.glob(os.path.join(ASSETS_DIR, f"*.{e}")))
    for path in preferred + others:
        try:
            pil = Image.open(path).convert("RGB")
            pil.thumbnail((512, 512))
            return np.array(pil, dtype=np.uint8), os.path.basename(path)
        except Exception:
            continue
    return None, None

if up is None:
    img, default_name = load_default_image()
    if img is None:
        st.warning("No image found in `assets/`. "
                   "Save one there, or upload an image in the sidebar.")
        st.stop()
    st.info(f"No upload: using default `{default_name}` 😎. Upload your own in the sidebar.")
else:
    pil = Image.open(up).convert("RGB")
    pil.thumbnail((512, 512))           # keep INN fast in the demo
    img = np.array(pil, dtype=np.uint8)

# ---------------- run pipeline ----------------
enc = cc.encrypt(img, key, confusion, diffusion, rounds)
dec = cc.decrypt(enc, key, confusion, diffusion, rounds)
lossless = np.array_equal(dec, img)

c1, c2, c3 = st.columns(3)
c1.image(img, caption="Original", use_container_width=True)
c2.image(enc, caption="Encrypted", use_container_width=True)
c3.image(dec, caption="Decrypted", use_container_width=True)

if lossless:
    st.success("✅ Decryption is exact (lossless)")
else:
    st.error("❌ Recovery mismatch")

# ---------------- step-by-step gallery ----------------
def render_gallery(shape, steps, ncol=4):
    for i in range(0, len(steps), ncol):
        cols = st.columns(ncol)
        for col, (label, fl) in zip(cols, steps[i:i + ncol]):
            col.image(fl.reshape(shape), caption=label, use_container_width=True)
            col.caption(f"entropy {entropy(fl):.3f}  ·  adj-corr {corr_adjacent(fl):+.3f}")

if show_steps:
    st.subheader("Encryption, step by step")
    st.caption("Confusion permutes pixel **positions**, so the histogram is unchanged but the "
               "pattern scrambles. Diffusion changes pixel **values**, so the histogram flattens "
               "and entropy climbs toward 8.0. Watch both numbers per step.")
    eshape, esteps = encrypt_trace(img, key, confusion, diffusion, rounds)
    render_gallery(eshape, esteps)

    st.subheader("Decryption, step by step")
    st.caption("The same stages run in reverse with the same key: un-diffusion restores the "
               "original values, un-confusion puts pixels back in place, until the image returns "
               "exactly. Entropy falls back and the original structure reappears.")
    dshape, dsteps = decrypt_trace(enc, key, confusion, diffusion, rounds)
    render_gallery(dshape, dsteps)

# ---------------- metrics ----------------
st.subheader("Security metrics")
img2 = img.copy(); img2.reshape(-1)[0] ^= 1            # flip one bit of plaintext
enc2 = cc.encrypt(img2, key, confusion, diffusion, rounds)
npcr, uaci = npcr_uaci(enc, enc2)

m = st.columns(5)
m[0].metric("Cipher entropy", f"{entropy(enc):.4f}", help="ideal 8.0")
m[1].metric("Plain entropy", f"{entropy(img):.4f}")
m[2].metric("Cipher adj-corr", f"{corr_adjacent(enc):+.4f}", help="ideal ~0")
m[3].metric("NPCR %", f"{npcr:.3f}", help="ideal ~99.6")
m[4].metric("UACI %", f"{uaci:.3f}", help="ideal ~33.4")

h1, h2 = st.columns(2)
h1.pyplot(hist_fig(img, "Plaintext histogram"))
h2.pyplot(hist_fig(enc, "Ciphertext histogram (should be flat)"))

# ---------------- downloads ----------------
def png_bytes(a):
    buf = io.BytesIO(); Image.fromarray(a).save(buf, "PNG"); return buf.getvalue()

d1, d2 = st.columns(2)
d1.download_button("⬇️ Download encrypted", png_bytes(enc), "encrypted.png", "image/png")
d2.download_button("⬇️ Download decrypted", png_bytes(dec), "decrypted.png", "image/png")
