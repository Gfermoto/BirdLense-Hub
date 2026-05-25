"""OV-safe export helpers for Birds-Classifier-EfficientNetB2 (mean-pool, not broken AvgPool(1408))."""

from __future__ import annotations

from pathlib import Path

INPUT_SIZE = 260


def export_onnx_ov_safe(src_dir: str | Path, onnx_path: str | Path) -> Path:
    """
    Export classifier with ``ReduceMean`` global pool (OpenVINO/iGPU compatible).

    HF ``pooler`` is ``AvgPool2d(kernel_size=1408)`` which breaks OV frontends.
    """
    import torch
    import torch.nn as nn
    from transformers import EfficientNetForImageClassification

    src = Path(src_dir)
    out = Path(onnx_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    hf = EfficientNetForImageClassification.from_pretrained(str(src))
    hf.eval()

    class _OvSafeClassifier(nn.Module):
        def __init__(self, inner: nn.Module) -> None:
            super().__init__()
            self.backbone = inner.efficientnet
            self.dropout = inner.dropout
            self.classifier = inner.classifier

        def forward(self, pixel_values: torch.Tensor) -> torch.Tensor:
            feats = self.backbone(pixel_values, return_dict=True).last_hidden_state
            pooled = feats.mean(dim=(2, 3))
            return self.classifier(self.dropout(pooled))

    wrapper = _OvSafeClassifier(hf).eval()
    dummy = torch.zeros(1, 3, INPUT_SIZE, INPUT_SIZE, dtype=torch.float32)
    with torch.no_grad():
        torch.onnx.export(
            wrapper,
            dummy,
            str(out),
            input_names=["pixel_values"],
            output_names=["logits"],
            opset_version=18,
        )
    return out


def export_openvino_ir_from_onnx(
    onnx_path: str | Path,
    xml_path: str | Path,
    *,
    fp16: bool = True,
) -> Path:
    import openvino as ov

    xml = Path(xml_path)
    xml.parent.mkdir(parents=True, exist_ok=True)
    ov_model = ov.convert_model(str(onnx_path))
    ov.save_model(ov_model, str(xml), compress_to_fp16=fp16)
    return xml
