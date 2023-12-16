import os
import sys
import shutil

import utils


def tidy_up(registry_dir):
    boost_lib_dirs = utils.find_boost_lib_dirs(os.path.join(registry_dir, "modules"))

    # TODO Ensure everything is patch created etc, warn and stop if changes will be lost

    for lib in boost_lib_dirs:
        diffed_sources_dir = os.path.join(lib, "diffed_sources")
        if os.path.exists(diffed_sources_dir):
            print(f"Removing {diffed_sources_dir}")
            shutil.rmtree(diffed_sources_dir)

    temp_tidy(registry_dir)


def temp_tidy(registry_dir):
    # boost_lib_dirs = utils.find_boost_lib_dirs(os.path.join(registry_dir, "modules"))
    # boost_libs_newest_dirs = utils.find_boost_lib_newest_dirs(boost_lib_dirs)

    # files_to_delete = ['BUILD.bazel', 'WORKSPACE.bazel']

    # for lib in boost_libs_newest_dirs:
    #   for filename in files_to_delete:
    #     file_path = os.path.join(lib, filename)
    #     if os.path.exists(file_path):
    #         os.remove(file_path)
    #         print(f"Deleted: {file_path}")
    #     else:
    #         print(f"File not found: {file_path}")
    pass


# Usage
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python TidyForCommit.py <registry_folder>")
        sys.exit(1)

    tidy_up(sys.argv[1])
