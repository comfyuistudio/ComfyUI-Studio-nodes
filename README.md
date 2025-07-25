ComfyUI Studio Nodes

This repository contains a collection of custom nodes for ComfyUI, designed to enhance your workflow with improved image manipulation and documentation capabilities. Below are the descriptions for each node:

📄 Markdown Link Generator (MarkdownModelNote)

This utility node is designed to generate and display markdown-formatted notes directly within your ComfyUI workflow. It's particularly useful for documenting model usage, linking to external resources, or providing quick information about specific assets.

Features:

•
Dynamic Markdown Generation: Automatically formats input url, filename, and folder into a clickable markdown link and displays the output folder path.

Inputs:

•
url (STRING): The URL associated with the model or resource.

•
filename (STRING): The name of the model file (e.g., model.safetensors).

•
folder (STRING): The local path where the model is stored (e.g., App\\ComfyUI\\models\\clip).

Outputs:

•
markdown_note (STRING): The generated markdown string. This can be connected to other nodes if needed.

🧩 Aspect Ratio Image Size (AspectRatioImageSize)

This node helps you determine the appropriate dimensions for your images based on a desired aspect ratio and a specified width. It's crucial for maintaining visual consistency and avoiding distortion when working with various image generation models.

Features:

•
Aspect Ratio Calculation: Calculates the corresponding height for a given width and aspect ratio.

•
Horizontal/Vertical Direction: Allows you to specify whether the aspect ratio applies horizontally or vertically, providing flexibility for different image orientations.

Inputs:

•
width (INT): The desired width of the image.

•
aspect_ratio (STRING): The target aspect ratio (e.g., "1:1", "16:9", "4:3").

•
direction (STRING): Specifies if the aspect ratio is applied horizontally or vertically ("Horizontal", "Vertical").

Outputs:

•
width (INT): The calculated width.

•
height (INT): The calculated height.

•
resolution_label (STRING): A label showing the calculated resolution (e.g., "1024x576").

🖼️ Resize to Aspect Ratio (AspectRatioResizeImage)

This node provides robust image resizing capabilities, allowing you to resize images to a specific width while maintaining a chosen aspect ratio. It offers both stretching and intelligent cropping options to ensure your images fit the desired dimensions without unwanted distortion.

Features:

•
Aspect Ratio Resizing: Resizes images to a target width and calculated height based on a selected aspect ratio.

•
Horizontal/Vertical Direction: Adjusts the aspect ratio application based on horizontal or vertical orientation.

•
Crop Method Switcher: Choose between:

•
Stretch: Stretches the image to fit the target dimensions, potentially causing distortion.

•
Crop: Intelligently crops the image to match the target aspect ratio before resizing, preventing stretching and maintaining visual integrity.



Inputs:

•
image (IMAGE): The input image to be resized.

•
width (INT): The desired output width of the image.

•
aspect_ratio (STRING): The target aspect ratio (e.g., "1:1", "16:9", "4:3").

•
direction (STRING): Specifies if the aspect ratio is applied horizontally or vertically ("Horizontal", "Vertical").

•
crop_method (STRING): Determines how the image is adjusted to the aspect ratio ("Stretch", "Crop").

Outputs:

•
resized_image (IMAGE): The resized image.

•
resolution_label (STRING): A label showing the final resolution (e.g., "1024x576").

