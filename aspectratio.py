import numpy as np
import folder_paths
import torch
from PIL import Image

# 🧩 1. Aspect Ratio Image Size Calculator
class AspectRatioImageSize:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "width": ("INT", {
                    "default": 0, "min": 0, "max": 4096, "step": 16
                }),
                "height": ("INT", {
                    "default": 0, "min": 0, "max": 4096, "step": 16
                }),
                "aspect_ratio": ([
                    "1:1", "16:9", "5:4", "4:3", "3:2",
                    "2.39:1", "21:9", "18:9", "17:9", "1.85:1"
                ], {"default": "1:1"}),
                "direction": (["Horizontal", "Vertical"], {"default": "Horizontal"})
            }
        }

    RETURN_TYPES = ("INT", "INT", "STRING")
    RETURN_NAMES = ("width", "height", "resolution_label")
    FUNCTION = "calculate_size"
    CATEGORY = "STUDIO_NODES"

    def calculate_size(self, width, height, aspect_ratio, direction):
        # Priority 1: If both width and height are manually set (> 0), use them
        if width > 0 and height > 0:
            final_width = width
            final_height = height
        # Priority 2: If only width is set, calculate height from aspect ratio
        elif width > 0 and height == 0:
            ratios = {
                "1:1": (1, 1), "16:9": (16, 9), "5:4": (5, 4), "4:3": (4, 3),
                "3:2": (3, 2), "2.39:1": (2.39, 1), "21:9": (21, 9),
                "18:9": (18, 9), "17:9": (17, 9), "1.85:1": (1.85, 1)
            }
            w, h = ratios.get(aspect_ratio, (1, 1))
            if direction == "Vertical":
                w, h = h, w
            final_width = width
            final_height = int(round(width * h / w))
        # Priority 3: If only height is set, calculate width from aspect ratio
        elif width == 0 and height > 0:
            ratios = {
                "1:1": (1, 1), "16:9": (16, 9), "5:4": (5, 4), "4:3": (4, 3),
                "3:2": (3, 2), "2.39:1": (2.39, 1), "21:9": (21, 9),
                "18:9": (18, 9), "17:9": (17, 9), "1.85:1": (1.85, 1)
            }
            w, h = ratios.get(aspect_ratio, (1, 1))
            if direction == "Vertical":
                w, h = h, w
            final_height = height
            final_width = int(round(height * w / h))
        # Priority 4: Default case - both are 0, use aspect ratio with 1 megapixel
        else:
            import math
            # 1 megapixel = 1,000,000 pixels
            target_pixels = 1000000
            
            ratios = {
                "1:1": (1, 1), "16:9": (16, 9), "5:4": (5, 4), "4:3": (4, 3),
                "3:2": (3, 2), "2.39:1": (2.39, 1), "21:9": (21, 9),
                "18:9": (18, 9), "17:9": (17, 9), "1.85:1": (1.85, 1)
            }
            w, h = ratios.get(aspect_ratio, (1, 1))
            if direction == "Vertical":
                w, h = h, w
            
            # Calculate dimensions for 1 megapixel with given aspect ratio
            # width * height = target_pixels
            # width / height = w / h
            # So: width = sqrt(target_pixels * w / h), height = sqrt(target_pixels * h / w)
            final_width = int(round(math.sqrt(target_pixels * w / h)))
            final_height = int(round(math.sqrt(target_pixels * h / w)))
            
            # Make divisible by 16
            final_width = int(round(final_width / 16) * 16)
            final_height = int(round(final_height / 16) * 16)
        
        return final_width, final_height, f"{final_width}x{final_height}"


class AspectRatioResizeImage:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "width": ("INT", {"default": 0, "min": 0, "max": 4096, "step": 16}),
                "height": ("INT", {
                    "default": 0, "min": 0, "max": 4096, "step": 16
                }),
                "aspect_ratio": ([
                    "1:1", "16:9", "5:4", "4:3", "3:2",
                    "2.39:1", "21:9", "18:9", "17:9", "1.85:1"
                ], {"default": "1:1"}),
                "direction": (["Horizontal", "Vertical"], {"default": "Horizontal"}),
                "crop_method": (["Stretch", "Crop"], {"default": "Stretch"})
            }
        }

    RETURN_TYPES = ("IMAGE", "INT", "INT", "STRING")
    RETURN_NAMES = ("resized_image", "width", "height", "resolution_label")
    FUNCTION = "resize_image"
    CATEGORY = "STUDIO_NODES"

    def make_divisible_by_16(self, value):
        """Round value to nearest multiple of 16"""
        return int(round(value / 16) * 16)

    def resize_image(self, image, width, height, aspect_ratio, direction, crop_method):
        # Calculate target dimensions with same priority logic as AspectRatioImageSize
        # Priority 1: If both width and height are manually set (> 0), use them
        if width > 0 and height > 0:
            target_width = width
            target_height = height
        # Priority 2: If only width is set, calculate height from aspect ratio
        elif width > 0 and height == 0:
            ratios = {
                "1:1": (1, 1), "16:9": (16, 9), "5:4": (5, 4), "4:3": (4, 3),
                "3:2": (3, 2), "2.39:1": (2.39, 1), "21:9": (21, 9),
                "18:9": (18, 9), "17:9": (17, 9), "1.85:1": (1.85, 1)
            }
            w_ratio, h_ratio = ratios.get(aspect_ratio, (1, 1))
            if direction == "Vertical":
                w_ratio, h_ratio = h_ratio, w_ratio
            target_width = width
            target_height = int(round(width * h_ratio / w_ratio))
        # Priority 3: If only height is set, calculate width from aspect ratio
        elif width == 0 and height > 0:
            ratios = {
                "1:1": (1, 1), "16:9": (16, 9), "5:4": (5, 4), "4:3": (4, 3),
                "3:2": (3, 2), "2.39:1": (2.39, 1), "21:9": (21, 9),
                "18:9": (18, 9), "17:9": (17, 9), "1.85:1": (1.85, 1)
            }
            w_ratio, h_ratio = ratios.get(aspect_ratio, (1, 1))
            if direction == "Vertical":
                w_ratio, h_ratio = h_ratio, w_ratio
            target_height = height
            target_width = int(round(height * w_ratio / h_ratio))
        # Priority 4: Default case - both are 0, use aspect ratio with 1 megapixel
        else:
            import math
            # 1 megapixel = 1,000,000 pixels
            target_pixels = 1000000
            
            ratios = {
                "1:1": (1, 1), "16:9": (16, 9), "5:4": (5, 4), "4:3": (4, 3),
                "3:2": (3, 2), "2.39:1": (2.39, 1), "21:9": (21, 9),
                "18:9": (18, 9), "17:9": (17, 9), "1.85:1": (1.85, 1)
            }
            w_ratio, h_ratio = ratios.get(aspect_ratio, (1, 1))
            if direction == "Vertical":
                w_ratio, h_ratio = h_ratio, w_ratio
            
            # Calculate dimensions for 1 megapixel with given aspect ratio
            # width * height = target_pixels
            # width / height = w_ratio / h_ratio
            # So: width = sqrt(target_pixels * w_ratio / h_ratio), height = sqrt(target_pixels * h_ratio / w_ratio)
            target_width = int(round(math.sqrt(target_pixels * w_ratio / h_ratio)))
            target_height = int(round(math.sqrt(target_pixels * h_ratio / w_ratio)))
            
            # Make divisible by 16
            target_width = int(round(target_width / 16) * 16)
            target_height = int(round(target_height / 16) * 16)
        
        # Ensure dimensions are divisible by 16
        target_width = self.make_divisible_by_16(target_width)
        target_height = self.make_divisible_by_16(target_height)

        # ComfyUI image format is BHWC (batch, height, width, channels)
        # Extract the first image from the batch
        image_tensor = image[0]  # Shape: (H, W, C)
        
        # Convert tensor to numpy array (already in HWC format)
        image_np = image_tensor.cpu().numpy()
        
        # Convert from [0,1] float to [0,255] uint8
        image_np = np.clip(image_np * 255.0, 0, 255).astype(np.uint8)

        pil_image = Image.fromarray(image_np)
        original_width, original_height = pil_image.size

        if crop_method == "Crop":
            # Calculate the aspect ratio of the original image
            original_aspect_ratio = original_width / original_height
            target_aspect_ratio = target_width / target_height

            if original_aspect_ratio > target_aspect_ratio:
                # Original is wider than target, need to crop width to match target aspect ratio
                # Calculate new width based on original height and target aspect ratio
                new_width = int(original_height * target_aspect_ratio)
                left = (original_width - new_width) // 2
                right = left + new_width
                cropped_image = pil_image.crop((left, 0, right, original_height))
            else:
                # Original is taller than target, need to crop height to match target aspect ratio
                # Calculate new height based on original width and target aspect ratio
                new_height = int(original_width / target_aspect_ratio)
                top = (original_height - new_height) // 2
                bottom = top + new_height
                cropped_image = pil_image.crop((0, top, original_width, bottom))
            
            # Now resize the cropped image to the target dimensions without stretching
            pil_image = cropped_image.resize((target_width, target_height), Image.LANCZOS)
        else: # Stretch
            pil_image = pil_image.resize((target_width, target_height), Image.LANCZOS)

        # Convert back to tensor format for ComfyUI (BHWC)
        resized_np = np.array(pil_image).astype(np.float32) / 255.0
        
        # Add batch dimension back: (H, W, C) -> (1, H, W, C)
        resized_tensor = torch.from_numpy(resized_np).unsqueeze(0)

        return (resized_tensor, target_width, target_height, f"{target_width}x{target_height}")


# 📄 3. Markdown Link Generator (optional example)
class MarkdownModelNote:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "url": ("STRING", {"default": ""}),
                "filename": ("STRING", {"default": "model.safetensors"}),
                "folder": ("STRING", {"default": "App\\ComfyUI\\models\\clip"})
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("markdown_note",)
    FUNCTION = "create_markdown"
    CATEGORY = "STUDIO_NODES"

    def create_markdown(self, url, filename, folder):
        note = f"""### Model: [{filename}]({url})  
**Output folder:**  
`{folder}`

---"""
        return (note,)


# 🔗 Register all nodes here
NODE_CLASS_MAPPINGS = {
    "AspectRatioImageSize": AspectRatioImageSize,
    "AspectRatioResizeImage": AspectRatioResizeImage,
    "MarkdownModelNote": MarkdownModelNote,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AspectRatioImageSize": "🧩 Aspect Ratio Image Size",
    "AspectRatioResizeImage": "🖼️ Resize to Aspect Ratio",
    "MarkdownModelNote": "📄 Markdown Link Generator",
}
