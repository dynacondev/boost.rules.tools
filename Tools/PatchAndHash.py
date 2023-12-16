import os
import shutil
import sys
import subprocess
import json

import utils

# Step 1, stage changes, record which modules have changed
# Step 2, bump relevant versions, noting which are already bumped
# Step 3, calc hashes etc


def get_commit_before_oldest_local_only(remote_branch="origin/main"):
    # Fetch the latest information from the remote
    subprocess.run(["git", "fetch"])

    # Get all local-only commits
    result = subprocess.run(
        ["git", "log", "--oneline", f"{remote_branch}..HEAD"],
        stdout=subprocess.PIPE,
        text=True,
    )

    commits = result.stdout.strip().split("\n")
    if len(commits) > 1:
        # Get the hash of the second-to-last commit (oldest local-only)
        oldest_local_only = commits[-1].split()[0]

        # Get the commit before the oldest local-only commit
        result = subprocess.run(
            ["git", "log", "--oneline", "-1", f"{oldest_local_only}^"],
            stdout=subprocess.PIPE,
            text=True,
        )

        return result.stdout.strip().split()[0]  # Return the hash of the commit
    else:
        # If there are no local-only commits, return the latest commit
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], stdout=subprocess.PIPE, text=True
        )
        return result.stdout.strip()


def detect_changed_modules(registry_dir, base_commit_hash):
    boost_lib_dirs = utils.find_boost_lib_dirs(os.path.join(registry_dir, "modules"))
    modified_modules = []

    def check_and_add(path):
        # Check if the trimmed path starts with "modules" + os.sep #TODO HERE!
        if path.startswith("modules" + os.sep):
            # Split the path by os.sep and extract the second segment
            segments = path.split(os.sep)
            if len(segments) >= 2:
                second_segment = segments[1]
                if second_segment not in modified_modules:
                    modified_modules.append(second_segment)

    # Run git status with porcelain flag
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=registry_dir,
        stdout=subprocess.PIPE,
        text=True,
    )

    for line in result.stdout.splitlines():
        if line.startswith("??") or line.startswith(" M"):
            # Strip the git status characters and leading spaces
            trimmed_path = line[3:].strip().strip('"')
            check_and_add(trimmed_path)

    # Run git diff between the commit hash and HEAD
    result = subprocess.run(
        ["git", "diff", "--name-only", base_commit_hash],
        cwd=registry_dir,
        stdout=subprocess.PIPE,
        text=True,
    )

    # Parse the output
    for file_path in result.stdout.strip().split("\n"):
        check_and_add(file_path)

    # First, create a list of joined paths
    modified_module_dirs = [
        os.path.join(registry_dir, "modules", segment) for segment in modified_modules
    ]

    # Then, filter this list based on whether each path is in boost_lib_dirs
    modified_module_dirs = [
        dir_path for dir_path in modified_module_dirs if dir_path in boost_lib_dirs
    ]

    return modified_module_dirs


def detect_not_bumped(registry_dir, changed_modules, base_commit_hash):
    awaiting_bump = []
    for module_dir in changed_modules:
        folders = []
        result = subprocess.run(
            [
                "git",
                "ls-tree",
                base_commit_hash,
                module_dir + os.sep,
            ],
            stdout=subprocess.PIPE,
            text=True,
            cwd=registry_dir,
        )

        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) > 1 and parts[1] == "tree":  # 'tree' indicates a folder
                folder_name = parts[3]
                folders.append(os.path.join(registry_dir, folder_name))

        if len(folders) != 0 and (
            utils.find_newest_version_from_paths(folders)
            is not utils.find_boost_lib_newest_dirs(module_dir)
        ):
            awaiting_bump.append(module_dir)

    return awaiting_bump


def bump_versions(modules_to_bump):
    pass


def detect_changed_sources(registry_dir):
    boost_lib_dirs = utils.find_boost_lib_dirs(os.path.join(registry_dir, "modules"))
    changed_modules = []

    for lib in boost_lib_dirs:
        lib_source = utils.find_boost_sources([lib])[:1]

        if lib_source:  # Check if lib_source is not empty
            lib_source = lib_source[0]
        else:
            # print("No source found for:", os.path.basename(lib)) # TODO debug at info level
            continue

        # Check the status to see if there are any changes that aren't staged
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=lib_source,
            stdout=subprocess.PIPE,
            text=True,
        )

        unstaged_changes = []
        for line in result.stdout.splitlines():
            status_code = line[:2]

            # Check for untracked (??) and modified but not staged ( M)
            if status_code != "A ":
                file_path = line[3:]
                unstaged_changes.append(file_path)

        if unstaged_changes:
            changed_modules.append(lib)

    return changed_modules


def patch_and_hash(registry_dir, updated_modules):
    boost_libs_newest_dirs = utils.find_boost_lib_newest_dirs(updated_modules)
    patch_file_name = "patch.diff"

    for lib in updated_modules:
        newest_version = utils.find_matching_path(
            boost_libs_newest_dirs,
            os.path.basename(lib)
            + os.path.sep,  # Adding the separator after makes sure we don't match only the start of a segment of path
        )
        patches_folder = os.path.join(
            newest_version,
            "patches",
        )
        diff_file = os.path.join(patches_folder, patch_file_name)
        lib_source = utils.find_boost_sources([lib])[:1][0]

        print("Adding files in:", os.path.basename(lib))
        subprocess.run(["git", "add", "."], cwd=lib_source)

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

        # Copy the MODULE.bazel file to the version folder
        src = os.path.join(lib_source, "MODULE.bazel")
        dst = os.path.join(newest_version, os.path.basename(src))
        shutil.copy(src, dst)


# Usage
if __name__ == "__main__":
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print(
            "Usage: python PatchAndHash.py <registry_folder> (Optional:) <base_git_commit_hash>"
        )
        sys.exit(1)

    registry_folder = sys.argv[1]
    if len(sys.argv) == 3:
        base_git_commit_hash = sys.argv[2]
        print(f"Base git commit hash: {base_git_commit_hash}")
    else:
        base_git_commit_hash = get_commit_before_oldest_local_only()
        print(
            f"Base git commit hash (Commit immediately before all local commits): {base_git_commit_hash}"
        )

    # Detect changed modules since commit
    updated_modules = detect_changed_modules(registry_folder, base_git_commit_hash)

    # Detect modules that haven't been bumped & need to be
    bump_modules = detect_not_bumped(
        registry_folder, updated_modules, base_git_commit_hash
    )

    # If there are modules to bump, ask user if they want to continue
    if bump_modules:
        bumped_module_names = [os.path.basename(module) for module in bump_modules]
        bumped_module_names = "\n".join(bumped_module_names)
        print(
            f"The following modules need to be version bumped:\n{bumped_module_names}\n"
        )
        response = input("Are you sure you want to continue? (y/n): ")
        if response.lower() in ["y", "yes"]:
            bump_versions(bump_modules)
        else:
            print("Version bump cancelled.")
            sys.exit(0)

    source_updated_modules = detect_changed_sources(registry_folder)

    # If there are modules to patch & hash, ask user if they want to continue
    if source_updated_modules:
        updated_module_names = [
            os.path.basename(module) for module in source_updated_modules
        ]
        updated_module_names = "\n".join(updated_module_names)
        print(
            f"The following modules will have their patches updated and hashed:\n{updated_module_names}\n"
        )
        response = input("Are you sure you want to continue? (y/n): ")
        if response.lower() in ["y", "yes"]:
            patch_and_hash(sys.argv[1], source_updated_modules)
        else:
            print("Patch & Hash cancelled.")
            sys.exit(0)

    # If there are no modules to bump or update, exit
    if not bump_modules and not source_updated_modules:
        print("No modules have updates or need to be bumped.")
        sys.exit(0)
