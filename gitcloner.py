import os
import subprocess
import threading
import time
import json
import shutil
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

class GitCloneManager:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "repositories": ("STRING", {
                    "multiline": True,
                    "default": """https://github.com/ltdrdata/ComfyUI-Manager
https://huggingface.co/spaces/huggingface/CodeBERTa-small-v1 models/codebert
https://github.com/WASasquatch/was-node-suite-comfyui
branch:main https://github.com/user/repo custom_nodes/custom-repo"""
                }),
                "auto_clone": ("BOOLEAN", {"default": True}),
                "max_concurrent_clones": ("INT", {"default": 2, "min": 1, "max": 5}),
                "clone_depth": ("INT", {"default": 0, "min": 0, "max": 100}),
                "enable_notifications": ("BOOLEAN", {"default": True}),
                "force_update": ("BOOLEAN", {"default": False}),
                "clone_submodules": ("BOOLEAN", {"default": False}),
            },
            "optional": {
                "hf_token": ("STRING", {
                    "multiline": False,
                    "default": "",
                    "placeholder": "hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                }),
                "git_token": ("STRING", {
                    "multiline": False,
                    "default": "",
                    "placeholder": "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                }),
            }
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("clone_report", "repository_list")
    FUNCTION = "clone_repositories"
    CATEGORY = "STUDIO_NODES"
    OUTPUT_NODE = True

    def __init__(self):
        self.clone_status = {}
        self.base_path = os.path.dirname(folder_paths.models_dir)
        self.custom_nodes_path = os.path.join(self.base_path, "custom_nodes")
        self.models_path = folder_paths.models_dir
        self.history_file = os.path.join(self.base_path, ".git_clone_history.json")
        self.clone_history = self.load_history()
        self.interrupt_flag = threading.Event()
        self.git_processes = []
        self.clone_threads = []

    def load_history(self):
        """Load clone history from file"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logging.warning(f"Could not load clone history: {e}")
        return {}

    def save_history(self):
        """Save clone history to file"""
        try:
            os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
            with open(self.history_file, 'w') as f:
                json.dump(self.clone_history, f, indent=2)
        except Exception as e:
            logging.warning(f"Could not save clone history: {e}")

    def check_interrupt(self):
        """Check if clone should be interrupted"""
        if self.interrupt_flag.is_set():
            return True
        
        if COMFYUI_INTERRUPT_AVAILABLE:
            try:
                return execution.PromptServer.instance.client_id is None or execution.interrupt_processing
            except:
                pass
        
        return False

    def interrupt_clones(self):
        """Interrupt all active clones"""
        self.interrupt_flag.set()
        
        # Terminate git processes
        for process in self.git_processes[:]:
            try:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=3.0)
                    except subprocess.TimeoutExpired:
                        process.kill()
                self.git_processes.remove(process)
            except Exception as e:
                logging.warning(f"Error terminating git process: {e}")
        
        # Wait for threads
        for thread in self.clone_threads:
            if thread.is_alive():
                thread.join(timeout=2.0)
        
        self.clone_threads.clear()
        self.git_processes.clear()
        self.interrupt_flag.clear()

    def send_notification(self, title, message, enable_notifications):
        """Send desktop notification if available and enabled"""
        if enable_notifications and NOTIFICATIONS_AVAILABLE:
            try:
                plyer.notification.notify(
                    title=title,
                    message=message,
                    app_name="ComfyUI Git Clone",
                    timeout=5
                )
            except Exception as e:
                logging.warning(f"Could not send notification: {e}")

    def is_git_available(self):
        """Check if git is available in system"""
        try:
            subprocess.run(['git', '--version'], capture_output=True, check=True, timeout=5)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def parse_repository_line(self, line):
        """Parse a single repository line into components"""
        parts = line.strip().split()
        if len(parts) < 1:
            return None, None, None, None, "Empty line"
        
        branch = None
        url = None
        custom_path = None
        
        # Check for branch specification
        if parts[0].startswith('branch:'):
            if len(parts) < 2:
                return None, None, None, None, "Branch specified but no URL provided"
            branch = parts[0].split(':', 1)[1]
            url = parts[1]
            if len(parts) >= 3:
                custom_path = parts[2]
        else:
            url = parts[0]
            if len(parts) >= 2:
                custom_path = parts[1]
        
        # Determine repository type and default path
        repo_name = url.rstrip('/').split('/')[-1]
        if repo_name.endswith('.git'):
            repo_name = repo_name[:-4]
        
        if custom_path:
            target_path = custom_path
            if not target_path.startswith('/'):  # Relative path
                if target_path.startswith('custom_nodes/'):
                    target_dir = os.path.join(self.custom_nodes_path, target_path[13:])
                elif target_path.startswith('models/'):
                    target_dir = os.path.join(self.models_path, target_path[7:])
                else:
                    target_dir = os.path.join(self.models_path, target_path)
        else:
            # Auto-detect based on URL
            if 'huggingface.co' in url.lower():
                target_path = f"models/hf_repos/{repo_name}"
                target_dir = os.path.join(self.models_path, f"hf_repos/{repo_name}")
            else:
                # Assume it's a custom node
                target_path = f"custom_nodes/{repo_name}"
                target_dir = os.path.join(self.custom_nodes_path, repo_name)
        
        return url, target_dir, target_path, branch, None

    def get_repository_info(self, target_dir):
        """Get information about existing repository"""
        if not os.path.exists(target_dir):
            return None
        
        try:
            # Check if it's a git repository
            git_dir = os.path.join(target_dir, '.git')
            if not os.path.exists(git_dir):
                return {"status": "not_git", "message": "Directory exists but is not a git repository"}
            
            # Get current branch and remote URL
            result = subprocess.run(
                ['git', '-C', target_dir, 'branch', '--show-current'],
                capture_output=True, text=True, timeout=5
            )
            current_branch = result.stdout.strip() if result.returncode == 0 else "unknown"
            
            result = subprocess.run(
                ['git', '-C', target_dir, 'remote', 'get-url', 'origin'],
                capture_output=True, text=True, timeout=5
            )
            remote_url = result.stdout.strip() if result.returncode == 0 else "unknown"
            
            # Get last commit info
            result = subprocess.run(
                ['git', '-C', target_dir, 'log', '-1', '--format=%H|%s|%cd', '--date=short'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                commit_hash, commit_msg, commit_date = result.stdout.strip().split('|', 2)
                return {
                    "status": "git_repo",
                    "branch": current_branch,
                    "remote_url": remote_url,
                    "last_commit": commit_hash[:8],
                    "commit_message": commit_msg,
                    "commit_date": commit_date
                }
            
            return {"status": "git_repo", "branch": current_branch, "remote_url": remote_url}
            
        except Exception as e:
            return {"status": "error", "message": f"Error checking repository: {str(e)}"}

    def calculate_directory_size(self, directory):
        """Calculate total size of directory"""
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(directory):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    if os.path.exists(filepath):
                        total_size += os.path.getsize(filepath)
        except Exception:
            pass
        return total_size

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

    def git_clone_worker(self, clone_info, enable_notifications, clone_depth, force_update, clone_submodules, hf_token, git_token):
        """Worker function for git clone operations"""
        url, target_dir, target_path, branch, key = clone_info
        
        try:
            self.clone_status[key] = {"status": "starting", "progress": 0, "error": None}
            
            if self.check_interrupt():
                self.clone_status[key] = {"status": "interrupted", "progress": 0, "error": "Clone interrupted by user"}
                return
            
            # Check if directory exists
            repo_info = self.get_repository_info(target_dir)
            if repo_info and repo_info["status"] == "git_repo":
                if force_update:
                    # Update existing repository
                    self.clone_status[key]["status"] = "updating"
                    
                    git_cmd = ['git', '-C', target_dir, 'pull']
                    if branch:
                        git_cmd = ['git', '-C', target_dir, 'pull', 'origin', branch]
                    
                else:
                    # Repository already exists
                    size = self.calculate_directory_size(target_dir)
                    self.clone_status[key] = {
                        "status": "exists",
                        "progress": 100,
                        "error": None,
                        "size": size,
                        "info": repo_info
                    }
                    return
            elif repo_info and repo_info["status"] == "not_git":
                if force_update:
                    # Remove non-git directory
                    shutil.rmtree(target_dir)
                else:
                    self.clone_status[key] = {
                        "status": "error",
                        "progress": 0,
                        "error": "Directory exists but is not a git repository. Use force_update to overwrite."
                    }
                    return
            
            # Prepare git command
            if not repo_info or force_update:
                # Create parent directory
                os.makedirs(os.path.dirname(target_dir), exist_ok=True)
                
                git_cmd = ['git', 'clone']
                
                # Add depth if specified
                if clone_depth > 0:
                    git_cmd.extend(['--depth', str(clone_depth)])
                
                # Add submodules if requested
                if clone_submodules:
                    git_cmd.append('--recurse-submodules')
                
                # Add branch if specified
                if branch:
                    git_cmd.extend(['-b', branch])
                
                # Handle authentication
                clone_url = url
                if hf_token and 'huggingface.co' in url.lower():
                    clone_url = url.replace('https://huggingface.co/', f'https://oauth2:{hf_token}@huggingface.co/')
                elif git_token and ('github.com' in url.lower() or 'gitlab.com' in url.lower()):
                    if url.startswith('https://github.com/'):
                        clone_url = url.replace('https://github.com/', f'https://{git_token}@github.com/')
                    elif url.startswith('https://gitlab.com/'):
                        clone_url = url.replace('https://gitlab.com/', f'https://oauth2:{git_token}@gitlab.com/')
                
                git_cmd.extend([clone_url, target_dir])
                
                self.clone_status[key]["status"] = "cloning"
            
            # Execute git command
            process = subprocess.Popen(
                git_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            self.git_processes.append(process)
            
            # Monitor process
            output_lines = []
            while process.poll() is None:
                if self.check_interrupt():
                    process.terminate()
                    self.clone_status[key] = {"status": "interrupted", "progress": 0, "error": "Clone interrupted by user"}
                    return
                
                try:
                    line = process.stdout.readline()
                    if line:
                        output_lines.append(line.strip())
                        # Extract progress from git output
                        if 'Receiving objects:' in line or 'Resolving deltas:' in line:
                            try:
                                if '%' in line:
                                    percent_parts = line.split('%')
                                    if len(percent_parts) > 0:
                                        percent_str = percent_parts[0].split()[-1]
                                        if percent_str.isdigit():
                                            self.clone_status[key]["progress"] = int(percent_str)
                            except:
                                pass
                except:
                    pass
                
                time.sleep(0.1)
            
            # Remove from tracking
            if process in self.git_processes:
                self.git_processes.remove(process)
            
            # Check result
            if process.returncode == 0:
                size = self.calculate_directory_size(target_dir)
                repo_info = self.get_repository_info(target_dir)
                
                # Update history
                clone_record = {
                    'url': url,
                    'target_path': target_path,
                    'branch': branch,
                    'size': size,
                    'clone_date': datetime.now().isoformat(),
                    'repo_info': repo_info
                }
                self.clone_history[target_dir] = clone_record
                
                self.clone_status[key] = {
                    "status": "completed",
                    "progress": 100,
                    "error": None,
                    "size": size,
                    "info": repo_info
                }
                
                self.send_notification(
                    "Git Clone Complete",
                    f"Successfully cloned {os.path.basename(target_path)}",
                    enable_notifications
                )
            else:
                error_output = '\n'.join(output_lines[-10:])
                self.clone_status[key] = {
                    "status": "error",
                    "progress": 0,
                    "error": f"Git operation failed (exit code {process.returncode}): {error_output}"
                }
                
                self.send_notification(
                    "Git Clone Failed",
                    f"Failed to clone {os.path.basename(target_path)}",
                    enable_notifications
                )
                
                # Clean up failed clone
                if os.path.exists(target_dir) and not repo_info:
                    try:
                        shutil.rmtree(target_dir)
                    except:
                        pass
        
        except Exception as e:
            if self.check_interrupt():
                self.clone_status[key] = {"status": "interrupted", "progress": 0, "error": "Clone interrupted by user"}
            else:
                self.clone_status[key] = {
                    "status": "error",
                    "progress": 0,
                    "error": str(e)
                }
                
                self.send_notification(
                    "Git Clone Error",
                    f"Error cloning {target_path}: {str(e)}",
                    enable_notifications
                )

    def clone_queue_manager(self, clone_queue, max_concurrent, enable_notifications, clone_depth, force_update, clone_submodules, hf_token, git_token):
        """Manage clone queue with concurrent limits"""
        active_threads = []
        
        while clone_queue or active_threads:
            if self.check_interrupt():
                clone_queue.clear()
                for thread in active_threads:
                    if thread.is_alive():
                        thread.join(timeout=1.0)
                break
            
            # Clean up completed threads
            active_threads = [t for t in active_threads if t.is_alive()]
            
            # Start new clones
            while len(active_threads) < max_concurrent and clone_queue:
                if self.check_interrupt():
                    break
                
                clone_info = clone_queue.pop(0)
                thread = threading.Thread(
                    target=self.git_clone_worker,
                    args=(clone_info, enable_notifications, clone_depth, force_update, clone_submodules, hf_token, git_token)
                )
                thread.daemon = True
                thread.start()
                active_threads.append(thread)
                self.clone_threads.append(thread)
            
            time.sleep(0.1)

    def get_repository_list(self):
        """Get formatted list of cloned repositories"""
        if not self.clone_history:
            return "No repositories cloned yet."
        
        repo_lines = ["=== CLONED REPOSITORIES ==="]
        
        for target_dir, info in sorted(self.clone_history.items(), key=lambda x: x[1].get('clone_date', ''), reverse=True):
            clone_date = info.get('clone_date', 'Unknown')[:19].replace('T', ' ')
            size_str = self.format_size(info.get('size', 0))
            target_path = info.get('target_path', target_dir)
            branch = info.get('branch', 'default')
            
            repo_info = info.get('repo_info', {})
            status_info = ""
            if repo_info.get('last_commit'):
                status_info = f" | {repo_info['last_commit']}"
            
            repo_lines.append(f"{clone_date} | {target_path} | {branch} | {size_str}{status_info}")
        
        return "\n".join(repo_lines)

    def clone_repositories(self, repositories, auto_clone, max_concurrent_clones, clone_depth,
                          enable_notifications, force_update, clone_submodules, hf_token="", git_token=""):
        """Main function to handle repository cloning"""
        lines = [line.strip() for line in repositories.split('\n') if line.strip()]
        
        if not lines:
            return ("No repositories specified", self.get_repository_list())
        
        # Check git availability
        if not self.is_git_available():
            return ("ERROR: Git is not available on this system. Please install Git to use this node.", 
                   self.get_repository_list())
        
        results = []
        clone_queue = []
        
        # Clear previous status
        self.clone_status.clear()
        
        # Parse all repository lines
        for i, line in enumerate(lines):
            url, target_dir, target_path, branch, error = self.parse_repository_line(line)
            
            if error:
                results.append(f"Line {i+1}: ERROR - {error}")
                continue
            
            # Check current repository status
            repo_info = self.get_repository_info(target_dir)
            repo_name = os.path.basename(target_path)
            
            if repo_info:
                if repo_info["status"] == "git_repo":
                    if force_update:
                        results.append(f"🔄 {repo_name}: Will update existing repository")
                    else:
                        commit_info = f" ({repo_info.get('last_commit', 'unknown')})" if repo_info.get('last_commit') else ""
                        results.append(f"✓ {repo_name}: Already cloned{commit_info}")
                        continue
                elif repo_info["status"] == "not_git":
                    if force_update:
                        results.append(f"⚠ {repo_name}: Will overwrite non-git directory")
                    else:
                        results.append(f"✗ {repo_name}: Directory exists but is not a git repository")
                        continue
                elif repo_info["status"] == "error":
                    results.append(f"⚠ {repo_name}: {repo_info['message']}")
            
            if not auto_clone:
                results.append(f"⏸ {repo_name}: Ready to clone (auto_clone disabled)")
                continue
            
            # Add to clone queue
            key = f"clone_{i}"
            clone_queue.append((url, target_dir, target_path, branch, key))
        
        # Execute clones if auto_clone is enabled
        if auto_clone and clone_queue:
            # Clear interrupt and thread tracking
            self.interrupt_flag.clear()
            self.clone_threads.clear()
            
            # Start queue manager
            queue_thread = threading.Thread(
                target=self.clone_queue_manager,
                args=(clone_queue, max_concurrent_clones, enable_notifications, clone_depth, 
                     force_update, clone_submodules, hf_token, git_token)
            )
            queue_thread.daemon = True
            queue_thread.start()
            
            # Monitor progress
            while queue_thread.is_alive():
                if self.check_interrupt():
                    self.interrupt_clones()
                    break
                
                time.sleep(0.5)
                
                # Show progress
                in_progress = []
                for key, status in self.clone_status.items():
                    if status['status'] in ['cloning', 'updating']:
                        progress = status.get('progress', 0)
                        in_progress.append(f"⬇ {key}: {progress}%")
                
                if in_progress:
                    print(f"Clones in progress: {len(in_progress)}")
            
            queue_thread.join(timeout=2.0)
            
            # Collect results
            for key, status_info in self.clone_status.items():
                clone_num = int(key.split('_')[1])
                line = lines[clone_num]
                url, target_dir, target_path, branch, _ = self.parse_repository_line(line)
                repo_name = os.path.basename(target_path)
                
                if status_info.get("status") == "completed":
                    size_str = self.format_size(status_info.get("size", 0))
                    results.append(f"✓ {repo_name}: Cloned successfully to {target_path} ({size_str})")
                elif status_info.get("status") == "exists":
                    size_str = self.format_size(status_info.get("size", 0))
                    results.append(f"✓ {repo_name}: Repository already exists ({size_str})")
                elif status_info.get("status") == "interrupted":
                    results.append(f"⏸ {repo_name}: Clone interrupted by user")
                elif status_info.get("status") == "error":
                    error_msg = status_info.get("error", "Unknown error")
                    results.append(f"✗ {repo_name}: Clone failed - {error_msg}")
        
        # Save history
        self.save_history()
        
        # Generate summary
        total_repos = len(lines)
        successful = len([r for r in results if r.startswith("✓") and ("Cloned successfully" in r or "updated successfully" in r)])
        existing = len([r for r in results if "Already cloned" in r or "already exists" in r])
        failed = len([r for r in results if r.startswith("✗")])
        interrupted = len([r for r in results if "interrupted" in r])
        
        # Send completion notification
        if auto_clone and successful > 0:
            self.send_notification(
                "Git Clones Complete",
                f"Successfully cloned/updated {successful}/{total_repos} repositories",
                enable_notifications
            )
        
        summary = f"""=== GIT CLONE REPORT ===
Total repositories: {total_repos}
Successfully cloned/updated: {successful}
Already existing: {existing}
Interrupted: {interrupted}
Failed: {failed}
Max concurrent: {max_concurrent_clones}
Clone depth: {'Full history' if clone_depth == 0 else f'{clone_depth} commits'}
Force update: {force_update}
Include submodules: {clone_submodules}

Details:
""" + "\n".join(results)
        
        return (summary, self.get_repository_list())

# Node registration
NODE_CLASS_MAPPINGS = {
    "GitCloneManager": GitCloneManager
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "GitCloneManager": "🔧 Git Repository Clone Manager"
}