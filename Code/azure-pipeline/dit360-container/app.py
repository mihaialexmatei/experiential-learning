from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import torch
from diffusers import DiffusionPipeline
import base64
from io import BytesIO
import traceback

app = FastAPI(title="DiT360 Inference API")

pipeline = None

class GenerationRequest(BaseModel):
    prompt: str
    negative_prompt: Optional[str] = ""
    num_inference_steps: Optional[int] = 28
    guidance_scale: Optional[float] = 3.5
    seed: Optional[int] = None
    height: Optional[int] = 1024
    width: Optional[int] = 2048

class GenerationResponse(BaseModel):
    image_base64: str
    seed_used: int

@app.on_event("startup")
async def load_model():
    """Load FLUX.1-dev with DiT360 LoRA adapter from LOCAL directories"""
    global pipeline
    try:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
        
        print(f"Loading models on {device} with dtype {dtype}...")
        if torch.cuda.is_available():
            print(f"GPU: {torch.cuda.get_device_name(0)}")
            print(f"GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")
        
        # Load FLUX.1-dev from LOCAL bundled models
        print("Loading FLUX.1-dev from /app/models/flux...")
        pipeline = DiffusionPipeline.from_pretrained(
            "/app/models/flux",  # LOCAL PATH
            torch_dtype=dtype,
            local_files_only=True  # Don't try to download
        )
        print("FLUX.1-dev loaded successfully")
        
        # Load DiT360 LoRA adapter from LOCAL bundled models
        print("Loading DiT360 LoRA adapter from /app/models/dit360...")
        pipeline.load_lora_weights(
            "/app/models/dit360",  # LOCAL PATH
            local_files_only=True
        )
        print("DiT360 LoRA adapter loaded successfully")
        
        # Move to device
        pipeline = pipeline.to(device)
        
        print(f"All models loaded successfully on {device}")
        
    except Exception as e:
        print(f"Error loading model: {str(e)}")
        traceback.print_exc()
        raise

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    gpu_info = None
    if torch.cuda.is_available():
        gpu_info = {
            "name": torch.cuda.get_device_name(0),
            "memory_allocated_gb": round(torch.cuda.memory_allocated(0) / 1024**3, 2),
            "memory_reserved_gb": round(torch.cuda.memory_reserved(0) / 1024**3, 2)
        }
    
    return {
        "status": "healthy",
        "model_loaded": pipeline is not None,
        "gpu_available": torch.cuda.is_available(),
        "gpu_info": gpu_info
    }

@app.post("/generate", response_model=GenerationResponse)
async def generate_image(request: GenerationRequest):
    """Generate 360° panoramic image from prompt using DiT360"""
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    try:
        seed_used = request.seed if request.seed is not None else torch.randint(0, 2**32, (1,)).item()
        generator = torch.Generator(device=pipeline.device).manual_seed(seed_used)
        
        print(f"Generating panorama: {request.prompt[:100]}...")
        
        # Generate 360° panoramic image
        result = pipeline(
            prompt=request.prompt,
            negative_prompt=request.negative_prompt,
            num_inference_steps=request.num_inference_steps,
            guidance_scale=request.guidance_scale,
            generator=generator,
            height=request.height,
            width=request.width
        )
        
        # Convert to base64
        image = result.images[0]
        buffered = BytesIO()
        image.save(buffered, format="JPEG", quality=95)
        img_base64 = base64.b64encode(buffered.getvalue()).decode()
        
        print(f"Generation successful with seed {seed_used}")
        
        return GenerationResponse(
            image_base64=img_base64,
            seed_used=seed_used
        )
    
    except Exception as e:
        print(f"Generation failed: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "DiT360 Inference API",
        "docs": "/docs",
        "model": "FLUX.1-dev + DiT360 LoRA",
        "description": "Generate high-quality 360° panoramic images"
    }
