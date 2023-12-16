import os
import tarfile
import logging


# Find all boost modules by path
def find_boost_lib_dirs(modules_dir):
    boost_lib_dirs = []
    ignore_list = [
        "boost.rules.tools",
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


def find_boost_lib_newest_dirs(paths):
    boost_libs_newest_dirs = []

    # Handle single path input by converting it to a list
    if isinstance(paths, str):
        paths = [paths]

    for lib in paths:
        newest = find_newest_version_from_paths(
            [os.path.join(lib, path) for path in os.listdir(lib)]
        )
        if newest:
            boost_libs_newest_dirs.append(newest)

    return boost_libs_newest_dirs


# Find newest version folders
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
        logging.info(f"The newest version is: {os.path.basename(newest_version)}")
        return newest_version
    else:
        logging.error(f"No newest found. Directories were: {found_versions}")
        return None


def find_boost_sources(boost_lib_dirs):
    boost_sources = []

    for lib in boost_lib_dirs:
        diffed_sources_folder = os.path.join(lib, "diffed_sources")
        tar_path = os.path.join(diffed_sources_folder, "downloaded.tar.gz")
        root_directory = None

        if not os.path.exists(tar_path):
            logging.error(f"Couldn't find source archive for {os.path.basename(lib)}")
            continue

        with tarfile.open(tar_path, "r:gz") as tar:
            # Extract the names of all members in the tar file
            member_names = [member.name for member in tar.getmembers()]
            # Find the common prefix among all member names
            # os.path.commonpath returns the longest common sub-path of each pathname
            root_directory = os.path.commonpath(member_names)

        source_path = os.path.join(diffed_sources_folder, root_directory)

        if not os.path.exists(source_path):
            logging.error(f"Couldn't find source for {os.path.basename(lib)}")
            continue

        boost_sources.append(source_path)

    return boost_sources


def find_matching_path(paths, substring):
    # Use list comprehension to filter paths containing the substring
    matching_paths = [path for path in paths if substring in path]

    if len(matching_paths) > 1:
        logging.error(f"Multiple paths containing {substring} found: {matching_paths}")

    # Return the matching path or None if there are no matches
    return matching_paths[0] if matching_paths else None
