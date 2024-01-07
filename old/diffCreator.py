import os
import sys
import json
import shutil
import requests
import tarfile
import subprocess
from pathlib import Path


def copy_directory(src, dst):
    """
    Recursively copies files from src to dst directory,
    creating subdirectories if necessary.
    """
    copied_paths = []

    if not dst.exists():
        dst.mkdir(parents=True)
    for item in src.iterdir():
        dest_path = dst / item.name
        if item.is_dir():
            copy_directory(item, dest_path)
        else:
            shutil.copy2(item, dest_path)
            dest_item = dest_path / item.name
            copied_paths.append(dest_item)
    return copied_paths


def main(folder_path):
    # Step 1: Path validation (Assuming folder_path is passed correctly)
    folder = Path(folder_path)
    if not folder.is_dir():
        raise ValueError(f"The path {folder_path} is not a valid directory")

    # Step 2: Create "patches" folder
    patches_folder = folder / "1.83.0.bzl.1" / "patches"
    patches_folder.mkdir(parents=True, exist_ok=True)

    # Step 3: Parse source.json
    with open(folder / "1.83.0.bzl.1" / "source.json", "r") as f:
        source_data = json.load(f)
    url = source_data["url"]

    # Step 4: Create "diffed_sources" folder
    diffed_sources_folder = folder / "diffed_sources"
    diffed_sources_folder.mkdir(parents=True, exist_ok=True)

    # Step 5: Download and extract the URL
    # response = requests.get(url)
    # tar_path = diffed_sources_folder / "downloaded.tar.gz"
    # with open(tar_path, "wb") as f:
    #     f.write(response.content)
    # with tarfile.open(tar_path, "r:gz") as tar:
    #     tar.extractall(path=diffed_sources_folder) # TODO RE-ADD THIS!

    # Find the first directory inside 'diffed_sources_folder'
    first_directory_inside_diffed_sources = None
    for item in diffed_sources_folder.iterdir():
        if item.is_dir():
            first_directory_inside_diffed_sources = item
            break

    if first_directory_inside_diffed_sources is None:
        raise Exception("No directory found inside 'diffed_sources'")

    # Keep track of copied files and directories
    copied_paths = []

    # Assuming folder and first_directory_inside_diffed_sources are defined
    # Step 6: Copy files and directories
    source_folder = folder / "1.83.0.bzl.1"
    copied_paths = []
    for item in source_folder.iterdir():
        if item.name != "source.json" and item.name != "patches":
            dest_path = first_directory_inside_diffed_sources / item.name
            if item.is_file():
                copied_paths.append(dest_path)
                shutil.copy2(item, dest_path)  # Use copy2 to preserve metadata
            elif item.is_dir():
                copied_paths += copy_directory(
                    item, dest_path
                )  # Use the custom function for directories

    # Step 7: Create git diff
    subprocess.run(["git", "init"], cwd=first_directory_inside_diffed_sources)

    # Convert copied paths to relative paths and add them to the staging area
    for path in copied_paths:
        relative_path = path.relative_to(first_directory_inside_diffed_sources)
        subprocess.run(
            ["git", "add", str(relative_path)],
            cwd=first_directory_inside_diffed_sources,
        )

    # Create and write the git diff
    diff_command = ["git", "diff", "--cached"]
    diff = subprocess.check_output(
        diff_command, cwd=first_directory_inside_diffed_sources
    )
    with open(patches_folder / "patch.diff", "wb") as f:
        f.write(diff)

    # Calculate SHA256 hash of 'patch.diff' and encode in base64
    patch_diff_path = patches_folder / "patch.diff"
    integrity_cmd = (
        f"openssl dgst -sha256 -binary {patch_diff_path} | openssl base64 -A"
    )
    integrity_result = subprocess.run(
        integrity_cmd, shell=True, capture_output=True, text=True
    )
    integrity = "sha256-" + integrity_result.stdout.strip()

    print(f"Calculated hash: {integrity}")

    # Update 'source.json' with the new patch information
    source_json_path = folder / "1.83.0.bzl.1" / "source.json"
    with open(source_json_path, "r") as f:
        data = json.load(f)

    data["patches"] = {"patch.diff": integrity}

    with open(source_json_path, "w") as f:
        json.dump(data, f, indent=2)


if __name__ == "__main__":
    main(sys.argv[1])
