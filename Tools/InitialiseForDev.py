import os
import sys
import json
import requests
import tarfile
import subprocess
import logging

import utils


def initialise_setup(registry_dir):
    # Create a named logger
    logger = logging.getLogger("boost")
    # Set the logging level
    logger.setLevel(logging.DEBUG)
    # Create a handler that outputs to the console
    handler = logging.StreamHandler()
    # Set the format for the handler
    handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    # Add the handler to the logger
    logger.addHandler(handler)
    logging.basicConfig(
        level=logging.INFO
    )  # Set the logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    modules_dir = os.path.join(registry_dir, "modules")
    boost_lib_dirs = utils.find_boost_lib_dirs(modules_dir)
    boost_libs_newest_dirs = utils.find_boost_lib_newest_dirs(boost_lib_dirs)

    create_folders(boost_lib_dirs)
    boost_source_dirs = download_sources(boost_libs_newest_dirs)
    initialise_repos(boost_source_dirs, boost_libs_newest_dirs)

    # Set the local git exclude file so that all diffed_sources folders are ignored
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
        print(f"Added '{exclude_pattern}' to {exclude_file_path}")

    print("Initialization complete.")


def create_folders(boost_lib_dirs):
    # Create "diffed_sources" folder if it doesn't exist
    for lib in boost_lib_dirs:
        diffed_sources_dir = os.path.join(lib, "diffed_sources")
        if not os.path.exists(diffed_sources_dir):
            os.makedirs(diffed_sources_dir)


def download_sources(boost_libs_newest_dirs):
    # Download library from the url in source.json into diffed_sources, only if downloaded.tar.gz doesn't exist
    boost_sources = []

    for lib in boost_libs_newest_dirs:
        diffed_sources_folder = os.path.join(os.path.dirname(lib), "diffed_sources")
        tar_path = os.path.join(diffed_sources_folder, "downloaded.tar.gz")
        root_directory = None

        if not os.path.exists(tar_path):
            with open(os.path.join(lib, "source.json"), "r") as source_json_file:
                source_json = json.load(source_json_file)
                url = source_json["url"]
                logging.info(f"Downloading {lib} from {url}")
                response = requests.get(url)
            with open(tar_path, "wb") as f:
                f.write(response.content)

        with tarfile.open(tar_path, "r:gz") as tar:
            # Extract the names of all members in the tar file
            member_names = [member.name for member in tar.getmembers()]
            # Find the common prefix among all member names
            # os.path.commonpath returns the longest common sub-path of each pathname
            root_directory = os.path.commonpath(member_names)

        source_path = os.path.join(diffed_sources_folder, root_directory)

        if not os.path.exists(source_path):
            # Peek the root folder name, and if it doesn't exist, extract the folder
            with tarfile.open(tar_path, "r:gz") as tar:
                logging.info(f"Extracting {lib}")
                tar.extractall(path=diffed_sources_folder)

        boost_sources.append(source_path)

    return boost_sources


def initialise_repos(boost_source_dirs, boost_libs_newest_dirs):
    # Initialise git repo in the patched folders, commit everything & apply patch files from newest version
    for boost_source in boost_source_dirs:
        # Check if the .git directory exists
        if not os.path.exists(os.path.join(boost_source, ".git")):
            # Initialize the git repository if not already initialized
            subprocess.run(["git", "init"], cwd=boost_source)

            # Add all files to the staging area
            subprocess.run(["git", "add", "."], cwd=boost_source)

            # Commit the changes
            subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=boost_source)

            # Construct the patch file path
            patches_path = os.path.join(
                utils.find_matching_path(
                    boost_libs_newest_dirs,
                    os.path.basename(os.path.dirname(os.path.dirname(boost_source)))
                    + os.path.sep,  # Adding the "/" makes sure we don't match only the start of a segment of path
                ),
                "patches",
                "patch.diff",
            )

            # Apply most recent version's patches
            subprocess.run(["git", "apply", patches_path], cwd=boost_source)


# Usage
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python InitialiseForDev.py <registry_folder>")
        sys.exit(1)

    initialise_setup(sys.argv[1])
