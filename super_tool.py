import os
import sys
import subprocess
import threading
from queue import Queue
import json
import shutil
import requests
import tarfile
import logging
import time
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.styles import Style
from prompt_toolkit.shortcuts import (
    radiolist_dialog,
    checkboxlist_dialog,
    input_dialog,
    message_dialog,
    button_dialog,
    ProgressBar,
)

module_source_file_name = "source.json"


def main(registry_dir):
    # Important Variables
    last_command_status = None
    modules_dir = os.path.join(registry_dir, "modules")
    boost_lib_dirs = find_boost_lib_dirs(modules_dir)
    boost_lib_newest_version_dirs = find_boost_lib_newest_dirs(boost_lib_dirs)
    boost_source_dirs = find_boost_source_dirs(boost_lib_newest_version_dirs)

    # Setup logging
    logger = logging.getLogger("boost")  # Create a named logger
    logger.setLevel(logging.DEBUG)  # Set the logging level
    handler = logging.StreamHandler()  # Create a handler that outputs to the console
    handler.setFormatter(
        logging.Formatter("%(levelname)s: %(message)s")
    )  # Set the format for the handler
    logger.addHandler(handler)  # Add the handler to the logger
    logging.basicConfig(
        level=logging.INFO
    )  # Set the logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    # Main Menu loop
    while True:
        if last_command_status:
            menu_text = HTML(
                f"<ansired><b>Last Command Status: {last_command_status}</b></ansired>\n\nPlease select an option:"
            )
        else:
            menu_text = "Welcome to the super_tool! Please select an option:"

        menu_selection = radiolist_dialog(
            title="Main Menu",
            text=menu_text,
            values=[
                ("setup_registry", "Set up your Registry for Boost Module Maintenance"),
                ("patch_generator", "Generate Patches from Changes"),
                ("moduleBump", "Version Bump a Module"),
                ("boostBump", "Bump Boost Version (All Modules)"),
                ("clean", "Restore Clean Registry State (Not required to git commit)"),
            ],
            ok_text="Confirm",
            cancel_text="Exit",
            style=get_custom_style(),
        ).run()

        if menu_selection == "setup_registry":
            # Download all sources
            print("Downloading sources...")
            run_multithreaded_tasks(
                boost_lib_newest_version_dirs,
                download_source,
                num_threads=8,
                task_name="Downloading",
            )

            # Initialise git repos in each source so we can track changes
            print("Initializing source folders...")
            run_multithreaded_tasks(
                boost_source_dirs,
                initialize_repo,
                8,
                "Initializing",
                boost_lib_newest_version_dirs,
            )

            # Set the local git exclude file so that all diffed_sources folders are ignored
            print("Setting git exclude file...")
            set_git_exclude(registry_dir)

            last_command_status = "Registry initialization Success"
            print("Registry initialization complete!")

        elif menu_selection == "patch_generator":
            # Get the base commit to track changes from
            print("Getting base commit...")
            base_git_commit_hash = get_base_commit(registry_dir)

            # Detect changed sources since commit
            print("Detecting changed sources...")
            updated_sources = detect_changed_sources(boost_source_dirs)

            # Bump modules needing version bump (also patches them)
            print("Checking for modules needing bumping...")
            bumped_modules = bump_modules(
                registry_dir, base_git_commit_hash, updated_sources
            )

            # Remove bumped sources as they get patched in bumping
            for module in bumped_modules:
                updated_sources.remove(module)

            # Patch modules needing patches
            if updated_sources:
                print("Patching modules...")
                patch_and_hash(registry_dir, updated_sources)

            last_command_status = "Patching Complete"

        elif menu_selection == "moduleBump":
            last_command_status = "Module bumping isn't implemented yet. Sorry!"

        elif menu_selection == "boostBump":
            last_command_status = "Boost version bumping isn't implemented yet. Sorry!"

        elif menu_selection == "clean":
            print("Deleting files...")
            tidy_up(boost_lib_dirs)
            last_command_status = "Clean Complete"

        else:
            break


def download_source(boost_lib_newest_version):
    lib = os.path.dirname(boost_lib_newest_version)
    diffed_sources_dir = os.path.join(lib, "diffed_sources")
    tar_path = os.path.join(diffed_sources_dir, "downloaded.tar.gz")
    source_path = None

    # Create "diffed_sources" folder if it doesn't exist
    if not os.path.exists(diffed_sources_dir):
        os.makedirs(diffed_sources_dir)

    # Get some details from sourceck.json
    with open(
        os.path.join(boost_lib_newest_version, module_source_file_name), "r"
    ) as source_json_file:
        file = json.load(source_json_file)

        # Assume the source path based on the stripped prefix
        source_path = os.path.join(diffed_sources_dir, file.get("strip_prefix", ""))

        # Download the archive if needed
        if not os.path.exists(tar_path):
            url = file.get("url")
            response = requests.get(url)
            with open(tar_path, "wb") as f:
                f.write(response.content)

    # Extract the folder if it hasn't yet been extracted
    if source_path and not os.path.exists(source_path):
        with tarfile.open(tar_path, "r:gz") as tar:
            tar.extractall(path=diffed_sources_dir)


def initialize_repo(boost_source, boost_libs_newest_dirs):
    # Check if the .git directory exists
    if not os.path.exists(os.path.join(boost_source, ".git")):
        try:
            # Initialize the git repository, suppressing stdout and capturing stderr
            result = subprocess.run(
                ["git", "init", "-b", "main"],
                cwd=boost_source,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            if result.stderr:
                logging.error(
                    f"Error initializing repository: {result.stderr.decode()}"
                )

            # Add all files to the staging area
            result = subprocess.run(
                ["git", "add", "."],
                cwd=boost_source,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,  # Suppress some annoying "CRLF will be replaced by LF" warnings
            )
            if result.stderr:
                logging.error(f"Error adding files: {result.stderr.decode()}")

            # Commit the changes
            result = subprocess.run(
                [
                    "git",
                    "commit",
                    "--no-gpg-sign",
                    "-m",
                    "Initial commit",
                ],  # GPG has resource contention with multithreading and isn't needed here anyway
                cwd=boost_source,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            if result.stderr:
                logging.error(f"Error committing files: {result.stderr.decode()}")

            # Construct the patch file path
            patches_path = os.path.join(
                find_matching_path(
                    boost_libs_newest_dirs,
                    os.path.basename(os.path.dirname(os.path.dirname(boost_source)))
                    + os.path.sep,  # Adding the trailing separator makes sure we don't match only the start of a segment of path
                ),
                "patches",
                "patch.diff",
            )

            result = subprocess.run(
                ["git", "apply", "--whitespace=nowarn", patches_path],
                cwd=boost_source,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            if result.stderr:
                logging.error(f"Error applying patches: {result.stderr.decode()}")

        except subprocess.CalledProcessError as e:
            logging.error(f"An error occurred: {e}")


def set_git_exclude(registry_dir):
    git_info_dir = os.path.join(registry_dir, ".git", "info")
    exclude_file_path = os.path.join(git_info_dir, "exclude")
    exclude_pattern = "diffed_sources/"

    # Ensure the .git/info directory exists
    if not os.path.exists(git_info_dir):
        os.makedirs(git_info_dir)

    # Create the exclude file if it does not exist
    if not os.path.isfile(exclude_file_path):
        open(exclude_file_path, "w").close()

    # Read the current contents of the file
    with open(exclude_file_path, "r") as file:
        lines = file.readlines()

    # Check if the pattern already exists in the file
    if any(exclude_pattern in line for line in lines):
        logging.info(f"'{exclude_pattern}' already exists in exclude file.")
    else:
        # Append the pattern to the file
        with open(exclude_file_path, "a") as file:
            file.write(f"\n{exclude_pattern}\n")


def patch_generator(registry_dir):
    page_title = "Module Patch Generator"

    # base_commit_choice = button_dialog(
    #     title=page_title,
    #     text="Using commit "
    #     + base_git_commit_hash
    #     + " as base. Changes will be calculated since then.",
    #     buttons=[
    #         ("Confirm", True),
    #         ("Change Commit", False),
    #     ],
    #     style=get_custom_style(),
    # ).run()

    # if not base_commit_choice:
    #     base_git_commit_hash = input_dialog(
    #         title=page_title,
    #         text="Please enter the commit hash to use as base:",
    #         style=get_custom_style(),
    #     ).run()

    # # Detect changed modules since commit
    # updated_modules = detect_changed_modules(registry_dir, base_git_commit_hash)

    # Detect modules that haven't been bumped & need to be
    bump_modules = detect_not_bumped(
        registry_dir, updated_modules, base_git_commit_hash
    )

    # If there are modules to bump, ask user if they want to continue
    if bump_modules:  # TODO Also add in transitive bumps!
        choice = radiolist_dialog(
            title=page_title,
            text="The following modules have been changed and need a version bump:",
            values=[os.path.basename(module) for module in bump_modules],
            ok_text="Bump Versions",
            cancel_text="Cancel",
            style=get_custom_style(),
        ).run()

        if choice:
            # bump_versions(bump_modules) # TODO
            print(choice)

        # TODO only patch ones that have been bumped

        # Detect what modules have changes
        source_updated_modules = detect_changed_sources(modules_dir)

        if source_updated_modules:
            choice = radiolist_dialog(
                title=page_title,
                text="The following modules will have their patches updated and hashed:",
                values=[os.path.basename(module) for module in source_updated_modules],
                ok_text="Update Patches",
                cancel_text="Cancel",
                style=get_custom_style(),
            ).run()
            if choice:
                patch_and_hash(registry_dir, source_updated_modules)
        else:  # No changes
            # TODO inform of no changes
            pass

    # if confirm:
    #     text = input_dialog(title="Enter Text", text="Please enter some text:").run()
    #     message_dialog(title="Entered Text", text=f"You entered: {text}").run()
    # else:
    #     message_dialog(title="Cancelled", text="Operation cancelled.").run()

    if choice:
        pass


def get_base_commit(
    registry_dir,
    upstream_remote="upstream",
    upstream_branch="main",
    local_branch="HEAD",
):
    # Check if the 'upstream' remote exists, add it if not
    result = subprocess.run(
        ["git", "remote"],
        cwd=registry_dir,
        stdout=subprocess.PIPE,
        text=True,
    )

    if "upstream" not in result.stdout.strip().split("\n"):
        subprocess.run(
            ["git", "remote", "add", "upstream", "https://github.com/bazelbuild/bazel-central-registry"],
            cwd=registry_dir,
        )

    # Fetch the latest information from the upstream
    subprocess.run(
        ["git", "fetch", upstream_remote, upstream_branch],
        cwd=registry_dir,
    )

    # Find the last commit upstream that we based our changes on
    base_git_commit_hash = find_git_divergence(
        registry_dir, upstream_remote, upstream_branch, local_branch
    )

    if base_git_commit_hash:
        # Get the commit details for display to user
        commit_details = ""
        for key, value in get_commit_details(
            registry_dir, base_git_commit_hash
        ).items():
            commit_details += f"{key}: {value}\n"
    else:
        base_git_commit_hash = "** No Commit Found **"

    # Display confirmation dialogue
    alternate_commit = input_dialog(
        title="Verify Base Commit",
        text=f"We detected {base_git_commit_hash} as the most recent commit in the registry prior to your changes. If you'd like to track changes that occurred after another commit, please enter it below.\n\nCommit {base_git_commit_hash}:\n{commit_details}",
        style=get_custom_style(),
    ).run()

    if alternate_commit:
        base_git_commit_hash = alternate_commit

    return base_git_commit_hash


def find_git_divergence(
    registry_dir,
    upstream_remote="upstream",
    upstream_branch="main",
    local_branch="HEAD",
):
    # Get upstream commits
    result = subprocess.run(
        [
            "git",
            "log",
            "--oneline",
            f"{upstream_remote}/{upstream_branch}",
        ],
        cwd=registry_dir,
        stdout=subprocess.PIPE,
        text=True,
    )
    upstream_commits = [
        commit.split(" ")[0] for commit in result.stdout.strip().split("\n")
    ]

    # Get local commits
    result = subprocess.run(
        [
            "git",
            "log",
            "--oneline",
            f"{upstream_remote}/{upstream_branch}..{local_branch}",
        ],
        cwd=registry_dir,
        stdout=subprocess.PIPE,
        text=True,
    )
    local_commits = [
        commit.split(" ")[0] for commit in result.stdout.strip().split("\n")
    ]

    # Scenario 1: Most recent commit in main(upstream) with a parent from your branch
    for commit in upstream_commits:
        commit_hash = commit.split()[0]
        parents = (
            subprocess.run(
                ["git", "log", "--pretty=%p", "-n", "1", commit_hash],
                cwd=registry_dir,
                stdout=subprocess.PIPE,
                text=True,
            )
            .stdout.strip()
            .split()
        )
        for parent in parents:
            if parent in local_commits:
                return commit_hash

    # Scenario 2: Oldest commit of your local branch with a parent in main(upstream)
    for commit in reversed(local_commits):  # Start from the oldest
        commit_hash = commit.split()[0]
        parents = (
            subprocess.run(
                ["git", "log", "--pretty=%p", "-n", "1", commit_hash],
                cwd=registry_dir,
                stdout=subprocess.PIPE,
                text=True,
            )
            .stdout.strip()
            .split()
        )
        for parent in parents:
            if parent in upstream_commits:
                return parent


def get_commit_details(registry_dir, commit_hash):
    commands = {
        "Author": ["git", "show", "-s", "--format=%an", commit_hash],
        "Date": ["git", "show", "-s", "--format=%ad", commit_hash],
        "Message": ["git", "show", "-s", "--format=%B", commit_hash],
    }
    details = {}
    for key, command in commands.items():
        result = subprocess.run(
            command,
            cwd=registry_dir,
            stdout=subprocess.PIPE,
            text=True,
        )
        details[key] = result.stdout.strip()
    return details


def detect_changed_sources(boost_source_dirs):
    changed_sources = []

    for source in boost_source_dirs:
        # Check the status to see if there are any changes that aren't staged
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=source,
            stdout=subprocess.PIPE,
            text=True,
        )

        unstaged_changes = []
        for line in result.stdout.splitlines():
            status_code = line[:2]

            if status_code != "A " and not (
                status_code == "M " and line.endswith(".gitignore")
            ):
                file_path = line[3:]
                unstaged_changes.append(file_path)

        if unstaged_changes:
            changed_sources.append(source)

    return changed_sources


def bump_modules(registry_dir, base_git_commit_hash, updated_sources):
    awaiting_bump = []
    updated_modules = [
        os.path.join(registry_dir, os.path.basename(source))
        for source in updated_sources
    ]

    for module_dir in updated_modules:
        folders = []

        result = subprocess.run(
            [
                "git",
                "ls-tree",
                base_git_commit_hash,
                module_dir + os.sep,
            ],
            cwd=registry_dir,
            stdout=subprocess.PIPE,
            text=True,
        )

        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) > 1 and parts[1] == "tree":  # 'tree' indicates a folder
                folder_name = parts[3]
                folders.append(os.path.join(registry_dir, folder_name))

        if len(folders) != 0 and (
            find_newest_version_from_paths(folders)
            not in find_boost_lib_newest_dirs(module_dir)
        ):
            awaiting_bump.append(module_dir)

    results_array = None
    if awaiting_bump:
        # Display confirmation dialogue
        results_array = checkboxlist_dialog(
            title="Bump Modules",
            text="These modules need a version bump! Please select which modules you'd like to bump:",
            values=awaiting_bump,
            style=get_custom_style(),
        ).run()

    patched_sources = []
    if results_array:
        # TODO bump modules
        # awaiting_bump = [
        #     ("eggs", "Eggs"),
        #     ("bacon", "Bacon"),
        #     ("croissants", "20 Croissants"),
        #     ("daily", "The breakfast of the day"),
        # ]
        patched_sources = [
            updated_sources.substring(source) for source in results_array
        ]
        patch_and_hash(registry_dir, patched_sources)

    return patched_sources


def patch_and_hash(registry_dir, lib_sources):
    patch_file_name = "patch.diff"

    def task(lib_source, registry_dir):
        module_dir = os.path.join(
            registry_dir, os.path.dirname(os.path.dirname(lib_source))
        )
        newest_version = find_boost_lib_newest_dirs([module_dir])[0]
        patches_folder = os.path.join(
            newest_version,
            "patches",
        )
        diff_file = os.path.join(patches_folder, patch_file_name)

        subprocess.run(
            ["git", "add", "."],
            cwd=lib_source,
        )

        # Create and write the git diff
        diff = subprocess.check_output(
            ["git", "diff", "--cached"],
            cwd=lib_source,
        )
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

        # Update module_source_file_name with the new patch information
        source_json_path = os.path.join(
            os.path.dirname(patches_folder), module_source_file_name
        )

        with open(source_json_path, "r") as f:
            data = json.load(f)

        data["patches"] = {patch_file_name: integrity}

        with open(source_json_path, "w") as f:
            json.dump(data, f, indent=2)

        # Copy the MODULE.bazel file to the version folder
        src = os.path.join(lib_source, "MODULE.bazel")
        dst = os.path.join(newest_version, os.path.basename(src))
        shutil.copy(src, dst)

    run_multithreaded_tasks(
        lib_sources,
        task,
        4,
        "Patching",
        registry_dir,
    )


def tidy_up(boost_lib_dirs):
    # TODO Ensure everything is patch created etc, warn and stop if changes will be lost

    with ProgressBar() as pb:
        for lib in pb(boost_lib_dirs):
            diffed_sources_dir = os.path.join(lib, "diffed_sources")
            pb.title = HTML(f"<ansiblue>Removing {diffed_sources_dir}</ansiblue>")
            if os.path.exists(diffed_sources_dir):
                shutil.rmtree(diffed_sources_dir)


def find_boost_lib_dirs(modules_dir):
    #  TODO Ignore libs that don't have a diffed_sources folder but warn about it
    boost_lib_dirs = []
    ignore_list = [
        "boost.rules.tools",
        "boost",
    ]

    for module in os.listdir(modules_dir):
        if module in ignore_list:
            continue  # Skip the modules that are in the ignore list

        module_path = os.path.join(modules_dir, module)

        # Check if the item is a directory starting with "boost"
        if os.path.isdir(module_path) and module.startswith("boost."):
            boost_lib_dirs.append(module_path)
            logging.debug(f"Found Boost lib: {module}")

    boost_lib_dirs.sort()

    return boost_lib_dirs


def find_boost_source_dirs(boost_lib_newest_version_dirs):
    boost_source_dirs = []

    for lib_version in boost_lib_newest_version_dirs:
        try:
            # Open module_source_file_name and get the strip_prefix value
            with open(
                os.path.join(lib_version, module_source_file_name), "r"
            ) as source_json_file:
                source_json = json.load(source_json_file)
                strip_prefix = source_json.get("strip_prefix", "")

            # Construct and add the source directory path
            boost_source_dirs.append(
                os.path.join(
                    os.path.dirname(lib_version), "diffed_sources", strip_prefix
                )
            )

        except (IOError, json.JSONDecodeError) as e:
            logging.error(
                f"Error reading {module_source_file_name} for {lib_version}: {e}"
            )

    return boost_source_dirs


def find_boost_lib_newest_dirs(boost_lib_dirs):
    boost_libs_newest_dirs = []

    for lib in boost_lib_dirs:
        newest = find_newest_version_from_paths(
            [os.path.join(lib, path) for path in os.listdir(lib)]
        )
        if newest:
            boost_libs_newest_dirs.append(newest)

    return boost_libs_newest_dirs


def find_newest_version_from_paths(paths):
    found_versions = []

    # Find all directories starting with "1."
    for version in paths:
        if os.path.isdir(version) and os.path.basename(version).startswith("1."):
            found_versions.append(version)

    # Sort the directories based on the versioning scheme
    found_versions.sort(
        key=lambda x: tuple(
            int(part) for part in os.path.basename(x).split(".") if part.isdigit()
        )
    )

    # The newest directory is the last in the sorted list
    newest_version = found_versions[-1] if found_versions else None

    if newest_version:
        return newest_version
    else:
        logging.error(f"No newest found. Directories were: {found_versions}")
        return None


def find_matching_path(paths, substring):
    """Use list comprehension to filter paths containing the substring"""
    matching_paths = [path for path in paths if substring in path]

    if len(matching_paths) > 1:
        logging.error(f"Multiple paths containing {substring} found: {matching_paths}")

    # Return the matching path or None if there are no matches
    return matching_paths[0] if matching_paths else None


def run_multithreaded_tasks(
    items, worker_func, num_threads=4, task_name="Processing", *args, **kwargs
):
    """
    Run tasks across multiple threads with a progress bar.

    :param items: A list of items to process.
    :param worker_func: The function to process each item. It should take one iterable argument. Extra args from this function will be passed to the worker.
    :param num_threads: Number of threads to use.
    :param task_name: Name of the task for display purposes.
    :param args: Additional positional arguments to pass to worker_func.
    :param kwargs: Additional keyword arguments to pass to worker_func.
    """
    # Shared variables for progress tracking
    progress_lock = threading.Lock()
    completed_tasks = 0
    total_tasks = len(items)
    current_item = [None]  # Using a list to make it mutable
    items_queue = Queue()

    # Load the queue with items
    for item in items:
        items_queue.put(item)

    def thread_worker():
        nonlocal completed_tasks
        while not items_queue.empty():
            item = items_queue.get()
            worker_func(
                item, *args, **kwargs
            )  # Pass additional arguments to worker_func
            with progress_lock:
                completed_tasks += 1
                current_item[0] = str(item)
            items_queue.task_done()

    # Creating and starting threads
    threads = []
    for _ in range(num_threads):
        thread = threading.Thread(target=thread_worker)
        thread.start()
        threads.append(thread)

    # Updating the progress bar in the main thread
    with ProgressBar() as pb:
        for _ in pb(range(total_tasks)):
            while True:
                with progress_lock:
                    if completed_tasks > 0:
                        pb.title = HTML(
                            f"<ansiblue>{task_name} {current_item[0]}</ansiblue>"
                        )
                        completed_tasks -= 1
                        break
                time.sleep(0.1)

    # Waiting for all threads to finish
    for thread in threads:
        thread.join()


def get_custom_style():
    white = "#ffffff"
    black = "#000000"
    bazel_green = "#44a147"
    dialog_bg = "#f7f7f7"
    return Style.from_dict(
        {
            "dialog": f"bg:{bazel_green}",  # Dark Bazel green background for dialog
            "dialog frame.label": f"bg:{dialog_bg} {black}",  # White background, black text for frame labels
            "dialog.body": f"bg:{dialog_bg} {black}",  # Light grey background, black text for dialog body
            "button": f"bg:{bazel_green} {white}",  # Green background, white text for buttons
            "button.focused": f"bg:#FF0000 {black}",  # Lighter green and black text for focused buttons
            "radiolist": white,  # White text for radiolist items
            "radiobutton": bazel_green,  # Green for radio buttons
        }
    )


if __name__ == "__main__":
    workspace_dir = os.environ.get("BUILD_WORKSPACE_DIRECTORY")
    if workspace_dir is not None:
        main(workspace_dir)
    else:
        if len(sys.argv) > 2:
            print(
                "Usage: python super_tool.py < registry_folder >  < * Optional Shortcuts * >"
            )
        else:
            main(sys.argv[1])

    sys.exit(1)
