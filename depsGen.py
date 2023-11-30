import os
import sys
import subprocess
from html.parser import HTMLParser


# Function to clone the Git repository, if it doesn't exist
def clone_repo(repo_url, dir_name):
    if not os.path.exists(dir_name):
        subprocess.run(["git", "clone", repo_url])


# Clone the Git repository
repo_url = "https://github.com/pdimov/boostdep-report.git"
clone_repo(repo_url, "boostdep-report")

# Set the boost version
boostVersion = "boost-1.83.0"
path_to_html = os.path.join("boostdep-report", boostVersion, "module-overview.html")


# Define a parser to extract dependencies
class BoostDependencyParser(HTMLParser):
    def __init__(self, ignore_deps):
        super().__init__()
        self.ignore_deps = ignore_deps  # List of dependencies to ignore
        self.current_library = None  # Store the current library name
        self.dependencies = {}  # Dictionary to hold libraries and their dependencies
        self.in_h2_tag = False  # Flag to indicate if we're inside an h2 tag

    def handle_starttag(self, tag, attrs):
        # Detect the start of a library name (h2 tag)
        if tag == "h2":
            self.in_h2_tag = True
        elif tag == "p" and self.current_library:
            # We're now in the dependencies list for the current library
            self.in_h2_tag = False

    def handle_endtag(self, tag):
        # Detect the end of an h2 tag
        if tag == "h2":
            self.in_h2_tag = False

    def handle_data(self, data):
        if self.in_h2_tag:
            # Capture the library name
            self.current_library = data.strip()
            self.dependencies[self.current_library] = []
        elif self.current_library and not self.in_h2_tag:
            # Filter and add dependencies
            deps = [
                dep.strip()
                for dep in data.split()
                if dep.strip() not in self.ignore_deps
            ]
            self.dependencies[self.current_library].extend(deps)
            self.current_library = None  # Reset for next library


# List of dependencies to ignore
ignore_deps = ["(unknown)"]

# Create an instance of the parser with the ignore dependencies
parser = BoostDependencyParser(ignore_deps)
with open(path_to_html, "r") as file:
    parser.feed(file.read())

# Post-process dependencies: replace '~' with '.'
for lib, deps in list(parser.dependencies.items()):
    # Replace '~' with '.' in library names
    new_lib_name = lib.replace("~", ".")
    parser.dependencies[new_lib_name] = [dep.replace("~", ".") for dep in deps]
    if new_lib_name != lib:
        del parser.dependencies[lib]

# Print out each library and its dependencies
# for lib, deps in parser.dependencies.items():
#     print(f"{lib} = {deps}")


# def detect_cycles(graph):
#     """
#     Detects cycles in a dependency graph.
#     :param graph: Dictionary representing the dependency graph.
#     :return: List of cycles found in the graph.
#     """

#     def visit(node, path):
#         if node in path:
#             return path[path.index(node) :]  # Return the cycle
#         if node not in graph:
#             return []  # No dependencies to explore

#         path.append(node)
#         for neighbour in graph[node]:
#             cycle = visit(neighbour, path.copy())
#             if cycle:
#                 return cycle
#         return []

#     cycles = []
#     for lib in graph:
#         cycle = visit(lib, [])
#         if cycle:
#             cycles.append(cycle)

#     return cycles


# # Detect and print cyclic dependencies
# cyclic_dependencies = detect_cycles(parser.dependencies)
# for cycle in cyclic_dependencies:
#     print(" -> ".join(cycle))


# Step 1: Accept a folder path from the command line
folder_path = sys.argv[
    1
]  # The folder path is expected as the first command line argument

# Step 2: Extract the library name from the folder path
# library_name = os.path.basename(folder_path).replace("boost.", "")
library_name = os.path.basename(folder_path.rstrip("/\\")).replace("boost.", "")

print(f"Library name: {library_name}")

# Step 3: Modify the MODULE.bazel file
module_bazel_path = os.path.join(folder_path, "1.83.0.bzl.1", "MODULE.bazel")
deps_whitelist = ["boost.rules.tools", "platforms", "bazel_skylib", "bzip2", "lzma", "zlib", "zstd"]  # Whitelist of dependencies to keep

new_lines = []  # List to store modified lines of the file

with open(module_bazel_path, "r") as file:
    for line in file:
        # Keep lines that are not bazel_dep or are whitelisted
        if not line.startswith("bazel_dep") or any(
            whitelist in line for whitelist in deps_whitelist
        ):
            new_lines.append(line)

# Step 4: Add bazel_dep for each dependency of the library
if library_name in parser.dependencies:
    for dep in parser.dependencies[library_name]:
        new_lines.append(f'bazel_dep(name = "boost.{dep}", version = "1.83.0.bzl.1")\n')

# Write the modified content back to the MODULE.bazel file
with open(module_bazel_path, "w") as file:
    file.writelines(new_lines)


# Function to extract the last segment of a dependency name
def last_segment(dep_name):
    return dep_name.split(".")[-1]


# Modify the BUILD.bazel file
build_bazel_path = os.path.join(folder_path, "1.83.0.bzl.1", "BUILD.bazel")
# print(f"Modifying BUILD.bazel at {build_bazel_path}")

# Read the content of the BUILD.bazel file
with open(build_bazel_path, "r") as file:
    lines = file.readlines()

inside_boost_library, correct_library = False, False
new_lines = []  # List to store modified lines of the file

for line in lines:
    # print("line" + line)
    if "boost_library(" in line:
        inside_boost_library = True
        # print(f"Starting boost_library block for {library_name}")
        new_lines.append(line)
        continue

    if inside_boost_library:
        if line.strip().startswith("deps = ["):
            # print("Found deps section, starting to process dependencies.")
            correct_library = True
            new_lines.append(line)
            continue

        if correct_library and line.strip().startswith('"@boost.'):
            # print(f"Skipping old dependency line: {line.strip()}")
            continue  # Skip this line as it's an old dependency

        if correct_library and line.strip().startswith("]"):
            # End of deps section
            # print("Found end of deps section. Adding new deps")

            # Add new dependencies
            if library_name in parser.dependencies:
                for dep in parser.dependencies[library_name]:
                    dep_line = f'        "@boost.{dep}//:{last_segment(dep)}",\n'
                    new_lines.append(dep_line)
                    # print(f"Added dependency: {dep_line.strip()}")
            
            # Append end of deps section
            new_lines.append("    ],\n")
            continue

    if ")" in line and inside_boost_library:
        inside_boost_library = False
        # print(f"Ending boost_library block for {library_name}")

    new_lines.append(line)

# Write the modified content back to the BUILD.bazel file
with open(build_bazel_path, "w") as file:
    file.writelines(new_lines)
    # print("Finished modifying BUILD.bazel.")
