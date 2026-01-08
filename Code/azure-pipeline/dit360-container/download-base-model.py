from huggingface_hub import snapshot_download
import os

# Get token from environment variable
token = os.getenv("HF_TOKEN")
if not token:
    raise ValueError("HF_TOKEN environment variable is required")

# Download FLUX.1-dev (requires authentication)
print("Downloading FLUX.1-dev (23.8 GB)...")
snapshot_download(
    repo_id="black-forest-labs/FLUX.1-dev",
    local_dir="./models/flux",
    local_dir_use_symlinks=False,
    token=token
)

# Download DiT360 adapter
print("Downloading DiT360 adapter...")
snapshot_download(
    repo_id="Insta360-Research/DiT360-Panorama-Image-Generation",
    local_dir="./models/dit360",
    local_dir_use_symlinks=False,
    token=token  # Include token for consistency
)

print("Done!")
