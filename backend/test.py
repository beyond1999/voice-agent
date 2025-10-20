# import os
# os.environ["CT2_USE_CUDNN"] = "0"
# os.environ["CTRANSLATE2_USE_CUDNN"] = "0"
# from faster_whisper import WhisperModel
# model = WhisperModel("tiny", device="cuda", compute_type="int8")
# print("✅ CUDA running without cuDNN")


# from faster_whisper import WhisperModel
# import torch
# import ctranslate2
# import faster_whisper
# m = WhisperModel("tiny", device="cuda", compute_type="int8")
# print("torch:", torch.__version__, "cuda?", torch.cuda.is_available())
# print("ctranslate2:", ctranslate2.__version__)
# print("faster_whisper:", faster_whisper.__version__)


import os
os.environ["CT2_USE_CUDNN"] = "0"
os.environ["CTRANSLATE2_USE_CUDNN"] = "0"
os.environ["CT2_CUDA_TRUE_FP16_GEMM"] = "0"
os.environ["CT2_VERBOSE"] = "1"   # 观察日志

from faster_whisper import WhisperModel
m = WhisperModel("tiny", device="cuda", compute_type="int8_float16")
