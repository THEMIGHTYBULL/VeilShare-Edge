"""Runtime/backend telemetry panel.

Reports what acceleration is actually available on this machine:
ONNX Runtime version and providers, whether QNNExecutionProvider (Snapdragon
NPU) is present, plus CPU/platform facts. The UI shows this verbatim —
the app never claims NPU acceleration unless the QNN provider is really there.
"""

from __future__ import annotations

import platform


def runtime_panel() -> dict:
    info: dict = {
        "platform": platform.system(),
        "platform_release": platform.release(),
        "platform_version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor() or platform.machine(),
        "python": platform.python_version(),
    }

    try:
        import psutil

        vm = psutil.virtual_memory()
        info["cpu_count"] = psutil.cpu_count(logical=True)
        info["memory_total_mb"] = round(vm.total / (1024 * 1024))
    except Exception:
        pass

    try:
        import onnxruntime as ort

        providers = list(ort.get_available_providers())
        qnn = "QNNExecutionProvider" in providers
        info["onnxruntime"] = {
            "version": ort.__version__,
            "available_providers": providers,
            "qnn_execution_provider": qnn,
        }
        info["acceleration"] = (
            "QNN Execution Provider available — Snapdragon NPU path ready"
            if qnn
            else "CPU fallback (dev machine) — QNN Execution Provider not present"
        )
        info["acceleration_status"] = "qnn-ready" if qnn else "cpu-fallback"
    except ImportError:
        info["onnxruntime"] = None
        info["acceleration"] = "onnxruntime not installed in this environment"
        info["acceleration_status"] = "onnxruntime-missing"

    return info
