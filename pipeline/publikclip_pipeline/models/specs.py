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
        approx_mb=28,
    )
)

# clip-forge ships these pre-exported (MIT); its export-asd-onnx.py proves
# numerical parity against the LR-ASD reference implementation.
ULTRAFACE = register(
    ModelSpec(
        name="ultraface",
        filename="ultraface-rfb-320.onnx",
        url=(
            "https://github.com/JeremySNR/clip-forge/raw/main/resources/models/"
            "ultraface-rfb-320.onnx"
        ),
        approx_mb=2,
    )
)

LR_ASD_FRONTEND = register(
    ModelSpec(
        name="lr-asd",
        filename="frontend.onnx",
        url="https://github.com/JeremySNR/clip-forge/raw/main/resources/models/lr-asd-frontend.onnx",
        approx_mb=3,
    )
)

LR_ASD_BACKEND = register(
    ModelSpec(
        name="lr-asd",
        filename="backend.onnx",
        url="https://github.com/JeremySNR/clip-forge/raw/main/resources/models/lr-asd-backend.onnx",
        approx_mb=1,
    )
)
