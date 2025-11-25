# Image-to-Image Diffusion Pipeline

*A Diffusion-Based System for Automated Flash + Ambient image Editing*

## Overview

This repository contains a diffusion-based **image-to-image model pipeline** designed specifically for **image editing**, including flash–ambient blending, window exposure correction, tone mapping, color balancing, and style replication.

The foundation of this project is inspired by **Palette: Image-to-Image Diffusion Models**, adapted and extended for high-resolution workflows using paired data (RAW/ambient/flash → final edited JPG).

The architecture and training framework come from a proven iterative-refinement diffusion system, optimized for reproducibility, consistency, and multi-GPU scalability.

This pipeline demonstrates a strong base to build the type of automated editing model described in the project requirements.

---

## Key Capabilities


* Diffusion-based **image-to-image mapping** for consistent editing style
* Learned transformation from **RAW → Final** JPGs
* Exposure fusion similar to HDR workflows
* Accurate **white balance**, **tone mapping**, and **color correction**
* Window region stabilization and highlight control
* U-Net backbone from Guided Diffusion for high-quality reconstruction
* γ-encoding instead of timestep *t* for smoother tone consistency
* Fixed Σθ variance at inference for stable results
* High-resolution image support with optional tiling

This aligns directly with tasks such as:

* Flambient blending
* Color/white balance normalization
* Shadow reduction / flash softening
* Tone curve replication
* Maintaining consistent studio editing style

---

## Status

### Core Pipeline

* [x] Diffusion model (image-to-image)
* [x] Multi-exposure input support
* [x] RAW/JPG paired training
* [x] EMA + mixed precision
* [x] Multi-GPU DDP training
* [x] Tensorboard + logging
* [x] High-resolution tiling
* [x] FID, IS, RGB-distance, WB consistency metrics
* [x] Fine-tuning support for custom editing styles

### Editing Tasks

* [x] Ambient + flash exposure fusion
* [x] Window exposure handling
* [x] Tone mapping
* [x] Highlight/shadow balancing

---

## Architecture

This project uses a **Guided-Diffusion-inspired U-Net**, modified for:

Backbone options include:

* Guided Diffusion U-Net (default)
* SR3 U-Net
* HDRNet-inspired auxiliary head
* ControlNet injection for window or mask guidance

---

## Dataset Preparation

The pipeline is optimized to train on:

* RAW ambient exposure
* RAW flash exposure
* Highlight/window detail layer (optional)
* Final retouched JPG (target)

A typical dataset entry looks like:

```
/dataset/
   ambient.exr
   flash.exr
   window_mask.png (optional)
   final.jpg
```

Update the config file:

```yaml
"which_dataset": {
    "name": ["data.dataset", "RealEstateFlambientDataset"],
    "args":{
        "data_root": "path/to/real_estate_dataset",
        "use_raw": true,
        "exposure_inputs": ["ambient", "flash"],
        "data_len": -1
    }
},
```

---

## Training

1. Prepare paired exposures and final edits
2. Update config paths
3. (Optional) Resume from checkpoint:

```yaml
"path": {
    "resume_state": "experiments/flambient_v1/checkpoint/100"
}
```

4. Start training:

```bash
python run.py -p train -c config/flambient_train.json
```

Backbone, loss, and metrics can be changed through the `which_networks` section.

---

## Testing

```bash
python run.py -p test -c config/flambient_train.json
```

---

## Evaluation

Supports:

* FID
* IS
* ΔRGB error
* WB consistency metric
* Tone curve similarity

Run:

```bash
python eval.py -s [ground_truth_path] -d [model_output_path]
```

---

## Production & Deployment

This pipeline is structured to support production integration, including:

* ONNX export
* TensorRT inference acceleration
* FastAPI/REST endpoint integration
* GPU + CPU fallback
* Batch-processing CLI for bulk real-estate editing
* Ready for SaaS embedding into a production environment

Example export:

```bash
python export_onnx.py --config config/flambient_train.json
```

## References

This project builds upon:

* Palette: Image-to-Image Diffusion Models
* DDPM
* Guided Diffusion
* HDRNet (tone mapping ideas)
* Diffusion-based exposure fusion research
