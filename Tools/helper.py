import os
import argparse

file_extension = ".cc"


def find_cpp_files(directory):
    cpp_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(file_extension):
                # Calculate the relative path from the directory to the file
                relative_path = os.path.relpath(os.path.join(root, file), directory)
                cpp_files.append(relative_path)
    return sorted(cpp_files)


def generate_bazel_build(directory, library_name, extra_deps):
    header = 'load("@boost.rules.tools//:tools.bzl", "boost_test_set")\n\n'
    deps = ['    "@boost.' + library_name + "//:" + library_name + '",'] + [
        '    "' + dep + '",' for dep in extra_deps
    ]
    deps_variable = "DEPS = [\n" + "\n".join(deps) + "\n]\n\n"
    cpp_files = find_cpp_files(directory)

    test_suite = (
        "test_suite(\n"
        '    name = "tests",\n'
        "    tests = boost_test_set(\n"
        '        file_extensions = ".cc",\n'
        "        names = [\n"
        + "\n".join(
            [f'            "{file.replace(file_extension, "")}",' for file in cpp_files]
        )
        + '\n        ],\n        deps = DEPS,\n    ),\n)\n'
    )

    return header + deps_variable + test_suite


def main():
    parser = argparse.ArgumentParser(
        description="Generate a BUILD.bazel file for Boost library tests."
    )
    parser.add_argument(
        "directory",
        type=str,
        help="The path to the directory containing the test files.",
    )
    parser.add_argument(
        "library", type=str, help='The name of the Boost library, e.g., "accumulators".'
    )
    parser.add_argument(
        "--extra_deps",
        nargs="*",
        default=[],
        help="Additional dependencies to be added to the DEPS variable. Space-separated if multiple.",
    )
    args = parser.parse_args()

    build_content = generate_bazel_build(args.directory, args.library, args.extra_deps)

    with open(os.path.join(args.directory, "BUILD.bazel"), "w") as file:
        file.write(build_content)

    print("BUILD.bazel file generated successfully in", args.directory)


if __name__ == "__main__":
    main()
