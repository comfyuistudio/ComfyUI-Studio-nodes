# __init__.py
from .aspectratio import AspectRatioImageSize, AspectRatioResizeImage, MarkdownModelNote
from .huggingfacedownloader import HuggingFaceDownloader
from .gitcloner import GitCloneManager
from .transparentvideosave import TransparentVideoSave
from .jpg_exif_strip_node import JpgExifStripNode  

NODE_CLASS_MAPPINGS = {
    "AspectRatioImageSize": AspectRatioImageSize,
    "AspectRatioResizeImage": AspectRatioResizeImage,
    "MarkdownModelNote": MarkdownModelNote,
    "HuggingFaceDownloader": HuggingFaceDownloader,
    "GitCloneManager": GitCloneManager,
    "TransparentVideoSave": TransparentVideoSave,
    "JpgExifStrip": JpgExifStripNode,  
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AspectRatioImageSize": "🧩 Aspect Ratio Image Size",
    "AspectRatioResizeImage": "🖼️ Resize to Aspect Ratio",
    "MarkdownModelNote": "📄 Markdown Link Generator",
    "HuggingFaceDownloader": "🤗 HuggingFace Model Downloader Pro",
    "GitCloneManager": "🔧 Git Repository Clone Manager",
    "TransparentVideoSave": "🔧 TransparentVideoSave",
    "JpgExifStrip": "🖼️ JPG Converter & EXIF Stripper",  
}

NODE_CATEGORIES = {
    "AspectRatioImageSize": "STUDIO NODES",
    "AspectRatioResizeImage": "STUDIO NODES",
    "MarkdownModelNote": "STUDIO NODES",
    "HuggingFaceDownloader": "STUDIO NODES",
    "GitCloneManager": "STUDIO NODES",
    "TransparentVideoSave": "STUDIO NODES",
    "JpgExifStrip": "STUDIO NODES",  # ← add this
}
