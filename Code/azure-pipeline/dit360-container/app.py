from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import torch
from diffusers import DiffusionPipeline
import base64
from io import BytesIO
import os

app = FastAPI(title="DiT360 Inference API")

# Global variable to hold the model
pipeline = None

class GenerationRequest(BaseModel):
    prompt: str
    negative_prompt: Optional[str] = ""
    num_inference_steps: Optional[int] = 50
    guidance_scale: Optional[float] = 7.5
    seed: Optional[int] = None

class GenerationResponse(BaseModel):
    image_base64: str
    seed_used: int

@app.on_event("startup")
async def load_model():
    """Load DiT360 model on startup"""
    global pipeline
    try:
        model_id = "Insta360-Research/DiT360-Panorama-Image-Generation"
        
        # Check if GPU available
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Loading model on {device}...")
        
        pipeline = DiffusionPipeline.from_pretrained(
            model_id,
            torch_dtype=torch.float16 if device == "cuda" else torch.float32,
            use_safetensors=True
        )
        pipeline = pipeline.to(device)
        
        print(f"Model loaded successfully on {device}")
    except Exception as e:
        print(f"Error loading model: {str(e)}")
        raise

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "model_loaded": pipeline is not None,
        "gpu_available": torch.cuda.is_available()
    }

@app.post("/generate", response_model=GenerationResponse)
async def generate_image(request: GenerationRequest):
    """Generate 360° panoramic image from prompt"""
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    try:
        # Set seed for reproducibility
        generator = None
        seed_used = request.seed
        if request.seed is not None:
            generator = torch.Generator(device=pipeline.device).manual_seed(request.seed)
        else:
            seed_used = torch.randint(0, 2**32, (1,)).item()
            generator = torch.Generator(device=pipeline.device).manual_seed(seed_used)
        
        # Generate image
        result = pipeline(
            prompt=request.prompt,
            negative_prompt=request.negative_prompt,
            num_inference_steps=request.num_inference_steps,
            guidance_scale=request.guidance_scale,
            generator=generator
        )
        
        # Convert image to base64
        image = result.images[0]
        buffered = BytesIO()
        image.save(buffered, format="JPEG", quality=95)
        img_base64 = base64.b64encode(buffered.getvalue()).decode()
        
        return GenerationResponse(
            image_base64=img_base64,
            seed_used=seed_used
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "DiT360 Inference API", "docs": "/docs"}
