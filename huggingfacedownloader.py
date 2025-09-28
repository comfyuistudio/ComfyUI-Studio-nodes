import os
import requests
import threading
import time
import json
import hashlib
from urllib.parse import urlparse
from queue import Queue
from datetime import datetime
import folder_paths
import logging

try:
    import plyer  # For desktop notifications
    NOTIFICATIONS_AVAILABLE = True
except ImportError:
    NOTIFICATIONS_AVAILABLE = False

try:
    import execution
    COMFYUI_INTERRUPT_AVAILABLE = True
except ImportError:
    COMFYUI_INTERRUPT_AVAILABLE = False

class HuggingFaceDownloader:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "download_links": ("STRING", {
                    "multiline": True,
                    "default": "https://huggingface.co/StableDiffusionVN/Flux/resolve/main/Vae/flux_vae.safetensors vae flux_vae.safetensors"
                }),
                "auto_download": ("BOOLEAN", {"default": True}),
                "max_concurrent_downloads": ("INT", {"default": 3, "min": 1, "max": 10}),
                "max_download_speed_mbps": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1000.0, "step": 0.1}),
                "enable_resume": ("BOOLEAN", {"default": True}),
                "validate_files": ("BOOLEAN", {"default": False}),
                "enable_notifications": ("BOOLEAN", {"default": True}),
                "auto_organize": ("BOOLEAN", {"default": False}),
            },
            "optional": {
                "hf_token": ("STRING", {
                    "multiline": False,
                    "default": "",
                    "placeholder": "hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                }),
            }
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("status_report", "download_history")
    FUNCTION = "download_models"
    CATEGORY = "STUDIO_NODES"
    OUTPUT_NODE = True

    def __init__(self):
        self.download_status = {}
        self.download_queue = Queue()
        self.active_downloads = {}
        self.base_models_path = folder_paths.models_dir
        self.history_file = os.path.join(self.base_models_path, ".hf_download_history.json")
        self.download_history = self.load_history()
        self.interrupt_flag = threading.Event()
        self.download_threads = []
        
        # Model type organization mapping
        self.model_type_mapping = {
            'safetensors': 'checkpoints',
            'ckpt': 'checkpoints',
            'pt': 'checkpoints',
            'bin': 'checkpoints',
            'pth': 'checkpoints',
        }

    def load_history(self):
        """Load download history from file"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logging.warning(f"Could not load download history: {e}")
        return {}

    def save_history(self):
        """Save download history to file"""
        try:
            os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
            with open(self.history_file, 'w') as f:
                json.dump(self.download_history, f, indent=2)
        except Exception as e:
            logging.warning(f"Could not save download history: {e}")

    def check_interrupt(self):
        """Check if download should be interrupted"""
        # Check internal interrupt flag
        if self.interrupt_flag.is_set():
            return True
        
        # Check ComfyUI interrupt status if available
        if COMFYUI_INTERRUPT_AVAILABLE:
            try:
                return execution.PromptServer.instance.client_id is None or execution.interrupt_processing
            except:
                pass
        
        return False

    def interrupt_downloads(self):
        """Interrupt all active downloads"""
        self.interrupt_flag.set()
        
        # Wait for all download threads to finish
        for thread in self.download_threads:
            if thread.is_alive():
                thread.join(timeout=2.0)
        
        self.download_threads.clear()
        self.interrupt_flag.clear()
    def send_notification(self, title, message, enable_notifications):
        """Send desktop notification if available and enabled"""
        if enable_notifications and NOTIFICATIONS_AVAILABLE:
            try:
                plyer.notification.notify(
                    title=title,
                    message=message,
                    app_name="ComfyUI HF Downloader",
                    timeout=5
                )
            except Exception as e:
                logging.warning(f"Could not send notification: {e}")

    def parse_download_line(self, line):
        """Parse a single download line into components"""
        parts = line.strip().split()
        if len(parts) < 2:
            return None, None, None, "Invalid format: need at least URL and folder"
        
        url = parts[0]
        folder = parts[1]
        
        # If filename is provided, use it; otherwise extract from URL
        if len(parts) >= 3:
            filename = parts[2]
        else:
            parsed_url = urlparse(url)
            filename = os.path.basename(parsed_url.path)
            if not filename:
                return None, None, None, "Could not determine filename from URL"
        
        return url, folder, filename, None

    def get_organized_folder(self, folder, filename, auto_organize):
        """Get organized folder path based on file extension"""
        if not auto_organize:
            return folder
        
        file_ext = filename.split('.')[-1].lower()
        if file_ext in self.model_type_mapping:
            return self.model_type_mapping[file_ext]
        
        # Special cases for common model types
        filename_lower = filename.lower()
        if 'vae' in filename_lower:
            return 'vae'
        elif 'lora' in filename_lower or 'lycoris' in filename_lower:
            return 'loras'
        elif 'controlnet' in filename_lower:
            return 'controlnet'
        elif 'embedding' in filename_lower or 'textual_inversion' in filename_lower:
            return 'embeddings'
        
        return folder

    def calculate_file_hash(self, filepath):
        """Calculate SHA256 hash of a file"""
        hash_sha256 = hashlib.sha256()
        try:
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception:
            return None

    def get_remote_file_info(self, url, hf_token):
        """Get remote file size and etag for validation"""
        headers = {}
        if hf_token:
            headers['Authorization'] = f'Bearer {hf_token}'
        
        try:
            response = requests.head(url, headers=headers, timeout=10)
            if response.status_code == 200:
                return {
                    'size': int(response.headers.get('content-length', 0)),
                    'etag': response.headers.get('etag', '').strip('"'),
                    'last_modified': response.headers.get('last-modified', '')
                }
        except Exception as e:
            logging.warning(f"Could not get remote file info: {e}")
        return {'size': 0, 'etag': '', 'last_modified': ''}

    def download_file_worker(self, download_info, enable_notifications, max_speed_mbps, enable_resume, validate_files, hf_token):
        """Worker function for downloading a single file"""
        url, filepath, key, folder, filename = download_info
        
        try:
            self.download_status[key] = {"status": "starting", "progress": 0, "error": None, "speed": 0}
            
            # Check for interrupt before starting
            if self.check_interrupt():
                self.download_status[key] = {"status": "interrupted", "progress": 0, "error": "Download interrupted by user"}
                return
            
            headers = {}
            if hf_token:
                headers['Authorization'] = f'Bearer {hf_token}'
            
            # Check if we can resume
            resume_pos = 0
            if enable_resume and os.path.exists(filepath + ".tmp"):
                resume_pos = os.path.getsize(filepath + ".tmp")
                headers['Range'] = f'bytes={resume_pos}-'
            
            response = requests.get(url, headers=headers, stream=True, timeout=30)
            
            # Handle range request response
            if resume_pos > 0 and response.status_code == 206:
                total_size = resume_pos + int(response.headers.get('content-length', 0))
                mode = 'ab'  # Append mode for resume
            else:
                response.raise_for_status()
                total_size = int(response.headers.get('content-length', 0))
                resume_pos = 0  # Reset if range not supported
                mode = 'wb'   # Write mode for new download
            
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            temp_filepath = filepath + ".tmp"
            
            downloaded = resume_pos
            start_time = time.time()
            last_update = start_time
            
            # Calculate speed limit in bytes per second
            speed_limit_bps = max_speed_mbps * 1024 * 1024 if max_speed_mbps > 0 else 0
            
            with open(temp_filepath, mode) as f:
                self.download_status[key]["status"] = "downloading"
                
                for chunk in response.iter_content(chunk_size=8192):
                    # Check for interrupt frequently
                    if self.check_interrupt():
                        self.download_status[key] = {"status": "interrupted", "progress": 0, "error": "Download interrupted by user"}
                        return
                    
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        current_time = time.time()
                        
                        # Update progress and speed
                        if current_time - last_update >= 0.5:  # Update every 0.5 seconds for more responsive interrupts
                            if total_size > 0:
                                progress = (downloaded / total_size) * 100
                                self.download_status[key]["progress"] = round(progress, 1)
                            
                            # Calculate speed
                            elapsed = current_time - start_time
                            if elapsed > 0:
                                speed_bps = (downloaded - resume_pos) / elapsed
                                speed_mbps = speed_bps / (1024 * 1024)
                                self.download_status[key]["speed"] = round(speed_mbps, 2)
                            
                            last_update = current_time
                        
                        # Apply speed limiting
                        if speed_limit_bps > 0:
                            elapsed = current_time - start_time
                            expected_time = (downloaded - resume_pos) / speed_limit_bps
                            if elapsed < expected_time:
                                sleep_time = expected_time - elapsed
                                # Sleep in small chunks to allow interrupt checking
                                sleep_chunks = max(1, int(sleep_time / 0.1))
                                for _ in range(sleep_chunks):
                                    if self.check_interrupt():
                                        self.download_status[key] = {"status": "interrupted", "progress": 0, "error": "Download interrupted by user"}
                                        return
                                    time.sleep(sleep_time / sleep_chunks)
            
            # Final interrupt check before validation
            if self.check_interrupt():
                self.download_status[key] = {"status": "interrupted", "progress": 0, "error": "Download interrupted by user"}
                return
            
            # Validate file if requested
            if validate_files and total_size > 0:
                actual_size = os.path.getsize(temp_filepath)
                if actual_size != total_size:
                    raise Exception(f"File size mismatch: expected {total_size}, got {actual_size}")
            
            # Move temp file to final location
            if os.path.exists(filepath):
                os.remove(filepath)  # Remove existing file if any
            os.rename(temp_filepath, filepath)
            
            # Update history
            file_info = {
                'url': url,
                'folder': folder,
                'filename': filename,
                'size': os.path.getsize(filepath),
                'download_date': datetime.now().isoformat(),
                'hash': self.calculate_file_hash(filepath) if validate_files else None
            }
            self.download_history[filepath] = file_info
            
            self.download_status[key] = {
                "status": "completed", 
                "progress": 100, 
                "error": None,
                "size": os.path.getsize(filepath),
                "speed": 0
            }
            
            self.send_notification(
                "Download Complete", 
                f"Successfully downloaded {filename}",
                enable_notifications
            )
            
        except Exception as e:
            if self.check_interrupt():
                self.download_status[key] = {"status": "interrupted", "progress": 0, "error": "Download interrupted by user"}
            else:
                error_msg = str(e)
                self.download_status[key] = {
                    "status": "error", 
                    "progress": 0, 
                    "error": error_msg,
                    "speed": 0
                }
                
                self.send_notification(
                    "Download Failed", 
                    f"Failed to download {filename}: {error_msg}",
                    enable_notifications
                )
            
            # Clean up temp file if not resuming or interrupted
            temp_filepath = filepath + ".tmp"
            if os.path.exists(temp_filepath) and (not enable_resume or self.check_interrupt()):
                try:
                    os.remove(temp_filepath)
                except:
                    pass

    def download_queue_manager(self, max_concurrent, enable_notifications, max_speed_mbps, enable_resume, validate_files, hf_token):
        """Manage download queue with concurrent limits"""
        active_threads = []
        
        while not self.download_queue.empty() or active_threads:
            # Check for interrupt
            if self.check_interrupt():
                # Cancel remaining downloads in queue
                while not self.download_queue.empty():
                    try:
                        self.download_queue.get_nowait()
                    except:
                        break
                
                # Wait for active downloads to stop
                for thread in active_threads:
                    if thread.is_alive():
                        thread.join(timeout=1.0)
                
                break
            
            # Clean up completed threads
            active_threads = [t for t in active_threads if t.is_alive()]
            
            # Start new downloads if under limit
            while len(active_threads) < max_concurrent and not self.download_queue.empty():
                if self.check_interrupt():
                    break
                    
                download_info = self.download_queue.get()
                thread = threading.Thread(
                    target=self.download_file_worker,
                    args=(download_info, enable_notifications, max_speed_mbps, enable_resume, validate_files, hf_token)
                )
                thread.daemon = True
                thread.start()
                active_threads.append(thread)
                self.download_threads.append(thread)
            
            time.sleep(0.1)  # Small delay to prevent busy waiting

    def format_size(self, size_bytes):
        """Format file size in human readable format"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.1f} {size_names[i]}"

    def get_download_history_summary(self):
        """Get formatted download history summary"""
        if not self.download_history:
            return "No download history available."
        
        history_lines = ["=== DOWNLOAD HISTORY ==="]
        total_size = 0
        
        for filepath, info in sorted(self.download_history.items(), key=lambda x: x[1]['download_date'], reverse=True):
            date_str = info['download_date'][:19].replace('T', ' ')
            size_str = self.format_size(info['size'])
            total_size += info['size']
            
            history_lines.append(f"{date_str} | {info['filename']} | {size_str} | {info['folder']}/")
        
        history_lines.append(f"\nTotal downloaded: {len(self.download_history)} files ({self.format_size(total_size)})")
        return "\n".join(history_lines)

    def download_models(self, download_links, auto_download, max_concurrent_downloads, 
                       max_download_speed_mbps, enable_resume, validate_files, 
                       enable_notifications, auto_organize, hf_token=""):
        """Main function to handle model downloads"""
        lines = [line.strip() for line in download_links.split('\n') if line.strip()]
        
        if not lines:
            return ("No download links provided", self.get_download_history_summary())
        
        results = []
        
        # Clear previous download status
        self.download_status.clear()
        
        for i, line in enumerate(lines):
            url, folder, filename, error = self.parse_download_line(line)
            
            if error:
                results.append(f"Line {i+1}: ERROR - {error}")
                continue
            
            # Get organized folder if auto-organize is enabled
            final_folder = self.get_organized_folder(folder, filename, auto_organize)
            
            # Construct full file path
            folder_path = os.path.join(self.base_models_path, final_folder)
            filepath = os.path.join(folder_path, filename)
            
            # Check if file already exists and validate
            if os.path.exists(filepath):
                file_size = os.path.getsize(filepath)
                
                if validate_files:
                    # Get remote file info for validation
                    remote_info = self.get_remote_file_info(url, hf_token)
                    if remote_info['size'] > 0 and file_size != remote_info['size']:
                        results.append(f"⚠ {filename}: Size mismatch, will re-download")
                    else:
                        results.append(f"✓ {filename}: Already exists and validated ({self.format_size(file_size)})")
                        continue
                else:
                    results.append(f"✓ {filename}: Already exists ({self.format_size(file_size)})")
                    continue
            
            if not auto_download:
                results.append(f"⏸ {filename}: Ready to download (auto_download disabled)")
                continue
            
            # Add to download queue
            key = f"download_{i}"
            self.download_queue.put((url, filepath, key, final_folder, filename))
        
        if auto_download and not self.download_queue.empty():
            # Clear interrupt flag and download threads list
            self.interrupt_flag.clear()
            self.download_threads.clear()
            
            # Start queue manager
            queue_thread = threading.Thread(
                target=self.download_queue_manager,
                args=(max_concurrent_downloads, enable_notifications, max_download_speed_mbps, 
                      enable_resume, validate_files, hf_token)
            )
            queue_thread.daemon = True
            queue_thread.start()
            
            # Monitor downloads with interrupt checking
            while queue_thread.is_alive():
                if self.check_interrupt():
                    self.interrupt_downloads()
                    break
                
                time.sleep(0.5)  # Check more frequently for interrupts
                
                # Update results with current status
                in_progress = []
                for key, status in self.download_status.items():
                    if status['status'] == 'downloading':
                        progress = status.get('progress', 0)
                        speed = status.get('speed', 0)
                        in_progress.append(f"⬇ Download {key}: {progress}% ({speed} MB/s)")
                
                if in_progress:
                    print(f"Downloads in progress: {len(in_progress)}")
            
            # Wait for queue thread to finish
            queue_thread.join(timeout=2.0)
            
            # Collect final results
            for key, status_info in self.download_status.items():
                download_num = key.split('_')[1]
                line_num = int(download_num)
                url, folder, filename, _ = self.parse_download_line(lines[line_num])
                final_folder = self.get_organized_folder(folder, filename, auto_organize)
                
                if status_info.get("status") == "completed":
                    size_str = self.format_size(status_info.get("size", 0))
                    results.append(f"✓ {filename}: Downloaded successfully to {final_folder}/ ({size_str})")
                elif status_info.get("status") == "interrupted":
                    results.append(f"⏸ {filename}: Download interrupted by user")
                elif status_info.get("status") == "error":
                    error_msg = status_info.get("error", "Unknown error")
                    results.append(f"✗ {filename}: Download failed - {error_msg}")
        
        # Save history
        self.save_history()
        
        # Format final report
        total_files = len(lines)
        successful = len([r for r in results if r.startswith("✓") and "Downloaded successfully" in r])
        failed = len([r for r in results if r.startswith("✗")])
        interrupted = len([r for r in results if "interrupted" in r])
        skipped = len([r for r in results if "Already exists" in r])
        
        # Send completion notification
        if auto_download and successful > 0:
            self.send_notification(
                "Downloads Complete",
                f"Downloaded {successful}/{total_files} files successfully",
                enable_notifications
            )
        
        summary = f"""=== DOWNLOAD REPORT ===
Total files: {total_files}
Successful downloads: {successful}
Already existed: {skipped}
Interrupted: {interrupted}
Failed: {failed}
Max concurrent: {max_concurrent_downloads}
Speed limit: {'Unlimited' if max_download_speed_mbps == 0 else f'{max_download_speed_mbps} MB/s'}
Resume enabled: {enable_resume}
Validation enabled: {validate_files}
Auto-organize: {auto_organize}

Details:
""" + "\n".join(results)
        
        return (summary, self.get_download_history_summary())

# Node registration
NODE_CLASS_MAPPINGS = {
    "HuggingFaceDownloader": HuggingFaceDownloader
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "HuggingFaceDownloader": "🤗 HuggingFace Model Downloader Pro"
}