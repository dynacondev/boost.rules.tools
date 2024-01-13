# Multithreaded, TUI Tool for Bazel's Boost Modules 🚀

Welcome to boost.rules.tools! This repository is your toolkit for all things **Boost Module** related within the [Bazel](https://bazel.build/) ecosystem. Our goal is to make your life easier, so you (as an awesome package maintainer) can focus on editing a Boost module's `BUILD.bzl` file and let us handle the rest. ***Everything in here relates to the Boost modules in the [Bazel Central Registry](https://registry.bazel.build/).***

![Demo](https://github.com/dynacondev/boost.rules.tools/assets/118163872/de3be483-5dab-4b4d-a638-1a1fc178cc2f)

## ⚠︎ Current Status

This repo is currently under active development! Some of the tasks that are still beind developed are:

- ~~Module Version Bumping System~~ - Not required until after first PR to the BCR is complete
- Boost Version Changes - Working on automatically determining dependencies for all modules. Initial version based on [boostdep-report](https://github.com/pdimov/boostdep-report)
- Windows Support - Not yet tested
- Patching function - Tidy up for readability
- Multithreading - Currently implemented on download and repo initialization, a few more functions need implementation

## 👋 Hey You!

You must be here because either:

1. You are looking to modify or update Boost modules from the [Bazel Central Registry](https://registry.bazel.build/)
2. You are good at following the comments in the Boost Bazel files and wanted to see what was here

In either case, we're glad you're here! Feel free to submit issues, bounce around ideas or jump in and make whatever changes you think are needed! Or simply just use the tool to keep Boost modules up-to-date.

## 🧰 What's Inside?

There are two parts to this repository.

- The first is the [super_tool.py](super_tool.py) Python script that is for Boost Module Maintainers to use when making changes.
- The second is the [tools.bzl](tools.bzl) Bazel extension file used directly by the Boost modules to keep their `BUILD.bazel` files tidy.

*Note: This repo is itself a Bazel Module which is depended upon by EVERY Boost Module*

## 🛠️ Prerequisites

1. Bazel: We are using Bazel 7, but this should work with older versions just fine
2. Python (and pip): We are using Python 3.10, but none of these scripts are too fancy and should also work with older versions
3. Python dependencies: From this repo's root directory, you can run the following to get them:
```Bash
pip install -r ./requirements.txt
```

## 👨‍💻 Using the Python [super_tool.py](super_tool.py) - Boost Module Maintainers

You're in the right place if you want to do any of the following (or similar):

- Provide support for a new Boost version
- Fix a compile bug caused by a `BUILD.bazel`
- Fix or add some extra tests
- Add support for a platform that wasn't previously tested

### Step 1. Clone or Fork the Bazel Central Registry

Via either method, grab yourself a copy of [bazel-central-registry](https://github.com/bazelbuild/bazel-central-registry).

### ~~Step 2. Run the super_tool~~ - Not yet working! Please run the tool directly!

~~From the root directory of the [bazel-central-registry](https://github.com/bazelbuild/bazel-central-registry) you just cloned, run:~~

```bash
bazel run @boost.rules.tools//:super_tool
```

### Step 2. (Alternate) - Run [super_tool.py](super_tool.py) directly

If you'd prefer, you can simply get a clone of this repository and run the [super_tool.py](super_tool.py) script directly, passing in your registry directory as a parameter.

```bash
python <path to super_tool.py> <path to bazel-central-registry>
```

### Step 3. Setup Registry

Choose the first option - `Set up your Registry for Boost Module Maintenance`.

This option will sequentially download the boost source from the latest module version and extract it into the module folder. It will be placed inside a folder named `diffed_sources`. It will also apply the patch from the latest module version, meaning the boost source you find in the `diffed_sources` folder is exactly what bazel will see when someone tries to depend on it.

### Step 4. Edit Away!

Jump into the `diffed_sources` folder of any module and make your changes right in the boost module source. Feel free to edit the `BUILD.bazel`, `MODULE.bazel` or add any new files as necessary. Note, there's also a `BUILD.bazel` in the `/test` folder too, which is responsible for the unit tests.

*Note: Make sure not to edit the `MODULE.bazel` file that's in any of the module's version folders, as the latest will be overwritten by the one that's in the boost source.*

### Step 4. (Optional) - Modify the `presubmit.yml` or `source.json`

If you need to modify the `presubmit.yml` or `source.json` files that are in a module's version folder, you must first do a version bump on the module! This is so you aren't editing an already-published module version!

To bump a module's version, select the `Version Bump a Module` option and list the module names you want to bump, space separated.

*Note: If you've already made changes AND have patched the modules (step 5), it's probably already been version bumped. It doesn't matter if you do it again, the tool will let you know and not bump the module twice.*

### Step 5. Generate Patches from your Changes

Select the `Generate Patches from Changes` option.

This option will:

1. Find what modules you've changed
2. Bump the version on any modules that are still on a currently-released version
3. Generate a patch file and add it to the `patches` folder
4. Calculate the hash for the patch file and update it in the `source.json`

*Note: The tool usually knows which base commit you want, however, in the rare case you'd like to make two lots of changes and version bumps before up-streaming, you can use a different base commit hash to calculate changes since*

### Step 6. Commit your changes and PR!

The setup script kindly added an exclusion of the `diffed_sources` folders to your repository, so you can go ahead and commit whatever files you and the patching script have changed without having to delete any of the temporary stuff first!

If you'd like to restore the repository to it's original source-file free state, you can do so by choosing the `Restore Clean Registry State` option.

### Bonus - Updating the Boost Version

If you'd like to update the boost version, you can do so by choosing the `Bump Boost Version (All Modules)` option. This option will:

1. Bump the version on all modules to whichever boost version you input. The compatibility level will also be incremented, as compatibility between boost releases could be difficult - Unless someone really wants this feature, bumping compatibility level will remove the potential for mix and matching boost versions.
2. Calculate the dependencies between boost modules, and update both the `MODULE.bazel` and `BUILD.bazel` (module's main target) to match the dependencies required
3. Patch all modules so you can get started testing
4. Print out a long list of all the test files that are new or were deleted, so you can go through and update them all as necessary.

## ➕ The [tools.bzl](tools.bzl) Bazel Extensions File

The [tools.bzl](tools.bzl) file's purpose is to remove repeated content in Boost Module's `BUILD.bazel` files. The `boost_library` macro is used by every Boost module.

The key features of boost_library are:

- Finds headers and source files automatically, knowing boost library standard structures
- Adds a target alias, so modules can be targeted with, for example, `@boost.numeric.interval` instead of `@boost.numeric.interval//:interval`
- Assumes some default variables such as Public Visibility

There are also macros `boost_test` and `boost_test_set` which make adding tests FAR more concise. (A list of file names rather than multiple individually written `cc_test`)

There probably isn't much that needs to be modified here regularly as it's just for keeping things as compact as possible with the modules, but you might find there's an improvement that could be made Bazel-Boost module wide and here is definitely the right place to put it! Notably, there currently isn't a negative-test system implemented, which would be great to help us cover many of the boost tests that are *meant to fail in particular ways when built or run*.

## 👐 Contributing

Any info that isn't in this README is probably in code comments! We try and keep code well structured and commented in preference to efficiency, as this is just a tool and we want you to be able to jump in and see what's going on easily!

We love ideas, feel free to jump straight in and contribute, or better still, file a [GitHub issue](https://github.com/dynacondev/boost.rules.tools/issues) so we can discuss it together first! We respond quickly and are happy to hear anything you've got on your mind!