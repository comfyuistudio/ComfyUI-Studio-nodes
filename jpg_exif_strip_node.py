"""
ComfyUI Custom Node: JPG Converter & EXIF Stripper
Converts any image to JPEG, removes all EXIF metadata,
displays the result as a live preview inside the node,
and optionally saves the file to a named subfolder of ComfyUI/output/.
"""

import os
import re
import uuid
import torch
import numpy as np
from PIL import Image
import io
import folder_paths  # ComfyUI built-in path helper


class JpgExifStripNode:
    """
    Converts an input image to JPEG format, strips all EXIF metadata,
    renders a live preview thumbnail directly inside the node, and
    optionally saves the result to ComfyUI/output/<folder_name>/.
    """

    CATEGORY = "image/postprocessing"
    FUNCTION = "convert_and_strip"
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    OUTPUT_NODE = True  # Required to allow ui dict to be returned

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "quality": (
                    "INT",
                    {
                        "default": 90,
                        "min": 1,
                        "max": 100,
                        "step": 1,
                        "display": "slider",
                        "tooltip": "JPEG compression quality (1=lowest, 100=highest)",
                    },
                ),
                "optimize": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": "Enable JPEG optimization for smaller file size",
                    },
                ),
                "progressive": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": "Save as progressive JPEG (loads gradually in browsers)",
                    },
                ),
                # ── Save options ──────────────────────────────────────────
                "save_output": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": "Save the converted image(s) to ComfyUI/output/<folder_name>/",
                    },
                ),
                "folder_name": (
                    "STRING",
                    {
                        "default": "jpg_converted",
                        "tooltip": "Subfolder inside ComfyUI/output/ to save images into",
                    },
                ),
                "filename_prefix": (
                    "STRING",
                    {
                        "default": "img",
                        "tooltip": "Prefix for saved filenames, e.g. 'img' → img_0001.jpg",
                    },
                ),
            }
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _tensor_to_pil(self, frame: torch.Tensor) -> Image.Image:
        """Convert a single (H, W, C) float32 [0,1] tensor to a PIL RGB image."""
        np_frame = (frame.cpu().numpy() * 255).clip(0, 255).astype(np.uint8)
        return Image.fromarray(np_frame, mode="RGB")

    def _pil_to_tensor(self, pil_img: Image.Image) -> torch.Tensor:
        """Convert a PIL RGB image to a (H, W, C) float32 [0,1] tensor."""
        return torch.from_numpy(np.array(pil_img).astype(np.float32) / 255.0)

    def _jpeg_round_trip(
        self, pil_img: Image.Image, quality: int, optimize: bool, progressive: bool
    ) -> Image.Image:
        """
        Save image to an in-memory JPEG buffer (no exif= kwarg → zero metadata),
        then reload it. This guarantees the result is a clean JPEG with no EXIF.
        """
        buf = io.BytesIO()
        pil_img.save(
            buf,
            format="JPEG",
            quality=quality,
            optimize=optimize,
            progressive=progressive,
        )
        buf.seek(0)
        return Image.open(buf).convert("RGB")

    def _save_preview(self, pil_img: Image.Image) -> dict:
        """
        Save the image to ComfyUI's temp folder so the node can display it.
        Returns the image-info dict expected by the frontend.
        """
        temp_dir = folder_paths.get_temp_directory()
        os.makedirs(temp_dir, exist_ok=True)

        filename = f"jpg_exif_strip_{uuid.uuid4().hex[:12]}.jpg"
        pil_img.save(os.path.join(temp_dir, filename), format="JPEG", quality=95)

        return {"filename": filename, "subfolder": "", "type": "temp"}

    @staticmethod
    def _sanitize(name: str) -> str:
        """Strip characters that are unsafe in directory / file names."""
        return re.sub(r'[\\/:*?"<>|]', "_", name).strip() or "jpg_converted"

    def _next_filename(self, output_dir: str, prefix: str) -> str:
        """
        Return the next auto-incremented filename inside output_dir.
        Scans existing files matching '<prefix>_NNNN.jpg' and picks max+1.
        """
        pattern = re.compile(rf"^{re.escape(prefix)}_(\d{{4}})\.jpg$", re.IGNORECASE)
        existing = [
            int(m.group(1))
            for f in os.listdir(output_dir)
            if (m := pattern.match(f))
        ]
        index = (max(existing) + 1) if existing else 1
        return f"{prefix}_{index:04d}.jpg"

    def _save_to_output(
        self,
        pil_img: Image.Image,
        folder_name: str,
        filename_prefix: str,
        quality: int,
        optimize: bool,
        progressive: bool,
    ) -> str:
        """
        Save the clean JPEG to ComfyUI/output/<folder_name>/.
        Returns the full path of the saved file.
        """
        safe_folder = self._sanitize(folder_name)
        safe_prefix = self._sanitize(filename_prefix)

        output_base = folder_paths.get_output_directory()
        output_dir = os.path.join(output_base, safe_folder)
        os.makedirs(output_dir, exist_ok=True)

        filename = self._next_filename(output_dir, safe_prefix)
        filepath = os.path.join(output_dir, filename)

        pil_img.save(
            filepath,
            format="JPEG",
            quality=quality,
            optimize=optimize,
            progressive=progressive,
        )
        return filepath

    # ------------------------------------------------------------------
    # Main execution
    # ------------------------------------------------------------------

    def convert_and_strip(
        self,
        image: torch.Tensor,
        quality: int = 90,
        optimize: bool = True,
        progressive: bool = False,
        save_output: bool = False,
        folder_name: str = "jpg_converted",
        filename_prefix: str = "img",
    ):
        """
        Convert image(s) to JPEG, strip EXIF, show in-node preview,
        and optionally save to ComfyUI/output/<folder_name>/.
        """
        batch_size = image.shape[0]
        result_tensors = []
        preview_images = []
        saved_paths = []

        for i in range(batch_size):
            # 1. Tensor → PIL
            pil_img = self._tensor_to_pil(image[i])

            # 2. JPEG round-trip → strips ALL metadata
            clean_pil = self._jpeg_round_trip(pil_img, quality, optimize, progressive)

            # 3. In-node preview (always)
            preview_images.append(self._save_preview(clean_pil))

            # 4. Optional save to output folder
            if save_output:
                path = self._save_to_output(
                    clean_pil, folder_name, filename_prefix, quality, optimize, progressive
                )
                saved_paths.append(path)
                print(f"[JpgExifStrip] Saved → {path}")

            # 5. PIL → tensor
            result_tensors.append(self._pil_to_tensor(clean_pil))

        output_tensor = torch.stack(result_tensors, dim=0)

        return {
            "ui": {"images": preview_images},
            "result": (output_tensor,),
        }


# ---------------------------------------------------------------------------
# Node registration
# ---------------------------------------------------------------------------

NODE_CLASS_MAPPINGS = {
    "JpgExifStrip": JpgExifStripNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "JpgExifStrip": "JPG Converter & EXIF Stripper",
}
