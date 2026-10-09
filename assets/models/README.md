# Offline person segmentation

`pphumanseg.onnx` is the FP32 `human_segmentation_pphumanseg_2023mar.onnx` from OpenCV Zoo:
https://github.com/opencv/opencv_zoo/tree/main/models/human_segmentation_pphumanseg

SHA-256: `552d8a984054e59b5d773d24b9b12022b22046ceb2bbc4c9aaeaceb36a9ddf24`.
Apache 2.0; accompanying license is `pphumanseg-LICENSE`. Model is bundled so guest sessions do not download weights or require API credits. OpenCV DNN runs it on CPU, serialized with cached weights. RGB input 192×192, normalized to [-1, 1]; channel 1 is person probability.
