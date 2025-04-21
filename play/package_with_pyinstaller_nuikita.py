"""
Build script for Nuitka packaging of MAME Controls
with dependencies folder inside the preview directory
"""

import os
import subprocess
import shutil
import sys

def main():
    print("Starting Nuitka packaging for MAME Controls...")

    # Paths
    main_script = "mame_controls_main.py"
    icon_path = "mame.ico"

    # Output folders - with dependencies in preview folder
    build_dir = "build"
    mame_dir = "dist"                            # Top level MAME directory
    preview_dir = os.path.join(mame_dir, "preview")  # preview subdirectory
    settings_dir = os.path.join(preview_dir, "settings", "info")
    dist_folder = "MAME_Controls.dist"           # Nuitka dependencies folder name
    preview_dist = os.path.join(preview_dir, dist_folder)  # dependencies inside preview

    # Create the output directories
    os.makedirs(settings_dir, exist_ok=True)
    
    # Basic Nuitka command - using minimal options to avoid plugin errors
    cmd = [
        sys.executable,
        "-m", "nuitka",
        "--standalone",
        "--output-dir=build",
        "--output-filename=MAME_Controls",
    ]
    
    # Add icon if it exists
    if os.path.isfile(icon_path):
        cmd.append(f"--windows-icon-from-ico={icon_path}")

    # Add window mode on Windows
    if sys.platform == 'win32':
        cmd.append("--windows-disable-console")
        
    # Add main script
    cmd.append(main_script)

    # Run the build command
    print("Running Nuitka build command:")
    print(" ".join(cmd))
    
    try:
        subprocess.run(cmd, check=True)
        
        # The executable itself
        exe_name = "MAME_Controls.exe" if sys.platform == 'win32' else "MAME_Controls"
        exe_path = os.path.join(build_dir, exe_name)
        
        # The distribution folder with all dependencies
        dist_path = os.path.join(build_dir, dist_folder)
        
        if not os.path.exists(exe_path):
            print(f"Error: Executable not found at {exe_path}")
            files = os.listdir(build_dir) if os.path.exists(build_dir) else []
            print(f"Files in build directory: {files}")
            return
            
        if not os.path.exists(dist_path):
            print(f"Error: Distribution folder not found at {dist_path}")
            return
            
        # Copy the distribution folder to inside the preview directory
        print(f"Copying distribution folder to {preview_dist}...")
        
        # Remove existing dist folder if it exists
        if os.path.exists(preview_dist):
            shutil.rmtree(preview_dist)
            
        # Copy the distribution folder
        shutil.copytree(dist_path, preview_dist)
        
        # Copy just the executable to the preview folder
        preview_exe = os.path.join(preview_dir, exe_name)
        print(f"Copying executable to {preview_exe}...")
        shutil.copy2(exe_path, preview_exe)
        
        # Create an empty settings file for compatibility
        settings_file = os.path.join(settings_dir, "settings.json") 
        if not os.path.exists(settings_file):
            with open(settings_file, 'w') as f:
                f.write("{}")
            print(f"Created empty settings file at {settings_file}")
        
        print("\nBuild Complete!")
        print(f"Directory structure created:")
        print(f"  {mame_dir}/")
        print(f"  └── preview/")
        print(f"      ├── {exe_name}")
        print(f"      ├── settings/info/settings.json")
        print(f"      └── {dist_folder}/")
        
    except subprocess.CalledProcessError as e:
        print(f"Error running Nuitka: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()