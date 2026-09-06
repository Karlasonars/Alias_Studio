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


# Kokoro-82M (E20-F02), Apache-2.0 — the story narrator. Three files per
# voice: the model, its config, and one voice pack. The .pth and every
# voice are LFS-stored, so each sha256 below IS the publisher's identity
# for the file (HF's lfs.oid, read from the repo tree API on 2026-09-06).
# config.json is a plain git blob: its sha256 was taken from two
# identical fetches whose ETag (14a726ed…) is the blob's git SHA-1, which
# kokoro_tts's verification recomputes from the bytes before pinning.
_KOKORO_URL = "https://huggingface.co/hexgrad/Kokoro-82M/resolve/main/"

KOKORO_MODEL = register(
    ModelSpec(
        name="kokoro",
        filename="kokoro-v1_0.pth",
        url=_KOKORO_URL + "kokoro-v1_0.pth",
        sha256="496dba118d1a58f5f3db2efc88dbdc216e0483fc89fe6e47ee1f2c53f18ad1e4",
        approx_mb=327,
    )
)

KOKORO_CONFIG = register(
    ModelSpec(
        name="kokoro",
        filename="config.json",
        url=_KOKORO_URL + "config.json",
        sha256="5abb01e2403b072bf03d04fde160443e209d7a0dad49a423be15196b9b43c17f",
        approx_mb=1,
    )
)


# One pinned voice pack per voice the deck offers (narrate/kokoro_tts.VOICES).
KOKORO_VOICES: dict[str, ModelSpec] = {
    "af_heart": register(
        ModelSpec(
            name="kokoro",
            filename="voices/af_heart.pt",
            url=_KOKORO_URL + "voices/af_heart.pt",
            sha256="0ab5709b8ffab19bfd849cd11d98f75b60af7733253ad0d67b12382a102cb4ff",
            approx_mb=1,
        )
    ),
    "af_bella": register(
        ModelSpec(
            name="kokoro",
            filename="voices/af_bella.pt",
            url=_KOKORO_URL + "voices/af_bella.pt",
            sha256="8cb64e02fcc8de0327a8e13817e49c76c945ecf0052ceac97d3081480e8e48d6",
            approx_mb=1,
        )
    ),
    "am_adam": register(
        ModelSpec(
            name="kokoro",
            filename="voices/am_adam.pt",
            url=_KOKORO_URL + "voices/am_adam.pt",
            sha256="ced7e284aba12472891be1da3ab34db84cc05cc02b5889535796dbf2d8b0cb34",
            approx_mb=1,
        )
    ),
    "am_michael": register(
        ModelSpec(
            name="kokoro",
            filename="voices/am_michael.pt",
            url=_KOKORO_URL + "voices/am_michael.pt",
            sha256="9a443b79a4b22489a5b0ab7c651a0bcd1a30bef675c28333f06971abbd47bd37",
            approx_mb=1,
        )
    ),
    "bf_emma": register(
        ModelSpec(
            name="kokoro",
            filename="voices/bf_emma.pt",
            url=_KOKORO_URL + "voices/bf_emma.pt",
            sha256="d0a423deabf4a52b4f49318c51742c54e21bb89bbbe9a12141e7758ddb5da701",
            approx_mb=1,
        )
    ),
    "bm_george": register(
        ModelSpec(
            name="kokoro",
            filename="voices/bm_george.pt",
            url=_KOKORO_URL + "voices/bm_george.pt",
            sha256="f1bc812213dc59774769e5c80004b13eeb79bd78130b11b2d7f934542dab811b",
            approx_mb=1,
        )
    ),
}
