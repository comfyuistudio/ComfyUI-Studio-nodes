# __init__.py

# Import your node classes
from .aspectratio import AspectRatioImageSize, AspectRatioResizeImage, MarkdownModelNote
from .huggingfacedownloader import HuggingFaceDownloader
from .gitcloner import GitCloneManager
from .chromasaver import Chromasaver
# Register all nodes in one dictionary
NODE_CLASS_MAPPINGS = {
    "AspectRatioImageSize": AspectRatioImageSize,
    "AspectRatioResizeImage": AspectRatioResizeImage,
    "MarkdownModelNote": MarkdownModelNote,
    "HuggingFaceDownloader": HuggingFaceDownloader,
    "GitCloneManager": GitCloneManager,
    "Chromasaver": Chromasaver,
}

# Display names for the nodes
NODE_DISPLAY_NAME_MAPPINGS = {
    "AspectRatioImageSize": "🧩 Aspect Ratio Image Size",
    "AspectRatioResizeImage": "🖼️ Resize to Aspect Ratio",
    "MarkdownModelNote": "📄 Markdown Link Generator",
    "HuggingFaceDownloader": "🤗 HuggingFace Model Downloader Pro",
    "GitCloneManager": "🔧 Git Repository Clone Manager",
    "Chromasaver": "🔧 Chromasaver",
}

# Assign a category for all nodes (so they appear in the left menu)
NODE_CATEGORIES = {
    "AspectRatioImageSize": "STUDIO NODES",
    "AspectRatioResizeImage": "STUDIO NODES",
    "MarkdownModelNote": "STUDIO NODES",
    "HuggingFaceDownloader": "STUDIO NODES",
    "GitCloneManager": "STUDIO NODES",
    "Chromasaver": "STUDIO NODES",
}
