"""
RoadEye ADAS - INT8 Quantization & Optimization Script
=======================================================
Auto-configured for: C:\\Users\\Karthik R\\Downloads\\roadeye_models-karthik\\backend

Run:  python optimize_int8.py
"""

import os
import sys
import time
import numpy as np

# ─── PATHS (pre-configured for your project) ──────────────────────────────────
BASE = r"C:\Users\Karthik R\Downloads\roadeye_models-karthik\backend"

MODELS = {
    "detection":   os.path.join(BASE, "models", "detection",   "yolo26n_indian_road_best.onnx"),
    "segmentation":os.path.join(BASE, "models", "segmentation","yolo11m-road-seg.onnx"),
    "pothole":     os.path.join(BASE, "models", "pothole",     "pothole-detection-yolov8.onnx"),
    "depth":       os.path.join(BASE, "models", "depth",       "unet_depthwise_nano_best.onnx"),
}

OUTPUT_DIR  = os.path.join(BASE, "models_int8")
INPUT_SIZE  = (640, 640)   # Must match fixed model input (YOLO models are 640×640)
NUM_CALIB   = 50
# ──────────────────────────────────────────────────────────────────────────────


def preprocess_model(src, preprocessed_path):
    """
    REQUIRED step before INT8 quantization.
    Runs shape inference + model optimization so quantizer can
    correctly identify and fuse ops — without this, INT8 is SLOWER.
    """
    try:
        from onnxruntime.quantization import quant_pre_process
        quant_pre_process(input_model_path=src, output_model_path=preprocessed_path)
        return True
    except Exception as e:
        print(f"    ⚠  Pre-process failed (will try without): {e}")
        return False


def quantize_dynamic(src, dst):
    """Dynamic INT8 — fastest, no calibration data needed."""
    import tempfile, shutil, os
    tmp = src + ".preprocessed.onnx"
    try:
        from onnxruntime.quantization import quantize_dynamic, QuantType

        # Always pre-process first — without this INT8 runs SLOWER than FP32
        pre_ok = preprocess_model(src, tmp)
        actual_src = tmp if pre_ok and os.path.exists(tmp) else src

        quantize_dynamic(
            model_input=actual_src,
            model_output=dst,
            weight_type=QuantType.QInt8,
        )
        return True
    except Exception as e:
        print(f"    ⚠  Dynamic quant failed: {e}")
        return False
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def quantize_static(src, dst):
    """Static INT8 with QDQ format — best accuracy & speed on x64."""
    import os
    tmp = src + ".preprocessed.onnx"
    try:
        import onnx
        from onnxruntime.quantization import (
            quantize_static, QuantType, CalibrationDataReader,
            QuantFormat, quant_pre_process
        )

        # Step 1 — pre-process
        pre_ok = preprocess_model(src, tmp)
        actual_src = tmp if pre_ok and os.path.exists(tmp) else src

        # Step 2 — read actual input shape from the (preprocessed) model
        model = onnx.load(actual_src)
        input_node = model.graph.input[0]
        input_name = input_node.name
        try:
            dims = input_node.type.tensor_type.shape.dim
            h = dims[2].dim_value if dims[2].dim_value > 0 else 640
            w = dims[3].dim_value if dims[3].dim_value > 0 else 640
        except Exception:
            h, w = 640, 640
        print(f"    Model input shape: {h}×{w}")

        # Step 3 — calibration data at model's actual size
        calib = [np.random.rand(1, 3, h, w).astype(np.float32) for _ in range(NUM_CALIB)]

        class Reader(CalibrationDataReader):
            def __init__(self): self.i = 0
            def get_next(self):
                if self.i >= len(calib): return None
                d = {input_name: calib[self.i]}; self.i += 1; return d
            def rewind(self): self.i = 0

        # Step 4 — quantize with QDQ format (best on x86/x64)
        quantize_static(
            model_input=actual_src,
            model_output=dst,
            calibration_data_reader=Reader(),
            quant_format=QuantFormat.QDQ,
            weight_type=QuantType.QInt8,
            activation_type=QuantType.QInt8,
        )
        return True
    except Exception as e:
        print(f"    ⚠  Static quant failed: {e}")
        return False
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def benchmark(path, runs=15):
    try:
        import onnxruntime as ort
        import onnx, multiprocessing
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = multiprocessing.cpu_count()
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        sess = ort.InferenceSession(path, sess_options=opts)
        inp  = sess.get_inputs()[0].name
        h, w = INPUT_SIZE
        dummy = np.random.rand(1, 3, h, w).astype(np.float32)
        for _ in range(3): sess.run(None, {inp: dummy})   # warmup
        t = []; 
        for _ in range(runs):
            t0 = time.perf_counter()
            sess.run(None, {inp: dummy})
            t.append((time.perf_counter()-t0)*1000)
        return np.mean(t)
    except Exception as e:
        return None


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 62)
    print("  RoadEye ADAS — INT8 Optimizer")
    print("=" * 62)

    # Verify model files exist
    missing = [k for k, v in MODELS.items() if not os.path.exists(v)]
    if missing:
        print(f"\n❌ Missing models: {missing}")
        print("   Check that the paths above are correct.")
        sys.exit(1)

    print(f"\n✅ Found {len(MODELS)} models. Starting INT8 conversion...\n")

    summary = []
    for name, src in MODELS.items():
        size_mb = os.path.getsize(src) / 1e6
        dst_name = os.path.splitext(os.path.basename(src))[0] + "_int8.onnx"
        dst = os.path.join(OUTPUT_DIR, dst_name)

        print(f"  ▶  {name:14s}  ({size_mb:.1f} MB)  →  {dst_name}")

        # Try dynamic first, fall back to static
        ok = quantize_dynamic(src, dst)
        if not ok:
            ok = quantize_static(src, dst)

        if ok and os.path.exists(dst):
            new_mb  = os.path.getsize(dst) / 1e6
            pct     = (1 - new_mb / size_mb) * 100

            orig_ms = benchmark(src)
            int8_ms = benchmark(dst)
            speedup = (orig_ms / int8_ms) if (orig_ms and int8_ms) else None

            print(f"     ✅  {size_mb:.1f} MB → {new_mb:.1f} MB  ({pct:.0f}% smaller)", end="")
            if speedup:
                print(f"  |  {orig_ms:.0f}ms → {int8_ms:.0f}ms  ({speedup:.1f}× faster)")
            else:
                print()
            summary.append((name, dst, orig_ms, int8_ms))
        else:
            print(f"     ❌  Failed to quantize {name}")

    # ── Write updated backend config ──────────────────────────────────────────
    config_path = os.path.join(BASE, "models_int8_paths.py")
    with open(config_path, "w") as f:
        f.write('"""\nAuto-generated by optimize_int8.py — INT8 model paths.\nImport this in your backend instead of the original paths.\n"""\n\n')
        f.write(f'MODELS_INT8 = {{\n')
        for name, dst, _, _ in summary:
            f.write(f'    "{name}": r"{dst}",\n')
        f.write('}\n\n')
        f.write('INPUT_SIZE = (320, 320)  # Use this in your preprocessor\n')
    print(f"\n  📄  Saved model path config → {config_path}")

    print("\n" + "=" * 62)
    print("  ✅  All done! INT8 models saved to:")
    print(f"      {OUTPUT_DIR}")
    print("\n  Next: run  python patch_backend.py  to auto-update main.py")
    print("=" * 62 + "\n")


if __name__ == "__main__":
    main()
