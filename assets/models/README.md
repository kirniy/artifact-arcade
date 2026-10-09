# Offline portrait matting

`modnet-portrait.onnx` comes from https://huggingface.co/Xenova/modnet (`onnx/model.onnx`), based on https://github.com/ZHKKKe/MODNet.

The dynamic ONNX export was simplified with onnxsim to fixed input `[1,3,384,512]` so the existing OpenCV DNN backend can load it. No extra runtime dependency is required.

SHA-256: `2355474400c5e219eb9d19f4f2f34923a2421bd61141adc446cddb6db8cc43ce`.
Apache 2.0; accompanying license is `modnet-LICENSE`. Model is bundled so guest sessions do not download weights or require API credits. OpenCV DNN runs it on CPU, serialized with cached weights. Neutral luminance RGB input, normalized to [-1, 1]; single output is foreground alpha. Small disconnected predictions are discarded. No circles, polygons or face/torso patches are drawn into the mask.
