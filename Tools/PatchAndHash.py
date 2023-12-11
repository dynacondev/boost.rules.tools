import os
import sys
import subprocess
import json

import utils


def patch_and_hash(registry_dir):
    boost_lib_dirs = utils.find_boost_lib_dirs(os.path.join(registry_dir, "modules"))
    boost_libs_newest_dirs = utils.find_boost_lib_newest_dirs(boost_lib_dirs)

    patch_file_name = "patch.diff"

    for lib in boost_lib_dirs:
        patches_folder = os.path.join(
            utils.find_matching_path(
                boost_libs_newest_dirs,
                os.path.basename(lib)
                + os.path.sep,  # Adding the separator after makes sure we don't match only the start of a segment of path
            ),
            "patches",
        )
        lib_source = utils.find_boost_sources([lib])[:1]

        if lib_source:  # Check if lib_source is not empty
            lib_source = lib_source[0]
        else:
            continue

        # Check the status to see if there are any changes
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=lib_source,
            stdout=subprocess.PIPE,
            text=True,
        )

        # If result.stdout is not empty, there are changes to be added
        if result.stdout.strip():
            # Add all files to the staging area
            print("Adding files in:", os.path.basename(lib))
            subprocess.run(["git", "add", "."], cwd=lib_source)
        else:
            # No files to be added
            print("No files to add in:", os.path.basename(lib))

        diff_file = os.path.join(patches_folder, patch_file_name)

        # Create and write the git diff
        diff = subprocess.check_output(["git", "diff", "--cached"], cwd=lib_source)
        with open(diff_file, "wb") as f:
            f.write(diff)

        # Calculate SHA256 hash of 'patch.diff' and encode in base64
        integrity_result = subprocess.run(
            f"openssl dgst -sha256 -binary '{diff_file}' | openssl base64 -A",
            shell=True,
            capture_output=True,
            text=True,
        )
        integrity = "sha256-" + integrity_result.stdout.strip()

        print(f"Calculated hash: {integrity}")

        # Update 'source.json' with the new patch information
        source_json_path = os.path.join(os.path.dirname(patches_folder), "source.json")

        with open(source_json_path, "r") as f:
            data = json.load(f)

        data["patches"] = {patch_file_name: integrity}

        with open(source_json_path, "w") as f:
            json.dump(data, f, indent=2)

    # If changes have been made:
    # List all changed files, ask for confirmation?
    # If according to temp text we don't have a new version folder, generate one
    # In newest version folder:
    # Generate patch with added files
    # Calculate hash and add to source.json


# Usage
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(
            "Usage: python PatchAndHash.py <registry_folder>  Optional: <BaseGitCommitHash>"
        )
        sys.exit(1)

    patch_and_hash(sys.argv[1])
