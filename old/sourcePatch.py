import os
import json
import sys

def update_source_json(folder_path):
    # Extract the library name from the folder path
    # library_name = folder_path.split("/")[-1].split(".")[1]
    library_name = os.path.basename(folder_path.rstrip("/\\")).replace("boost.", "")

    # Check if the specific subfolder exists
    subfolder_path = os.path.join(folder_path, "1.83.0.bzl.1")
    if not os.path.exists(subfolder_path):
        print("Subfolder '1.83.0.bzl.1' not found.")
        return

    # Path to the source.json file
    json_file_path = os.path.join(subfolder_path, "source.json")

    # Check if the source.json file exists
    if not os.path.exists(json_file_path):
        print("source.json file not found.")
        return

    # Read the existing source.json
    with open(json_file_path, "r") as json_file:
        source_data = json.load(json_file)

    # Add the strip_prefix key
    source_data["strip_prefix"] = f"{library_name}-boost-1.83.0"

    # Write the updated source.json file
    with open(json_file_path, "w") as json_file:
        json.dump(source_data, json_file, indent=2)

    print(f"source.json updated successfully in {subfolder_path}")

# Usage
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script_name.py <folder_path>")
        sys.exit(1)

    folder_path = sys.argv[1]
    update_source_json(folder_path)
