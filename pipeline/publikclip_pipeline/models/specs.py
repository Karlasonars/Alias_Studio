"""Concrete model registry entries.

Whisper weights are managed by faster-whisper's HuggingFace cache (pointed
at PUBLIKCLIP_HOME/models/hf via HF_HOME in the ASR stage); everything else
is fetched explicitly through the registry so the app can show one honest
download progress list. All entries are ungated — no tokens, no accounts
(the CAM++ Apache-2.0 verification is what made that possible).
"""

from .registry import ModelSpec, register

LAUGHTER = register(
    ModelSpec(
        name="laughter-jrgillick",
        filename="best.pth.tar",
        url=(
            "https://github.com/jrgillick/laughter-detection/raw/master/"
            "checkpoints/in_use/resnet_with_augmentation/best.pth.tar"
        ),
        # Hashed from bytes whose git blob SHA-1 (13651a0e…) matches the one
        # GitHub's contents API records for this path — the publisher's own
        # identity for the file, not a hash of whatever one download returned.
        sha256="bfe450e41926a4e9de2abf007c9a13fa8420439eaa1383e986563c565f5ef206",
        approx_mb=10,
    )
)

PANNS_CNN14_MAX = register(
    ModelSpec(
        name="panns-cnn14-decisionlevelmax",
        filename="Cnn14_DecisionLevelMax.pth",
        url=(
            "https://zenodo.org/record/3987831/files/"
            "Cnn14_DecisionLevelMax_mAP%3D0.385.pth?download=1"
        ),
        # Zenodo's CDN has been observed serving a different, unparseable
        # blob under this same URL on some requests (content-length varied
        # 327428481 vs 513950654 bytes across otherwise-identical fetches).
        # Pinned against the file's own oc-checksum response header so a
        # bad edge response gets rejected and retried instead of silently
        # accepted.
        sha256="dd3b4043a87d4ec13df8082c0fcfee3fb5084151808e47e060987a95eabdd142",
        approx_mb=312,
    )
)

CAMPPLUS = register(
    ModelSpec(
        name="campplus",
        filename="campplus_cn_common.bin",
        url="https://huggingface.co/funasr/campplus/resolve/main/campplus_cn_common.bin",
        # This IS the publisher's hash: the file is LFS-stored, and this value
        # is HF's lfs.oid for it (also served as X-Linked-ETag on the resolve
        # URL). Our download hashed to the same value before pinning.
        sha256="3388cf5fd3493c9ac9c69851d8e7a8badcfb4f3dc631020c4961371646d5ada8",
        approx_mb=28,
    )
)

# clip-forge ships these pre-exported (MIT); its export-asd-onnx.py proves
# numerical parity against the LR-ASD reference implementation.
#
# All three sha256s below were computed from bytes whose git blob SHA-1
# matched GitHub's contents-API record for the path (a5e23096…, 99749647…,
# 7828a59f… respectively) — verified against the publisher's identity for
# the file first, then hashed. The matches also prove none of these is an
# LFS pointer: a pointer's blob hash could never equal a hash over the
# binary.
ULTRAFACE = register(
    ModelSpec(
        name="ultraface",
        filename="ultraface-rfb-320.onnx",
        url=(
            "https://github.com/JeremySNR/clip-forge/raw/main/resources/models/"
            "ultraface-rfb-320.onnx"
        ),
        sha256="34cd7e60aeff28744c657de7a3dc64e872d506741de66987f3426f2b79f88017",
        approx_mb=2,
    )
)

LR_ASD_FRONTEND = register(
    ModelSpec(
        name="lr-asd",
        filename="frontend.onnx",
        url="https://github.com/JeremySNR/clip-forge/raw/main/resources/models/lr-asd-frontend.onnx",
        sha256="f7c055612cd6f1f2da3ab8257567ab68a6b0d69b5e436699a5cf65334dd79461",
        approx_mb=3,
    )
)

LR_ASD_BACKEND = register(
    ModelSpec(
        name="lr-asd",
        filename="backend.onnx",
        url="https://github.com/JeremySNR/clip-forge/raw/main/resources/models/lr-asd-backend.onnx",
        sha256="9453caa09998027995664fd5a3b1fab4ad0de30a92c6beba8c29c3619de510a9",
        approx_mb=1,
    )
)
