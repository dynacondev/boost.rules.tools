# Hopefully, the need for these OSxCPU config_setting()s will be obviated by a fix to https://github.com/bazelbuild/platforms/issues/36

config_setting(
    name = "linux_arm",
    constraint_values = [
        "@platforms//os:linux",
        "@platforms//cpu:arm",
    ],
)

config_setting(
    name = "linux_ppc",
    constraint_values = [
        "@platforms//os:linux",
        "@platforms//cpu:ppc",
    ],
)

config_setting(
    name = "linux_aarch64",
    constraint_values = [
        "@platforms//os:linux",
        "@platforms//cpu:aarch64",
    ],
)

config_setting(
    name = "linux_x86_64",
    constraint_values = [
        "@platforms//os:linux",
        "@platforms//cpu:x86_64",
    ],
)

config_setting(
    name = "osx_arm64",
    constraint_values = [
        "@platforms//os:osx",
        "@platforms//cpu:aarch64",
    ],
)

config_setting(
    name = "osx_x86_64",
    constraint_values = [
        "@platforms//os:osx",
        "@platforms//cpu:x86_64",
    ],
)

config_setting(
    name = "windows_x86_64",
    constraint_values = [
        "@platforms//os:windows",
        "@platforms//cpu:x86_64",
    ],
)

config_setting(
    name = "android_arm",
    constraint_values = [
        "@platforms//os:android",
        "@platforms//cpu:arm",
    ],
)

config_setting(
    name = "android_aarch64",
    constraint_values = [
        "@platforms//os:android",
        "@platforms//cpu:aarch64",
    ],
)

# Building boost results in many warnings. Downstream users won't be interested, so just disable them.
default_copts = select({
    "@platforms//os:windows": ["/W0"],
    "//conditions:default": ["-w"],
})

default_defines = select({
    ":windows_x86_64": ["BOOST_ALL_NO_LIB"],  # Turn auto_link off in MSVC compiler
    "//conditions:default": [],
})

def srcs_list(library_name, exclude):
    return native.glob(
        ["libs/%s/src/*" % library_name],
        exclude = ["**/*.asm", "**/*.S", "**/*.doc"] + exclude,
        allow_empty = True,
    )

def hdr_list(library_name, exclude = []):
    return native.glob(
        ["libs/%s/include/boost/**" % library_name],
        exclude = exclude,
        allow_empty = True,
    )

def boost_library(
        name,
        boost_name = None,
        defines = [],
        includes = [],
        hdrs = [],
        srcs = [],
        copts = [],
        exclude_hdr = [],
        exclude_src = [],
        visibility = ["//visibility:public"],
        **kwargs):
    if boost_name == None:
        boost_name = name

    return native.cc_library(
        name = name,
        visibility = visibility,
        defines = default_defines + defines,
        includes = ["libs/%s/include" % boost_name] + includes,
        hdrs = hdr_list(boost_name, exclude_hdr) + hdrs,
        srcs = srcs_list(boost_name, exclude_src) + srcs,
        copts = default_copts + copts,
        licenses = ["notice"],
        **kwargs
    )

# Some boost libraries are not safe to use as dynamic libraries unless a
# BOOST_*_DYN_LINK define is set when they are compiled and included, notably
# Boost.Test. When the define is set, the libraries are not safe to use
# statically. This is an attempt to work around that. We build an explicit .so
# with cc_binary's linkshared=True and then we reimport it as a C++ library and
# expose it as a boost_library.

def boost_so_library(
        name,
        boost_name = None,
        defines = [],
        includes = [],
        hdrs = [],
        srcs = [],
        deps = [],
        copts = [],
        exclude_hdr = [],
        exclude_src = [],
        **kwargs):
    if boost_name == None:
        boost_name = name

    native.cc_binary(
        name = "lib_internal_%s" % name,
        defines = default_defines + defines,
        includes = ["libs/%s/include" % boost_name] + includes,
        srcs = hdr_list(boost_name, exclude_hdr) + hdrs + srcs_list(boost_name, exclude_src) + srcs,
        deps = deps,
        copts = default_copts + copts,
        linkshared = True,
        visibility = ["//visibility:private"],
        **kwargs
    )
    native.filegroup(
        name = "%s_dll_interface_file" % name,
        srcs = [":lib_internal_%s" % name],
        output_group = "interface_library",
        visibility = ["//visibility:private"],
    )
    native.cc_import(
        name = "_imported_%s" % name,
        shared_library = ":lib_internal_%s" % name,
        interface_library = ":%s_dll_interface_file" % name,
        visibility = ["//visibility:private"],
    )
    return boost_library(
        name = name,
        boost_name = boost_name,
        defines = defines,
        includes = includes,
        hdrs = hdrs,
        exclude_hdr = exclude_hdr,
        exclude_src = native.glob(["**"]),
        deps = deps + [":_imported_%s" % name],
        **kwargs
    )
