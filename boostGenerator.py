import os
import json
import requests
import subprocess
import sys

def generate_source_json(folder_path):
    # Extract the library name from the folder path
    library_name = folder_path.split("/")[-1].split(".")[1]

    # Check if the specific subfolder exists
    subfolder_path = os.path.join(folder_path, "1.83.0.bzl.1")
    if not os.path.exists(subfolder_path):
        print("Subfolder '1.83.0.bzl.1' not found.")
        return

    # Define the URL
    url = f"https://github.com/boostorg/{library_name}/archive/refs/tags/boost-1.83.0.tar.gz"

    # Download the file
    response = requests.get(url)
    if response.status_code == 200:
        file_name = os.path.join(
            "/Users/lukeaguilar/Downloads", f"{library_name}-boost-1.83.0.tar.gz"
        )
        with open(file_name, "wb") as file:
            file.write(response.content)

        # Compute SHA256 and encode in base64
        integrity_cmd = f"openssl dgst -sha256 -binary {file_name} | openssl base64 -A"
        integrity_result = subprocess.run(
            integrity_cmd, shell=True, capture_output=True, text=True
        )
        integrity = "sha256-" + integrity_result.stdout.strip()

        print(f"Calculated hash: {integrity}")

        # Create the source.json content
        source_data = {
            "integrity": integrity,
            "patch_strip": 0,
            "patches": {},
            "url": url,
        }

        # Write the source.json file
        with open(os.path.join(subfolder_path, "source.json"), "w") as json_file:
            json.dump(source_data, json_file, indent=4)

        print(f"source.json created/updated successfully in {subfolder_path}")
    else:
        print("Failed to download the file.")


# Usage
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script_name.py <folder_path>")
        sys.exit(1)

    folder_path = sys.argv[1]
    generate_source_json(folder_path)