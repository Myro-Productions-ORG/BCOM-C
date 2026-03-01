  Context:                                                                                 
  You are implementing a Donut fine-tuning pipeline for an OCR project targeting IRS Form  
  990 documents. The system runs on an NVIDIA DGX Spark (GB10, aarch64, 128 GB unified     
  memory, sm_121, CUDA 13.0, Ubuntu 24.04). PyTorch standard pip wheels do not support     
  sm_121 — all training must run inside the NGC container nvcr.io/nvidia/pytorch:25.01-py3.
                                                                                           
  Project root: /home/nmyers/Projects/Data-Sets/ALA-OCR/                                
  Project venv: /home/nmyers/Projects/Data-Sets/ALA-OCR/.venv/ (has: lxml, Pillow,
  pdf2image, numpy, datasets, huggingface_hub, pytest, tqdm — no ML packages)
  Dataset: /home/nmyers/datasets/irs-990-synthetic/ — HF DatasetDict, 24K/3K/3K
  train/val/test, schema: {image: PIL 2550×3300 RGB, ground_truth: JSON string, filing_id:
  str}. The ground_truth is already in Donut format: {"gt_parse": {"f1_27": "549405",
  "f1_44": "456949", ...}} with ~80 fields per sample.
  BobSpark-APIs: /home/nmyers/Projects/BobSpark-APIs/ — FastAPI server running on port 9010
   (uvicorn). Has training/router.py, training/advisor.py, finetune/router.py,
  finetune/service.py, finetune/models.py. Uses SQLite via db.py. BCOM-C dashboard
  (/home/nmyers/Projects/BCOM-C/) polls GET /api/jobs/ every 5s for live job progress.
  HF account: MyroProductoCodo — credentials already configured.

  ---
  What to build:

  1. Training script at finetune/train_donut.py (runs inside NGC container):
  - Load naver-clova-ix/donut-base from HuggingFace Hub
  - Load dataset from /home/nmyers/datasets/irs-990-synthetic/ using
  datasets.load_from_disk()
  - Add task token <s_irs990> and all field name tokens (e.g. <f1_27>, </f1_27>, etc.) to
  the tokenizer/model
  - Resize Donut's image processor to match training images (1280px height, keep aspect or
  pad to match)
  - Implement a DonutDataset (torch Dataset) that: decodes the gt_parse JSON, formats it as
   Donut's token sequence (<s_irs990><f1_27>549405</f1_27>...), returns (pixel_values,
  labels) tensors
  - Training loop: AdamW, cosine LR schedule, gradient checkpointing on, mixed precision
  (bf16 on Blackwell), batch size tuned for 128 GB VRAM
  - Log training/val loss to stdout in format PROGRESS chunk X/Y: Z% so jobs/service.py can
   parse it
  - Save checkpoints to /home/nmyers/models/donut-irs990/checkpoint-{step}/
  - Save final model to /home/nmyers/models/donut-irs990/
  - Accept CLI args: --epochs, --batch-size, --lr, --output, --dataset

  2. Docker launcher at finetune/launch_donut.sh:
  - Runs train_donut.py inside nvcr.io/nvidia/pytorch:25.01-py3 with --gpus all, mounts the
   project dir, dataset dir, and models dir
  - Passes all CLI args through
  - Writes stdout/stderr to /home/nmyers/datasets/finetune.log

  3. BobSpark-APIs integration:
  - Add "finetune.train_donut" as a known job pattern in jobs/service.py KNOWN_JOBS list
  (log_fixed = /home/nmyers/datasets/finetune.log), with progress regex matching the
  PROGRESS chunk X/Y: Z% format from the training script
  - Add POST /api/finetune/start to finetune/router.py that: accepts {epochs, batch_size,
  lr}, spawns launch_donut.sh as a background subprocess, stores job record in the
  finetune_jobs DB table, returns {job_id, pid, status}
  - Add GET /api/finetune/ to list recent finetune jobs with status
  - Make sure the finetune router is registered in main.py if it isn't already

  4. DB migration in db.py: add finetune_jobs table with columns (id TEXT PK, status TEXT,
  epochs INT, batch_size INT, lr REAL, pid INT, started_at TEXT, finished_at TEXT)

  5. Tests in tests/test_finetune.py:
  - Test DonutDataset returns correct tensor shapes
  - Test token sequence formatting from gt_parse dict
  - Test the /api/finetune/ list endpoint returns 200
  - Do NOT test actual training (too slow) — mock the subprocess call in the start test

  Constraints:
  - All training code must work inside the NGC container environment (no .venv — use the
  container's Python which has PyTorch, transformers, datasets pre-installed)
  - The launcher script must handle the Docker volume mounts correctly for aarch64
  - Keep launch_donut.sh idempotent — if a job is already running, refuse to start another
  - No cloud storage — all checkpoints stay local on the NVMe
  - The gt_parse field name tokens must be derived programmatically from field_map.json at
  /home/nmyers/Projects/Data-Sets/ALA-OCR/field_map.json, not hardcoded

  Success criteria:
  - bash finetune/launch_donut.sh --epochs 1 --batch-size 2 starts training inside the NGC
  container without errors
  - GET /api/jobs/ on port 9010 shows the finetune job with live progress percentage while
  it runs
  - All 5 tests pass

