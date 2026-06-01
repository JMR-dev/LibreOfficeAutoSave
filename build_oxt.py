import os
import zipfile
import shutil

def build_oxt():
    build_dir = "build"
    dist_dir = "dist"
    oxt_name = "AutoSave.oxt"

    # Clean previous builds
    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)
    if not os.path.exists(dist_dir):
        os.makedirs(dist_dir)

    # Copy source files to build directory
    shutil.copytree("src", build_dir)

    # Create the .oxt file (which is a zip archive)
    oxt_path = os.path.join(dist_dir, oxt_name)
    with zipfile.ZipFile(oxt_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(build_dir):
            for file in files:
                file_path = os.path.join(root, file)
                # The archive root should be the contents of the 'build' dir
                arcname = os.path.relpath(file_path, build_dir).replace("\\", "/")
                zipf.write(file_path, arcname)

    print(f"Successfully built extension: {oxt_path}")

if __name__ == "__main__":
    build_oxt()
