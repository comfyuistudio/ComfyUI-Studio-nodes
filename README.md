# 🎨 Aspect Ratio Nodes for ComfyUI

A collection of custom nodes for ComfyUI that provide flexible aspect ratio calculations and image resizing with intelligent dimension handling.

## 📋 Features

- **Smart dimension calculation** with priority-based logic
- **1 megapixel default sizing** for consistent file sizes across all aspect ratios
- **Multiple aspect ratio presets** including cinematic and social media formats
- **Automatic 16-divisible rounding** for AI model compatibility
- **Flexible resize options** with crop or stretch methods
- **Horizontal/Vertical direction support**

## 🧩 Nodes Included

### 1. **🧩 Aspect Ratio Image Size**
Calculates width and height based on aspect ratios with intelligent priority handling.

**Inputs:**
- `width` (INT): Target width (0 = auto-calculate)
- `height` (INT): Target height (0 = auto-calculate)  
- `aspect_ratio` (DROPDOWN): Pre-defined aspect ratios
- `direction` (DROPDOWN): Horizontal or Vertical orientation

**Outputs:**
- `width` (INT): Calculated width
- `height` (INT): Calculated height
- `resolution_label` (STRING): Formatted resolution string (e.g., "1920x1080")

### 2. **🖼️ Resize to Aspect Ratio**
Resizes images to specific dimensions using the same intelligent sizing logic.

**Inputs:**
- `image` (IMAGE): Input image to resize
- `width` (INT): Target width (0 = auto-calculate)
- `height` (INT): Target height (0 = auto-calculate)
- `aspect_ratio` (DROPDOWN): Pre-defined aspect ratios
- `direction` (DROPDOWN): Horizontal or Vertical orientation
- `crop_method` (DROPDOWN): Stretch or Crop to fit

**Outputs:**
- `resized_image` (IMAGE): Processed image
- `width` (INT): Final width
- `height` (INT): Final height
- `resolution_label` (STRING): Formatted resolution string

### 3. **📄 Markdown Link Generator**
Utility node for creating markdown notes with model links and folder paths.

## 🎯 Priority Logic

The nodes use an intelligent 4-tier priority system:

1. **Manual Override** (`width > 0` AND `height > 0`)
   - Uses exact dimensions provided
   - Ignores aspect ratio settings

2. **Width-Based Calculation** (`width > 0`, `height = 0`)
   - Uses provided width
   - Calculates height from aspect ratio

3. **Height-Based Calculation** (`width = 0`, `height > 0`)
   - Uses provided height
   - Calculates width from aspect ratio

4. **1 Megapixel Default** (`width = 0`, `height = 0`)
   - Calculates dimensions for exactly 1,000,000 pixels
   - Uses selected aspect ratio
   - Perfect for consistent file sizes

## 📐 Supported Aspect Ratios

| Ratio | Description | Example Use |
|-------|-------------|-------------|
| **1:1** | Square | Social media posts, avatars |
| **16:9** | Widescreen | YouTube, TV, monitors |
| **5:4** | Classic photo | Instagram posts |
| **4:3** | Standard photo | Traditional photography |
| **3:2** | DSLR photo | Camera sensors |
| **2.39:1** | Cinematic | Ultra-wide movies |
| **21:9** | Ultra-wide | Gaming monitors |
| **18:9** | Mobile | Modern smartphones |
| **17:9** | Mobile wide | Some phone screens |
| **1.85:1** | Cinema | Theater projection |

## 💡 Usage Examples

### Example 1: Default 1 Megapixel Sizing
```
width = 0, height = 0, aspect_ratio = "16:9"
→ Output: ~1333x750 (≈1 megapixel)
```

### Example 2: Width-Based Calculation
```
width = 1920, height = 0, aspect_ratio = "16:9"
→ Output: 1920x1080
```

### Example 3: Manual Override
```
width = 1920, height = 1200, aspect_ratio = "16:9" (ignored)
→ Output: 1920x1200
```

### Example 4: Vertical Orientation
```
width = 0, height = 0, aspect_ratio = "16:9", direction = "Vertical"
→ Output: ~750x1333 (9:16 ratio)
```

## 🔧 Technical Details

- **Automatic 16-divisibility**: All dimensions are rounded to the nearest multiple of 16 for optimal AI model compatibility
- **Precise calculations**: Uses mathematical formulas to ensure exact aspect ratios
- **Memory efficient**: 1 megapixel default keeps file sizes manageable
- **PIL integration**: High-quality image processing with LANCZOS resampling

## 🚀 Installation

### Method 1: ComfyUI Manager (Recommended)
1. Open ComfyUI Manager
2. Search for "Aspect Ratio Nodes"
3. Click Install
4. Restart ComfyUI

### Method 2: Manual Installation
1. Navigate to your ComfyUI `custom_nodes` folder
2. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/comfyui-aspect-ratio-nodes.git
   ```
3. Restart ComfyUI

### Method 3: Direct Download
1. Download the repository as ZIP
2. Extract to `ComfyUI/custom_nodes/`
3. Restart ComfyUI

## 📱 Perfect For

- **AI Image Generation**: Consistent dimensions for stable diffusion
- **Social Media Content**: Pre-configured aspect ratios for different platforms
- **Video Production**: Cinematic and broadcast aspect ratios
- **Photography**: Standard camera and print formats
- **Web Design**: Responsive image sizing

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- ComfyUI community for the amazing framework
- Contributors and testers who helped improve these nodes

---

**Made with ❤️ for the ComfyUI community**
